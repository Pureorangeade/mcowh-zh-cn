"""Add Chinese glyphs to this build's Phyre bitmap fonts without moving metadata.

Preserves original ASCII glyphs and texture pixels. Rare unused CJK slots are
reassigned; new bitmaps occupy appended atlas rows. This is a prototype for the
English-base patch, not a general Japanese font extension.
"""
import math
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

GLYPH_START = 0xD8E
RECORD = struct.Struct("<III8fB")


def inspect(data: bytes):
    if data[:4] != b"RYHP":
        raise ValueError("Not a Phyre resource")
    count = struct.unpack_from("<I", data, GLYPH_START - 11)[0]
    if not 100 <= count <= 10000:
        raise ValueError("Unsupported font glyph count")
    end = GLYPH_START + count * RECORD.size
    rows = [RECORD.unpack_from(data, o) for o in range(GLYPH_START, end, RECORD.size)]
    if rows[0][0] != 32 or any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError("Font character table is not sorted")
    descriptor = data.index(b"PBitmapFont\0", end)
    width, height = struct.unpack_from("<II", data, descriptor - 8)
    tex_size = struct.unpack_from("<I", data, 0x50)[0]
    if width * height != tex_size or width not in (4096, 8192):
        raise ValueError("Unsupported texture format")
    tex_start = len(data) - tex_size
    size = struct.unpack_from("<I", data, 0xD77)[0]
    if not 16 <= size <= 64:
        raise ValueError("Unsupported native font size")
    return rows, end, descriptor, width, height, tex_start, size


def uleb128(value):
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def serialize_glyphs(data, rows):
    """Grow the observed Phyre array and its matching fixup count.

    Every original font independently has these same relationships. Refuse any
    unfamiliar layout instead of guessing at additional relocation metadata.
    """
    old_rows, end, descriptor, width, height, tex_start, size = inspect(data)
    old_count, count = len(old_rows), len(rows)
    byte_size = old_count * RECORD.size
    padding = 4 - byte_size % 4
    expected = {0xCFA: old_count, 0xCFE: byte_size + padding, 0xD02: byte_size,
                0xD06: padding, 0x38: byte_size + padding + 102}
    if any(struct.unpack_from('<I', data, offset)[0] != value for offset, value in expected.items()):
        raise ValueError('Unsupported Phyre array header')
    if descriptor != end + padding + 22 or data[end:end + padding] != bytes(padding):
        raise ValueError('Unsupported Phyre array alignment')
    prefix = bytes.fromhex('0e0000000c0000000000000005000000030000000c000000580200014804015812000350230002')
    suffix = bytes.fromhex('487002080100')
    if data[descriptor + 15:tex_start] != prefix + uleb128(old_count) + suffix:
        raise ValueError('Unsupported Phyre array relocation metadata')
    new_size = count * RECORD.size
    new_padding = 4 - new_size % 4
    meta = bytearray(data[:GLYPH_START])
    meta.extend(b''.join(RECORD.pack(*row) for row in rows))
    meta.extend(bytes(new_padding))
    meta.extend(data[end + padding:descriptor + 15])
    meta.extend(prefix + uleb128(count) + suffix)
    for offset, value in {0xCFA: count, 0xCFE: new_size + new_padding, 0xD02: new_size,
                          0xD06: new_padding, 0x38: new_size + new_padding + 102,
                          GLYPH_START - 11: count}.items():
        struct.pack_into('<I', meta, offset, value)
    shift = new_size + new_padding - byte_size - padding
    return meta, descriptor + shift


def extend(data: bytes, chars: set[str], font_path: Path, *, weight: int = 500, grow: bool = False) -> tuple[bytes, dict]:
    rows, end, descriptor, width, height, tex_start, size = inspect(data)
    codes = {r[0] for r in rows}
    required = {ord(c) for c in chars if ord(c) >= 128}
    missing = sorted(required - codes)
    # Keep ASCII, kana, punctuation, and all characters needed by the translation.
    donors = sorted((r[0] for r in rows if 0x4E00 <= r[0] <= 0x9FFF and r[0] not in required), reverse=True)
    if not grow and len(donors) < len(missing):
        raise ValueError("Insufficient CJK slots; supply a full CJK font template")
    if not required:
        return data, {"added": 0, "redrawn": 0, "removed_codes": []}
    with TTFont(font_path) as font_data:
        unavailable = required - set(font_data.getBestCmap())
        axes = font_data["fvar"].axes if "fvar" in font_data else []
        weight_axis = next((a for a in axes if a.axisTag == "wght"), None)
        if weight_axis is None or not weight_axis.minValue <= weight <= weight_axis.maxValue:
            raise ValueError("Source font must support the requested variable weight")
        variations = [weight if a.axisTag == "wght" else a.defaultValue for a in axes]
    if unavailable:
        raise ValueError("Source font lacks characters: " + ", ".join(f"U+{c:04X}" for c in sorted(unavailable)))
    replace = {} if grow else dict(zip(donors, missing))
    cell = size + 4
    columns = width // cell
    new_height = height + math.ceil(len(required) / columns) * cell
    atlas = Image.new("L", (width, new_height), 0)
    atlas.paste(Image.frombytes("L", (width, height), data[tex_start:]), (0, 0))
    font = ImageFont.truetype(str(font_path), size=size)
    # Noto Sans SC's default is weight 100. Explicitly render existing and
    # missing translation characters together so a word never mixes weights.
    font.set_variation_by_axes(variations)
    metrics = {}
    for index, code in enumerate(sorted(required)):
        char = chr(code)
        x = (index % columns) * cell + 2
        y = height + (index // columns) * cell + 2
        bbox = font.getbbox(char, anchor="ls")
        if bbox is None or bbox[2] - bbox[0] > cell - 2 or bbox[3] - bbox[1] > cell - 2:
            raise ValueError(f"Glyph exceeds atlas cell: U+{code:04X}")
        # Game offsets specify the distance from the baseline to the glyph's top.
        glyph = Image.new("L", (bbox[2] - bbox[0], bbox[3] - bbox[1]), 0)
        ImageDraw.Draw(glyph).text((-bbox[0], -bbox[1]), char, font=font, fill=255, anchor="ls")
        atlas.paste(glyph, (x, y))
        metrics[code] = (float(x), float(y), float(glyph.width), float(glyph.height),
                         float(bbox[0]), float(-bbox[1]), float(font.getlength(char)), 0.0)
    new_rows = []
    for row in rows:
        code = replace.get(row[0], row[0])
        if code in metrics:
            new_rows.append((code, 0, 0, *metrics[code], 0))
        else:
            new_rows.append(row)
    if grow:
        new_rows.extend((code, 0, 0, *metrics[code], 0) for code in missing)
    new_rows.sort(key=lambda r: r[0])
    if grow:
        meta, descriptor = serialize_glyphs(data, new_rows)
    else:
        meta = bytearray(data[:tex_start])
        for i, row in enumerate(new_rows):
            RECORD.pack_into(meta, GLYPH_START + i * RECORD.size, *row)
    struct.pack_into("<I", meta, descriptor - 4, new_height)
    struct.pack_into("<I", meta, 0x50, width * new_height)
    result = bytes(meta) + atlas.tobytes()
    verify = inspect(result)
    if required - {r[0] for r in verify[0]}:
        raise ValueError("Font coverage verification failed")
    return result, {"added": len(missing), "redrawn": len(required), "font_weight": weight,
                    "array_grown": grow, "glyphs_before": len(rows), "glyphs_after": len(new_rows),
                    "removed_codes": [] if grow else donors[:len(missing)],
                    "width": width, "height_before": height, "height_after": new_height}
