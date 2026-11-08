"""Read-only audit of installed patch files, backups, resources and glyph coverage.

This never launches the game or writes to its resources. File integrity is not
evidence that the game's renderer displays translated text correctly.
"""
import argparse
import hashlib
import json
from pathlib import Path

from bundle import metadata
from fonts import inspect
from install_local import safe_path
from resources import Archive, GAME, PROJECT, sha256
from release_config import RELEASE_FOLDER
from game_compat import EXE_NAME, executable_state


def file_state(path: Path, original_hash: str, patched_hash: str | None = None):
    if not path.is_file():
        return {"state": "missing", "sha256": None}
    digest = sha256(path)
    if patched_hash is not None and digest == patched_hash:
        state = "patched"
    elif digest == original_hash:
        state = "original"
    else:
        state = "different"
    return {"state": state, "sha256": digest}


def installation_state(rows):
    guards = [row for row in rows if not row["patch_target"]]
    targets = [row for row in rows if row["patch_target"]]
    if not guards or not targets or any(row["state"] not in {"original", "compatible"} for row in guards):
        return "unsupported_or_incomplete"
    states = {row["state"] for row in targets}
    if states == {"patched"}:
        return "installed"
    if states == {"original"}:
        return "original"
    if states <= {"original", "patched"}:
        return "mixed"
    return "unsupported_or_incomplete"


def audit(game: Path, bundle: Path):
    game = game.resolve()
    manifest = metadata(bundle)
    patched = {f["path"]: f for f in manifest["report"]["files"]}
    files = []
    for entry in manifest["baseline"]["files"]:
        path = entry["path"]
        target = patched.get(path)
        status = (executable_state(safe_path(game, path), entry["sha256"]) if path == EXE_NAME
                  else file_state(safe_path(game, path), entry["sha256"], target["sha256"] if target else None))
        files.append({"path": path, "patch_target": target is not None, **status})
    state = installation_state(files)
    originals = {f["path"]: f for f in manifest["baseline"]["files"]}
    backups = [{"path": path, **file_state(safe_path(game / ".mcowh-zh-backup", path), originals[path]["sha256"])}
               for path in patched]
    resources = []
    fonts = []
    if state == "installed":
        archive = Archive(game)
        by_name = {entry.name: entry for entry in archive.entries}
        needed = {ord(c) for c in manifest["report"]["required_characters"]}
        for entry in manifest["resources"]:
            raw = archive.read(by_name[entry["name"]])
            digest = hashlib.sha256(raw).hexdigest()
            resources.append({"name": entry["name"], "matches": digest == entry["sha256"], "sha256": digest})
            if entry["name"].startswith("d3d11/common/text/"):
                glyphs = inspect(raw)[0]
                absent = sorted(needed - {row[0] for row in glyphs})
                fonts.append({"name": entry["name"], "missing_characters": "".join(chr(c) for c in absent),
                              "covers_demo_text": not absent})
    backup_ok = all(item["state"] == "original" for item in backups)
    installation_ok = state == "installed" and all(item["matches"] for item in resources)
    installation_ok = installation_ok and bool(fonts) and all(item["covers_demo_text"] for item in fonts)
    return {"schema": 1, "patch_version": manifest["version"], "installation_state": state,
            "installed_content_verified": installation_ok, "original_backups_verified": backup_ok,
            "bundle_sha256": sha256(bundle), "files": files, "backups": backups,
            "resources": resources, "fonts": fonts, "runtime_display_verified": False,
            "runtime_test_owner": "user", "note": "Read-only audit. In-game display and layout remain unverified."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=GAME)
    parser.add_argument("--bundle", type=Path, default=PROJECT / "dist" / RELEASE_FOLDER / "patch.mcpatch")
    parser.add_argument("--out", type=Path, default=PROJECT / "work/installation-audit.json")
    args = parser.parse_args()
    result = audit(args.game, args.bundle)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({k: result[k] for k in ["patch_version", "installation_state", "installed_content_verified",
                                          "original_backups_verified", "runtime_display_verified"]}))
    print(f"Resources checked: {len(result['resources'])}; fonts checked: {len(result['fonts'])}")
