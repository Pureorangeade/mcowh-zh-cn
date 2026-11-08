# 开发与本地构建

当前发行版为0.3.4-story-compat。需要Python 3.12、requirements.txt中的依赖、Node，以及完整检查时使用的Windows Edge。玩家不需要这些依赖。

仓库不包含原游戏BIN、存档或备份。源码通常放在游戏目录下的_zh_patch；构建、差分重建与安装测试使用work中的隔离副本，不写回实际游戏。work/baseline.json可从源码包profiles/steam-1527978.json复制；干净英文build 1527978资源由开发者自行提供。

## 当前构建

准备work/clean-fixture中的干净英文副本、原始解包材料（work/extracted、work/textures及索引）、Noto Sans SC可变字体。测试还需独立的5文件日文资源副本work/japanese-fixture。原始图片索引可使用texture_inventory.py生成；不要从已装汉化的目录导出英文基准。

从历史v0.3.3-menu-fix Release下载原始玩家ZIP及-source.zip到dist，核对docs/package-verification-0.3.3.json中的哈希。将其中patch.mcpatch放入dist/MCOWH-zh-CN-0.3.3-menu-fix/，再重建冻结基线：

```powershell
python -c "import sys; from pathlib import Path; sys.path.insert(0,'tools'); from bundle import prepare; prepare(Path('dist/MCOWH-zh-CN-0.3.3-menu-fix/patch.mcpatch'),Path('work/clean-fixture'),Path('build/0.3.3-menu-fix'))"
python tools/build_story_compat.py
python tools/verify_story_compat.py
python tools/bundle.py
python tools/editor_data.py
```

当前构建器明确限制为34个新增数据库正文、7段确认书名对话、局部字符串兼容及字库追加；修改更多译文时，须同步源绑定批次与允许变更范围。不要绕过范围验证或直接运行旧的build_full.py覆盖当前基线。

公共事件解析器保留未知元数据和未改字节。其读取流程参考wolftrans公开实现并改写为Python，tools/common_events.py按MPL-2.0提供，随包附许可证和来源声明；该开发用解析器不由玩家安装器加载。只针对已校验的本游戏1000事件布局。

## 检查与打包

测试对比冻结0.3.0源码，还需从历史Release取得MCOWH-development-baseline-0.3.0.zip，将其中两个旧ZIP放入dist。完整安装测试覆盖0.3.0和0.3.3还原兼容。缺少这些本机材料时不能宣称完整验证通过。

```powershell
python -m unittest discover -s tests -p test_*.py
node tests/editor_core.test.js
node tests/editor_browser.test.js
python -m PyInstaller --noconfirm --onefile --windowed --name MCOWH_Chinese_Patch --distpath dist/MCOWH-zh-CN-0.3.4-story-compat --workpath build/pyinstaller-0.3.4 --specpath build tools/installer.py
python tools/verify_release.py
python tools/make_release.py
```

verify_release.py只在work/release-test-0.3.4-story-compat运行安装器，不启动游戏。打包前必须有与本次EXE和差分哈希相符的release-verification.json。玩家包只含安装器、差分、编辑器与说明；源码包排除原始BIN、存档、work/build、备份和密钥。

菜单中ASCII逗号、空格、动作编号和行结束符属于程序格式。只翻译标签。人名继续保留英文，19项属性范围及历史说明见PANEL_ONLY_0067.md，菜单历史修复见MENU_FIX_0068.md，新版范围见STORY_0069.md。
