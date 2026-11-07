"""Strict, lossless readers for the specific formats found in Steam build 1527978."""
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class StringField:
    id: str
    start: int
    end: int
    raw: bytes
    field_index: int = -1

    @property
    def text(self):
        return self.raw.decode("utf-8")


def database_fields(data: bytes) -> list[StringField]:
    magic = b"\x00W\x00\x00OL\x00FM\x00\xc1"
    if not data.startswith(magic):
        raise ValueError("Unsupported WOLF database")
    pos = len(magic)

    def integer():
        nonlocal pos
        if pos + 4 > len(data):
            raise ValueError("Truncated database integer")
        value = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        return value

    count = integer()
    if count > 1000:
        raise ValueError("Invalid database type count")
    result = []
    for table in range(count):
        if integer() != 0xFFFFFFFE:
            raise ValueError(f"Missing type separator: {table}")
        integer()  # preserved unknown type attribute
        num_fields = integer()
        if num_fields > 10000:
            raise ValueError("Invalid field count")
        fields = [integer() for _ in range(num_fields)]
        rows = integer()
        if rows > 100000:
            raise ValueError("Invalid row count")
        int_count = sum(f < 2000 for f in fields)
        str_count = num_fields - int_count
        # File values are serialized by numeric/string storage index, not GUI order.
        for row in range(rows):
            pos += 4 * int_count
            if pos > len(data):
                raise ValueError("Truncated integer array")
            for column in range(str_count):
                start = pos
                length = integer()
                if length < 1 or pos + length > len(data):
                    raise ValueError("Invalid string extent")
                raw = data[pos:pos + length]
                if raw[-1:] != b"\0":
                    raise ValueError(f"Missing string terminator: {table}/{row}/{column}")
                pos += length
                result.append(StringField(f"db/{table}/{row}/{column}", start, pos, raw[:-1], fields.index(2000 + column)))
    if data[pos:] != b"\xc1":
        raise ValueError("Unexpected database trailer")
    return result


def project_context(data: bytes) -> list[dict]:
    """Read editor metadata for context only; never rewrite it for translation."""
    pos = 0

    def integer():
        nonlocal pos
        value = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        return value

    def string():
        nonlocal pos
        size = integer()
        if size < 1 or pos + size > len(data) or data[pos + size - 1] != 0:
            raise ValueError("Invalid project string")
        value = data[pos:pos + size - 1].decode("utf8", errors="replace")
        pos += size
        return value

    count = integer()
    if count > 1000:
        raise ValueError("Invalid project type count")
    result = []
    for _ in range(count):
        name = string()
        fields = [string() for _ in range(integer())]
        rows = [string() for _ in range(integer())]
        description = string()
        size = integer()
        types = list(data[pos:pos + size])
        pos += size
        for _ in range(integer()):
            string()
        for _ in range(integer()):
            for _ in range(integer()):
                string()
        for _ in range(integer()):
            for _ in range(integer()):
                integer()
        for _ in range(integer()):
            integer()
        result.append(dict(name=name, fields=fields, rows=rows, description=description, types=types))
    if pos != len(data):
        raise ValueError("Unexpected project trailer")
    return result


def replace_database(data: bytes, translations: dict[str, str]) -> bytes:
    fields = database_fields(data)
    ids = {f.id for f in fields}
    if translations.keys() - ids:
        raise ValueError("Unknown database translation IDs")
    pieces = []
    previous = 0
    for field in fields:
        if field.id not in translations:
            continue
        raw = translations[field.id].encode("utf-8")
        if b"\0" in raw:
            raise ValueError("NUL inside translation")
        pieces += [data[previous:field.start], struct.pack("<I", len(raw) + 1), raw, b"\0"]
        previous = field.end
    pieces.append(data[previous:])
    result = b"".join(pieces)
    check = database_fields(result)
    for old, new in zip(fields, check, strict=True):
        expected = translations[old.id].encode("utf-8") if old.id in translations else old.raw
        if new.raw != expected:
            raise ValueError(f"Database round-trip mismatch: {old.id}")
    return result


def unpack_scripts(data: bytes) -> list[tuple[str, bytes]]:
    if data[:4] != b"PACK":
        raise ValueError("Invalid script pack")
    count, pos = struct.unpack_from("<II", data, 4)
    if pos != 16 or count > 100000:
        raise ValueError("Unsupported script pack header")
    first = struct.unpack_from("<I", data, 12)[0]
    records = []
    for _ in range(count):
        length = struct.unpack_from("<I", data, pos)[0]
        if length < 2 or pos + length + 8 > len(data):
            raise ValueError("Invalid script name extent")
        raw_name = data[pos + 4:pos + 4 + length]
        if raw_name[-1:] != b"\0":
            raise ValueError("Invalid script name terminator")
        name = raw_name[:-1].decode("ascii")
        if not name.startswith("data/") or ".." in name or "\\" in name:
            raise ValueError("Unsafe script path")
        offset = struct.unpack_from("<I", data, pos + length + 4)[0]
        records.append((name, offset))
        pos += length + 8
    if pos != first:
        raise ValueError("Invalid pack table extent")
    result = []
    for name, offset in records:
        if pos != offset:
            raise ValueError("Non-contiguous script content")
        length = struct.unpack_from("<I", data, offset)[0]
        pos = offset + 4 + length
        if pos > len(data):
            raise ValueError("Truncated script")
        result.append((name, data[offset + 4:pos]))
    if pos != len(data):
        raise ValueError("Unexpected pack trailer")
    return result


def pack_scripts(records: list[tuple[str, bytes]]) -> bytes:
    names = [name.encode("ascii") + b"\0" for name, _ in records]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate script paths")
    offset = 16 + sum(8 + len(name) for name in names)
    table = [b"PACK", struct.pack("<III", len(records), 16, offset)]
    bodies = []
    for name, (_, data) in zip(names, records, strict=True):
        table += [struct.pack("<I", len(name)), name, struct.pack("<I", offset)]
        bodies += [struct.pack("<I", len(data)), data]
        offset += 4 + len(data)
    return b"".join(table + bodies)


def unpack_text_dictionary(data: bytes) -> list[tuple[str, str]]:
    if data[:4] != b'TEXT' or len(data) < 8:
        raise ValueError('Invalid TEXT dictionary')
    count = struct.unpack_from('<I', data, 4)[0]
    if count > 10000:
        raise ValueError('Invalid TEXT dictionary count')
    pos = 8
    records = []
    for _ in range(count):
        values = []
        for _ in range(2):
            if pos + 4 > len(data):
                raise ValueError('Truncated TEXT dictionary')
            size = struct.unpack_from('<I', data, pos)[0]
            pos += 4
            if size > len(data) - pos:
                raise ValueError('Invalid TEXT string size')
            values.append(data[pos:pos + size].decode('utf8'))
            pos += size
        records.append(tuple(values))
    if pos != len(data) or len({k for k, _ in records}) != len(records):
        raise ValueError('Unexpected TEXT dictionary trailer or duplicate key')
    return records


def pack_text_dictionary(records: list[tuple[str, str]]) -> bytes:
    data = bytearray(b'TEXT' + struct.pack('<I', len(records)))
    for record in records:
        for text in record:
            raw = text.encode('utf8')
            data.extend(struct.pack('<I', len(raw)))
            data.extend(raw)
    result = bytes(data)
    if unpack_text_dictionary(result) != records:
        raise ValueError('TEXT dictionary round-trip failed')
    return result
