"""Validated, source-bound user edits kept separate from generated translations."""
import json
from pathlib import Path
from localization import digest, validate
from translation_policy import apply_policy
from resources import Archive, PROJECT
from formats import database_fields, unpack_text_dictionary
from render_textures import text_for

OVERRIDES = PROJECT / 'translations/user-overrides.json'

IMAGE_ENGLISH = {
 'tx_exit':'Quit','tx_start':'Start','tx_press_steam':'Press Any Key','tx_new':'NEW',
 'tx_press':'Press Any Button','tx_option':'Options','tx_vs':'Battle Other Heroes','tx_extra':'Extras',
 'tx_continue':'Continue Quest','tx_playable':'Unlock Full Version', 'tx_buy':'Buy',
 'tx_clear':'Clear','tx_type':'Type','tx_wt_01':'WT','tx_turn':'Turn', 'tx_performance':'PERFORMANCE',
 'tx_details':'DETAILS','tx_select':'Select','tx_status':'STATUS','tx_perks':'PERKS','tx_return':'Return',
 'tx_gift':'GIFT','tx_attention':'ATTENTION','tx_dialog':'Dialog','tx_sell':'Sell','tx_ability':'ABILITY',
 'tx_platform':'PLATFORM','tx_cost':'Cost','tx_enchant':'ENCHANT','tx_world':'WORLD','tx_silver':'Lapis',
 'tx_party':'PARTY','tx_wt':'WT','tx_list':'List','tx_equipment':'EQUIPMENT','tx_quantity':'Quantity',
 'tx_condition':'CONDITIONS','tx_distance02':'Rival Distance','tx_km':'km','tx_distance':'Distance','tx_day':'day(s)',
 'tx_equip':'Equip','tx_system':'System','tx_item2':'Stored Items','tx_reward':"Heroes' Rewards",
 'tx_foot2':'Items on the Ground','tx_item':'Items','tx_log':'Log','tx_depot':'Dream Vault',
 'tx_not':'*Does not include effects','tx_foot':'Position','tx_skill':'Skill','tx_baggage':'Transport',
 'tx_world_mini':'World','tx_difficulty':'Select Difficulty','tx_demolition':'Demolish Room',
 'tx_movie':'Watch Movies','tx_build':'Expand Room','tx_cross':'Cross-Save','tx_search':'Search Rooms',
 'tx_twitter':'Twitter Settings','tx_point':'Genesis Room','tx_upload':'Upload','tx_exchange':'Spirit Room',
 'tx_set':'Make Room','tx_playback':'View Replays','tx_controller':'Controller Settings','tx_download':'Download',
 'tx_ex':'Extras','tx_vs_record':'Match Evaluation','tx_record':'Match Records','tx_comment':'Evaluation Comments',
 'tx_operation_b':'Controls Type B','tx_replay':'Replay','tx_castle':'Customize Castle','tx_special':'Get New Special',
 'tx_offcampaign':'Offline Campaign Worlds','tx_special2':'View Specials','tx_epilogue':'View Epilogue',
 'tx_sound':'Sound Settings','tx_operation_a':'Controls Type A','tx_name':'Change Name','tx_newclass':'Get New Classes',
 'tx_bgm':'Listen to BGM','tx_chara':'Select Character','tx_operate':'Control Settings','tx_load':'Load',
 'tx_appoint':'Specify World Name','tx_history':'Explored Worlds','tx_wait':'Match Room','tx_campaign':'Campaign Worlds',
 'tx_recorder':'KOs','tx_medal':'View Medals','tx_resident':'Arrange Residents','tx_result':'Quest Evaluation',
 'tx_limit':'Select Rules','tx_keyboard':'Keyboard Settings','tx_ready':'Prepare for Quest','tx_save':'Save',
 'tx_memory':'Adventure Records','tx_data':'Class Records','tx_picture':'Screen Settings','tx_class':'Select Class',
 'tx_random':'Random','tx_winner':'Conquering Heroes','tx_newperks':'Get New Perks','tx_playback02':'View Match Replays',
 'tx_vs2':"'s Match",'tx_replay02':'Match Replays', 'tx_cancel_def':'Cancel','tx_cancel_select':'Cancel',
 'tx_delete_def':'Delete 1ch','tx_delete_select':'Delete 1ch','tx_random_select':'Random','tx_random_def':'Random',
 'tx_fix_def':'Confirm','tx_fix_select':'Confirm','tx_key_small_letter_off':'Lowercase','tx_key_small_letter':'Lowercase',
 'tx_totalget_stone_vs':'Obtained Spirit Stones','tx_stoneunit_s':'piece(s)','tx_stoneunit_l':'piece(s)',
 'tx_totalget_stone':'Obtained Genesis Stones'
}
IMAGE_EXACT = {
 'title/tx_new':'Start a New Quest', 'ready/tx_world':'Select World', 'ready/tx_perks':'Select Perks',
 'ready/tx_system':'System Settings','ready/tx_depot':'Open Dream Vault','game_menu/tx_buy':'Shop List'
}
IMAGE_EXACT.update({'common/icon/ic_'+n:en for n,en in {
    'hp':'HP','st':'ST','en':'EN','hp_02':'HP','st_02':'ST','en_02':'EN','lv':'Lv','exp':'Exp'}.items()})
IMAGE_EXACT.update({'game_main/base_06_2':'Lv / HP / ST / EN','game_main/base_03':'WT','game_main/tx_lv':'Lv'})


def category(entry):
    if entry['kind'] != 'database':
        return {'message':'剧情与事件', 'choice':'对话选项', 'button':'界面按钮'}.get(entry['kind'], '其他')
    table = int(entry['id'].split('/')[1])
    if table == 72 and entry['id'].endswith('/1'):
        return '序章与结尾'
    if table == 1:
        return '技能'
    if table in {3,4,5,6,8,9,10,11}:
        return '物品与装备'
    if table == 13:
        return '状态效果'
    if table in {28,30,37,38,42,69,70,71}:
        return '角色与天赋'
    return '系统与界面'


def base_catalogue():
    entries = apply_policy([json.loads(s) for s in (PROJECT/'translations/full.zh-CN.jsonl').read_text('utf8').splitlines()])
    records = []
    for e in entries:
        context = e.get('context', {})
        records.append({'id':e['id'], 'source':e['source'], 'translation':e['translation'],
            'source_sha256':e['source_sha256'], 'kind':e['kind'], 'category':category(e),
            'location':e.get('script') or ' / '.join(str(context.get(k,'')) for k in ['table','row','field']),
            'status':e['status'], 'locked':e.get('locked',False), 'context':context,
            'internal_command':e.get('internal_command',False)})
    arc = Archive(PROJECT/'work/clean-fixture')
    by_name = {e.name:e for e in arc.entries}
    system = json.loads((PROJECT/'translations/system.zh-CN.json').read_text('utf8'))
    for filename, changes in system.items():
        path = 'd3d11/data/'+('basicdata/' if filename=='cdatabase.dat' else '')+filename
        raw = arc.read(by_name[path])
        sources = {f.id:f.text for f in database_fields(raw)} if filename=='cdatabase.dat' else dict(unpack_text_dictionary(raw))
        for key, translation in changes.items():
            source = sources[key]
            records.append({'id':f'system/{filename}/{key}', 'source':source, 'translation':translation,
                'source_sha256':digest(source), 'kind':'system', 'category':'存档与系统提示',
                'location':filename+' / '+key, 'status':'curated', 'locked':False})
    translations = json.loads((PROJECT/'translations/textures.zh-CN.json').read_text('utf8'))
    index = json.loads((PROJECT/'work/textures/index.json').read_text('utf8'))
    classes = {e['id']:e['source'] for e in entries}
    for item in index:
        target = text_for(item['name'], translations)
        if not target or not item['supported']:
            continue
        relative = item['name'].split('/sc_ui/')[1].removesuffix('.png.phyre')
        name = relative.rsplit('/',1)[-1]
        source = IMAGE_EXACT.get(relative, IMAGE_ENGLISH.get(name))
        if relative.startswith('ready/class_tx/'):
            number = int(name.split('_')[1])
            source = classes[f'db/28/{100+number}/0']
        elif relative.startswith('ex/class_data/'):
            source = ['Perfect!','Excellent!','Great!','Nice!','Good','Newbie'][int(name[-1])]
        if source is None:
            raise ValueError('Missing English image caption: '+relative)
        records.append({'id':'image/'+item['name'], 'source':source, 'translation':target,
            'source_sha256':digest(source), 'kind':'image', 'category':'界面图片文字',
            'location':relative, 'status':'curated', 'locked':False})
    if len({r['id'] for r in records}) != len(records):
        raise ValueError('Duplicate editor IDs')
    from japanese_sources import annotate_japanese
    annotate_japanese(records)
    return records


def check_edit(record, edit):
    if edit.get('source_sha256') != record['source_sha256']:
        raise ValueError('英文原文版本不匹配：'+record['id'])
    target = edit.get('translation')
    if not isinstance(target,str) or not target.strip() or len(target)>40000:
        raise ValueError('译文为空或过长：'+record['id'])
    target.encode('utf8')
    if record.get('locked') and target != record['source']:
        raise ValueError(('此条为程序指令，必须保留原样：' if record.get('internal_command') else '此条按约定保留英文缩写：')+record['id'])
    validate(record['source'], target, single_argument=record['kind']=='choice', preserve_linebreaks=False)
    if record['kind']=='image' and ('\n' in target or '\r' in target):
        raise ValueError('图片文字必须为一行：'+record['id'])


def validate_edits(payload, records):
    if not isinstance(payload,dict) or payload.get('schema')!=1 or payload.get('project')!='mcowh-zh':
        raise ValueError('不是本项目的译文修订文件')
    entries = payload.get('entries')
    if not isinstance(entries,list) or len(entries)>20000:
        raise ValueError('无效的修订列表')
    by_id = {r['id']:r for r in records}
    result = {}
    for edit in entries:
        if not isinstance(edit,dict):
            raise ValueError('无效的修订条目')
        key = edit.get('id')
        if key not in by_id or key in result:
            raise ValueError('未知或重复条目：'+str(key))
        check_edit(by_id[key], edit)
        result[key] = edit
    return result


def load_edits(records=None, path=OVERRIDES):
    if not path.exists():
        return {}
    return validate_edits(json.loads(path.read_text('utf8')), records or base_catalogue())


def validate_review_decisions(payload, records):
    decisions=payload.get('review_decisions',[])
    if not isinstance(decisions,list) or len(decisions)>20000:
        raise ValueError('无效的终审标记列表')
    by_id={r['id']:r for r in records}; result={}
    for decision in decisions:
        if not isinstance(decision,dict):
            raise ValueError('无效的终审标记')
        key=decision.get('id'); record=by_id.get(key)
        if not record or key in result or record.get('locked'):
            raise ValueError('未知、重复或已锁定的终审条目：'+str(key))
        if decision.get('source_sha256')!=record['source_sha256']:
            raise ValueError('终审标记的英文原文版本不匹配：'+key)
        if decision.get('status') not in {'deferred_final','resolved'} or decision.get('scope')!='entry':
            raise ValueError('无效的终审状态：'+key)
        if not isinstance(decision.get('reason'),str) or len(decision['reason'])>2000:
            raise ValueError('终审原因为空或过长：'+key)
        result[key]=decision
    return result


def load_review_decisions(records=None, path=OVERRIDES):
    if not path.exists():return {}
    return validate_review_decisions(json.loads(path.read_text('utf8')),records or base_catalogue())


def load_effective_edits(records=None, path=OVERRIDES):
    """Keep drafts intact; an unresolved whole entry ships its English source."""
    records=records or base_catalogue()
    edits=load_edits(records,path)
    decisions=load_review_decisions(records,path)
    for record in records:
        if decisions.get(record['id'],{}).get('status')=='deferred_final':
            edits[record['id']]={'id':record['id'],'source_sha256':record['source_sha256'],
                'translation':record['source'],'translation_method':'user_deferred_retention',
                'review_status':'deferred_final','human_reviewed':False}
    return edits


def apply_text_edits(entries, edits):
    output = []
    for entry in apply_policy(entries):
        if entry['id'] in edits:
            edit=edits[entry['id']]
            entry = {**entry, 'translation':edit['translation'], 'status':'curated',
                     'translation_method':edit.get('translation_method','user_edit'),
                     'review_status':edit.get('review_status','user_revision'),
                     'human_reviewed':edit.get('human_reviewed',False),
                     'edited_by_user':edit.get('translation_method')!='current_online_chat_llm'}
        output.append(entry)
    return output
