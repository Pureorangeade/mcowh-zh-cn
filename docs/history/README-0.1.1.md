# Mystery Chronicle: One Way Heroics 简体中文补丁项目

当前交付为 **0.1.1-demo 字体修正版**，不是全量汉化。用户截图已确认设置菜单和声音设置的可见中文显示通过，汉字粗细混用已修复；教程、物品说明及其他界面仍待验收，翻译范围未扩大。

游戏的启动、按键操作与截图验收由用户完成。开发方不操作游戏界面。当前验收步骤见 [用户验收清单](docs/USER_TEST.md)。

## 玩家使用

可分发目录为 `dist/MCOWH-zh-CN-demo`，包含独立安装程序、差分包和说明。玩家无需安装 Python、字体或开发工具。

1. 关闭游戏，把整个补丁压缩包解压到任意可写目录。
2. 双击 `MCOWH_Chinese_Patch.exe`。
3. 检查自动识别的游戏目录，必要时手动选择含 `MC_OneWayHeroics.exe` 的目录。
4. 点击“安装汉化”，完成后正常通过 Steam 启动。
5. 还原时重新运行安装程序，点击“还原原版”。

**从 0.1.0-demo 升级：** 关闭游戏，运行新版安装程序，先点击“还原原版”，完成后再点击“安装汉化”。实际游戏目录的旧补丁不会因开发构建而自动升级。

当前仅支持本地验证过的 Steam **英文版 build 1527978**。安装程序以文件哈希确认版本，会拒绝未知版本或已被其他补丁修改的目标文件。原文件保存在游戏目录的 `.mcowh-zh-backup` 中；保留此目录才能还原。

演示内容：16 条数据库译文，含设置菜单、新手教程提示、木盾名称和说明；8 段教程开场对话；79 处确认、取消等按钮标签。标题菜单的图片文字、其他物品和剧情仍为原文。

## 当前验证状态

- 资源索引校验、LZ4 解压及四字节 XOR 已验证。
- 数据库 63,821 个字符串字段及两个 PACK 包均可逐字节往返处理。
- 11 个修改后的资源重新读取后与预期一致。
- 差分包可在干净文件上重建全部 5 个修改文件，哈希与开发构建一致。
- 单元测试覆盖版本拒绝、重复安装、安装失败回滚、备份还原和冲突保护。
- 独立 EXE 已通过干净文件上的重建、安装、重复安装及还原测试；各步退出码为 0，文件哈希与预期一致，记录见 `docs/release-verification.json`。
- 用户提供的 0.1.0 设置菜单、声音设置截图确认中文替换生效，截图中未见明显缺字或裁切，但字重不一致，验收未通过。
- 0.1.1 将全部演示译文的非 ASCII 字形统一重绘：Seurat regular 500、demibold 600、Skip 700；避免可变字体默认字重 100，并保留 ASCII 字形和原图像素。用户已提供两个页面的复验截图，汉字粗细协调，未见明显缺字或裁切；物品说明及教程流程仍待用户完成。

这份技术演示只应作为后续验证和开发的起点。

## 开发目录

```text
tools/resources.py       索引读取、基线、提取、资源回写
tools/formats.py         WOLF 数据库和 PACK 格式
tools/fonts.py           演示字形和字图扩展
tools/build.py           译文校验、资源构建、重新读取验证
tools/delta.py           源哈希约束的复制/字面量差分
tools/bundle.py          差分分发包构建和本地重建
tools/install_local.py   校验、备份、安装、回滚、还原
tools/installer.py       玩家图形界面和独立 EXE 入口
tools/export_text.py     带上下文的候选文本导出
tools/audit_installation.py 只读检查安装、备份及演示字形覆盖
translations/            演示译文及术语表
tests/                   文件完整性和回滚测试
work/                    本地基线、解包资源、译文候选；不分发
build/                   本地生成文件；不作为玩家补丁直接分发
dist/                    最终可分发补丁
docs/                    格式说明、测试记录及后续工作
licenses/                第三方字体及运行库许可
```

## 重建步骤

使用 Python 3.12 和 `requirements.txt` 中的依赖。以下命令从 `_zh_patch` 目录运行；`--game` 默认指向其上一级游戏目录。

```powershell
python -m pip install -r requirements.txt
python tools/resources.py baseline
python tools/resources.py index
python tools/resources.py extract --contains common/text/win32
python tools/resources.py extract --contains basicdata/database.
python tools/resources.py extract --contains .pack
python tools/export_text.py
python tools/build.py --font "C:\Windows\Fonts\NotoSansSC-VF.ttf"
python -m unittest discover -s tests -v
python tools/bundle.py --source ".."
python -m PyInstaller --noconfirm --onefile --windowed --name MCOWH_Chinese_Patch --distpath dist/MCOWH-zh-CN-demo --workpath build/pyinstaller --specpath build tools/installer.py
python tools/verify_release.py
```

首次基线必须来自未修改的游戏。本项目已存在基线时，工具会拒绝把不同文件静默覆盖成新基线。`build.py` 的输出路径必须与输入游戏目录分开。

安装后如需重新构建，先还原游戏，或使用本地干净副本并传入 `--game`。构建差分也可以通过 `--source` 指向包含原始索引和相关数据文件的备份目录。

`work/translation/catalogue.jsonl` 包含稳定 ID、原文、占位符、数据库表/行/字段上下文或脚本路径。它是规则筛选出的翻译候选，不代表所有可见文字已被发现。保留 `source_sha256` 以便后续检出游戏升级带来的原文变化。

已安装补丁时，可运行 `python tools/audit_installation.py` 做只读诊断。报告保存到 `work/installation-audit.json`；该工具不启动游戏，也不会把文件完整性检查当作画面验收通过。

## 当前技术边界和后续工作

1. 完成游戏内设置菜单、教程开场、木盾说明的显示验收；确认字形方向、基线、尺寸及换行。
2. 扩展字库序列化数组，或重建完整字体资源。演示版只重分配少量未被译文使用的日文汉字槽位；此方案不适合作为最终全量字库。英文版中手动输入这些被替换的罕见日文字符可能缺字。
3. 继续定位标题菜单、其他界面图片文字及尚未导出的显示字符串。
4. 为全量译文增加审核状态、翻译合并、术语检查和覆盖率报告；目前构建器直接读取 `translations/demo.zh-CN.json`。
5. 翻译和人工校对，优先系统菜单、基础装备、技能、教程，再推进剧情和结局。
6. 在新游戏、旧存档、多分辨率及完整流程上验收后发布测试版。

新增中文字形使用本机 Noto Sans SC 渲染。来源与许可见 `licenses/Noto-OFL.txt` 和第三方声明。分发包提供基于玩家原始资源的差分，不包含完整游戏数据包或主程序。
