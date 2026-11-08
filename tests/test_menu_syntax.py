"""Prevent translated menu punctuation from disabling gameplay actions."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from menu_syntax import menu_entries,validate_menu_commands
from localization import validate
from editing import base_catalogue,load_effective_edits,apply_text_edits,validate_edits


class MenuSyntaxTests(unittest.TestCase):
    def test_labels_translate_but_original_action_suffix_is_literal(self):
        validate('Use, 500000\r\n','使用, 500000\r\n',preserve_linebreaks=False)
        for bad in ['使用，500000\r\n','使用,500000\r\n','使用, 400000\r\n','使用\r\n','使用, 500000\n']:
            with self.assertRaises(ValueError):validate('Use, 500000\r\n',bad,preserve_linebreaks=False)

    def test_multiline_cancel_and_return_keep_negative_ids_and_order(self):
        source='Cancel, 2\r\nContinue, -1'
        validate(source,'取消, 2\r\n继续, -1')
        for bad in ['取消, -1\r\n继续, 2','取消, 2\r\n继续, 1','取消, 2\r\n继续, -1\r\n','取消, 2\r\n\r\n继续, -1']:
            with self.assertRaises(ValueError):validate(source,bad,preserve_linebreaks=False)

    def test_database_import_rejects_malformed_menu_before_it_reaches_build(self):
        row={'id':'menu','source':'Equip, 100000\r\n','source_sha256':'hash','kind':'database'}
        payload={'schema':1,'project':'mcowh-zh','entries':[{'id':'menu','source_sha256':'hash','translation':'装备，100000\r\n'}]}
        with self.assertRaises(ValueError):validate_edits(payload,[row])
        payload['entries'][0]['translation']='装备, 100000\r\n'
        self.assertEqual(len(validate_edits(payload,[row])),1)

    def test_current_all_eighteen_menu_templates_preserve_action_routes(self):
        rows=apply_text_edits(base_catalogue(),load_effective_edits())
        menus=[r for r in rows if menu_entries(r['source']) is not None]
        self.assertEqual(len(menus),18)
        for row in menus:validate_menu_commands(row['source'],row['translation'])
        fixes=json.loads((ROOT/'translations/menu-command-fields.json').read_text('utf8'))['fields']
        self.assertEqual(len(fixes),12)
        for key,fix in fixes.items():
            with self.assertRaises(ValueError):validate_menu_commands(fix['source'],fix['baseline_032_translation'])
            validate_menu_commands(fix['source'],fix['translation'])

    def test_plain_prose_is_not_a_menu_template(self):
        self.assertIsNone(menu_entries('Use, if you need it.'))
        self.assertIsNone(menu_entries('HP +10, ST +5.'))
        validate('Use, if you need it.','需要时使用。')

    def test_legacy_crcrlf_menu_ending_is_preserved(self):
        self.assertEqual(menu_entries('Use, 500000\r\r\n'),[('Use',', 500000\r\r\n')])
        validate('Use, 500000\r\r\n','使用, 500000\r\r\n')


if __name__=='__main__':unittest.main()
