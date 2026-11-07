"""Source-verified binary copy/literal deltas for local resource reconstruction."""
import hashlib
import struct
import zlib


def create(source: bytes, target: bytes, block=1024) -> bytes:
    table = {}
    for pos in range(0, len(source) - block + 1, block):
        table.setdefault(hashlib.blake2b(source[pos:pos + block], digest_size=8).digest(), []).append(pos)
    operations = []
    literals = bytearray()
    pos = 0
    while pos < len(target):
        match = None
        if pos + block <= len(target):
            part = target[pos:pos + block]
            for candidate in table.get(hashlib.blake2b(part, digest_size=8).digest(), ()):
                if source[candidate:candidate + block] == part:
                    match = candidate
                    break
        if match is None:
            literals.append(target[pos])
            pos += 1
            continue
        if literals:
            operations.append((0, bytes(literals)))
            literals.clear()
        length = block
        while (pos + length + block <= len(target) and match + length + block <= len(source)
               and target[pos + length:pos + length + block] == source[match + length:match + length + block]):
            length += block
        operations.append((1, match, length))
        pos += length
    if literals:
        operations.append((0, bytes(literals)))
    output = bytearray(b"MCD1" + hashlib.sha256(source).digest() + hashlib.sha256(target).digest())
    output += struct.pack("<QI", len(target), len(operations))
    for op in operations:
        output.append(op[0])
        if op[0] == 0:
            output += struct.pack("<I", len(op[1])) + op[1]
        else:
            output += struct.pack("<II", op[1], op[2])
    return zlib.compress(output, 9)


def apply(source: bytes, patch: bytes) -> bytes:
    decoder = zlib.decompressobj()
    data = decoder.decompress(patch, 128 * 1024 * 1024)
    if not decoder.eof or decoder.unused_data or len(data) < 80 or data[:4] != b"MCD1":
        raise ValueError("Invalid or oversized delta")
    if hashlib.sha256(source).digest() != data[4:36]:
        raise ValueError("Delta source hash mismatch")
    size, count = struct.unpack_from("<QI", data, 68)
    if size > 128 * 1024 * 1024 or count > 1000000:
        raise ValueError("Invalid delta output size")
    pos = 80
    output = bytearray()
    for _ in range(count):
        if pos >= len(data):
            raise ValueError("Truncated delta")
        opcode = data[pos]
        pos += 1
        if opcode == 0:
            length = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            if pos + length > len(data):
                raise ValueError("Truncated literal")
            output += data[pos:pos + length]
            pos += length
        elif opcode == 1:
            offset, length = struct.unpack_from("<II", data, pos)
            pos += 8
            if offset + length > len(source):
                raise ValueError("Copy outside delta source")
            output += source[offset:offset + length]
        else:
            raise ValueError("Invalid delta opcode")
        if len(output) > size:
            raise ValueError("Delta exceeds expected output")
    if pos != len(data) or len(output) != size or hashlib.sha256(output).digest() != data[36:68]:
        raise ValueError("Delta output verification failed")
    return bytes(output)
