"""Build and verify a local technical demonstration. Does not install it."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from resources import Archive, GAME, PROJECT, rebuild, sha256
from formats import database_fields, replace_database, unpack_scripts, pack_scripts
from fonts import extend
from release_config import PATCH_VERSION

TOKENS = re.compile(r"\\(?:[A-Za-z_]+|[-+])\[[^\]\r\n]*\]|<[^>\r\n]+>|\$[A-Za-z][A-Za-z0-9]*")


def check_tokens(source: str, target: str):
    if "\0" in target or Counter(TOKENS.findall(source)) != Counter(TOKENS.findall(target)):
        raise ValueError(f"Control tokens changed: {source!r}")


def build(game: Path, out: Path, translation: Path, font: Path):
    game, out = game.resolve(), out.resolve()
    if out == game or game.is_relative_to(out):
        raise ValueError("Build must not overwrite the installed game")
    baseline = json.loads((PROJECT / "work/baseline.json").read_text("utf8"))
    pinned = {f["path"]: f for f in baseline["files"]}
    arc = Archive(game)
    for relative in ["MC_OneWayHeroics.exe", "D3D11/Data/archive.bin"]:
        if sha256(game / relative) != pinned[relative]["sha256"]:
            raise ValueError(f"Unsupported or modified original: {relative}")
    source = json.loads(translation.read_text("utf8"))
    replacements = {}
    base_names = {}
    originals = {}
    by_name = {e.name: e for e in arc.entries}

    def read(name):
        if name not in originals:
            originals[name] = arc.read(by_name[name])
        return originals[name]

    name = "d3d11/data/basicdata/database.dat"
    fields = {f.id: f for f in database_fields(read(name))}
    for key, target in source["database"].items():
        check_tokens(fields[key].text, target)
    replacements[name] = replace_database(read(name), source["database"])
    script_count = 0
    ui_count = 0
    for name in ["d3d11/data/event/event.pack", "d3d11/data/uiscript/uiscript.pack"]:
        records = unpack_scripts(read(name))
        changed = []
        seen = set()
        for path, data in records:
            if path in source["scripts"]:
                text = data.decode("utf8")
                for change in source["scripts"][path]:
                    a, b = change["source"], change["target"]
                    check_tokens(a, b)
                    if text.count(a) != 1:
                        raise ValueError(f"Script source is not unique: {path}")
                    text = text.replace(a, b)
                data = text.encode("utf8")
                seen.add(path)
                script_count += 1
            if "uiscript.pack" in name:
                # Keep every number, command and asset path. Translate only the
                # final label column of a Button definition.
                for a, b in source["ui_labels"].items():
                    pattern = rb"(?m)^(Button:[^\r\n]*,\s*)" + re.escape(a.encode()) + rb"(?=\r?$)"
                    data, count = re.subn(pattern, lambda m: m[1] + b.encode("utf8"), data)
                    ui_count += count
            changed.append((path, data))
        if "event.pack" in name and seen != set(source["scripts"]):
            raise ValueError("Unknown translated script paths")
        new = pack_scripts(changed)
        if unpack_scripts(new) != changed:
            raise ValueError("Script pack verification failed")
        replacements[name] = new
    text_values = list(source["database"].values()) + list(source["ui_labels"].values())
    text_values += [c["target"] for changes in source["scripts"].values() for c in changes]
    chars = set("".join(text_values))
    fonts = []
    for e in arc.entries:
        if not e.name.startswith("d3d11/common/text/"):
            continue
        base_name = e.name
        data = read(base_name)
        if "seurat-pro-m-20" in e.name:
            # This original font contains only 228 characters. Use the same
            # family's complete 16-point font as a scalable template instead.
            base_name = e.name.replace("m-20", "m-16")
            data = read(base_name).replace(b"m-16.fgen#BitmapFont", b"m-20.fgen#BitmapFont")
        weight = 700 if "skip-std" in e.name else 600 if "seurat-pro-db" in e.name else 500
        data, report = extend(data, chars, font, weight=weight)
        replacements[e.name] = data
        base_names[e.name] = base_name
        fonts.append({"name": e.name, "base": base_name, **report})
    out.mkdir(parents=True, exist_ok=True)
    changed_groups = sorted({by_name[name].group for name in replacements})
    data_out = out / "D3D11/Data"
    data_out.mkdir(parents=True, exist_ok=True)
    for group in changed_groups:
        g = arc.groups[group]
        relative = "D3D11/Data/" + g["name"]
        if sha256(game / relative) != pinned[relative]["sha256"]:
            raise ValueError(f"Modified original data file: {g['name']}")
    rebuild(arc, replacements, out)
    recipes = PROJECT / "work/replacements"
    recipes.mkdir(exist_ok=True)
    for name, data in replacements.items():
        dest = recipes / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    report = {"version": PATCH_VERSION, "stage": "technical-demo", "steam_build_id": "1527978", "database_entries": len(source["database"]),
              "event_scripts": script_count, "ui_button_labels": ui_count, "fonts": fonts,
              "required_characters": "".join(sorted(c for c in chars if ord(c) >= 128)),
              "changed_resources": [{"name": n, "base": base_names.get(n, n),
                  "sha256": hashlib.sha256(d).hexdigest()} for n, d in replacements.items()],
              "files": []}
    report["files"] = [{"path": p.relative_to(out).as_posix(), "size": p.stat().st_size,
                        "sha256": sha256(p)} for p in sorted(data_out.glob("*.bin"))]
    (out / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({k: report[k] for k in ["database_entries", "event_scripts", "ui_button_labels"]}))
    print(f"Verified {len(replacements)} rebuilt resources; {len(report['files'])} changed files")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--game", type=Path, default=GAME)
    p.add_argument("--out", type=Path, default=PROJECT / "build/demo")
    p.add_argument("--translation", type=Path, default=PROJECT / "translations/demo.zh-CN.json")
    p.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"))
    a = p.parse_args()
    build(a.game, a.out, a.translation, a.font)
