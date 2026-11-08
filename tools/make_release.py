"""Package verified binaries, notices, and source without extracted game assets."""
import json
from pathlib import Path
import shutil
import zipfile

from resources import PROJECT, sha256
from release_config import PATCH_VERSION, RELEASE_FOLDER


PLAYER_README = f"""Mystery Chronicle: One Way Heroics 简体中文补丁 {PATCH_VERSION}

本版补译34段序章、结局与后日谈正文（154页），逐段对照实际日文。
加入通关标识的旧英文职业记录兼容，以及开局旧英文死因的显示兼容。
原菜单动作修复及19项人物属性译名继承0.3.3；187张文字图、HUD和已有字形不变。
人名暂留英文。按用户决定统一“绝伦之书”，同步7段旧对话。
新增字库字符只做追加，不重画原字形。实际游戏内显示仍待用户验收。

仅支持Steam英文版build 1527978。Steam语言请设为English并等待下载完成。

安装或升级
1. 退出游戏，完整解压ZIP到可写目录。
2. 运行MCOWH_Chinese_Patch.exe，核对游戏目录。
3. 如已安装旧汉化，先“还原原版”，再“安装汉化”。不要直接覆盖旧汉化。
4. 保留.mcowh-zh-backup和存档。通过Steam自行启动游戏验收。
安装器不会启动或操作游戏；无需Python、额外字体或翻译模型。
patch.mcpatch必须与安装程序放在同一目录。
需还原时，退出游戏，再用本安装器“还原原版”。
重建和备份占数GB空间，请在游戏盘及系统临时目录留足空间。

请重点检查已有海盗／风来人的通关标识、序章书页及开局旧死因。
无需重新通关或故意死亡，具体步骤见USER_TEST.md。
旧死因中的未知或有歧义怪物名可能仍保留英文；原始记录不被直接编辑。
F18—F21仍按既有决定保留，见FINAL_REVIEW.md。
本版不等于所有视频、职员表和全游戏流程都已完成汉化与精校。

三语对照编辑
打开“汉化译文编辑器.html”，英文与实际日文只读、中文可编辑。
共12,238条编辑记录，11,985条有实际日文来源；新正文可筛选“序章与结尾”。
修改自动存浏览器草稿，完成后“导出修订”，交回JSON合入并重建补丁。
编辑器不会直接修改游戏。详见EDITING.md。

更新范围、用户决定及离线证据见RELEASE_0.3.4.md、STORY_0069.md、
user-decisions-0069.json、story-0069-diff.json、runtime-compat-proof.json、
release-verification.json及isolated-install-audit.json。
SHA256SUMS.txt记录包内文件哈希，第三方声明见licenses。
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
                 "RELEASE_0.3.4.md", "STORY_0069.md", "test-verification-0.3.4.json", "user-decisions-0069.json", "story-0069-diff.json", "runtime-compat-proof.json", "RELEASE_0.3.3.md", "MENU_FIX_0068.md", "menu-0068-diff.json", "RELEASE_0.3.2.md", "PANEL_ONLY_0067.md", "panel-only-0067-diff.json", "DEATH_TEXT_FOLLOWUP.md"]:
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
