# Mystery Chronicle: One Way Heroics 简体中文补丁

当前版本：**0.3.4-story-compat**（2026-11-08）。

[下载补丁](https://github.com/Pureorangeade/mcowh-zh-cn/releases/latest) · [更新说明](docs/RELEASE_0.3.4.md) · [修改翻译](docs/EDITING.md) · [问题反馈](https://github.com/Pureorangeade/mcowh-zh-cn/issues)

## 安装

在Releases下载 **MCOWH-zh-CN-0.3.4-story-compat.zip**，不要下载GitHub自动生成的Source code压缩包作为安装包。

1. 在Steam中把游戏语言设为English，等待下载完成，退出游戏。
2. 完整解压补丁ZIP到可写目录，运行MCOWH_Chinese_Patch.exe，核对游戏目录。
3. 如已安装旧汉化，先“还原原版”，再“安装汉化”。不要直接覆盖旧补丁。
4. 通过Steam自行启动游戏。玩家无需Python、额外字体或翻译模型。

安装器和patch.mcpatch须放在同一文件夹。仅支持Steam英文版 **build 1527978**。保留.mcowh-zh-backup和存档；卸载汉化时退出游戏，再用安装器“还原原版”。

## 当前版本

- 补译34段序章、主线结局、人物与职业后日谈正文，共154页；逐段对照实际日文，英日差异经用户裁定。
- 加入通关标识兼容处理：在局部查询字符串中匹配旧英文职业记录，保留中文职业名。
- 加入开局旧英文死因的显示兼容。找到系统保存整句死因、开局注入$dead的实际路径；未知或有歧义的旧怪物名保留原样。
- 统一“绝伦之书”，同步7段旧对话。19项人物属性和0.3.3菜单动作修复保留；187张文字图、HUD与已有字形不变，字库只追加缺字。人名仍保留英文。

这些改动已通过离线校验，实际通关标识、旧死因和书页版式仍需玩家验收；没有启动游戏或直接修改任何存档。具体步骤见[USER_TEST](docs/USER_TEST.md)。未宣称所有视频、片尾职员表与全游戏流程都已汉化、精校完成。

三语编辑器包含12,238条记录，11,985条有实际日文来源。新正文可筛选“序章与结尾”，中文可编辑，导出JSON合入并重建后进入游戏。编辑器不会直接修改游戏，详见[编辑说明](docs/EDITING.md)。

22项终审问题保留，人名仍暂留英文，F18—F21维持既有决定。更新范围及用户决定见[0069说明](docs/STORY_0069.md)，兼容逻辑见[证据](docs/runtime-compat-proof.json)。

## 源码与维护

仓库包含工具、英日中翻译数据、三语编辑器模板、翻译批次和验收记录。游戏原始BIN、存档、备份、临时解包文件及生成程序不进入Git历史；玩家包通过Releases提供。

本地依赖及构建见[开发说明](docs/DEVELOPMENT.md)，修订约定见[贡献说明](CONTRIBUTING.md)。完整检查需自行提供合法拥有的原版资源。68项Python测试、编辑器与隔离安装／还原证据见[QA](docs/QA.md)。

游戏名称及原始素材归各自权利人所有。本项目为非官方汉化，第三方声明见[licenses](licenses/THIRD-PARTY-NOTICES.txt)。
