# Mystery Chronicle: One Way Heroics 简体中文补丁

当前版本：**0.3.2-panel-only**（2026-11-08）。

[下载补丁](https://github.com/Pureorangeade/mcowh-zh-cn/releases/latest) · [更新说明](docs/RELEASE_0.3.2.md) · [修改翻译](docs/EDITING.md) · [问题反馈](https://github.com/Pureorangeade/mcowh-zh-cn/issues)

## 安装

在右侧 **Releases** 下载 `MCOWH-zh-CN-0.3.2-panel-only.zip`，无需下载GitHub自动生成的Source code压缩包。

1. 在Steam中把游戏语言设为 **English**，等待下载完成，退出游戏。
2. 完整解压补丁ZIP到可写目录，运行 `MCOWH_Chinese_Patch.exe`，核对游戏目录。
3. 已安装旧版汉化时，先“还原原版”，再“安装汉化”。不要直接覆盖旧补丁。
4. 完成后通过Steam启动游戏。无需Python、额外字体或翻译模型。

安装器与 `patch.mcpatch` 必须放在同一文件夹。仅支持Steam英文版 **build 1527978**；保留 `.mcowh-zh-backup` 和存档。卸载汉化时退出游戏，再用安装器“还原原版”。

## 当前版本

本版按用户最新要求，从冻结的0.3.0-llm-review重新制作，只修改19项属性在人物面板中的29处数据库字段。MOV为“移速”。

其余数据库字段、187张文字图、8套字库、事件脚本和系统资源保持0.3.0原样。HP、ST、EN、Lv、Exp、WT以及HUD均不套用被否决的0.3.1改动。开局$dead英文问题未在本次修改。

玩家包：dist/MCOWH-zh-CN-0.3.2-panel-only.zip。仅支持Steam英文版build 1527978。

退出游戏，完整解压。先用安装器“还原原版”，再安装新版；不要覆盖旧汉化或删除备份/存档。开发方只做离线与隔离测试，由用户启动和验证游戏。

现行范围及构建方法见[0067说明](docs/PANEL_ONLY_0067.md)，用户验收见[USER_TEST](docs/USER_TEST.md)，资源差异见[差异证明](docs/panel-only-0067-diff.json)。

三语编辑器：editor/汉化译文编辑器.html；包内也有独立HTML。12,204条记录，11,951条有日文正文。修改后导出修订JSON，合入并重建后进入游戏。编辑器不会直接修改游戏，详见[编辑说明](docs/EDITING.md)。

保留22项终审记录，人名继续暂留英文；F18—F21维持0.3.0使用的英文含义。离线校验不代表全游戏精校或画面验收完成。

## 源码与维护

仓库包含补丁工具、英日中翻译数据、三语编辑器模板、翻译批次和验收记录。游戏原始资源、存档、本机备份、临时解包文件和生成的程序不进入Git历史。玩家安装包通过Releases提供。

开发入口及本地资源要求见[开发说明](docs/DEVELOPMENT.md)，翻译修订约定见[贡献说明](CONTRIBUTING.md)。完整资源测试需要开发者自行提供合法拥有的原版游戏文件。57项本地自动测试与8步隔离安装/还原验证记录见[QA](docs/QA.md)。

游戏名称及原始素材归各自权利人所有。本项目为非官方汉化；第三方字体与运行库声明见[licenses](licenses/THIRD-PARTY-NOTICES.txt)。
