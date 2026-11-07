"""Package entry-by-entry translations authored in chat; never call a model."""
import argparse
import json
from pathlib import Path
import re
from editing import base_catalogue,load_edits,validate_edits
from llm_workflow import numeric_literals,validate_retained_terms,validate_personal_names,retained_term_issues
from localization import digest
from resources import PROJECT


def prepare(batch, text_path, destination):
    if not re.fullmatch(r'\d{4}',batch):raise ValueError('Batch ID must contain four digits')
    texts=json.loads(text_path.read_text('utf-8-sig'))
    if not isinstance(texts,dict) or not texts:raise ValueError('Expected a nonempty entry-to-translation mapping')
    records=base_catalogue();by_id={r['id']:r for r in records};edits=load_edits(records)
    old={e['id']:e for e in json.loads(destination.read_text('utf8'))['entries']} if destination.exists() else {}
    issues=retained_term_issues()
    entries=[]
    for key,target in texts.items():
        if key not in by_id or not isinstance(target,str):raise ValueError('Unknown entry or invalid text: '+str(key))
        record=by_id[key];previous=edits.get(key,{})
        if numeric_literals(record['source'])!=numeric_literals(target):raise ValueError('Number mismatch: '+key)
        validate_retained_terms(record['source'],target,issues)
        validate_personal_names(record['source'],target)
        entry={'id':key,'source_sha256':record['source_sha256'],'source':record['source'],'translation':target,
            'previous_translation':old.get(key,{}).get('previous_translation',previous.get('translation',record['translation'])),
            'translation_method':'current_online_chat_llm','review_status':'llm_translated','human_reviewed':False,'batch':batch,
            'japanese_check':record['japanese'],
            'provenance':'Authored entry by entry in the current online chat model. English display text and available Japanese context checked; absent Japanese originals explicitly recorded. No separate API or local machine translation model call.'}
        supersedes=old.get(key,{}).get('supersedes_batch') or previous.get('batch')
        if supersedes and supersedes!=batch:entry['supersedes_batch']=supersedes
        entries.append(entry)
    payload={'schema':1,'project':'mcowh-zh','batch':batch,'authored_text_sha256':digest(text_path.read_text('utf-8-sig')),'entries':entries}
    validate_edits(payload,records)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'prepared':len(entries),'new_entries':sum(e['id'] not in edits for e in entries),
                      'revised_entries':sum(e['id'] in edits for e in entries)},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('batch');p.add_argument('--text',type=Path);p.add_argument('--out',type=Path)
    a=p.parse_args();folder=PROJECT/'translations/llm-batches'
    prepare(a.batch,a.text or folder/f'{a.batch}-text.json',a.out or folder/f'{a.batch}.json')
