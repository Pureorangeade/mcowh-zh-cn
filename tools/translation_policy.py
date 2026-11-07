"""User preferences enforced both in the editor and during patch builds."""
import re
import json
from pathlib import Path
from functools import lru_cache
from localization import controls

ABBREVIATIONS = {'STR', 'VIT', 'AGI', 'INT', 'WIL', 'CHR', 'LOK', 'LCK', 'CLM', 'SWM',
                 'ATK', 'FOR', 'ARM', 'DEF', 'RED', 'ACC', 'MOV', 'EVA', 'COM', 'CRI', 'ID',
                 'HP', 'ST', 'EN', 'WT', 'LV', 'EXP'}


@lru_cache(maxsize=1)
def confirmed_panel_fields():
    path=Path(__file__).resolve().parents[1]/'translations/panel-attribute-fields.json'
    return json.loads(path.read_text('utf8')).get('fields',{}) if path.exists() else {}


def preserve_abbreviations(entry):
    if entry['kind'] != 'database':
        return False
    fields=confirmed_panel_fields()
    if entry.get('id') in fields:
        from localization import digest
        if digest(entry['source'])!=fields[entry['id']]['source_sha256']:
            raise ValueError('Confirmed panel field source changed: '+entry['id'])
        return False
    plain = entry['source']
    for a, b, _ in reversed(controls(plain)):
        plain = plain[:a] + ' ' + plain[b:]
    words = re.findall(r'[A-Za-z]+', plain)
    if not words or not any(word.upper() in ABBREVIATIONS for word in words):
        return False
    if not all(word.upper() in ABBREVIATIONS or word in {'Lvl', 'Lv', 'Adj', 'Exp'} for word in words):
        return False
    rest = re.sub(r'[A-Za-z0-9\s.,%％+\-:/&()\[\]]', '', plain)
    return not rest


def apply_policy(entries):
    result = []
    for entry in entries:
        if entry['kind']=='choice' and entry['source']=='reset':
            entry={**entry,'translation':'reset','status':'retained_command','locked':True,
                   'internal_command':True,'lock_reason':'选项列表控制指令，不是显示文本'}
        elif entry.get('id') in confirmed_panel_fields():
            # The inherited catalogue already persisted the old lock; remove
            # it only for the exact user-approved, source-bound display fields.
            preserve_abbreviations(entry)  # validates the pinned source hash
            entry={**entry,'locked':False}
            entry.pop('lock_reason',None)
            if entry.get('status')=='retained_abbreviation':entry['status']='untranslated'
        elif preserve_abbreviations(entry):
            entry = {**entry, 'translation': entry['source'], 'status': 'retained_abbreviation',
                     'locked': True, 'lock_reason': '按用户偏好保留属性英文缩写'}
        result.append(entry)
    return result
