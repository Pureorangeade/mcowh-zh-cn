# 开发与本地构建

开发工具使用Python 3.12和requirements.txt列出的依赖，编辑器核心检查使用Node.js。发行程序在Windows通过PyInstaller打包，玩家不需要这些依赖。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
node tests/editor_core.test.js
```

仓库不含原游戏资源、本机备份或存档。历史开发记录中的绝对路径、build、work、dist和截图位置属于原开发环境，不是干净克隆后自动具备的内容。相关原始资源测试需要自行准备合法的Steam英文版build 1527978；日文正文对照来源为日语资源depot 409003。不要把原游戏数据提交到仓库。

当前Python工具以所在仓库为PROJECT，部分读取GAME默认指向PROJECT的上一级目录。可将源码放在游戏目录下的_zh_patch文件夹中；支持--game或--source参数的工具也可显式指定隔离副本。构建和测试应始终使用隔离目录，不将产物直接写回实际游戏，也不修改存档。

## 0.3.2最小构建的输入

本版必须复用冻结0.3.0资源，不能重新渲染字体、图片或重译整库。需要：

1. work/baseline.json：Steam英文版文件哈希基线，已公开在profiles/steam-1527978.json；复制到work后使用。
2. work/clean-fixture：与基线匹配的英文原版隔离副本，包含安装器需要的13个资源文件和原版可执行文件；这些文件由开发者本机提供。
3. dist/MCOWH-zh-CN-0.3.0-llm-review.zip及对应-source.zip：冻结0.3.0发布包，哈希记录见docs/package-verification-0.3.0.json。
4. dist/MCOWH-zh-CN-0.3.0-llm-review/patch.mcpatch：上述玩家ZIP中的差分包。
5. build/0.3.0-llm-review：用冻结差分包及干净英文副本重建的旧版资源。bundle.prepare提供重建入口，产物不需安装到游戏。

Releases中的MCOWH-development-baseline-0.3.0.zip包含第3项的两个冻结旧ZIP，将其解压到dist，再从旧玩家ZIP取出patch.mcpatch到第4项路径。它只包含旧发布差分和源码，不含原游戏BIN；第2项原版资源仍需开发者自行提供。这些输入不等同于GitHub自动生成的源码ZIP，不要自行猜造基线。

重建第5项示例（先确认项目根目录下的work/clean-fixture与profiles基线匹配）：

```powershell
python -c "import sys; from pathlib import Path; sys.path.insert(0,'tools'); from bundle import prepare; prepare(Path('dist/MCOWH-zh-CN-0.3.0-llm-review/patch.mcpatch'),Path('work/clean-fixture'),Path('build/0.3.0-llm-review'))"
```

准备完输入后：

```powershell
python tools/build_panel_only.py
python tools/verify_panel_only.py
python tools/bundle.py
python -m unittest discover -s tests -q
node tests/editor_core.test.js
```

完整测试还依赖此前解包的work/extracted、图片索引/原图和本机Noto Sans SC字体。tests/editor_browser.test.js使用Windows Edge隔离无头配置；无这些输入时不能宣称完整测试通过。

打包独立程序：

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --name MCOWH_Chinese_Patch --distpath dist/MCOWH-zh-CN-0.3.2-panel-only --workpath build/pyinstaller-0.3.2 --specpath build tools/installer.py
python tools/verify_release.py
python tools/make_release.py
```

verify_release在work隔离目录中验证安装和还原，不启动游戏。具备冻结0.3.0、0.3.1差分包时，会覆盖这两版的还原兼容性。发布前确认版本号、差分和EXE哈希匹配验证记录，再上传玩家ZIP和SHA256校验文件到Release。不要将原游戏BIN、EXE或展开后的字体/图片上传。
