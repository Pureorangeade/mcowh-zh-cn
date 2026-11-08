"""Build story and local-string compatibility changes on frozen 0.3.3."""
import copy,hashlib,json
from pathlib import Path
from bundle import metadata
from common_events import parse
from editing import base_catalogue,load_effective_edits
from extract_japanese import read
from fonts import extend,inspect
from formats import database_fields,replace_database
from localization import validate
from menu_syntax import menu_entries,validate_menu_commands
from release_config import PATCH_VERSION
from resources import Archive,PROJECT,rebuild,sha256
from runtime_compat import patch


def main():
    assert PATCH_VERSION=='0.3.4-story-compat'
    pinned=json.loads((PROJECT/'docs/package-verification-0.3.3.json').read_text('utf8'))
    for key in ['player_zip','source_zip']:
        assert sha256(PROJECT/'dist'/pinned[key])==pinned[key+'_sha256']
    frozen=metadata(PROJECT/'dist/MCOWH-zh-CN-0.3.3-menu-fix/patch.mcpatch')
    base=PROJECT/'build/0.3.3-menu-fix'
    for item in frozen['report']['files']:assert sha256(base/item['path'])==item['sha256']
    clean=Archive(PROJECT/'work/clean-fixture');arc=Archive(base)
    for item in frozen['baseline']['files']:assert sha256(PROJECT/'work/clean-fixture'/item['path'])==item['sha256']
    dbname='d3d11/data/basicdata/database.dat';common='d3d11/data/basicdata/commonevent.dat'
    original_db=read(arc,dbname)
    before={f.id:f.text for f in database_fields(original_db)}
    english={f.id:f.text for f in database_fields(read(clean,dbname))}
    batch=json.loads((PROJECT/'translations/llm-batches/0069.json').read_text('utf8'))
    changed={e['id']:e['translation'] for e in batch['entries']}
    assert len(changed)==41 and sum(k.startswith('db/72/') for k in changed)==34
    for entry in batch['entries']:validate(entry['source'],entry['translation'],preserve_linebreaks=False)
    db=replace_database(original_db,{k:v for k,v in changed.items() if k.startswith('db/')})
    # Seven existing dialogue revisions only change the user-approved book name.
    from formats import unpack_scripts,pack_scripts
    from localization import apply_spans
    catalogue=[json.loads(l) for l in (PROJECT/'translations/full.zh-CN.jsonl').read_text('utf8').splitlines()]
    by_id={e['id']:e for e in catalogue}
    script_revisions=[e for e in batch['entries'] if not e['id'].startswith('db/')]
    packname='d3d11/data/event/event.pack';packs=dict(unpack_scripts(read(arc,packname)))
    from collections import defaultdict
    groups=defaultdict(list)
    for entry in script_revisions:
        info=by_id[entry['id']];path=info['script']
        previous=entry['previous_translation']
        assert previous.replace('无双之书','绝伦之书')==entry['translation']
        groups[path].append((previous,entry['translation']))
    for path,revisions in groups.items():
        text=packs[path].decode('utf8')
        for old,new in revisions:
            assert text.count(old)==1,path
            text=text.replace(old,new,1)
        packs[path]=text.encode('utf8')
    scriptpack=pack_scripts(list(packs.items()))
    after={f.id:f.text for f in database_fields(db)}
    dbchanges={k for k in before if before[k]!=after[k]}
    assert dbchanges=={k for k in changed if k.startswith('db/')}
    assert len(dbchanges)==34
    records=base_catalogue();edits=load_effective_edits(records)
    for r in records:
        if r['kind']=='database':
            assert after[r['id']]==edits.get(r['id'],{}).get('translation',r['translation']),r['id']
    for k,v in english.items():
        if menu_entries(v) is not None:validate_menu_commands(v,after[k])
    compat,compat_proof=patch(read(clean,common),english,after)
    (PROJECT/'docs/runtime-compat-proof.json').write_text(json.dumps(compat_proof,ensure_ascii=False,indent=2),encoding='utf8')
    replacements={r['name']:read(arc,r['name']) for r in frozen['report']['changed_resources']}
    replacements.update({dbname:db,packname:scriptpack,common:compat})
    required=set(frozen['report']['required_characters'])|{c for t in changed.values() for c in t if ord(c)>=128}|set('死于')
    font_proof=[]
    for name,data in list(replacements.items()):
        if not name.startswith('d3d11/common/text/'):continue
        rows,_,_,width,height,start,_=inspect(data)
        missing={c for c in required if ord(c) not in {r[0] for r in rows}}
        weight=700 if 'skip-std' in name else 600 if 'seurat-pro-db' in name else 500
        result,proof=extend(data,missing,Path('C:/Windows/Fonts/NotoSansSC-VF.ttf'),weight=weight,grow=True)
        new=inspect(result);newrows={r[0]:r for r in new[0]}
        assert all(newrows[r[0]]==r for r in rows),name
        assert result[new[5]:new[5]+width*height]==data[start:],name
        assert {ord(c) for c in required}<={r[0] for r in new[0]},name
        replacements[name]=result;font_proof.append({'name':name,**proof,'all_existing_glyph_metrics_and_pixels_unchanged':True})
    unchanged=[n for n,raw in replacements.items() if n!=common and raw==read(arc,n)]
    for name,raw in replacements.items():
        dest=PROJECT/'work/replacements'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    out=PROJECT/'build'/PATCH_VERSION;out.mkdir(parents=True,exist_ok=True)
    rebuild(clean,replacements,out)
    from llm_workflow import snapshot
    review=snapshot();report=copy.deepcopy(frozen['report'])
    report.update(version=PATCH_VERSION,stage='story-and-runtime-string-compatibility',baseline_release=frozen['version'],
        catalogue_entries=len(catalogue),database_entries=frozen['report']['database_entries']+34,
        user_edit_count=len(load_effective_edits()),required_characters=''.join(sorted(required)),fonts=font_proof,
        full_game_localization_complete=False,minimal_change_proof='story-0069-diff.json')
    from editing import apply_text_edits
    from collections import Counter
    effective=apply_text_edits(catalogue,edits)
    report['translation_statuses']=dict(Counter(e['status'] for e in effective))
    report['translation_methods']=dict(Counter(e.get('translation_method','retained_english' if e.get('locked') else 'legacy_draft') for e in effective))
    report['review_snapshot'].update(model_entries=review['counts']['llm_translated'],last_translation_batch='0069',
        final_review_entry_count=review['final_review_entry_count'],runtime_followups=['Class badges and historical death display need user in-game confirmation'])
    report['changed_resources']=[{'name':n,'base':n,'sha256':hashlib.sha256(raw).hexdigest()} for n,raw in replacements.items()]
    report['files']=[{'path':p.relative_to(out).as_posix(),'size':p.stat().st_size,'sha256':sha256(p)} for p in sorted((out/'D3D11/Data').glob('*.bin'))]
    (out/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    proof={'version':PATCH_VERSION,'baseline':frozen['version'],'new_story_bodies':sorted(dbchanges),
        'english_story_characters':sum(len(e['source']) for e in batch['entries'] if e['id'].startswith('db/72/')),
        'existing_dialogue_revisions':[{k:e[k] for k in ['id','source','previous_translation','translation']} for e in script_revisions],
        'unchanged_resources':unchanged,'unchanged_resource_count':len(unchanged),'images_unchanged':187,
        'font_extensions':font_proof,'common_event_proof':'runtime-compat-proof.json','actual_game_modified':False,'runtime_verified':False}
    (PROJECT/'docs/story-0069-diff.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'version':PATCH_VERSION,'story_bodies':34,'dialogue_revisions':len(script_revisions),
        'resources':len(replacements),'unchanged_resources':len(unchanged),'fonts':font_proof},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
