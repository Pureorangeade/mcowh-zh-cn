import json
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from editing import base_catalogue,load_effective_edits,load_edits,load_review_decisions
from editor_data import import_revision
from japanese_sources import annotate_japanese
from llm_workflow import final_review_issues,queue


class SourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.records=base_catalogue()

    def test_japanese_internal_label_is_not_display_original(self):
        row=next(r for r in self.records if r['id']=='db/6/35/0')
        self.assertEqual(row['source'],"Angel's Feather")
        self.assertIn('魔王の心臓',row['japanese']['internal_hint'])
        self.assertEqual(row['japanese']['text'],'堕天の羽根')
        self.assertEqual(row['japanese']['availability'],'verified_display')
        # Removing a verified source must leave the hint separate, never promoted.
        with tempfile.TemporaryDirectory() as folder:
            copy=dict(row);annotate_japanese([copy],Path(folder)/'missing.json')
            self.assertEqual(copy['japanese']['text'],'')
            self.assertEqual(copy['japanese']['availability'],'missing')

    def test_verified_japanese_requires_alignment_and_provenance(self):
        row={'id':'test','source_sha256':'hash'}
        source={'id':'test','source_sha256':'hash','text':'実際の表示文','kind':'verified_display','origin':'test fixture','version':'test'}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'jp.json';p.write_text(json.dumps({'schema':1,'entries':[source]}),encoding='utf8')
            annotate_japanese([row],p)
            self.assertEqual(row['japanese']['text'],source['text'])
            for key,value in [('source_sha256','wrong'),('origin',''),('kind','internal_label')]:
                p.write_text(json.dumps({'schema':1,'entries':[{**source,key:value}]}),encoding='utf8')
                with self.assertRaises(ValueError):annotate_japanese([row],p)

    def test_deferred_roundtrip_keeps_draft_but_effective_build_uses_original(self):
        row=next(r for r in self.records if r['id']=='db/3/0/0')
        edit={'id':row['id'],'source_sha256':row['source_sha256'],'translation':'中文草稿'}
        decision={k:edit[k] for k in ['id','source_sha256']}
        decision.update(scope='entry',status='deferred_final',reason='语境待查')
        payload={'schema':1,'project':'mcowh-zh','entries':[edit],'review_decisions':[decision]}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'in.json';out=Path(folder)/'saved.json'
            p.write_text(json.dumps(payload),encoding='utf8');import_revision(p,out)
            self.assertEqual(load_edits(self.records,out)[row['id']]['translation'],'中文草稿')
            self.assertEqual(load_effective_edits(self.records,out)[row['id']]['translation'],row['source'])
            saved=out.read_bytes()
            bad={**decision,'source_sha256':'stale'}
            p.write_text(json.dumps({**payload,'review_decisions':[bad]}),encoding='utf8')
            with self.assertRaises(ValueError):import_revision(p,out)
            self.assertEqual(out.read_bytes(),saved)
            # Legacy import preserves existing review decisions.
            p.write_text(json.dumps({**payload,'review_decisions':[]}),encoding='utf8');import_revision(p,out)
            self.assertEqual(load_review_decisions(self.records,out)[row['id']]['status'],'deferred_final')
            p.write_text(json.dumps({**payload,'entries':[],'review_decisions':[{**decision,'status':'resolved'}]}),encoding='utf8');import_revision(p,out)
            self.assertEqual(load_effective_edits(self.records,out)[row['id']]['translation'],'中文草稿')

    def test_temporary_terms_are_deferred_without_including_permanent_attributes(self):
        issues=final_review_issues(self.records)
        self.assertTrue({'Zeukrees','Pluton','Auris'}.issubset({q.get('term') for q in issues}))
        self.assertNotIn('Sp.',{q.get('term') for q in issues})
        by_id={r['id']:r for r in self.records}
        self.assertFalse(any(by_id[key]['locked'] for q in issues for key in q['entry_ids']))

    def test_source_difference_does_not_spread_to_other_entries_or_survive_source_change(self):
        # A decision about one item must not mark every similar phrase, or a new version.
        rows=[{'id':'one','source':'HP +25%','source_sha256':'hash-one'},
              {'id':'two','source':'HP +25%','source_sha256':'hash-two'}]
        question={'id':'difference','status':'deferred_final','scope':'source_difference',
                  'entry_ids':['one'],'source_sha256s':{'one':'hash-one'}}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'policy.json'
            path.write_text(json.dumps({'questions':[question]}),encoding='utf8')
            with patch('llm_workflow.POLICY',path),patch('llm_workflow.load_review_decisions',return_value={}):
                self.assertEqual(final_review_issues(rows)[0]['entry_ids'],['one'])
                changed=[{**rows[0],'source_sha256':'changed'},rows[1]]
                with self.assertRaises(ValueError):final_review_issues(changed)

    def test_queue_scopes_next_batch_and_includes_bilingual_context(self):
        output=io.StringIO()
        # Queue behavior must not depend on which real batches have already finished.
        with patch('llm_workflow.load_edits',return_value={}),contextlib.redirect_stdout(output):
            queue(4,table=6,start_row=106)
        rows=json.loads(output.getvalue())
        self.assertEqual(len(rows),4)
        for row in rows:
            self.assertTrue(row['id'].startswith('db/6/'))
            self.assertGreaterEqual(int(row['id'].split('/')[2]),106)
            self.assertIn('availability',row['japanese'])
            self.assertTrue(row['related_english'])
            self.assertIn('deferred_terms',row)


if __name__=='__main__':unittest.main()
