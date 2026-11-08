"""Build the broad text draft from original resources; never installs it."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from formats import database_fields, pack_scripts, replace_database, unpack_scripts, pack_text_dictionary, unpack_text_dictionary
from fonts import extend
from localization import apply_spans, digest, validate
from release_config import PATCH_VERSION
from resources import Archive, PROJECT, rebuild, sha256
from editing import load_effective_edits, apply_text_edits


def build(game, out, translation, font):
    game, out = game.resolve(), out.resolve()
    if out == game or game.is_relative_to(out):
        raise ValueError('Output must be separate from original game files')
    entries = [json.loads(line) for line in translation.read_text('utf8').splitlines()]
    edits = load_effective_edits()
    entries = apply_text_edits(entries, edits)
    if len({e['id'] for e in entries}) != len(entries):
        raise ValueError('Duplicate translation IDs')
    baseline = json.loads((PROJECT / 'work/baseline.json').read_text('utf8'))
    pinned = {f['path']: f for f in baseline['files']}
    for name in ['MC_OneWayHeroics.exe', 'D3D11/Data/archive.bin']:
        if sha256(game / name) != pinned[name]['sha256']:
            raise ValueError('Modified or unsupported original: ' + name)
    arc = Archive(game)
    by_name = {e.name: e for e in arc.entries}
    by_resource = defaultdict(list)
    for entry in entries:
        if entry['status'] == 'untranslated' or not entry['translation']:
            raise ValueError('Empty/untranslated catalogue entry')
        if digest(entry['source']) != entry['source_sha256']:
            raise ValueError('Translation source hash differs')
        validate(entry['source'], entry['translation'], single_argument=entry['kind'] == 'choice',
                 preserve_linebreaks=entry['status'] != 'curated')
        by_resource[entry['resource']].append(entry)
    replacements = {}
    for name, rows in by_resource.items():
        raw = arc.read(by_name[name])
        if name.endswith('database.dat'):
            originals = {f.id: f.text for f in database_fields(raw)}
            for e in rows:
                if originals.get(e['id']) != e['source']:
                    raise ValueError('Original database string changed: ' + e['id'])
            replacements[name] = replace_database(raw, {e['id']: e['translation'] for e in rows})
        elif name.endswith('.pack'):
            scripts = defaultdict(list)
            for e in rows:
                scripts[e['script']].append(e)
            records = unpack_scripts(raw)
            output = []
            for path, data in records:
                if path in scripts:
                    data = apply_spans(data.decode('utf8'), scripts.pop(path)).encode('utf8')
                output.append((path, data))
            if scripts:
                raise ValueError('Unknown translated scripts')
            encoded = pack_scripts(output)
            if unpack_scripts(encoded) != output:
                raise ValueError('Script round-trip failed')
            replacements[name] = encoded
        else:
            raise ValueError('Unapproved translation resource: ' + name)
    system = json.loads((PROJECT / 'translations/system.zh-CN.json').read_text('utf8'))
    for filename, changes in system.items():
        for key in changes:
            item = edits.get(f'system/{filename}/{key}')
            if item:
                changes[key] = item['translation']
    for filename, changes in system.items():
        name = 'd3d11/data/' + ('basicdata/' if filename == 'cdatabase.dat' else '') + filename
        raw = arc.read(by_name[name])
        if filename == 'cdatabase.dat':
            replacements[name] = replace_database(raw, changes)
        else:
            records = unpack_text_dictionary(raw)
            if changes.keys() - {k for k, _ in records}:
                raise ValueError('Unknown system dictionary keys')
            output = [(key, changes.get(key, value)) for key, value in records]
            for (key, source), (_, target) in zip(records, output, strict=True):
                validate(source, target, preserve_linebreaks=False)
            replacements[name] = pack_text_dictionary(output)
    texture_folder = PROJECT / 'work/textures/translated'
    texture_manifest = texture_folder / 'manifest.json'
    textures = json.loads(texture_manifest.read_text('utf8')) if texture_manifest.exists() else []
    for texture in textures:
        name = texture['name']
        edit = edits.get('image/' + name)
        if edit and edit['translation'] != texture['text']:
            raise ValueError('图片译文已修改，请先运行 render_textures.py：' + name)
        original = arc.read(by_name[name])
        data = (texture_folder / texture['file']).read_bytes()
        if hashlib.sha256(original).hexdigest() != texture['original_sha256'] or hashlib.sha256(data).hexdigest() != texture['sha256']:
            raise ValueError('Text texture input hash differs: ' + name)
        replacements[name] = data
    chars = set(''.join(e['translation'] for e in entries))
    chars.update(''.join(t for changes in system.values() for t in changes.values()))
    fonts = []
    for entry in arc.entries:
        if entry.name.startswith('d3d11/common/text/'):
            weight = 700 if 'skip-std' in entry.name else 600 if 'seurat-pro-db' in entry.name else 500
            data, report = extend(arc.read(entry), chars, font, weight=weight, grow=True)
            replacements[entry.name] = data
            fonts.append({'name': entry.name, 'base': entry.name, **report})
            print(f"Font {entry.name}: {report['glyphs_before']} -> {report['glyphs_after']} glyphs", flush=True)
    for group in {by_name[n].group for n in replacements}:
        path = 'D3D11/Data/' + arc.groups[group]['name']
        if sha256(game / path) != pinned[path]['sha256']:
            raise ValueError('Modified source data: ' + path)
    out.mkdir(parents=True, exist_ok=True)
    rebuild(arc, replacements, out)
    for name, data in replacements.items():
        dest = PROJECT / 'work/replacements' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    kinds = Counter(e['kind'] for e in entries)
    states = Counter(e['status'] for e in entries)
    from llm_workflow import snapshot
    review = snapshot()
    if any(review['counts'].get(k,0) for k in ['awaiting_user','awaiting_retranslation']):
        raise ValueError('Release requires ordinary translation and unanswered queues to be empty')
    report = {'version': PATCH_VERSION, 'stage': 'llm-retranslation-review', 'steam_build_id': '1527978',
        'catalogue_entries': len(entries), 'translation_statuses': dict(states), 'by_kind': dict(kinds),
        'user_edit_count': len(edits),
        'translation_methods':dict(Counter(e.get('translation_method','retained_english' if e.get('locked') else 'legacy_draft') for e in entries)),
        'system_dictionary_entries': sum(len(c) for k, c in system.items() if k != 'cdatabase.dat'),
        'runtime_default_entries': len(system['cdatabase.dat']),
        'database_entries': kinds['database'], 'event_scripts': len({e.get('script') for e in entries if e['kind'] == 'message'}),
        'event_message_blocks': kinds['message'], 'event_choices': kinds['choice'], 'ui_button_labels': kinds['button'],
        'image_textures': len(textures), 'image_text_entries': textures,
        'fonts': fonts, 'required_characters': ''.join(sorted(c for c in chars if ord(c) >= 128)),
        'changed_resources': [{'name': n, 'base': n, 'sha256': hashlib.sha256(d).hexdigest()} for n, d in replacements.items()],
        'files': [{'path': p.relative_to(out).as_posix(), 'size': p.stat().st_size, 'sha256': sha256(p)}
                  for p in sorted((out / 'D3D11/Data').glob('*.bin'))],
        'full_game_localization_complete': False,
        'review_snapshot':{'model_entries':review['counts'].get('llm_translated',0),'retained_original':review['counts'].get('retained_original',0),
                           'retained_english':review['counts'].get('retained_english',0),'retained_commands':review['counts'].get('retained_command',0),
                           'final_review_issue_count':review['final_review_issue_count'],'final_review_entry_count':review['final_review_entry_count'],
                           'last_translation_batch':max(review['llm_batches']),'personal_names':'temporarily English','panel_labels':'see source-bound panel-attribute-fields.json',
                           'runtime_followups':['startup $dead may retain English; unresolved'], 'gameplay_review_numbers':['F18','F19','F20','F21']},
        'remaining_scope': ['final semantic review of chat-model translations', 'deferred English/Japanese gameplay differences F18-F21',
                            'temporary English personal names', 'remaining image text and logo', 'executable literals',
                            'excluded/unconfirmed fields', 'runtime layout and progression validation']}
    (out / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'version': PATCH_VERSION, 'entries': len(entries), 'by_kind': dict(kinds),
                      'required_non_ascii_characters': len(report['required_characters']),
                      'rebuilt_resources': len(replacements)}, ensure_ascii=False), flush=True)
    return report


if __name__ == '__main__':
    if PATCH_VERSION in {'0.3.2-panel-only','0.3.3-menu-fix'}:
        raise SystemExit('Use the dedicated frozen-release builder: build_panel_only.py for 0.3.2 or build_menu_fix.py for 0.3.3.')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game', type=Path, default=PROJECT / 'work/clean-fixture')
    p.add_argument('--out', type=Path, default=PROJECT / 'build' / PATCH_VERSION)
    p.add_argument('--translation', type=Path, default=PROJECT / 'translations/full.zh-CN.jsonl')
    p.add_argument('--font', type=Path, default=Path('C:/Windows/Fonts/NotoSansSC-VF.ttf'))
    a = p.parse_args()
    build(a.game, a.out, a.translation, a.font)
