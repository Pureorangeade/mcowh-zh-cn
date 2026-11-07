"""Build the standalone bilingual editor or import its validated revision file."""
import argparse
import json
from pathlib import Path
import shutil
from datetime import datetime
from editing import base_catalogue, load_edits, validate_edits, load_review_decisions, validate_review_decisions, OVERRIDES
from localization import digest
from release_config import PATCH_VERSION
from resources import PROJECT


def export_editor(output):
    records = base_catalogue()
    edits = load_edits(records)
    from llm_workflow import pending_questions, review_state, final_review_issues
    questions = pending_questions(records)
    pending_ids = {key for q in questions for key in q['entry_ids']}
    for record in records:
        record['review_state'] = review_state(record, edits, pending_ids)
    data = {'version':PATCH_VERSION, 'records':records, 'initial_edits':list(edits.values()),
            'initial_review_decisions':list(load_review_decisions(records).values()),
            'final_review_issues':final_review_issues(records), 'pending_questions':questions,
            'source_fingerprint':digest(''.join(r['id']+r['source_sha256'] for r in records))}
    folder = PROJECT/'tools/editor'
    html = (folder/'template.html').read_text('utf8')
    encoded = json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    for key, value in [('__DATA__',encoded), ('__CORE__',(folder/'core.js').read_text('utf8')),
                       ('__APP__',(folder/'app.js').read_text('utf8'))]:
        html = html.replace(key,value)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(html,encoding='utf8')
    print(f'Bilingual editor: {len(records)} entries, {output.stat().st_size:,} bytes')


def import_revision(path, output=OVERRIDES):
    records = base_catalogue()
    incoming_payload=json.loads(path.read_text('utf-8-sig'))
    incoming = validate_edits(incoming_payload,records)
    incoming_reviews=validate_review_decisions(incoming_payload,records)
    edits = load_edits(records,path=output)
    reviews=load_review_decisions(records,path=output)
    edits.update(incoming)
    reviews.update(incoming_reviews)
    payload = {'schema':1,'project':'mcowh-zh','entries':list(edits.values()),'review_decisions':list(reviews.values())}
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():
        backup=output.with_name(output.stem+'.backup-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
        shutil.copy2(output,backup)
    temp=output.with_suffix('.tmp')
    with temp.open('x',encoding='utf8') as stream:
        json.dump(payload,stream,ensure_ascii=False,indent=2)
    temp.replace(output)
    print(f'Imported {len(incoming)} edits; total {len(edits)}. Game files were not changed.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--import-file',type=Path)
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    if a.import_file:
        import_revision(a.import_file,a.out or OVERRIDES)
    else:
        export_editor(a.out or PROJECT/'editor/汉化译文编辑器.html')
