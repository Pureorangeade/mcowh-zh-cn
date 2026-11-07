"""Install/restore the locally built demo, with original-file verification.

Developer entry point. The standalone distributable is built separately.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path, PurePosixPath
import shutil

from resources import GAME, PROJECT, sha256


def game_running():
    if os.name != "nt":
        return False
    class Process(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
                    ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD),
                    ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD),
                    ("exe", wintypes.WCHAR * 260)]
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Process)]
    k.Process32NextW.argtypes = k.Process32FirstW.argtypes
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = k.CreateToolhelp32Snapshot(2, 0)
    if handle == wintypes.HANDLE(-1).value:
        raise OSError("Cannot inspect running processes")
    try:
        entry = Process()
        entry.size = ctypes.sizeof(entry)
        more = k.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            if entry.exe.lower() == "mc_onewayheroics.exe":
                return True
            more = k.Process32NextW(handle, ctypes.byref(entry))
        return False
    finally:
        k.CloseHandle(handle)


def safe_path(root: Path, relative: str):
    parts = PurePosixPath(relative)
    if parts.is_absolute() or ".." in parts.parts or ":" in relative or "\\" in relative:
        raise ValueError("Unsafe patch path")
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("Patch path escapes game directory")
    return result


def atomic_copy(source: Path, target: Path):
    temp = target.with_name(target.name + ".mcowh-zh-tmp")
    created = False
    try:
        with source.open("rb") as src, temp.open("xb") as dest:
            created = True
            shutil.copyfileobj(src, dest, 1024 * 1024)
            dest.flush()
            os.fsync(dest.fileno())
        os.replace(temp, target)
    finally:
        if created and temp.exists():
            temp.unlink()


def write_state(path: Path, value):
    temp = path.with_suffix(".new")
    with temp.open("w", encoding="utf8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def operation(action: str, game: Path, build: Path, baseline: dict):
    game = game.resolve()
    if game_running():
        raise ValueError("请先关闭游戏，再安装或还原补丁。")
    report = json.loads((build / "build-report.json").read_text("utf8")) if action == "install" else None
    originals = {f["path"]: f for f in baseline["files"]}
    backup = game / ".mcowh-zh-backup"
    journal = backup / "state.json"
    exe = game / "MC_OneWayHeroics.exe"
    if not exe.is_file() or sha256(exe) != originals["MC_OneWayHeroics.exe"]["sha256"]:
        raise ValueError("不支持的游戏主程序版本。")
    backup.mkdir(exist_ok=True)
    # Lock survives process termination as a file but the OS releases its byte lock.
    lock = (backup / "lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        state = json.loads(journal.read_text("utf8")) if journal.exists() else None
        if action == "restore":
            if not state:
                return "没有已安装的补丁。"
            files = state["files"]
            for item in files:
                relative = item["path"]
                saved = safe_path(backup, relative)
                if sha256(saved) != item["original_sha256"]:
                    raise ValueError(f"备份校验失败：{relative}")
                current = sha256(safe_path(game, relative))
                if current not in [item["original_sha256"], item["sha256"]]:
                    raise ValueError(f"文件被其他程序修改，未覆盖：{relative}")
            state["status"] = "restoring"
            write_state(journal, state)
            for item in files:
                atomic_copy(safe_path(backup, item["path"]), safe_path(game, item["path"]))
                if sha256(safe_path(game, item["path"])) != item["original_sha256"]:
                    raise ValueError("还原后的文件校验失败。")
            state["status"] = "restored"
            write_state(journal, state)
            return "已还原原版，文件哈希与备份一致。"
        files = [{**item, "original_sha256": originals[item["path"]]["sha256"]} for item in report["files"]]
        if state and state["status"] == "installed":
            if state["files"] == files and all(sha256(safe_path(game, x["path"])) == x["sha256"] for x in files):
                return "相同版本的补丁已经安装。"
            raise ValueError("请先还原已安装的补丁，再安装新版本。")
        if state and state["status"] not in ("restored", "rolled_back"):
            raise ValueError("上次操作未完成，请先执行还原。")
        # Validate every input before changing any installed file.
        for item in files:
            relative = item["path"]
            if sha256(safe_path(game, relative)) != item["original_sha256"]:
                raise ValueError(f"原版文件已修改或版本不符：{relative}")
            if sha256(safe_path(build.resolve(), relative)) != item["sha256"]:
                raise ValueError(f"补丁文件校验失败：{relative}")
            saved = safe_path(backup, relative)
            saved.parent.mkdir(parents=True, exist_ok=True)
            if not saved.exists():
                atomic_copy(safe_path(game, relative), saved)
            if sha256(saved) != item["original_sha256"]:
                raise ValueError(f"原版备份校验失败：{relative}")
        state = {"schema": 1, "stage": "technical-demo", "status": "prepared", "files": files}
        write_state(journal, state)
        try:
            state["status"] = "installing"
            write_state(journal, state)
            # Index last: until then, the original offsets remain valid.
            for item in sorted(files, key=lambda x: x["path"].endswith("archive.bin")):
                atomic_copy(safe_path(build.resolve(), item["path"]), safe_path(game, item["path"]))
            if any(sha256(safe_path(game, x["path"])) != x["sha256"] for x in files):
                raise ValueError("安装结果校验失败。")
            state["status"] = "installed"
            write_state(journal, state)
        except Exception:
            for item in files:
                atomic_copy(safe_path(backup, item["path"]), safe_path(game, item["path"]))
            state["status"] = "rolled_back"
            write_state(journal, state)
            raise
        return "汉化技术演示补丁已安装。"
    finally:
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "restore"])
    parser.add_argument("--game", type=Path, default=GAME)
    parser.add_argument("--build", type=Path, default=PROJECT / "build/demo")
    args = parser.parse_args()
    baseline = json.loads((PROJECT / "work/baseline.json").read_text("utf8"))
    print(operation(args.action, args.game, args.build, baseline))
