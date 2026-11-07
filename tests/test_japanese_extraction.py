import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from extract_japanese import decode_script,display_spans,script_signature
from editing import base_catalogue,validate_edits
from localization import digest
from translation_policy import apply_policy


class JapaneseExtractionTests(unittest.TestCase):
    def test_script_encoding_and_choice_labels_with_spaces_and_comments(self):
        text='@putselect 質問 どうしたらいい？ 306 #- 日本語コメント\r\n@putselect reset\r\n'
        self.assertEqual(decode_script(text.encode('cp932')),(text,'cp932'))
        spans=list(display_spans(text))
        self.assertEqual(spans[0][4],'質問 どうしたらいい？')
        self.assertEqual(spans[1][4],'reset')
        en='@putselect Ask_what_to_do 306 #- English comment\n@putselect reset\n'
        self.assertEqual(script_signature(text),script_signature(en))
        self.assertNotEqual(script_signature(text),script_signature(en.replace('306','307')))

    def test_ui_alignment_allows_caption_and_geometry_but_preserves_action(self):
        en='Size: 515\nCaption:Load&Game\nText: Center, Top, $str1\nButton: 135, Under, 178, 38, -1, Cancel\n'
        ja='\ufeff# 説明\nSize: 464\nCaption:ロード\nText: Center, Top, $str1\nButton: 240, Under, 178, 38, -1, 戻る\n'
        self.assertEqual(script_signature(en,ui=True),script_signature(ja,ui=True))
        self.assertNotEqual(script_signature(en,ui=True),script_signature(ja.replace('-1','1'),ui=True))
        self.assertNotEqual(script_signature(en,ui=True),script_signature(ja.replace('$str1','$str2'),ui=True))

    def test_control_directive_cannot_be_translated_or_override_build_policy(self):
        row={'id':'choice/test/0','kind':'choice','source':'reset','source_sha256':digest('reset'),'translation':'重置','status':'machine_draft'}
        protected=apply_policy([row])[0]
        self.assertEqual(protected['translation'],'reset')
        self.assertTrue(protected['locked'])
        self.assertTrue(protected['internal_command'])
        payload={'schema':1,'project':'mcowh-zh','entries':[{'id':row['id'],'source_sha256':row['source_sha256'],'translation':'重置'}]}
        with self.assertRaises(ValueError):validate_edits(payload,[protected])

    def test_real_source_alignment_is_complete_for_scripts_and_source_bound(self):
        report=json.loads((ROOT/'docs/japanese-resource-verification.json').read_text('utf8'))
        self.assertTrue(report['usable'])
        self.assertEqual(report['resource_blocks_decompressed'],430)
        self.assertEqual(report['database_string_fields'],63821)
        self.assertTrue(report['database_layout_matches'])
        records=base_catalogue()
        self.assertEqual(sum(r['japanese']['availability']=='verified_display' for r in records),11951)
        for kind in ['message','button']:
            self.assertTrue(all(r['japanese']['text'] for r in records if r['kind']==kind))
        self.assertTrue(all(r['japanese']['text'] for r in records if r['kind']=='choice' and not r.get('internal_command')))
        by_id={r['id']:r for r in records}
        self.assertIn('協力NPC',by_id['db/6/164/3']['japanese']['text'])
        self.assertIn('移動停止',by_id['db/6/91/3']['japanese']['text'])
        for source in json.loads((ROOT/'translations/japanese-sources.json').read_text('utf8'))['entries']:
            self.assertEqual(source['source_sha256'],by_id[source['id']]['source_sha256'])
            self.assertEqual(source['japanese_sha256'],digest(source['text']))
            self.assertEqual(source['alignment']['semantic_review'],'pending')


if __name__=='__main__':unittest.main()
