"""Track direct chat-model translation separately from inherited MT drafts.

No model/API is called by this utility. Translations are authored in the online
conversation, then imported with source hashes and explicit provenance.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from editing import base_catalogue, load_edits, validate_edits, load_review_decisions
from editor_data import import_revision
from resources import PROJECT
from localization import controls

POLICY = PROJECT/'translations/translation-workflow.json'


def pending_questions(records=None):
    questions=[dict(q) for q in json.loads(POLICY.read_text('utf8'))['questions'] if q['status']=='awaiting_user']
    tracked=[]
    for question in questions:
        terms=list(question.get('tracked_terms',[]))
        if question.get('scope')=='term' and question.get('term'):
            terms.append(question['term'])
        if terms:tracked.append((question,terms))
    if tracked:
        records=base_catalogue() if records is None else records
        for question,terms in tracked:
            pattern=r'(?<![A-Za-z])(?:'+'|'.join(re.escape(term) for term in terms)+r')(?![A-Za-z])'
            matching=[r['id'] for r in records if re.search(pattern,r['source'],re.I)]
            question['entry_ids']=list(dict.fromkeys(question.get('entry_ids',[])+matching))
    return questions


def final_review_issues(records=None):
    records=records or base_catalogue()
    questions=[dict(q) for q in json.loads(POLICY.read_text('utf8'))['questions'] if q['status']=='deferred_final']
    for question in questions:
        if question.get('scope')=='source_difference':
            by_id={r['id']:r for r in records}
            bindings=question.get('source_sha256s',{})
            question['entry_ids']=[key for key in question['entry_ids'] if key in by_id]
            for key in question['entry_ids']:
                if bindings.get(key)!=by_id[key]['source_sha256']:
                    raise ValueError('Stale bilingual review decision: '+key)
            continue
        # Term issues cover future occurrences too; they do not block translation of the rest of a sentence.
        term=question.get('term','')
        question['entry_ids']=[r['id'] for r in records if term and re.search(r'(?<![A-Za-z])'+re.escape(term)+r'(?![A-Za-z])',r['source'],re.I)]
    for decision in load_review_decisions(records).values():
        if decision['status']=='deferred_final':
            questions.append({**decision,'entry_ids':[decision['id']],'question':decision['reason']})
    return questions


def review_state(record, edits, pending_ids):
    if record.get('internal_command'):
        return 'retained_command'
    if record.get('locked'):
        return 'retained_english'
    if record['id'] in pending_ids:
        return 'awaiting_user'
    edit=edits.get(record['id'])
    if edit and edit.get('translation_method')=='user_confirmed_retention' and edit['translation']==record['source']:
        return 'retained_original'
    if edit and edit.get('translation_method')=='current_online_chat_llm':
        return 'llm_translated'
    if edit:
        return 'user_revision'
    return 'awaiting_retranslation'


def numeric_literals(text):
    for a,b,_ in reversed(controls(text)):
        text=text[:a]+' '+text[b:]
    return re.findall(r'[-+]?\d+(?:\.\d+)?%?',text)


def validate_retained_terms(source, target, issues):
    for issue in issues:
        term=issue.get('term','')
        if issue.get('scope') not in {'term','phrase'} or not term:continue
        pattern=r'(?<![A-Za-z])'+re.escape(term)+r'(?![A-Za-z])'
        occurrences=re.findall(pattern,source,re.I)
        if occurrences and len(re.findall(pattern,target,re.I))!=len(occurrences):
            raise ValueError('User-retained term must remain in English: '+term)


def retained_term_issues(policy=None):
    if policy is None:policy=json.loads(POLICY.read_text('utf8'))
    return [q for q in policy.get('questions',[]) if q['status']=='deferred_final'
            or q['status']=='user_confirmed' and q.get('retain_original_term')]


def validate_personal_names(source, target, policy=None):
    """Enforce the user's temporary English spelling without anglicizing titles."""
    if policy is None:
        policy=json.loads(POLICY.read_text('utf8')).get('personal_name_policy',{})
    if policy.get('status')!='user_confirmed_temporary':return
    for name in policy.get('names',[]):
        term=name['english']
        pattern=r'(?<![A-Za-z])'+re.escape(term)+r'(?![A-Za-z])'
        if re.search(pattern,source) and not re.search(pattern,target):
            raise ValueError('Personal name must remain in English: '+term)
        for alias in name.get('previous_chinese_aliases',[]):
            if alias and alias in target:
                raise ValueError('Superseded Chinese personal name: '+alias+' -> '+term)


def snapshot():
    records=base_catalogue()
    edits=load_edits(records)
    questions=pending_questions(records)
    pending_ids={key for q in questions for key in q['entry_ids']}
    counts=Counter(review_state(r,edits,pending_ids) for r in records)
    deferred=final_review_issues(records)
    deferred_ids={key for issue in deferred for key in issue['entry_ids']}
    return {'schema':1,'method':'current_online_chat_llm','separate_api_called':False,
            'total_entries':len(records),'counts':dict(counts),
            'llm_batches':dict(sorted(Counter(e.get('batch','unassigned') for e in edits.values() if e.get('translation_method')=='current_online_chat_llm').items())),
            'unresolved_questions':questions,'final_review_issue_count':len(deferred),
            'final_review_entry_count':len(deferred_ids),'deferred_final_issues':deferred,
            'japanese_display_entries':sum(r['japanese']['availability']=='verified_display' for r in records),
            'japanese_internal_hint_entries':sum(bool(r['japanese']['internal_hint']) for r in records),
            'full_retranslation_complete':not deferred and not any(counts[k] for k in ['awaiting_user','awaiting_retranslation']),
            'game_files_modified':False}


def commit_batch(path):
    payload=json.loads(path.read_text('utf-8-sig'))
    records=base_catalogue()
    by_id={r['id']:r for r in records}
    edits=validate_edits(payload,records)
    pending={key for q in pending_questions(records) for key in q['entry_ids']}
    pending.update(k for k,d in load_review_decisions(records).items() if d['status']=='deferred_final')
    locked={r['id'] for r in records if r.get('locked')}
    deferred_terms=retained_term_issues()
    if not edits:
        raise ValueError('Empty translation batch')
    for key,edit in edits.items():
        if key in pending or key in locked:
            raise ValueError('Locked or unresolved translation: '+key)
        if edit.get('translation_method')!='current_online_chat_llm' or edit.get('review_status')!='llm_translated' or edit.get('human_reviewed') is not False:
            raise ValueError('Missing or misleading translation provenance: '+key)
        if edit.get('source')!=by_id[key]['source']:
            raise ValueError('Batch English source differs: '+key)
        if numeric_literals(edit['source'])!=numeric_literals(edit['translation']):
            raise ValueError('Numeric literals changed; requires explicit review: '+key)
        validate_retained_terms(edit['source'],edit['translation'],deferred_terms)
        validate_personal_names(edit['source'],edit['translation'])
    import_revision(path)
    result=snapshot()
    destination=PROJECT/'docs/llm-retranslation-progress.json'
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'imported':len(edits),'counts':result['counts']},ensure_ascii=False))


def queue(limit, category=None, table=None, start_row=0):
    records=base_catalogue();edits=load_edits(records)
    final_issues=final_review_issues(records)
    pending={key for q in pending_questions(records) for key in q['entry_ids']}
    deferred={k for k,d in load_review_decisions(records).items() if d['status']=='deferred_final'}
    grouped={}
    for row in records:
        group=row['id'].rsplit('/',1)[0] if row['kind']=='database' else row['location']
        grouped.setdefault(group,[]).append(row)
    result=[]
    for row in records:
        if category and row['category']!=category:continue
        if table is not None:
            parts=row['id'].split('/')
            if row['kind']!='database' or int(parts[1])!=table or int(parts[2])<start_row:continue
        if row['id'] not in deferred and review_state(row,edits,pending)=='awaiting_retranslation':
            group=row['id'].rsplit('/',1)[0] if row['kind']=='database' else row['location']
            related=grouped[group]
            if row['kind']!='database':
                at=related.index(row);related=related[max(0,at-2):at+3]
            result.append({**row,'context_group':group,'related_english':[{'id':r['id'],'source':r['source'],'japanese':r['japanese']} for r in related if r['id']!=row['id']],
                           'deferred_terms':[issue['term'] for issue in final_issues if row['id'] in issue['entry_ids'] and issue.get('term')],
                           'deferred_issues':[{k:issue[k] for k in ['id','scope','question','decision'] if k in issue}
                                              for issue in final_issues if row['id'] in issue['entry_ids']]})
            if len(result)>=limit:break
    print(json.dumps(result,ensure_ascii=False,indent=2))


def export_final_review():
    records=base_catalogue();by_id={r['id']:r for r in records};edits=load_edits(records)
    issues=final_review_issues(records)
    for issue in issues:
        issue['entries']=[{'id':key,'source':by_id[key]['source'],'japanese':by_id[key]['japanese'],
            'translation':edits.get(key,{}).get('translation',by_id[key]['translation']),
            'translation_state':review_state(by_id[key],edits,set()),
            'source_sha256':by_id[key]['source_sha256']} for key in issue['entry_ids']]
    path=PROJECT/'docs/final-review-queue.json'
    path.write_text(json.dumps({'schema':1,'issues':issues},ensure_ascii=False,indent=2),encoding='utf8')
    print(f'Final review: {len(issues)} issues, {path}')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','queue','commit','final-review'])
    parser.add_argument('file',type=Path,nargs='?')
    parser.add_argument('--limit',type=int,default=30)
    parser.add_argument('--category')
    parser.add_argument('--table',type=int)
    parser.add_argument('--start-row',type=int,default=0)
    args=parser.parse_args()
    if args.action=='commit':
        if not args.file:parser.error('commit requires a batch file')
        commit_batch(args.file)
    elif args.action=='queue':queue(max(1,min(args.limit,600)),args.category,args.table,max(0,args.start_row))
    elif args.action=='final-review':export_final_review()
    else:print(json.dumps(snapshot(),ensure_ascii=False,indent=2))
