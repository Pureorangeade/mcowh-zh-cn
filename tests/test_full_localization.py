"""Checks protecting script execution and the expanded Phyre glyph arrays."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from fonts import extend, inspect, serialize_glyphs
from localization import apply_spans, controls, database_display, digest, display_candidate, script_spans, validate
from translate_full import units
from formats import pack_text_dictionary, unpack_text_dictionary
from resources import Archive


class LocalizationTests(unittest.TestCase):
    def test_system_dictionary_real_round_trip_and_keys_are_preserved(self):
        arc = Archive(ROOT / 'work/clean-fixture')
        for name in ['text_dict.bin', 'error_code_dict.bin']:
            entry = next(e for e in arc.entries if e.name == 'd3d11/data/' + name)
            raw = arc.read(entry)
            records = unpack_text_dictionary(raw)
            self.assertEqual(pack_text_dictionary(records), raw)
            changed = [(k, '中文测试\n换行' if i == 0 else v) for i, (k, v) in enumerate(records)]
            self.assertEqual(unpack_text_dictionary(pack_text_dictionary(changed)), changed)
            with self.assertRaises(ValueError):
                unpack_text_dictionary(raw[:-1])

    def test_config_sections_are_preserved_and_model_commands_rejected(self):
        source = '// comment\r\n[KB_set]\r\n<C>Update?\r\n[/KB_set]'
        validate(source, source.replace('Update?', '更新？'))
        with self.assertRaises(ValueError):
            validate(source, source.replace('[KB_set]', '[KB_reset]'))
        with self.assertRaises(ValueError):
            validate('Hello', '@erase_save')

    def test_balanced_controls_and_embedded_commands_stay_literal(self):
        source = '@L_mes\r\nBGM:ending.mid\r\n\\img[\\cself[5]]Hello <PLAYER> $tmp1!'
        self.assertEqual([t for _, _, t in controls(source)],
                         ['@L_mes', '\r\n', 'BGM:ending.mid', '\r\n', '\\img[\\cself[5]]', '<PLAYER>', '$tmp1'])
        target = source.replace('Hello', '你好')
        validate(source, target)
        with self.assertRaises(ValueError):
            validate(source, target.replace('[5]', '[6]'))

    def test_paths_and_internal_fields_are_not_display_candidates(self):
        self.assertFalse(display_candidate('BGM/Boss.MID\r\nOther'))
        self.assertFalse(database_display(22, 1, '所持アイテムコード[全部]'))
        self.assertFalse(database_display(71, 0, 'ID'))
        self.assertFalse(database_display(28, 16, '短縮パーツ名'))
        self.assertFalse(database_display(28, 14, '短縮名'))
        self.assertTrue(database_display(5, 0, '名前'))
        self.assertTrue(database_display(63, 1, '文章'))

    def test_only_display_spans_are_replaced_including_duplicate_messages(self):
        text = '# English comment\r\n@mes\r\nHello\r\n@mes\r\nHello\r\n@putselect Say_hello 1 # memo\r\n'
        spans = list(script_spans(text))
        self.assertEqual([s[0] for s in spans], ['message', 'message', 'choice'])
        entries = [{'kind': k, 'start': a, 'end': b, 'source': s, 'source_sha256': digest(s),
                    'translation': '你好' if k == 'message' else '打招呼'} for k, _, a, b, s in spans]
        target = apply_spans(text, entries)
        self.assertEqual(target, '# English comment\r\n@mes\r\n你好\r\n@mes\r\n你好\r\n@putselect 打招呼 1 # memo\r\n')
        with self.assertRaises(ValueError):
            apply_spans(text.replace('Hello', 'Changed', 1), entries)

    def test_choice_normalization_cannot_modify_paths_inside_control_tokens(self):
        source = '\\img[SystemGra/a_b.png]Give_10_to_$tmp1'
        parts = units(source, 'choice')
        literal = [s for k, s in parts if k == 'literal']
        self.assertIn('\\img[SystemGra/a_b.png]', literal)
        self.assertIn('10', literal)
        self.assertIn('$tmp1', literal)

    def test_original_font_layout_is_exactly_reproducible_for_all_eight_fonts(self):
        for path in (ROOT / 'work/extracted/d3d11/common/text').glob('*.phyre'):
            data = path.read_bytes()
            info = inspect(data)
            metadata, descriptor = serialize_glyphs(data, info[0])
            self.assertEqual(bytes(metadata), data[:info[5]], path.name)
            self.assertEqual(descriptor, info[2], path.name)

    def test_grown_font_preserves_every_original_code_without_donor_slots(self):
        path = ROOT / 'work/extracted/d3d11/common/text/win32-seurat-pro-m-20.fgen.phyre'
        data = path.read_bytes()
        old = inspect(data)
        chars = {chr(c) for c in range(0x4E00, 0x4E00 + 5000)}
        new, report = extend(data, chars, Path('C:/Windows/Fonts/NotoSansSC-VF.ttf'), grow=True)
        info = inspect(new)
        self.assertTrue({r[0] for r in old[0]} | {ord(c) for c in chars} <= {r[0] for r in info[0]})
        self.assertEqual([r for r in old[0] if r[0] < 128], [r for r in info[0] if r[0] < 128])
        self.assertEqual(data[old[5]:], new[info[5]:info[5] + old[3] * old[4]])
        self.assertEqual(struct.unpack_from('<I', new, 0xCFA)[0], len(info[0]))
        self.assertEqual(report['removed_codes'], [])
        self.assertGreater(report['glyphs_after'], 5000)
        # The new layout itself must pass all strict array/fixup relationships.
        metadata, _ = serialize_glyphs(new, info[0])
        self.assertEqual(bytes(metadata), new[:info[5]])


if __name__ == '__main__':
    unittest.main()
