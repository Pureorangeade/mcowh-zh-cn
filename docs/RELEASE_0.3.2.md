# 0.3.2-panel-only

2026-11-08

本版按用户最新要求，从冻结的0.3.0-llm-review重新制作，只修改19项属性在人物面板中的29处数据库字段。MOV为“移速”。

其余数据库字段、187张文字图、8套字库、事件脚本和系统资源保持0.3.0原样。HP、ST、EN、Lv、Exp、WT以及HUD均不套用被否决的0.3.1改动。开局$dead英文问题未在本次修改。

详细译名和字段范围见PANEL_ONLY_0067.md，差异证据见panel-only-0067-diff.json。0.3.0原分发ZIP保持不变，0.3.1仅作为历史包和还原兼容性测试输入。

离线验证：57项Python测试、编辑器核心及独立浏览器测试；独立EXE在隔离目录执行8步重建、旧版安装后还原、新版安装/重复安装/还原。具体完成结果以release-verification.json、release-text-verification.json及isolated-install-audit.json为准。

升级：退出游戏，使用安装器先“还原原版”，再安装本版。不要覆盖旧汉化或删除备份/存档。本版安装与游戏画面由用户手动完成。
