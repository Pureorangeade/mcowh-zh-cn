"""Package verified binaries, notices, and source without extracted game assets."""
import json
from pathlib import Path
import shutil
import zipfile

from resources import PROJECT, sha256
from release_config import PATCH_VERSION, RELEASE_FOLDER


PLAYER_README = f"""Mystery Chronicle: One Way Heroics 简体中文补丁 {PATCH_VERSION}

本版修复12处菜单配置，解决使用、快捷栏、装备、拾取等选项显示编号且无法正常生效的问题。
其余内容完整继承0.3.2，包括你确认的19项人物属性译名（MOV为“移速”）。
图片、字体、HUD、脚本和其余文字与0.3.2一致。
HP、ST、EN、Lv、Exp、WT仍保留0.3.0的英文样式；人名仍暂留英文。
F18—F21四项英日玩法差异仍沿用当前英文版含义，保留至后续判断。
开局$dead动态死因仍可能显示英文，本版尚未确认或修复，见DEATH_TEXT_FOLLOWUP.md。
本版仍待游戏内验收，尚不能宣称全游戏精校完成。

仅支持 Steam 英文版 build 1527978。日文版资源不能直接安装此补丁。
若此前为取得日文资源切换过语言，请先在Steam属性中切回English并等待下载完成。

安装或升级
1. 退出游戏，完整解压压缩包到可写目录。
2. 如已装旧补丁，先使用旧包安装程序“还原原版”，保留.mcowh-zh-backup。
   新程序已在隔离副本验证可还原0.3.0和0.3.2，再安装本版。
3. 确保Steam语言为English。切换语言后若文件校验失败，可在Steam验证完整性后重试。
4. 运行MCOWH_Chinese_Patch.exe，核对游戏目录，点击“安装汉化”。
5. 完成后由你通过Steam启动游戏验收，安装器不会启动或操作游戏。
无需Python、字体或翻译模型；patch.mcpatch必须与安装程序放在一起。
安装前校验原文件并备份。不要直接覆盖安装到旧汉化上，也不要删除备份或存档。
需还原时退出游戏，运行本安装程序并点击“还原原版”。
重建和备份占数GB空间，请在游戏盘和系统临时目录留足空间。

本版内容
保留187张文字图、8套字库及0.3.2的19项属性；仅修复12处菜单分隔符和格式。
共12,204条编辑记录，其中12,084条模型译文及已确认标签；7条原文、50条其余缩写模板及63条程序指令保留。
12处修复及其余200项资源逐字节不变的证据，见menu-0068-diff.json；19项属性的历史变更见panel-only-0067-diff.json。
22项终审记录包含18项暂留英文人名及F18—F21；查看FINAL_REVIEW.md。
其他图片、游戏标志、硬编码及完整流程仍有待核对，不能据此计算全游戏汉化率。

三语对照编辑
打开“汉化译文编辑器.html”，英文、实际日文只读，中文可编辑。
修改自动存浏览器草稿，完成后“导出修订”并把JSON发回聊天合入。
改动需重建、安装新版才会进入游戏；编辑器不会直接改游戏。
详情见EDITING.md，验收步骤见USER_TEST.md。
离线安装、还原、资源与字形审计见release-verification.json及isolated-install-audit.json。
SHA256SUMS.txt记录包内文件哈希；第三方声明见licenses。
"""


def main():
    release = PROJECT / "dist" / RELEASE_FOLDER
    record = json.loads((PROJECT / "docs/release-verification.json").read_text("utf8"))
    if record.get("version") != PATCH_VERSION:
        raise ValueError("Verification record differs from current release version")
    if sha256(release / "MCOWH_Chinese_Patch.exe") != record["executable_sha256"]:
        raise ValueError("Executable differs from verified release")
    if sha256(release / "patch.mcpatch") != record["bundle_sha256"]:
        raise ValueError("Bundle differs from verified release")
    (release / "使用说明.txt").write_text(PLAYER_README, encoding="utf-8-sig")
    from editor_data import export_editor
    export_editor(release / '汉化译文编辑器.html')
    for name in ["QA.md", "release-verification.json", "USER_TEST.md", "manual-verification.json", "EDITING.md",
                 "llm-editor-verification.json", "isolated-install-audit.json", "release-text-verification.json", "FINAL_REVIEW.md", "final-review-queue.json",
                 "USER_REVIEW_0065.md", "user-review-0065-verification.json", "PERSONAL_NAMES_0064.md", "personal-name-registry.json",
                 "RELEASE_0.3.3.md", "MENU_FIX_0068.md", "menu-0068-diff.json", "RELEASE_0.3.2.md", "PANEL_ONLY_0067.md", "panel-only-0067-diff.json", "DEATH_TEXT_FOLLOWUP.md"]:
        shutil.copy2(PROJECT / "docs" / name, release / name)
    for source in (PROJECT / "licenses").iterdir():
        if source.is_file():
            dest = release / "licenses" / source.name
            dest.parent.mkdir(exist_ok=True)
            shutil.copy2(source, dest)
    # Development operation log is not part of the release.
    contents = [p for p in release.rglob("*") if p.is_file() and p.name not in ("last-operation.txt", "SHA256SUMS.txt")]
    sums = "\n".join(f"{sha256(p)}  {p.relative_to(release).as_posix()}" for p in sorted(contents)) + "\n"
    (release / "SHA256SUMS.txt").write_text(sums, encoding="utf8")
    player_zip = PROJECT / f"dist/MCOWH-zh-CN-{PATCH_VERSION}.zip"
    with zipfile.ZipFile(player_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(contents + [release / "SHA256SUMS.txt"]):
            archive.write(path, RELEASE_FOLDER + "/" + path.relative_to(release).as_posix())
    source_zip = PROJECT / f"dist/MCOWH-zh-CN-{PATCH_VERSION.removesuffix('-demo')}-source.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in ["tools", "translations", "tests", "docs", "licenses"]:
            for path in sorted((PROJECT / name).rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts and '.backup-' not in path.name and path.suffix!='.tmp':
                    archive.write(path, "MCOWH-zh-CN-source/" + path.relative_to(PROJECT).as_posix())
        for name in ["README.md", "CONTRIBUTING.md", "requirements.txt", ".gitignore"]:
            archive.write(PROJECT / name, "MCOWH-zh-CN-source/" + name)
        archive.write(PROJECT / "work/baseline.json", "MCOWH-zh-CN-source/profiles/steam-1527978.json")
    for path in [player_zip, source_zip]:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError("Release zip verification failed")
        print(f"{path.name}: {path.stat().st_size:,} bytes, sha256 {sha256(path)}")


if __name__ == "__main__":
    main()
