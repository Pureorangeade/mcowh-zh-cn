"""Render translated native UI text assets at their original dimensions.

This is a deterministic game-asset build step. The Phyre header, format, UV
canvas, and byte length remain unchanged. Only dedicated text textures qualify.
"""
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from localization import digest
from resources import PROJECT
from texture_inventory import decode


def text_for(name, translations):
    relative = name.split('/sc_ui/')[1].removesuffix('.png.phyre')
    folder, basename = relative.rsplit('/', 1)
    if folder == 'ready/class_tx':
        match = re.fullmatch(r'tx_(\d{2})_[bs]', basename)
        return translations['classes'].get(match[1]) if match else None
    if folder == 'ex/class_data':
        match = re.fullmatch(r'tx_grade_(\d)', basename)
        return translations['grades'].get(match[1]) if match else None
    return translations.get(folder, {}).get(basename)


def render(original, name, text, font_path):
    box = original.getbbox()
    if box is None:
        raise ValueError('Cannot place text on an empty source asset')
    x0, y0, x1, y1 = box
    old_width, old_height = x1 - x0, y1 - y0
    # Native title images are scaled by the game. Fit them to a common visual
    # height instead of filling each English word's differently sized bounds.
    title_name = name.rsplit('/', 1)[-1].removesuffix('.png.phyre')
    title_height = None
    if '/title/' in name:
        if title_name in {'tx_start', 'tx_extra', 'tx_option', 'tx_exit'}:
            title_height = 68
        elif title_name in {'tx_new', 'tx_continue', 'tx_vs'}:
            title_height = 48
    height_limit = min(old_height, title_height) if title_height else old_height
    fill, stroke = (255, 255, 255, 255), (40, 35, 30, 255)
    outlined = False
    if '/game_menu/' in name:
        fill, stroke = (23, 19, 112, 255), None
        if '/tx_log.' in name:
            fill, stroke = (255, 255, 255, 255), (40, 35, 30, 255)
        if '/tx_not.' in name:
            fill, stroke = (255, 220, 0, 255), None
    elif '/game_main/' in name or '/result/tx_totalget' in name:
        fill, stroke, outlined = (0, 192, 255, 255), (8, 0, 70, 255), True
    elif '/ready/class_tx/' in name:
        stroke, outlined = (0, 100, 230, 255), True
    elif '/title/' in name or '/common/text/' in name:
        stroke, outlined = (25, 20, 120, 255), True
        if '/tx_new.' in name and '/common/' in name:
            fill, stroke = (255, 235, 0, 255), (0, 0, 0, 255)
        if '/tx_clear.' in name:
            fill, stroke = (0, 255, 255, 255), (0, 0, 0, 255)
        if text.startswith('▶'):
            stroke, outlined = None, False
    elif '/ready/keyboard/' in name:
        fill, stroke = ((150, 230, 250, 255) if '_def.' in name else (23, 19, 112, 255)), None
        if '_off.' in name:
            fill = (170, 170, 170, 255)
    font = None
    for size in range(max(12, int(old_height * 1.6)), 5, -1):
        candidate = ImageFont.truetype(str(font_path), size=size)
        candidate.set_variation_by_axes([600])
        border = max(1, round(size * (0.045 if title_height else 0.065 if outlined else 0.02))) if stroke else 0
        bounds = candidate.getbbox(text, stroke_width=border)
        if bounds[2] - bounds[0] <= old_width and bounds[3] - bounds[1] <= height_limit:
            font = candidate
            break
    if font is None:
        raise ValueError('Translated image text does not fit: ' + name)
    picture = Image.new('RGBA', original.size, (255, 255, 255, 0))
    left = x0 if text.startswith('▶') else (x0 + x1 - bounds[2] + bounds[0]) / 2
    top = (y0 + y1 - bounds[3] + bounds[1]) / 2
    if title_height:
        left = (original.width - bounds[2] + bounds[0]) / 2
        top = (original.height - bounds[3] + bounds[1]) / 2
    ImageDraw.Draw(picture).text((round(left - bounds[0]), round(top - bounds[1])), text, font=font,
                                 fill=fill, stroke_width=border, stroke_fill=stroke)
    new_box = picture.getbbox()
    if not new_box or not (x0 <= new_box[0] and y0 <= new_box[1] and new_box[2] <= x1 and new_box[3] <= y1):
        raise ValueError('Translated image exceeds original ink bounds: ' + name)
    return picture


def main():
    from editing import load_effective_edits
    edits = load_effective_edits()
    folder = PROJECT / 'work/textures'
    translations = json.loads((PROJECT / 'translations/textures.zh-CN.json').read_text('utf8'))
    index = json.loads((folder / 'index.json').read_text('utf8'))
    output = folder / 'translated'
    output.mkdir(exist_ok=True)
    manifest = []
    tiles = []
    for entry in index:
        text = text_for(entry['name'], translations)
        if 'image/' + entry['name'] in edits:
            text = edits['image/' + entry['name']]['translation']
        if not text or not entry['supported']:
            continue
        raw = (folder / f"{entry['id']:03d}.phyre").read_bytes()
        original, start = decode(raw)
        picture = render(original, entry['name'], text, Path('C:/Windows/Fonts/NotoSansSC-VF.ttf'))
        modified = raw[:start] + ImageOps.flip(picture).tobytes()
        if len(modified) != len(raw) or decode(modified)[0].tobytes() != picture.tobytes():
            raise ValueError('Texture byte/size verification failed')
        dest = output / f"{entry['id']:03d}.phyre"
        dest.write_bytes(modified)
        picture.save(output / f"{entry['id']:03d}.png")
        import hashlib
        manifest.append({'name': entry['name'], 'text': text, 'file': dest.name,
            'original_sha256': hashlib.sha256(raw).hexdigest(), 'sha256': hashlib.sha256(modified).hexdigest(),
            'width': original.width, 'height': original.height})
        tile = Image.new('RGB', (260, 100), (40, 45, 60))
        draw = ImageDraw.Draw(tile)
        draw.text((4, 3), f"{entry['id']:03d} {entry['name'].split('/sc_ui/')[1]}", fill='white')
        crop = picture.crop(picture.getbbox())
        crop.thumbnail((250, 75))
        tile.paste(crop, ((260 - crop.width) // 2, 22 + (75 - crop.height) // 2), crop)
        tiles.append(tile)
    for page in range((len(tiles) + 59) // 60):
        sheet = Image.new('RGB', (1560, 1000), (25, 30, 45))
        for offset, tile in enumerate(tiles[page * 60:(page + 1) * 60]):
            sheet.paste(tile, ((offset % 6) * 260, (offset // 6) * 100))
        sheet.save(output / f'contact-{page:02d}.png')
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    print(f'{len(manifest)} translated text textures; dimensions and Phyre metadata preserved')


if __name__ == '__main__':
    main()
