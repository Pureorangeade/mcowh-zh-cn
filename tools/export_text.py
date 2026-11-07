"""Export UTF-8 JSONL translation candidates with stable IDs and editor context."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from formats import database_fields, project_context, unpack_scripts
from resources import Archive, GAME, PROJECT
from build import TOKENS


def candidate(text):
    if not text.strip() or not re.search(r"[A-Za-z]{2}", TOKENS.sub("", text)):
        return False
    if re.search(r"(?im)^\s*[@#]|(?:[A-Za-z_]+/){2,}|\.(?:png|jpg|at9|ogg|txt|dat|bin|csv)(?:\b|$)", text):
        return False
    # Pure identifiers and configuration values need programmer review.
    if re.fullmatch(r"[A-Z_\d\s.,;:\-]+", text):
        return False
    return True


def export(game: Path, output: Path):
    archive = Archive(game)
    by_name = {e.name: e for e in archive.entries}
    root = "d3d11/data/basicdata/"
    data = archive.read(by_name[root + "database.dat"])
    context = project_context(archive.read(by_name[root + "database.project"]))
    rows = []
    for field in database_fields(data):
        table, row, column = map(int, field.id.split("/")[1:])
        if 58 <= table <= 64 and column != 1:
            continue
        info = context[table]
        if field.field_index >= len(info["types"]) or info["types"][field.field_index] != 0:
            continue
        try:
            text = field.text
        except UnicodeDecodeError:
            continue
        if not candidate(text):
            continue
        rows.append({"id": field.id, "resource": root + "database.dat", "source": text,
            "translation": "", "status": "untranslated", "source_sha256": hashlib.sha256(field.raw).hexdigest(),
            "context": {"table": info["name"], "row": info["rows"][row] if row < len(info["rows"]) else "",
                "field": info["fields"][field.field_index]}, "tokens": TOKENS.findall(text)})
    for path, raw in unpack_scripts(archive.read(by_name["d3d11/data/event/event.pack"])):
        try:
            text = raw.decode("utf8")
        except UnicodeDecodeError:
            continue
        lines = text.splitlines(keepends=True)
        active = False
        block = []
        index = 0

        def emit():
            nonlocal index
            source = "".join(block).rstrip("\r\n")
            if candidate(source):
                rows.append({"id": f"script/{path}/mes/{index}", "resource": "d3d11/data/event/event.pack",
                    "script": path, "source": source, "translation": "", "status": "untranslated",
                    "source_sha256": hashlib.sha256(source.encode()).hexdigest(), "tokens": TOKENS.findall(source),
                    "context": {"command": "@mes/@L_mes/@R_mes", "block": index}})
            index += 1
        for line in lines:
            trimmed = line.strip()
            if trimmed.startswith(("@", "#")):
                if block:
                    emit()
                    block = []
                active = bool(re.match(r"@(?:[LR]_)?mes(?:\s|$)", trimmed))
            elif active:
                block.append(line)
        if block:
            emit()
    output.mkdir(parents=True, exist_ok=True)
    with (output / "catalogue.jsonl").open("w", encoding="utf8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    stats = {"candidate_count": len(rows), "database_candidates": sum(r["id"].startswith("db/") for r in rows),
             "script_blocks": sum(r["id"].startswith("script/") for r in rows),
             "source_characters": sum(len(r["source"]) for r in rows),
             "unique_source_texts": len({r["source"] for r in rows}),
             "scope": "Heuristic candidates from database.dat and @mes blocks only; not total localization coverage."}
    (output / "catalogue-stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=GAME)
    parser.add_argument("--out", type=Path, default=PROJECT / "work/translation")
    args = parser.parse_args()
    export(args.game, args.out)
