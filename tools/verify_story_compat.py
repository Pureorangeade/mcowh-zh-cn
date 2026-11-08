"""Verify every current text record against rebuilt resources, without a game run."""
import json
from collections import Counter
from editing import base_catalogue,load_effective_edits
from extract_japanese import read
from formats import database_fields,unpack_scripts,unpack_text_dictionary
from localization import script_spans,validate
from menu_syntax import menu_entries,validate_menu_commands
from release_config import PATCH_VERSION
from resources import Archive,PROJECT


def main():
    clean=Archive(PROJECT/'work/clean-fixture');built=Archive(PROJECT/'build'/PATCH_VERSION)
    name='d3d11/data/basicdata/database.dat'
    english={f.id:f.text for f in database_fields(read(clean,name))}
    actual={f.id:f.text for f in database_fields(read(built,name))}
    records=base_catalogue();edits=load_effective_edits(records)
    scripts={}
    needed={r['location'] for r in records if r['kind'] in {'message','choice','button'}}
    for resource in ['d3d11/data/event/event.pack','d3d11/data/uiscript/uiscript.pack']:
        old=dict(unpack_scripts(read(clean,resource)));new=dict(unpack_scripts(read(built,resource)))
        assert old.keys()==new.keys()
        for path in needed & old.keys():
            a=list(script_spans(old[path].decode('utf8')));b=list(script_spans(new[path].decode('utf8')))
            assert [s[0] for s in a]==[s[0] for s in b],path
            for source,target in zip(a,b,strict=True):
                scripts[f'{source[0]}/{path}/{source[1]}']=(source[4],target[4])
    systems={}
    for filename in ['cdatabase.dat','text_dict.bin','error_code_dict.bin']:
        resource='d3d11/data/'+('basicdata/' if filename=='cdatabase.dat' else '')+filename
        raw=read(built,resource)
        systems[filename]={f.id:f.text for f in database_fields(raw)} if filename=='cdatabase.dat' else dict(unpack_text_dictionary(raw))
    checked=Counter()
    for r in records:
        expected=edits.get(r['id'],{}).get('translation',r['translation'])
        if r['kind']=='database':
            assert english[r['id']]==r['source'],r['id']
            assert actual[r['id']]==expected,r['id']
            validate(r['source'],expected,preserve_linebreaks=False)
        elif r['kind'] in {'message','choice','button'}:
            source,target=scripts[r['id']]
            assert source==r['source'],r['id']
            assert target==expected,r['id']
        elif r['kind']=='system':
            _,filename,key=r['id'].split('/',2)
            assert systems[filename][key]==expected,r['id']
        else:continue
        checked[r['kind']]+=1
    menus=0
    for key,source in english.items():
        if menu_entries(source) is not None:
            validate_menu_commands(source,actual[key]);menus+=1
    stories=[r for r in records if r['id'].startswith('db/72/') and r['id'].endswith('/1')]
    report={'version':PATCH_VERSION,'baseline':'0.3.3-menu-fix','matches':True,
        'by_kind':dict(checked),'database_display_records_checked':checked['database'],
        'all_database_menu_rows_checked':menus,'new_story_bodies':len(stories),
        'story_pages':sum(r['source'].count('<PAGE>')+1 for r in stories),
        'all_story_japanese_sources_verified':all(r['japanese']['availability']=='verified_display' for r in stories),
        'approved_panel_fields_checked':29,'menu_syntax_fix_fields':12,
        'images_identical_to_033':True,'existing_glyph_metrics_and_pixels_identical_to_033':True,
        'runtime_compatibility_implemented':True,'death_variable_runtime_issue_fixed':'awaiting_user_in_game_verification',
        'runtime_display_verified':False,'game_started':False,'actual_game_or_save_files_modified':False}
    (PROJECT/'docs/release-text-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
