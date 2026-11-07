"""Export display candidates and an explicit excluded-field inventory."""
import argparse
from collections import Counter
import json
from pathlib import Path
from formats import database_fields, project_context, unpack_scripts
from localization import database_display, digest, display_candidate, script_spans
from resources import Archive, PROJECT


def export(game, output):
    arc = Archive(game)
    by_name = {e.name: e for e in arc.entries}
    root = 'd3d11/data/basicdata/'
    context = project_context(arc.read(by_name[root + 'database.project']))
    entries, excluded = [], []
    for field in database_fields(arc.read(by_name[root + 'database.dat'])):
        try:
            source = field.text
        except UnicodeDecodeError:
            continue
        if not display_candidate(source):
            continue
        table, row, column = map(int, field.id.split('/')[1:])
        info = context[table]
        label = info['fields'][field.field_index]
        if info['types'][field.field_index] != 0 or not database_display(table, column, label):
            excluded.append({'id': field.id, 'source': source, 'field': label, 'reason': 'internal_or_unconfirmed_field'})
            continue
        entries.append({'id': field.id, 'kind': 'database', 'resource': root + 'database.dat',
            'source': source, 'source_sha256': digest(source), 'translation': '', 'status': 'untranslated',
            'context': {'table_index': table, 'table': info['name'], 'field': label,
                        'row': info['rows'][row] if row < len(info['rows']) else ''}})
    for resource in ['d3d11/data/event/event.pack', 'd3d11/data/uiscript/uiscript.pack']:
        for path, raw in unpack_scripts(arc.read(by_name[resource])):
            try:
                text = raw.decode('utf8')
            except UnicodeDecodeError:
                excluded.append({'script': path, 'resource': resource, 'reason': 'non_utf8_script_preserved'})
                continue
            for kind, index, a, b, source in script_spans(text):
                if not display_candidate(source):
                    continue
                entries.append({'id': f'{kind}/{path}/{index}', 'kind': kind, 'resource': resource,
                    'script': path, 'start': a, 'end': b, 'source': source, 'source_sha256': digest(source),
                    'translation': '', 'status': 'untranslated'})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in entries), encoding='utf8')
    output.with_name('excluded-fields.json').write_text(json.dumps(excluded, ensure_ascii=False, indent=2), encoding='utf8')
    stats = {'entries': len(entries), 'by_kind': dict(Counter(e['kind'] for e in entries)),
             'source_characters': sum(len(e['source']) for e in entries), 'excluded_fields': len(excluded),
             'scope': 'Selected English database display fields, event messages/choices and UI Button labels. Images, executable literals and unconfirmed fields are separate work.'}
    output.with_name('full-catalogue-stats.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game', type=Path, default=PROJECT / 'work/clean-fixture')
    p.add_argument('--out', type=Path, default=PROJECT / 'work/translation/full-catalogue.jsonl')
    a = p.parse_args()
    export(a.game, a.out)
