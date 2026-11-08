# 开发与本地构建

当前发行版为0.3.3-menu-fix。Python 3.12及依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
node tests/editor_core.test.js
```

仓库不含原游戏资源或存档。部分工具默认GAME为仓库上一级目录，可将源码放入游戏目录下的_zh_patch；构建和安装测试始终使用隔离副本，不写回实际游戏。work/baseline.json可从profiles/steam-1527978.json复制，原版英文build 1527978资源需由开发者本机提供。

## 当前0.3.3构建

需要work/clean-fixture中的干净英文副本，以及冻结0.3.2玩家ZIP和-source.zip，哈希见docs/package-verification-0.3.2.json。可从GitHub历史v0.3.2-panel-only Release下载两个原始附件到dist；从玩家ZIP取出patch.mcpatch，放入dist/MCOWH-zh-CN-0.3.2-panel-only/。

```powershell
python -c "import sys; from pathlib import Path; sys.path.insert(0,'tools'); from bundle import prepare; prepare(Path('dist/MCOWH-zh-CN-0.3.2-panel-only/patch.mcpatch'),Path('work/clean-fixture'),Path('build/0.3.2-panel-only'))"
python tools/build_menu_fix.py
python tools/verify_panel_only.py
python tools/bundle.py
```

build_menu_fix.py只改冻结0.3.2中的12个菜单配置字段；不重新渲染字体、图片或重译。build_panel_only.py保留为0.3.2历史构建入口，在当前版本会拒绝运行，以免漏掉菜单修复。

完整测试还需work/extracted原始字体/数据库/脚本、work/textures的原始图片和索引，以及Noto Sans SC字体；tests/editor_browser.test.js使用Windows Edge隔离无头配置。测试对比冻结0.3.0源码，需取得历史Release中的MCOWH-development-baseline-0.3.0.zip并将其中两个旧ZIP放入dist。缺少本机输入时不能宣称完整测试通过。

```powershell
python -m unittest discover -s tests -q
node tests/editor_core.test.js
python tools/editor_data.py
node tests/editor_browser.test.js
python -m PyInstaller --noconfirm --onefile --windowed --name MCOWH_Chinese_Patch --distpath dist/MCOWH-zh-CN-0.3.3-menu-fix --workpath build/pyinstaller-0.3.3 --specpath build tools/installer.py
python tools/verify_release.py
python tools/make_release.py
```

独立EXE在work/release-test-0.3.3-menu-fix验证安装与还原；具备冻结0.3.0和0.3.2差分包时覆盖这两版还原兼容性。发布前核对EXE、差分、生成的玩家ZIP与验证记录，源码及玩家分发包均不包含原游戏BIN或存档。玩家无需这些开发依赖。

菜单模板中的ASCII逗号、其后空格、整数动作编号和行结束符属于程序格式。只翻译标签；Python导入/构建及编辑器导出均拒绝破坏这些字段。详见MENU_FIX_0068.md。
