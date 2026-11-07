"""Read Phyre RGBA8 UI textures and create offline contact sheets."""
import json
import argparse
from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageOps
from resources import Archive, GAME, PROJECT


def decode(data):
    size = struct.unpack_from('<I', data, 0x50)[0]
    start = len(data) - size
    descriptor = data.rindex(b'PTexture2D\0', 0, start)
    width, height = struct.unpack_from('<II', data, descriptor - 8)
    if data[descriptor + 11:descriptor + 17] != b'RGBA8\0' or size != width * height * 4:
        raise ValueError('Only single-level RGBA8 textures are supported')
    return ImageOps.flip(Image.frombytes('RGBA', (width, height), data[start:])), start


def main(game):
    arc = Archive(game)
    out = PROJECT / 'work/textures'
    out.mkdir(parents=True, exist_ok=True)
    entries = [e for e in arc.entries if '/sc_ui/' in e.name and Path(e.name).name.startswith('tx_')]
    index = []
    tiles = []
    for entry in entries:
        try:
            data = arc.read(entry)
            picture, start = decode(data)
        except ValueError as error:
            index.append({'name': entry.name, 'supported': False, 'reason': str(error)})
            continue
        identifier = len(tiles)
        path = out / f'{identifier:03d}.png'
        picture.save(path)
        raw = out / f'{identifier:03d}.phyre'
        raw.write_bytes(data)
        index.append({'id': identifier, 'name': entry.name, 'supported': True,
                      'width': picture.width, 'height': picture.height, 'bbox': picture.getbbox()})
        tile = Image.new('RGB', (260, 110), (40, 45, 60))
        label = entry.name.split('/sc_ui/')[1]
        draw = ImageDraw.Draw(tile)
        draw.text((5, 4), f'{identifier:03d} {label}', fill='white')
        box = picture.getbbox()
        if box:
            crop = picture.crop(box)
            crop.thumbnail((250, 82))
            tile.paste(crop, ((260 - crop.width) // 2, 25 + (82 - crop.height) // 2), crop)
        tiles.append(tile)
    for page in range((len(tiles) + 59) // 60):
        sheet = Image.new('RGB', (1560, 1100), (25, 30, 45))
        for offset, tile in enumerate(tiles[page * 60:(page + 1) * 60]):
            sheet.paste(tile, ((offset % 6) * 260, (offset // 6) * 110))
        sheet.save(out / f'contact-{page:02d}.png')
    (out / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf8')
    print(f'UI text textures: {len(index)} inventoried, {len(tiles)} decoded')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, default=PROJECT / 'work/clean-fixture')
    main(parser.parse_args().game)
