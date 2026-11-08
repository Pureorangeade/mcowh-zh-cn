"""Rebase the approved 19 panel terms on frozen release 0.3.0 assets."""
import hashlib
import json
from bundle import metadata
from formats import database_fields, replace_database
from llm_workflow import snapshot
from release_config import PATCH_VERSION
from resources import Archive, PROJECT, rebuild, sha256


def main():
    if PATCH_VERSION!='0.3.2-panel-only':
        raise ValueError('Use build_menu_fix.py for the current release; this builder is frozen to 0.3.2.')
    pinned = json.loads((PROJECT/'docs/package-verification-0.3.0.json').read_text('utf8'))
    for key in ['player_zip', 'source_zip']:
        assert sha256(PROJECT/'dist'/pinned[key]) == pinned[key+'_sha256']
    frozen = metadata(PROJECT/'dist/MCOWH-zh-CN-0.3.0-llm-review/patch.mcpatch')
    base = PROJECT/'build/0.3.0-llm-review'
    for item in frozen['report']['files']:
        assert sha256(base/item['path']) == item['sha256'], item['path']
    arc = Archive(base)
    index = {e.name:e for e in arc.entries}
    policy = json.loads((PROJECT/'translations/panel-attribute-fields.json').read_text('utf8'))
    fields = policy['fields']
    assert len(policy['terms']) == 19 and len(fields) == 29
    dbname = 'd3d11/data/basicdata/database.dat'
    original = arc.read(index[dbname])
    before = {f.id:f.text for f in database_fields(original)}
    for key, value in fields.items():
        assert before[key] == value['source'], key
        assert hashlib.sha256(value['source'].encode()).hexdigest() == value['source_sha256']
    modified = replace_database(original, {k:v['translation'] for k,v in fields.items()})
    after = {f.id:f.text for f in database_fields(modified)}
    changes = {k:{'before':before[k], 'after':after[k]} for k in before if before[k] != after[k]}
    assert set(changes) == set(fields) and before.keys() == after.keys()
    assert set(c for v in fields.values() for c in v['translation'] if ord(c)>=128) <= set(frozen['report']['required_characters'])
    replacements = {}
    report = frozen['report']
    unchanged = []
    for resource in report['changed_resources']:
        name = resource['name']
        raw = arc.read(index[name])
        assert hashlib.sha256(raw).hexdigest() == resource['sha256'], name
        if name == dbname:
            raw = modified
        else:
            unchanged.append(name)
        replacements[name] = raw
        dest = PROJECT/'work/replacements'/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    assert len(unchanged) == 200
    out = PROJECT/'build'/PATCH_VERSION
    out.mkdir(parents=True, exist_ok=True)
    rebuild(Archive(PROJECT/'work/clean-fixture'), replacements, out)
    proof = {'version':PATCH_VERSION, 'baseline':frozen['version'], 'approved_terms':policy['terms'],
             'changed_database_fields':changes, 'changed_field_count':len(changes),
             'unchanged_database_fields':len(before)-len(changes),
             'unchanged_resource_count':len(unchanged), 'unchanged_resources':unchanged,
             'images_fonts_and_scripts_identical_to_030':True, 'actual_game_modified':False}
    (PROJECT/'docs/panel-only-0067-diff.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
    review = snapshot()
    report.update(version=PATCH_VERSION, stage='panel-only-from-0.3.0', user_edit_count=12091,
                  baseline_release='0.3.0-llm-review', minimal_change_proof='panel-only-0067-diff.json')
    report['translation_methods']['current_online_chat_llm'] += 29
    report['translation_methods']['retained_english'] -= 29
    report['translation_statuses']['curated'] += 29
    report['translation_statuses']['retained_abbreviation'] -= 29
    report['review_snapshot'].update(model_entries=12084, retained_english=50, last_translation_batch='0067',
                                    panel_labels='19 user-confirmed terms; 29 database fields only')
    assert review['counts']['llm_translated']==12084
    report['changed_resources'] = [{**r,'sha256':hashlib.sha256(replacements[r['name']]).hexdigest()} for r in report['changed_resources']]
    report['files'] = [{'path':p.relative_to(out).as_posix(),'size':p.stat().st_size,'sha256':sha256(p)} for p in sorted((out/'D3D11/Data').glob('*.bin'))]
    (out/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'version':PATCH_VERSION,'changed_fields':29,'unchanged_resources':200,'resources':len(replacements)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
