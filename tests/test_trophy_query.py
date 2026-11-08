"""Regress actual bytecode predicates, not only alias replacement strings."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from common_events import parse
from extract_japanese import read
from formats import database_fields
from resources import Archive
from trophy_query_fix import GLOBAL_FLAGS, LOCAL_FLAGS, patch


def expand(text, variables):
    return re.sub(r'\\(cself|s)\[(\d+)\]', lambda m: variables[
        (1600000 if m[1] == 'cself' else 3000000) + int(m[2])], text)


class TrophyQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        arc = Archive(ROOT/'build/0.3.4-story-compat')
        cls.raw = read(arc, 'd3d11/data/basicdata/commonevent.dat')
        cls.out, cls.proof = patch(cls.raw)
        cls.before = {e['id']: e for e in parse(cls.raw)}
        cls.after = {e['id']: e for e in parse(cls.out)}
        cls.zh = {f.id: f.text for f in database_fields(read(arc, 'd3d11/data/basicdata/database.dat'))}

    def test_previous_bug_reproduces_and_all_real_predicates_read_normalized_flags(self):
        # Actual 0.3.4 bytecode contains 25 SetString alias commands after load.
        # Keep global S0 English while running those commands on local cself[8].
        cases = 0
        for change in self.proof['changes']:
            eid, index = change['event'], change['command']
            original = self.before[eid]['commands'][index]
            fixed = self.after[eid]['commands'][index]
            aliases = self.before[eid]['commands'][5:30]
            self.assertEqual(len(aliases), 25)
            self.assertTrue(all(c['cid'] == 122 and c['args'] == [1600008,2304] for c in aliases))
            for row, en in [(106,'Pirate'), (124,'Wanderer')]:
                zh = self.zh[f'db/28/{row}/0']
                for difficulty in ['EASY','NORMAL','HARD','VERYHARD']:
                    for objective in ['堕天使撃破','魔王撃破','闇撃破','世界の果てへ','中級クリア','上級クリア']:
                        variables = {3000041:difficulty, **{1600000+i:zh+'で'+objective for i in [5,6,7]}}
                        for operand, template in enumerate(original['strings'][:len(original['args'])-1], 1):
                            wanted = expand(template, variables)
                            # One original predicate deliberately matches an open prefix.
                            legacy = wanted.replace('['+zh+'で','['+en+'で',1) + ('' if wanted.endswith(']') else ']')
                            local = legacy
                            for c in aliases:
                                local = local.replace(*c['strings'])
                            variables[3000000] = legacy
                            variables[1600008] = local
                            self.assertNotIn(wanted, variables[original['args'][operand] & 0xffffff])
                            self.assertIn(wanted, variables[fixed['args'][operand] & 0xffffff])
                            self.assertEqual(variables[3000000], legacy)
                            # Already-Chinese flags remain valid too.
                            variables[1600008] = wanted
                            self.assertIn(wanted, variables[fixed['args'][operand] & 0xffffff])
                            variables[1600008] = '[UnknownClassで未通关<NORMAL>]'
                            self.assertNotIn(wanted, variables[fixed['args'][operand] & 0xffffff])
                            cases += 1
        self.assertEqual(cases, 3456)

    def test_only_selected_operand_bytes_change(self):
        allowed = set()
        for c in self.proof['changes']:
            cmd = self.before[c['event']]['commands'][c['command']]
            for operand in c['operand_indexes']:
                allowed.update(range(cmd['offset']+5+operand*4, cmd['offset']+9+operand*4))
        different = {i for i,(a,b) in enumerate(zip(self.raw,self.out,strict=True)) if a != b}
        self.assertTrue(different)
        self.assertLessEqual(different, allowed)
        self.assertEqual(self.proof['changed_predicates'],45)
        self.assertEqual(self.proof['changed_operands'],72)
        for eid in self.before:
            if eid not in {741,806,846}:
                old,new = self.before[eid],self.after[eid]
                self.assertEqual(self.raw[old['offset']:old['end']],self.out[new['offset']:new['end']])
        self.assertEqual(len(self.raw),len(self.out))

    def test_wrong_or_already_patched_input_rejected(self):
        with self.assertRaises(AssertionError):
            patch(self.out)
        with self.assertRaises(ValueError):
            patch(b'invalid common event')


if __name__ == '__main__':
    unittest.main()
