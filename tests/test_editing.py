"""User preferences and source-bound human editing regression checks."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from editing import apply_text_edits, base_catalogue, validate_edits
from editor_data import import_revision
from localization import digest
from render_textures import render
from translation_policy import apply_policy
from PIL import Image


class EditingTests(unittest.TestCase):
    def test_only_requested_panel_text_differs_from_frozen_030(self):
        import zipfile
        from editing import load_edits
        with zipfile.ZipFile(ROOT/'dist/MCOWH-zh-CN-0.3.0-llm-review-source.zip') as z:
            old=json.loads(z.read('MCOWH-zh-CN-source/translations/user-overrides.json'))
        before={e['id']:e['translation'] for e in old['entries']}
        current=load_edits(self.records)
        fields=json.loads((ROOT/'translations/panel-attribute-fields.json').read_text('utf8'))
        self.assertEqual(len(fields['terms']),19)
        self.assertEqual(fields['terms']['MOV'],'移速')
        self.assertTrue(set(fields['terms']).isdisjoint({'HP','ST','EN','Lv','Exp','WT'}))
        changed={r['id'] for r in self.records if current.get(r['id'],{}).get('translation',r['translation'])!=before.get(r['id'],r['translation'])}
        self.assertEqual(changed,set(fields['fields']))
        self.assertEqual(len(changed),29)

    @classmethod
    def setUpClass(cls):
        cls.records = base_catalogue()
        cls.by_id = {r['id']:r for r in cls.records}

    def payload(self, key='db/3/0/0', translation='测试译文'):
        r = next(r for r in self.records if not r['locked'] and r['kind']=='database') if key=='db/3/0/0' else self.by_id[key]
        return {'schema':1,'project':'mcowh-zh','entries':[{'id':r['id'],'source_sha256':r['source_sha256'],'translation':translation}]}

    def test_confirmed_panel_labels_are_unlocked_and_source_bound(self):
        from editing import load_edits
        fields=json.loads((ROOT/'translations/panel-attribute-fields.json').read_text('utf8'))['fields']
        edits=load_edits(self.records)
        for key,field in fields.items():
            self.assertFalse(self.by_id[key]['locked'],key)
            self.assertEqual(edits[key]['translation'],field['translation'],key)
            self.assertEqual(self.by_id[key]['source_sha256'],field['source_sha256'],key)
        for key in ['db/58/18/1','db/58/19/1','db/62/171/1','db/62/246/1']:
            record=self.by_id[key]
            self.assertFalse(record['locked'], key)
        # Accessory-category ACC and unrelated numerical effects are not panel
        # accuracy labels, so the narrow approval cannot anglicize/translate them.
        for key in ['db/58/222/1','db/10/35/1']:
            self.assertTrue(self.by_id[key]['locked'],key)

    def test_policy_keeps_ordinary_item_and_dialogue_translations(self):
        for source,kind in [('Longsword','database'),('Gain STR during battle.','message'),('ATK boost','database')]:
            row={'source':source,'kind':kind,'translation':'中文','status':'machine_draft'}
            self.assertEqual(apply_policy([row])[0],row)

    def test_editor_catalogue_is_complete_unique_and_source_bound(self):
        self.assertEqual(len(self.records),12204)
        self.assertEqual(len(self.by_id),len(self.records))
        for r in self.records:
            self.assertEqual(r['source_sha256'],digest(r['source']))
        self.assertEqual(sum(r['locked'] and not r.get('internal_command') for r in self.records),50)
        self.assertEqual(sum(r.get('internal_command',False) for r in self.records),63)

    def test_import_rejects_stale_unknown_duplicate_and_locked_edits(self):
        valid=self.payload()
        changed=json.loads(json.dumps(valid));changed['entries'][0]['source_sha256']='wrong'
        unknown=json.loads(json.dumps(valid));unknown['entries'][0]['id']='unknown'
        duplicate=json.loads(json.dumps(valid));duplicate['entries']*=2
        for payload in [changed,unknown,duplicate,self.payload('db/10/35/1','力量'),{'schema':1,'project':'mcowh-zh','entries':[None]}]:
            with self.assertRaises(ValueError):validate_edits(payload,self.records)

    def test_control_tokens_checked_but_human_line_reflow_allowed(self):
        record={'id':'message/test','source':'\\c[2]Hello <PLAYER>\r\nGoodbye','source_sha256':'hash','kind':'message'}
        payload={'schema':1,'project':'mcowh-zh','entries':[{'id':record['id'],'source_sha256':'hash','translation':'\\c[2]你好 <PLAYER>，再见'}]}
        self.assertEqual(len(validate_edits(payload,[record])),1)
        for target in ['你好 <PLAYER>','\\c[3]你好 <PLAYER>','\\c[2]你好 <PLAYER>\n@erase_save']:
            payload['entries'][0]['translation']=target
            with self.assertRaises(ValueError):validate_edits(payload,[record])

    def test_atomic_import_preserves_existing_edits_and_build_consumes_overlay(self):
        p1=self.payload(translation='修订一')
        other=next(r for r in self.records if not r['locked'] and r['kind']=='message' and '\\' not in r['source'] and '<' not in r['source'] and '$' not in r['source'])
        p2=self.payload(other['id'],'修订二')
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'input.json';output=Path(folder)/'overrides.json'
            source.write_text(json.dumps(p1),encoding='utf8');import_revision(source,output)
            saved=output.read_bytes()
            invalid=json.loads(json.dumps(p2));invalid['entries'][0]['source_sha256']='stale'
            source.write_text(json.dumps(invalid),encoding='utf8')
            with self.assertRaises(ValueError):import_revision(source,output)
            self.assertEqual(output.read_bytes(),saved)
            source.write_text(json.dumps(p2),encoding='utf8');import_revision(source,output)
            edits=validate_edits(json.loads(output.read_text('utf8')),self.records)
            self.assertEqual(len(edits),2)
            row={**other,'translation':'原译文','status':'machine_draft'}
            changed=apply_text_edits([row],edits)[0]
            self.assertEqual(changed['translation'],'修订二')
            self.assertEqual(changed['status'],'curated')
            self.assertEqual(len(list(Path(folder).glob('overrides.backup-*.json'))),1)

    def test_title_menu_ink_height_and_native_canvas_unchanged(self):
        index=json.loads((ROOT/'work/textures/index.json').read_text('utf8'))
        from texture_inventory import decode
        heights={}
        for name,text,limit in [('tx_start','开始',68),('tx_extra','鉴赏',68),('tx_option','设置',68),('tx_exit','退出',68),('tx_new','开始新冒险',48),('tx_continue','继续冒险',48),('tx_vs','与其他勇者对战',48)]:
            entry=next(e for e in index if '/title/'+name+'.png.phyre' in e['name'])
            original,_=decode((ROOT/'work/textures'/f"{entry['id']:03d}.phyre").read_bytes())
            result=render(original,entry['name'],text,Path('C:/Windows/Fonts/NotoSansSC-VF.ttf'))
            self.assertEqual(result.size,original.size)
            x0,y0,x1,y1=result.getbbox();heights[name]=y1-y0
            self.assertLessEqual(y1-y0,limit)
            # Font side bearings differ slightly from the visible ink bounds.
            self.assertLessEqual(abs((x0+x1)/2-original.width/2),3)
        self.assertLessEqual(max(heights[k] for k in ['tx_start','tx_extra','tx_option','tx_exit'])-min(heights[k] for k in ['tx_start','tx_extra','tx_option','tx_exit']),3)


if __name__=='__main__':unittest.main()
