"""Player-facing standalone patch installer and restore tool."""
import argparse
import json
import os
from pathlib import Path
import queue
import re
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from bundle import metadata, prepare
from install_local import operation, game_running
from release_config import PATCH_VERSION, RELEASE_FOLDER


def default_bundle():
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1] / "dist" / RELEASE_FOLDER
    return base / "patch.mcpatch"


def find_games():
    candidates = []
    start = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    candidates += list(start.parents)[:5] + [start]
    roots = []
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                roots.append(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
        except OSError:
            pass
    for root in list(roots):
        config = root / "steamapps/libraryfolders.vdf"
        if config.exists():
            roots += [Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', config.read_text("utf8"))]
    for root in roots:
        manifest = root / "steamapps/appmanifest_409000.acf"
        if manifest.exists():
            match = re.search(r'"installdir"\s+"([^"]+)"', manifest.read_text("utf8"))
            if match:
                candidates.append(root / "steamapps/common" / match[1])
    return list(dict.fromkeys(p.resolve() for p in candidates if (p / "MC_OneWayHeroics.exe").is_file()))


def execute(action: str, game: Path, bundle: Path):
    manifest = metadata(bundle)
    if game_running():
        raise ValueError("请先关闭游戏，再安装或还原补丁。")
    journal = game / ".mcowh-zh-backup/state.json"
    if action == "restore":
        return operation(action, game, Path(), manifest["baseline"])
    if journal.exists():
        state = json.loads(journal.read_text("utf8"))
        if state["status"] == "installed":
            # Let the installer check the actual installed hashes, too.
            with tempfile.TemporaryDirectory(prefix="mcowh-zh-status-") as temp:
                out = Path(temp)
                (out / "build-report.json").write_text(json.dumps(manifest["report"]), encoding="utf8")
                return operation(action, game, out, manifest["baseline"])
    with tempfile.TemporaryDirectory(prefix="mcowh-zh-build-") as temp:
        staging = Path(temp)
        prepare(bundle, game, staging)
        return operation(action, game, staging, manifest["baseline"])


def gui(bundle: Path):
    root = tk.Tk()
    root.title("不可思议编年史：单向勇者 · 简体中文补丁")
    root.geometry("690x340")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=f"简体中文补丁 · {PATCH_VERSION}", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
    ttk.Label(frame, text="适用 Steam 英文版 build 1527978。基于0.3.0，仅汉化指定19项属性，MOV为“移速”。\n人名暂留英文，游戏内效果待验收；从旧版升级请先还原原版，再安装。", padding=(0, 10)).pack(anchor="w")
    ttk.Label(frame, text="游戏目录").pack(anchor="w")
    games = find_games()
    path = tk.StringVar(value=str(games[0]) if games else "")
    row = ttk.Frame(frame)
    row.pack(fill="x", pady=6)
    entry = ttk.Entry(row, textvariable=path)
    entry.pack(side="left", fill="x", expand=True)
    browse = ttk.Button(row, text="选择目录", command=lambda: choose())
    browse.pack(side="right", padx=(8, 0))
    status = tk.StringVar(value="关闭游戏后，选择安装或还原。原文件将自动备份。")
    ttk.Label(frame, textvariable=status, wraplength=640).pack(anchor="w", pady=12)
    buttons = ttk.Frame(frame)
    buttons.pack(anchor="w")
    messages = queue.Queue()
    busy = [False]

    def choose():
        result = filedialog.askdirectory(title="选择包含 MC_OneWayHeroics.exe 的目录", initialdir=path.get() or None)
        if result:
            path.set(result)

    def start(action):
        if busy[0]:
            return
        game = Path(path.get()).resolve()
        busy[0] = True
        for widget in [install, restore, browse, entry]:
            widget.configure(state="disabled")
        status.set("正在校验、重建并安装补丁……" if action == "install" else "正在校验备份并还原原版……")

        def worker():
            try:
                messages.put((True, execute(action, game, bundle)))
            except Exception as error:
                messages.put((False, str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def poll():
        try:
            ok, text = messages.get_nowait()
            busy[0] = False
            for widget in [install, restore, browse, entry]:
                widget.configure(state="normal")
            status.set(text)
            if not ok:
                messagebox.showerror("操作未完成", text)
        except queue.Empty:
            pass
        root.after(100, poll)

    def close():
        if busy[0]:
            status.set("正在写入，请等待操作完成后关闭窗口。")
        else:
            root.destroy()
    install = ttk.Button(buttons, text="安装汉化", command=lambda: start("install"))
    install.pack(side="left")
    restore = ttk.Button(buttons, text="还原原版", command=lambda: start("restore"))
    restore.pack(side="left", padx=12)
    root.protocol("WM_DELETE_WINDOW", close)
    root.after(100, poll)
    root.mainloop()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle", type=Path, default=default_bundle())
    p.add_argument("--game", type=Path)
    p.add_argument("--action", choices=["install", "restore", "verify"])
    args = p.parse_args()
    if args.action:
        if not args.game:
            p.error("--game is required for command-line mode")
        if args.action == "verify":
            with tempfile.TemporaryDirectory(prefix="mcowh-zh-verify-") as temp:
                prepare(args.bundle, args.game, Path(temp))
            result = "差分包重建验证通过。"
        else:
            result = execute(args.action, args.game, args.bundle)
        log = args.bundle.parent / "last-operation.txt"
        log.write_text(result, encoding="utf8")
        if sys.stdout:
            print(result)
    else:
        gui(args.bundle)
