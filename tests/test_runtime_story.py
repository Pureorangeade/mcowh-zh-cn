"""Offline checks for story selection and display-only runtime compatibility."""
import hashlib,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from common_events import parse,encode_command
from extract_japanese import read
from formats import database_fields
from localization import controls,database_display,display_candidate,validate
from resources import Archive
from runtime_compat import class_aliases,enemy_aliases,patch


def run_strings(commands,variable,value):
    """Execute only inserted SetString/contains-branch operations on one local."""
    enabled=True
    for c in commands:
        cid,args,ss=c['cid'],c['args'],c['strings']
        if cid==112:
            assert args==[1,0x20000000|variable]
            enabled=ss[0] in value
        elif cid in {401,0}:pass
        elif cid==499:enabled=True
        elif cid==122:
            assert args==[variable,2304]
            if enabled:value=value.replace(ss[0],ss[1])
        else:raise AssertionError('Unexpected mutation or opcode '+str(cid))
    return value


class RuntimeStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original=Archive(ROOT/'work/clean-fixture');current=Archive(ROOT/'build/0.3.3-menu-fix')
        name='d3d11/data/basicdata/database.dat'
        cls.en={f.id:f.text for f in database_fields(read(original,name))}
        cls.zh={f.id:f.text for f in database_fields(read(current,name))}
        cls.raw=read(original,'d3d11/data/basicdata/commonevent.dat')
        cls.out,cls.proof=patch(cls.raw,cls.en,cls.zh)
        cls.before={e['id']:e for e in parse(cls.raw)};cls.after={e['id']:e for e in parse(cls.out)}

    def inserted(self,eid,after):
        old=self.before[eid]['commands'];new=self.after[eid]['commands']
        start=after+1+sum(p['added_commands'] for p in self.proof['events']
                          if p['event']==eid and p['after_original_command']<after)
        proof=next(p for p in self.proof['events'] if p['event']==eid and p['after_original_command']==after)
        return new[start:start+proof['added_commands']]

    def test_all_original_events_and_command_payloads_survive(self):
        self.assertEqual(len(self.before),1000)
        changed={i for i in self.before if len(self.before[i]['commands'])!=len(self.after[i]['commands'])}
        self.assertEqual(changed,{372,598,741,806,846})
        for eid,event in self.before.items():
            if eid not in changed:
                actual=self.after[eid]
                self.assertEqual(self.raw[event['offset']:event['end']],self.out[actual['offset']:actual['end']])
        for raw in [self.raw[:-1],self.raw+b'x',b'bad header']:
            with self.assertRaises((ValueError,AssertionError,IndexError)):parse(raw)

    def test_local_aliases_normalize_all_classes_and_difficulties(self):
        for eid in [741,806,846]:
            cmds=self.inserted(eid,4)
            for en,zh,row in self.proof['class_aliases']:
                for suffix in ['NORMAL','HARD','VERYHARD','EASY']:
                    for extras in ['', '+倉庫なし', '+倉庫なし+マニアモード']:
                        for objective in ['堕天使撃破','闇撃破','世界の果てへ','中級クリア','上級クリア']:
                            old=f'[{en}で{objective}<{suffix}>{extras}]'
                            expected=f'[{zh}で{objective}<{suffix}>{extras}]'
                            self.assertEqual(run_strings(cmds,1600008,old),expected)
                            self.assertEqual(run_strings(cmds,1600008,expected),expected)

    def test_no_partial_class_name_replacement_or_persistent_write(self):
        cmds=self.inserted(741,4)
        for value in ['Knight','[Dark Knightlyで闇撃破<NORMAL>]','[unknownで中級クリア<EASY>]']:
            self.assertEqual(run_strings(cmds,1600008,value),value)
        for proof in self.proof['events']:
            allowed={122} if proof['event'] in {741,806,846} else {0,112,122,401,499}
            commands=self.inserted(proof['event'],proof['after_original_command'])
            self.assertTrue(all(c['cid'] in allowed for c in commands))
            self.assertFalse(proof['writes_save'])

    def test_historical_deaths_translate_static_causes_and_known_enemies(self):
        for proof in self.proof['events']:
            if proof['event'] not in {372,598}:continue
            cmds=self.inserted(proof['event'],proof['after_original_command'])
            variable=1600000+int(proof['variable'].split('[')[1].split(']')[0])
            for row in range(1,17):
                en=self.en[f'db/32/{row}/3'];zh=self.zh[f'db/32/{row}/3']
                self.assertEqual(run_strings(cmds,variable,en),zh)
            for en,zh in enemy_aliases(self.en,self.zh):
                legacy='你本该已经been killed by \\c[51]'+en+'\\c[0]。'
                self.assertEqual(run_strings(cmds,variable,legacy),'你本该已经死于\\c[51]'+zh+'\\c[0]。')
            unknown='been killed by \\c[51]UnknownCreature\\c[0]'
            self.assertEqual(run_strings(cmds,variable,unknown),'死于\\c[51]UnknownCreature\\c[0]')
            for unchanged in ['与\\c[51]Alma\\c[0]交谈。','被\\c[51]未知魔物\\c[0]杀死']:
                self.assertEqual(run_strings(cmds,variable,unchanged),unchanged)

    def test_story_candidates_match_all_34_english_bodies_and_preserve_controls(self):
        expected={k for k,v in self.en.items() if k.startswith('db/72/') and k.endswith('/1') and display_candidate(v)}
        authored=json.loads((ROOT/'translations/llm-batches/0069-text.json').read_text('utf8'))
        actual={k for k in authored if k.startswith('db/72/')}
        self.assertEqual(actual,expected);self.assertEqual(len(actual),34)
        self.assertTrue(database_display(72,1,'表示項目'))
        japanese={e['id']:e for e in json.loads((ROOT/'translations/japanese-sources.json').read_text('utf8'))['entries']}
        for key in actual:
            validate(self.en[key],authored[key],preserve_linebreaks=False)
            self.assertEqual(japanese[key]['kind'],'verified_display')
            self.assertNotEqual(japanese[key]['text'],self.en[key])
        for row in [0,13,14,15,35,68,69,91,92,93,94]:
            self.assertNotIn(f'db/72/{row}/1',actual)
        self.assertIn('传讯水晶',authored['db/72/12/1'])
        self.assertIn('父亲病危',authored['db/72/46/1'])
        self.assertNotIn('爵位',authored['db/72/51/1'])
        self.assertIn('父母兄弟',authored['db/72/51/1'])

if __name__=='__main__':unittest.main()
