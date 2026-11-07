import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from editing import apply_text_edits
from llm_workflow import review_state,numeric_literals,commit_batch,validate_retained_terms,pending_questions


class LlmWorkflowTests(unittest.TestCase):
    def test_confirmed_original_terms_remain_protected_after_final_issue_closed(self):
        from llm_workflow import retained_term_issues
        issues=retained_term_issues({'questions':[
            {'status':'user_confirmed','retain_original_term':True,'term':'Max HP & ST','scope':'phrase'},
            {'status':'user_confirmed','term':'Sp.','scope':'term'},
            {'status':'deferred_final','term':'Pluton','scope':'term'}]})
        self.assertEqual({q['term'] for q in issues},{'Max HP & ST','Pluton'})
        validate_retained_terms('Cost Max HP & ST','消耗Max HP & ST',issues)
        validate_retained_terms('Sp. Healing Herb','特等疗伤草',issues)
        with self.assertRaises(ValueError):validate_retained_terms('Cost Max HP & ST','消耗最大HP与ST',issues)

    def test_personal_name_policy_preserves_identity_and_chinese_titles(self):
        from llm_workflow import validate_personal_names
        policy={'status':'user_confirmed_temporary','names':[
            {'english':'Alma','previous_chinese_aliases':['阿尔玛']},
            {'english':'Keyton','previous_chinese_aliases':['凯顿']}]}
        validate_personal_names("Keyton's Sword",'Keyton之剑',policy)
        validate_personal_names('Fallen Angel','堕天使',policy)
        validate_personal_names('Elzite and Nayuta','艾尔扎特与纳尤塔果',policy)
        validate_personal_names('Almanac','历书',policy)
        for source,target in [('Alma','阿尔玛'),('Slay Alma','讨伐堕天使'),('Keyton','Keyton（凯顿）')]:
            with self.assertRaises(ValueError):validate_personal_names(source,target,policy)

    def test_current_personal_names_follow_user_global_policy(self):
        from editing import base_catalogue,load_edits
        from llm_workflow import validate_personal_names
        rows=base_catalogue();edits=load_edits(rows)
        for row in rows:
            validate_personal_names(row['source'],edits.get(row['id'],{}).get('translation',row['translation']))

    def test_pending_terms_follow_aliases_and_new_occurrences_without_substring_matches(self):
        rows=[{'id':'new-aria','source':"Aria's robe"},
              {'id':'alias','source':'Lillith'}, {'id':'new-monomi','source':'Talk to Monomi'},
              {'id':'unrelated','source':'Maria and Monomii'}]
        question={'id':'names','status':'awaiting_user','scope':'source_difference',
                  'entry_ids':['explicit-marker'],'tracked_terms':['Aria','Lilith','Lillith','Monomi']}
        with tempfile.TemporaryDirectory() as temp:
            policy=Path(temp)/'policy.json';policy.write_text(json.dumps({'questions':[question]}),encoding='utf8')
            with patch('llm_workflow.POLICY',policy):
                resolved=pending_questions(rows)
            self.assertEqual(resolved[0]['entry_ids'],['explicit-marker','new-aria','alias','new-monomi'])
            self.assertEqual(question['entry_ids'],['explicit-marker'])

    def test_inherited_mt_is_not_counted_as_retranslated(self):
        row={'id':'example','status':'curated'}
        self.assertEqual(review_state(row,{},set()),'awaiting_retranslation')
        self.assertEqual(review_state(row,{}, {'example'}),'awaiting_user')
        self.assertEqual(review_state({**row,'locked':True},{},{'example'}),'retained_english')
        edit={'example':{'translation_method':'current_online_chat_llm'}}
        self.assertEqual(review_state(row,edit,set()),'llm_translated')
        self.assertEqual(review_state(row,edit,{'example'}),'awaiting_user')

    def test_numeric_effects_preserve_signs_percentages_and_order(self):
        source='\\c[61]ATK\\c[0] \\c[60]-15%\\c[0], HP +10, Range 2'
        self.assertEqual(numeric_literals(source),['-15%','+10','2'])
        self.assertNotEqual(numeric_literals(source),numeric_literals(source.replace('-15%','+15%')))

    def test_confirmed_retention_is_not_counted_as_translated(self):
        row={'id':'marker','source':'[Ver2.00用]'}
        edits={'marker':{'translation_method':'user_confirmed_retention','translation':row['source']}}
        self.assertEqual(review_state(row,edits,set()),'retained_original')
        edits['marker']['translation']='a new translation'
        self.assertEqual(review_state(row,edits,set()),'user_revision')

    def test_deferred_term_is_retained_without_blocking_sentence_translation(self):
        issues=[{'term':'Pluton','scope':'term'}]
        validate_retained_terms("Pluton's wings",'Pluton的翅膀',issues)
        with self.assertRaises(ValueError):validate_retained_terms("Pluton's wings",'普鲁顿的翅膀',issues)

    def test_runtime_status_numbers_are_not_translated_as_ordinary_words(self):
        from localization import validate
        validate('Barrier num Layers','结界num层',preserve_linebreaks=False)
        validate('Acid Lvnum','强酸 Lvnum',preserve_linebreaks=False)
        for source,target in [('Barrier num Layers','结界数值层'),('Acid Lvnum','强酸等级num')]:
            with self.assertRaises(ValueError):validate(source,target,preserve_linebreaks=False)

    def test_saved_model_batches_keep_sources_controls_numbers_and_provenance(self):
        from editing import base_catalogue,validate_edits,load_edits
        from localization import digest
        records=base_catalogue();by_id={r['id']:r for r in records}
        paths=sorted((ROOT/'translations/llm-batches').glob('[0-9][0-9][0-9][0-9].json'))
        self.assertGreaterEqual(len(paths),4)
        batches={}
        for path in paths:
            payload=json.loads(path.read_text('utf8'))
            changes=validate_edits(payload,records)
            batches[payload['batch']]=changes
            if payload.get('authored_text_sha256'):
                text_path=path.with_name(path.stem+'-text.json')
                text=text_path.read_text('utf-8-sig')
                self.assertEqual(payload['authored_text_sha256'],digest(text),path.name)
                self.assertEqual(json.loads(text),{key:edit['translation'] for key,edit in changes.items()},path.name)
            for key,edit in changes.items():
                self.assertEqual(edit['source'],by_id[key]['source'],key)
                self.assertEqual(edit['translation_method'],'current_online_chat_llm',key)
                self.assertEqual(edit['review_status'],'llm_translated',key)
                self.assertFalse(edit['human_reviewed'],key)
                self.assertEqual(numeric_literals(edit['source']),numeric_literals(edit['translation']),key)
        for key,edit in load_edits(records).items():
            if edit.get('translation_method')=='current_online_chat_llm':
                self.assertIn(key,batches.get(edit.get('batch'),{}),key)
                self.assertEqual(batches[edit['batch']][key]['translation'],edit['translation'],key)

    def test_llm_overlay_keeps_provenance_without_claiming_human_review(self):
        row={'id':'db/1/0/0','kind':'database','source':'Attack','translation':'旧译文'}
        edit={row['id']:{'translation':'攻击','translation_method':'current_online_chat_llm','review_status':'llm_translated','human_reviewed':False}}
        result=apply_text_edits([row],edit)[0]
        self.assertEqual(result['translation'],'攻击')
        self.assertFalse(result['edited_by_user'])
        self.assertFalse(result['human_reviewed'])
        self.assertEqual(result['review_status'],'llm_translated')

    def test_commit_rejects_unresolved_entries_and_numeric_changes_before_import(self):
        row={'id':'db/1/0/0','source':'Gain 10 HP','source_sha256':'hash','kind':'database'}
        edit={**row,'translation':'获得10 HP','translation_method':'current_online_chat_llm','review_status':'llm_translated','human_reviewed':False}
        payload={'schema':1,'project':'mcowh-zh','entries':[edit]}
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'batch.json';p.write_text(json.dumps(payload),encoding='utf8')
            with patch('llm_workflow.base_catalogue',return_value=[row]),patch('llm_workflow.load_review_decisions',return_value={}),patch('llm_workflow.pending_questions',return_value=[{'entry_ids':[row['id']]}]),patch('llm_workflow.import_revision') as importer:
                with self.assertRaises(ValueError):commit_batch(p)
                importer.assert_not_called()
            payload['entries'][0]['translation']='获得100 HP';p.write_text(json.dumps(payload),encoding='utf8')
            with patch('llm_workflow.base_catalogue',return_value=[row]),patch('llm_workflow.load_review_decisions',return_value={}),patch('llm_workflow.pending_questions',return_value=[]),patch('llm_workflow.import_revision') as importer:
                with self.assertRaises(ValueError):commit_batch(p)
                importer.assert_not_called()


if __name__=='__main__':unittest.main()
