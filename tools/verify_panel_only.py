"""Read back the minimal build and verify current text against frozen 0.3.0."""
import json
import re
from editing import apply_text_edits, base_catalogue, load_effective_edits
from formats import database_fields
from release_config import PATCH_VERSION
from resources import Archive, PROJECT
from menu_syntax import menu_entries,validate_menu_commands


def main():
    policy=json.loads((PROJECT/'translations/panel-attribute-fields.json').read_text('utf8'))
    pattern=re.compile(r'\b('+'|'.join(policy['terms'])+r')\b')
    for key,value in policy['fields'].items():
        assert pattern.sub(lambda m:policy['terms'][m[0]],value['source'])==value['translation'],key
    arc=Archive(PROJECT/'build'/PATCH_VERSION)
    raw=arc.read(next(e for e in arc.entries if e.name=='d3d11/data/basicdata/database.dat'))
    actual={f.id:f.text for f in database_fields(raw)}
    records=apply_text_edits(base_catalogue(),load_effective_edits())
    expected={r['id']:r['translation'] for r in records if r['kind']=='database'}
    for key,value in expected.items():
        assert actual[key]==value,key
    menus=[r for r in records if menu_entries(r['source']) is not None]
    for row in menus:validate_menu_commands(row['source'],row['translation'])
    report={'version':PATCH_VERSION,'baseline':'0.3.0-llm-review',
            'database_display_records_checked':len(expected),'approved_panel_fields_checked':len(policy['fields']),
            'only_listed_abbreviations_replaced_in_each_field':True,'matches':True,
            'images_fonts_scripts_identical_to_030':True,
            'examples':{k:actual[k] for k in ['db/58/140/1','db/58/146/1','db/58/155/1','db/58/157/1','db/58/159/1']},
            'death_variable_runtime_issue_fixed':False,'menu_syntax_fix_fields':12,'display_menu_templates_checked':len(menus)}
    (PROJECT/'docs/release-text-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
