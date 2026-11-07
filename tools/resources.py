"""Read Mystery Chronicle's local resource index and LZ4 resource blocks.

All offsets are byte offsets. The index starts with a case-folded rolling hash.
The XOR operation touches complete 32-bit words only, as in the game executable.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import struct

import lz4.block

KEY = bytes.fromhex("efbeadde")
TRANS = [bytes.maketrans(bytes(range(256)), bytes(x ^ k for x in range(256))) for k in KEY]
PROJECT = Path(__file__).resolve().parents[1]
GAME = PROJECT.parent


def xor(data: bytes) -> bytes:
    end = len(data) & ~3
    out = bytearray(data)
    for i in range(4):
        out[i:end:4] = data[i:end:4].translate(TRANS[i])
    return bytes(out)


def index_hash(data: bytes) -> int:
    value = 0
    for byte in data:
        value = (value * 131 + (byte & 0xDF)) & 0xFFFFFFFF
    return ((value & 0x07FFFFFF) << 4) | (len(data) & 15)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class Entry:
    index: int
    path_hash: int
    size: int
    packed_size: int
    group: int
    offset: int
    flags: int
    name: str


class Archive:
    def __init__(self, game: Path = GAME):
        self.game = game.resolve()
        self.data_dir = self.game / "D3D11" / "Data"
        self.raw = (self.data_dir / "archive.bin").read_bytes()
        self.decoded = xor(self.raw)
        self.prefix = self.decoded[:4]
        self.body = self.decoded[4:]
        if struct.unpack("<I", self.prefix)[0] != index_hash(self.body):
            raise ValueError("Archive checksum mismatch")
        h = struct.unpack_from("<16I", self.body)
        if self.body[:4] != b"bin." or h[2] != len(self.body):
            raise ValueError("Unsupported archive header")
        self.group_count, self.group_offset, self.count, self.entry_offset = h[8:12]
        if self.group_offset + self.group_count * 288 != self.entry_offset:
            raise ValueError("Unexpected group table extent")
        if self.entry_offset + self.count * 160 != len(self.body):
            raise ValueError("Unexpected file table extent")
        self.groups = []
        for i in range(self.group_count):
            o = self.group_offset + i * 288
            words = struct.unpack_from("<8I", self.body, o)
            name = self.body[o + 32:o + 288].split(b"\0")[0].decode("ascii")
            if not name.startswith("/data") or "/" in name[1:] or "\\" in name:
                raise ValueError("Unsafe archive group name")
            self.groups.append(dict(index=i, count=words[0], first=words[1], size=words[2], name=name[1:]))
        self.entries = []
        for i in range(self.count):
            o = self.entry_offset + i * 160
            w = struct.unpack_from("<8I", self.body, o)
            name = self.body[o + 32:o + 160].split(b"\0")[0].decode("ascii")
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or ":" in name or "\\" in name:
                raise ValueError("Unsafe resource path")
            e = Entry(i, *w[:6], name)
            if not 0 <= e.group < self.group_count:
                raise ValueError("Invalid group index")
            g = self.groups[e.group]
            if not (g["first"] <= i < g["first"] + g["count"]):
                raise ValueError("Resource outside its group")
            if e.offset < 32 or e.offset + e.packed_size > g["size"]:
                raise ValueError("Resource outside data file")
            self.entries.append(e)

    def read(self, entry: Entry) -> bytes:
        p = self.data_dir / self.groups[entry.group]["name"]
        with p.open("rb") as f:
            f.seek(entry.offset)
            data = f.read(entry.packed_size)
        if len(data) != entry.packed_size:
            raise ValueError(f"Truncated resource: {entry.name}")
        if entry.flags != 1:
            raise ValueError(f"Unsupported compression flag: {entry.flags}")
        result = lz4.block.decompress(xor(data), uncompressed_size=entry.size)
        if len(result) != entry.size:
            raise ValueError(f"Size mismatch: {entry.name}")
        return result

    def index_json(self):
        return {"groups": self.groups, "entries": [asdict(e) for e in self.entries]}


def rebuild(archive: Archive, replacements: dict[str, bytes], output: Path):
    """Append replacement blocks and write a new index to an independent directory."""
    output = output.resolve()
    if output == archive.game or archive.game.is_relative_to(output):
        raise ValueError("Refusing to rebuild over the source game")
    by_name = {e.name: e for e in archive.entries}
    if replacements.keys() - by_name.keys():
        raise ValueError("Unknown replacement resources")
    body = bytearray(archive.body)
    data_out = output / "D3D11/Data"
    data_out.mkdir(parents=True, exist_ok=True)
    for group in sorted({by_name[name].group for name in replacements}):
        g = archive.groups[group]
        dest = data_out / g["name"]
        shutil.copy2(archive.data_dir / g["name"], dest)
        with dest.open("ab") as stream:
            for name, new in replacements.items():
                entry = by_name[name]
                if entry.group != group:
                    continue
                stream.write(b"\0" * (-stream.tell() % 16))
                offset = stream.tell()
                packed = lz4.block.compress(new, mode="high_compression", compression=9, store_size=False)
                if lz4.block.decompress(packed, uncompressed_size=len(new)) != new:
                    raise ValueError("Compression round-trip failed")
                stream.write(xor(packed))
                o = archive.entry_offset + entry.index * 160
                struct.pack_into("<II", body, o + 4, len(new), len(packed))
                struct.pack_into("<I", body, o + 16, offset)
            stream.write(b"\0" * (-stream.tell() % 16))
            struct.pack_into("<I", body, archive.group_offset + group * 288 + 8, stream.tell())
    (data_out / "archive.bin").write_bytes(xor(struct.pack("<I", index_hash(body)) + bytes(body)))
    check = Archive(output)
    for name, expected in replacements.items():
        if check.read(check.entries[by_name[name].index]) != expected:
            raise ValueError(f"Rebuilt resource mismatch: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["index", "baseline", "extract", "verify"])
    parser.add_argument("--game", type=Path, default=GAME)
    parser.add_argument("--contains", default="")
    parser.add_argument("--out", type=Path, default=PROJECT / "work")
    args = parser.parse_args()
    archive = Archive(args.game)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.command == "baseline":
        paths = [args.game / "MC_OneWayHeroics.exe", args.game / "steam_api.dll"]
        paths += sorted((args.game / "D3D11").rglob("*"))
        files = [{"path": p.relative_to(args.game).as_posix(), "size": p.stat().st_size,
                  "sha256": sha256(p)} for p in paths if p.is_file()]
        output = {"app_id": 409000, "steam_build_id": "1527978", "files": files}
        dest = args.out / "baseline.json"
        if dest.exists():
            if json.loads(dest.read_text("utf-8")) != output:
                raise ValueError("Existing baseline differs; refusing to replace it")
        else:
            dest.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Baseline: {len(files)} files, {sum(f['size'] for f in files):,} bytes")
    elif args.command == "index":
        (args.out / "resource-index.json").write_text(json.dumps(archive.index_json(), indent=2), encoding="utf-8")
        print(f"Index: {archive.group_count} groups, {archive.count} resources")
    else:
        entries = [e for e in archive.entries if args.contains.lower() in e.name.lower()]
        for e in entries:
            data = archive.read(e)
            if args.command == "extract":
                dest = args.out / "extracted" / e.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                print(f"{e.size:>10} {e.name}")
        print(f"{args.command}: {len(entries)} resources OK")


if __name__ == "__main__":
    main()
