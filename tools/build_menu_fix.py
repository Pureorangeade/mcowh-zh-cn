"""Restore twelve menu action suffixes on frozen 0.3.2, preserving other assets."""
import copy
import hashlib
import json
from bundle import metadata
from formats import database_fields,replace_database
from menu_syntax import menu_entries,validate_menu_commands
from release_config import PATCH_VERSION
from resources import Archive,PROJECT,rebuild,sha256
from editing import base_catalogue,load_effective_edits,apply_text_edits


def main():
    if PATCH_VERSION!='0.3.3-menu-fix':raise ValueError('Builder is pinned to 0.3.3-menu-fix')
    pinned=json.loads((PROJECT/'docs/package-verification-0.3.2.json').read_text('utf8'))
    for key in ['player_zip','source_zip']:
        assert sha256(PROJECT/'dist'/pinned[key])==pinned[key+'_sha256']
    frozen=metadata(PROJECT/'dist/MCOWH-zh-CN-0.3.2-panel-only/patch.mcpatch')
    base=PROJECT/'build/0.3.2-panel-only'
    for item in frozen['report']['files']:
        assert sha256(base/item['path'])==item['sha256'],item['path']
    arc=Archive(base);index={e.name:e for e in arc.entries}
    clean=Archive(PROJECT/'work/clean-fixture');clean_index={e.name:e for e in clean.entries}
    for item in frozen['baseline']['files']:
        assert sha256(PROJECT/'work/clean-fixture'/item['path'])==item['sha256'],item['path']
    policy=json.loads((PROJECT/'translations/menu-command-fields.json').read_text('utf8'))
    fields=policy['fields'];assert len(fields)==12
    dbname='d3d11/data/basicdata/database.dat'
    original=arc.read(index[dbname])
    before={f.id:f.text for f in database_fields(original)}
    english={f.id:f.text for f in database_fields(clean.read(clean_index[dbname]))}
    for key,fix in fields.items():
        assert english[key]==fix['source'] and hashlib.sha256(english[key].encode()).hexdigest()==fix['source_sha256'],key
        assert before[key]==fix['baseline_032_translation'],key
        validate_menu_commands(english[key],fix['translation'])
    modified=replace_database(original,{k:v['translation'] for k,v in fields.items()})
    after={f.id:f.text for f in database_fields(modified)}
    changes={k:{'before':before[k],'after':after[k]} for k in before if before[k]!=after[k]}
    assert set(changes)==set(fields) and before.keys()==after.keys()
    all_menu_ids=[]
    for key,source in english.items():
        if menu_entries(source) is not None:
            validate_menu_commands(source,after[key]);all_menu_ids.append(key)
    records=apply_text_edits(base_catalogue(),load_effective_edits())
    display_menus=[r for r in records if menu_entries(r['source']) is not None]
    assert len(display_menus)==18
    for row in display_menus:validate_menu_commands(row['source'],row['translation'])
    for row in records:
        if row['kind']=='database':assert after[row['id']]==row['translation'],row['id']
    replacements={};unchanged=[]
    for entry in frozen['report']['changed_resources']:
        name=entry['name'];raw=arc.read(index[name])
        assert hashlib.sha256(raw).hexdigest()==entry['sha256'],name
        if name==dbname:raw=modified
        else:unchanged.append(name)
        replacements[name]=raw
        dest=PROJECT/'work/replacements'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    assert len(unchanged)==200
    out=PROJECT/'build'/PATCH_VERSION;out.mkdir(parents=True,exist_ok=True)
    rebuild(clean,replacements,out)
    proof={'version':PATCH_VERSION,'baseline':frozen['version'],'changed_database_fields':changes,
           'changed_field_count':12,'unchanged_database_fields':len(before)-12,
           'all_database_menu_rows_checked':all_menu_ids,'display_menu_templates_checked':len(display_menus),
           'unchanged_resource_count':len(unchanged),'unchanged_resources':unchanged,
           'images_fonts_scripts_identical_to_032':True,'actual_game_modified':False,'runtime_display_verified':False}
    (PROJECT/'docs/menu-0068-diff.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
    report=copy.deepcopy(frozen['report'])
    report.update(version=PATCH_VERSION,stage='menu-action-syntax-fix',baseline_release=frozen['version'],
                  minimal_change_proof='menu-0068-diff.json')
    report['review_snapshot'].update(last_translation_batch='0068',menu_syntax_fix_fields=12)
    report['changed_resources']=[{**r,'sha256':hashlib.sha256(replacements[r['name']]).hexdigest()} for r in report['changed_resources']]
    report['files']=[{'path':p.relative_to(out).as_posix(),'size':p.stat().st_size,'sha256':sha256(p)} for p in sorted((out/'D3D11/Data').glob('*.bin'))]
    (out/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'version':PATCH_VERSION,'changed_fields':12,'unchanged_resources':200,
                      'all_database_menu_rows_checked':len(all_menu_ids),'display_menu_templates':18},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
