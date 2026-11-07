"""Create a resumable local machine draft; never labels it human reviewed.

The development-only model/runtime live in work/, not in player packages.
Control tokens, numeric literals and line endings bypass the translation model.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import time
import unicodedata

from localization import controls, digest, validate
from resources import PROJECT
from translation_policy import apply_policy

MODEL_REVISION = '408d9bc410a388e1d9aef112a2daba955b945255'
GLOSSARY = {
    'Longsword': '长剑', 'Leather Coat': '皮衣', 'Wooden Shield': '木盾',
    'Memoria': '梅莫莉娅', 'Elzite': '艾尔扎石', 'Lapis': '拉比斯',
    'OK': '确认', 'Cancel': '取消', 'Yes': '是', 'No': '否', 'Back': '返回',
    'Continue': '继续', 'Finish': '完成', 'Quit': '退出', 'Retreat': '撤退',
    'Acquire': '获取', 'Expand': '扩建', 'Extend': '扩展', 'Arrange': '布置',
    'Tear&Down': '拆除', 'Save&Game': '保存游戏', 'No&Skip': '不跳过',
    'Skip': '跳过', 'Save': '保存', 'Delete': '删除', 'Play': '播放',
    'Tweet': '发布推文', 'Overwrite': '覆盖', 'Equip': '装备', 'List': '列表',
    'Details': '详情', 'Enchant': '附魔', 'None': '无', 'Reorder': '排序',
    'Drop': '丢弃', 'Attack': '攻击', 'Shoot': '射击', 'Pick Lock': '开锁',
    'Throw Item': '投掷物品', 'Concentrate': '集中', 'Force': '理力',
    'Force powers': '理力技能', 'Armor': '防御', 'Dmg Reduction': '伤害减免',
    'Block chance': '格挡几率', 'HP': '生命', 'ST': '耐力', 'EN': '饱食度',
    'WT': '重量', 'ATK': '攻击', 'FOR': '理力', 'ARM': '防御', 'RED': '减伤',
    'ACC': '命中', 'MOV': '速度', 'EVA': '闪避', 'COM': '连击', 'CRI': '暴击',
    'BGM': '背景音乐', 'SFX': '音效', 'Voice': '语音', 'MAX': '最大',
    'Tutorial': '新手教程', 'Start': '开始', 'Options': '设置', 'Extras': '鉴赏',
    'Level': '等级', 'Distance': '距离', 'Battle': '战斗', 'Assets': '资产',
    'Swordsman': '剑士', 'Knight': '骑士', 'Archer': '弓箭手', 'Pirate': '海盗',
    'Adventurer': '冒险者', 'Hero': '勇者', 'Merchant': '商人', 'Thief': '盗贼'
}
GLOSSARY.update({
    'it': '它', '% EN!': '% 饱食度！', '% without harm.': '% 的敌人，且未受伤。',
    'heavens before': '天际降临在',
    'Negates physical attacks for as long as barrier layers remain.': '屏障仍有层数时，可抵消物理攻击。',
    'Your vision becomes poor and you can\'t see where anything is.': '视野变差，无法看清周围事物的位置。',
    'Increase the number of items you can place in the Dream Vault.': '增加梦幻仓库可存放的物品数量。'
})
GLOSSARY.update({
    'Ha!': '哈！', 'His': '他的', 'Hm!': '哼！', 'Hm?': '嗯？', 'She': '她',
    'Um?': '嗯？', 'she': '她', 'Hey!': '喂！', 'Hmm!': '哼！', 'I am': '我是',
    'Mmm!': '唔！', 'Then': '然后', 'Wait': '等等', ', she': '，她', 'Egh!?': '咦！？',
    'Haha,': '哈哈，', 'Heey!': '喂！', 'Hehe!': '嘿嘿！', 'Help!': '救命！',
    'Huh?!': '啊？！', 'Then,': '然后，', 'WAIT!': '等等！', 'Whoa!': '哇！',
    '...Hm?': '……嗯？', '...Uh?': '……呃？', 'Aaah?!': '啊？！', 'Heheh!': '嘿嘿嘿！',
    'Hmm...': '嗯……', 'Hmmm?!': '嗯？！', 'Whoa?!': '哇？！', 'night.': '夜晚。',
    "you're": '你是', ', wait!': '，等等！', '...Wha?': '……什么？', 'And so,': '于是，',
    'Heey...': '喂……', 'Help...': '救命……', 'Hmmm...': '嗯……', 'If your': '如果你的',
    'Then it': '那么它', 'Warning': '警告', 'You are': '你是', 'Your...': '你的……',
    'He knows': '他知道', 'Hey hey!': '喂，喂！', 'Oh, wow.': '哦，哇。', 'Wow wow!': '哇，哇！',
    'Ah ha ha!': '啊哈哈！', 'Ahhhh!!!!': '啊——！！！！', 'Hey, hey!': '喂，喂！',
    'It is now': '现在是', "It's only": '这只是', 'Reaaally?': '真的吗？', 'Really...': '真的……',
    'Your bag,': '你的背包，', 'Oh, God...': '哦，天哪……', 'You really': '你真的',
    'is nearby.': '就在附近。', 'saved me!!': '救了我！！', 'was really': '真的很',
    'And then...': '然后……', 'If only she': '要是她能', 'Wait, wait!': '等等，等等！',
    'Wait, what?': '等等，什么？', '...Oh, whoa!': '……哦，哇！', 'Heh, hehe...': '嘿，嘿嘿……',
    'true horror!': '真正的恐怖！', 'How on earth!': '怎么会这样！', 'Really juicy!': '真是鲜嫩多汁！',
    'Oof, really...': '唉，真是的……', 'The most recent': '最近的', 'is looking this': '正朝这边看',
    'Fiiiiiine, fine.': '好——吧，好吧。', 'Nrgh, you cur...': '呃，你这混蛋……',
    'An Arc-Manticore?': '一只大蝎尾狮？', 'like this is you,': '这样的人就是你，',
    'Really, well sorry.': '真是的，好吧，对不起。', 'Thank you for paying decently': '谢谢你支付合理的报酬',
    "There are still potions I haven't": '还有一些药水，我尚未',
    "Nowadays you'd say he was a super stud.": '用现在的话来说，他就是个万人迷。',
    "These look like they'll definitely help": '这些东西看起来一定能派上用场',
    'Really bad.': '糟透了。', "You're really": '你真是',
    'Dream Vault': '梦幻仓库', 'Genesis Stones': '创世石', 'Genesis Stone': '创世石',
    'Perks': '天赋', 'Holy Shrine': '圣殿', 'Demon Lord': '魔王', 'Manticore': '蝎尾狮'
})
GLOSSARY.update({
    'Sorcerer': '理术师', 'Half-beast': '兽人', 'Ranger': '游侠', 'Gunner': '枪手',
    'One way Hero': '单向勇者', 'Assassin': '刺客', 'Dark Knight': '暗黑骑士',
    'Brawler': '拳斗士', 'Priest': '祭司', 'Zombie': '僵尸', 'Queen': '女王',
    'Astrologist': '占星术士', 'Samurai': '武士', 'Beast Hunter': '幻兽猎人',
    'Dracon': '龙人', 'Wrestler': '力士', 'Lord': '领主', 'Wanderer': '风来人',
    'Ult. Student': '超高校级', 'Pickaxe': '镐', 'Boomerang': '回旋镖',
    '[Frail] ': '[脆弱] ', '[Tough] ': '[坚韧] ', '[Villainous] ': '[凶恶] ',
    '[Strong] ': '[强壮] ', '[Stubborn] ': '[顽固] ', '[Wanted] ': '[被通缉] ',
    '[Famous] ': '[知名] ', '[Phantom] ': '[幻影] ', '[Rich] ': '[富有] ',
    '[Ancient] ': '[远古] ', '[Stingy] ': '[吝啬] ', '[Greedy] ': '[贪婪] ',
    '[Crazy] ': '[疯狂] ', '[Pesky] ': '[难缠] ', '[Nearsighted] ': '[近视] ',
    '[Seeking] ': '[寻觅] ', '[Strange] ': '[奇异] ', '[Stinky] ': '[恶臭] ',
    '[Fireproof] ': '[耐火] ', '[Lightningproof] ': '[耐雷] ', '[Floating] ': '[漂浮] ',
    '[Frightening] ': '[可怕] ', '[Subordinate] ': '[随从] ', '[Malefic] ': '[邪恶] ',
    '[Mighty] ': '[强大] ', '[Exotic] ': '[异域] ', '[Hairy] ': '[多毛] ',
    '[Persistent] ': '[执着] ', '[Whistling] ': '[吹口哨] ', '[Chubby] ': '[胖乎乎] ',
    '[Happy] ': '[快乐] ', '[Wacky] ': '[古怪] ', '[Scholarly] ': '[博学] ', '[Vagrant] ': '[流浪] ',
    'aaAaanh...': '啊嗯……', 'HmMMmmm!': '嗯——！', 'No, no, no, NOOOO!!!': '不，不，不，不——！！！',
    'Ugh, aaargghh...': '呃，啊——……', '(kkrrrrrrrrrruuuuuuuuurrrrrrhhhh!)': '（咕噜噜——！）',
    'Guffaw, hyuk hyuk hyuk.': '哇哈哈，嘿嘿嘿。', '...\r\n...I understand.': '……\r\n……我明白了。',
    'Ne-eigh...': '咴——……', 'Neeeiiiiighhh!?': '咴——！？', '*Crunch* *crunch*...': '咔嚓，咔嚓……',
    '*Gulp* *gulp*...': '咕嘟，咕嘟……', 'Fwwwwwwaaaaaaaaaaaaaaaahhhhh!!': '呼啊——！！',
    'Om nom nom nom nom.': '啊呜，嚼嚼嚼。', 'Aaaaaaaaeeeeehhh!': '啊——！',
    '...Ughhh...': '……呃……', 'UH HREH HREH HREH!!': '呜，嘿嘿嘿！！', 'Flap, flap, flap!': '扑棱，扑棱，扑棱！'
})
GLOSSARY.update({
    'Half-Beast': '兽人', 'One Way Hero': '单向勇者',
    'Strength UP': '力量提升', 'Agility UP': '敏捷提升', 'Vitality UP': '体质提升',
    'Intellect UP': '智力提升', 'Willpower UP': '意志提升', 'Charisma UP': '魅力提升',
    'Swim Coach': '游泳教练', 'Cliffhanger': '攀岩高手', 'Mileage UP': '里程提升',
    'Fire Resist': '火焰抗性', 'Healthy Living': '健康生活', 'Nimble Fingers': '巧手',
    'Pugilism': '拳术', 'Packing Tricks': '收纳技巧', 'Venture Funds': '冒险资金',
    'Keen Eye': '敏锐目光', 'Shields Up': '举盾防御', 'Deep Cuts': '重创',
    'Loving Care': '悉心照料', 'Accuracy UP': '命中提升', 'Animal Lover': '动物之友',
    'Dream Hunter': '梦境猎人', 'Play it Again': '再来一次', 'Butter Fingers': '笨手笨脚',
    'Stranger': '陌生人', 'I Feel Nothing': '毫无痛感', 'Unremarkable': '平凡无奇',
    'Final Difficulty Unlocked': '已解锁最终难度', 'Hard Mode Unlocked': '已解锁困难模式',
    'Castle Customization': '自定义城堡', 'Castle Customization ': '自定义城堡 ',
    'Completed All Campaigns': '已完成全部活动', 'View Basic Credits': '查看制作人员名单',
    'View Corridor of Dreams credits.': '查看梦之回廊制作人员名单。',
    'Opening': '序章', 'Ending': '结局', 'Credits': '制作人员名单', 'Campaigns': '活动',
    'Skill': '技能', 'Perk': '天赋', 'Enchantment': '附魔', 'Block': '格挡'
})


def checked_fragment(source, target):
    target = unicodedata.normalize('NFC', target)
    try:
        validate(source, target)
        if any(unicodedata.category(c) in {'Co', 'Cn'} for c in target):
            raise ValueError('Model emitted private-use or undefined characters')
        if re.search(r'(.{2,25}?)\1\1\1', target) or len(target) > max(120, len(source) * 5):
            raise ValueError('Repetitive model output')
    except ValueError:
        return source, True
    return target, target == source and bool(re.search('[A-Za-z]', source))


def units(source, kind):
    # Choices use underscores as display spaces in this game's event syntax.
    text = source
    spans = controls(text)
    for match in re.finditer(r'\d+(?:[.,]\d+)*', text):
        a, b = match.span()
        if not any(a < d and b > c for c, d, _ in spans):
            spans.append((a, b, match[0]))
    spans.sort()
    result = []
    previous = 0
    for a, b, token in spans + [(len(text), len(text), '')]:
        plain = text[previous:a]
        if kind == 'choice':
            plain = plain.replace('_', ' ')
        # Long prose is segmented without truncation; preserve edge whitespace.
        chunks = re.split(r'(?<=[.!?])(?=\s)', plain)
        for chunk in chunks:
            while len(chunk) > 600:
                cut = chunk.rfind(' ', 100, 600)
                if cut < 0:
                    cut = 600
                result.extend(plain_unit(chunk[:cut]))
                chunk = chunk[cut:]
            result.extend(plain_unit(chunk))
        if token:
            result.append(('literal', token))
        previous = b
    return result


def plain_unit(text):
    if not text:
        return []
    match = re.fullmatch(r'(\s*)(.*?)(\s*)', text, re.S)
    lead, core, tail = match.groups()
    out = [('literal', lead)] if lead else []
    if core:
        out.append(('translate' if re.search('[A-Za-z]', core) else 'literal', core))
    if tail:
        out.append(('literal', tail))
    return out


def reviewed_sources(entries):
    demo = json.loads((PROJECT / 'translations/demo.zh-CN.json').read_text('utf8'))
    reviewed = dict(demo['ui_labels'])
    reviewed.update(GLOSSARY)
    by_id = {e['id']: e for e in entries}
    for key, value in demo['database'].items():
        if key in by_id:
            reviewed[by_id[key]['source']] = value
    for changes in demo['scripts'].values():
        for change in changes:
            reviewed[change['source']] = change['target']
    return reviewed


def main(args):
    entries = [json.loads(line) for line in args.catalogue.read_text('utf8').splitlines()]
    reviewed = reviewed_sources(entries)
    plans = {e['id']: units(e['source'], e['kind']) for e in entries if e['source'] not in reviewed}
    cache_path = PROJECT / 'work/translation/mt-fragments.jsonl'
    cache = {}
    if cache_path.exists():
        for line in cache_path.read_text('utf8').splitlines():
            item = json.loads(line)
            if item['model_revision'] == MODEL_REVISION:
                cache[item['source']] = item['translation']
    needed = {text for plan in plans.values() for kind, text in plan if kind == 'translate'}
    cache.update({k: v for k, v in reviewed.items() if k in needed})
    pending = sorted(needed - cache.keys(), key=lambda text: (len(text), text))
    print(f'{len(entries)} entries, {len(needed)} unique fragments, {len(pending)} awaiting local translation', flush=True)
    if pending:
        # Reuse host Torch and NumPy; isolate the optional translation packages.
        import numpy  # noqa: F401
        sys.path.insert(0, str(PROJECT / 'work/mt-runtime'))
        import transformers.utils.import_utils as optional
        optional._sklearn_available = False
        optional._librosa_available = False
        optional._torchvision_available = False
        from transformers import MarianMTModel, MarianTokenizer
        import torch
        torch.set_num_threads(4)
        model_path = PROJECT / 'work/models/opus-mt-en-zh'
        tokenizer = MarianTokenizer.from_pretrained(model_path, local_files_only=True)
        model = MarianMTModel.from_pretrained(model_path, local_files_only=True).to('cuda').half().eval()
        started = time.monotonic()
        with cache_path.open('a', encoding='utf8', newline='\n') as log:
            for offset in range(0, len(pending), args.batch_size):
                batch = pending[offset:offset + args.batch_size]
                inputs = tokenizer(['>>cmn_Hans<< ' + t for t in batch], padding=True, return_tensors='pt').to('cuda')
                if inputs.input_ids.shape[1] > 500:
                    raise ValueError('Oversized source fragment; split it rather than truncate')
                with torch.inference_mode():
                    output = model.generate(**inputs, num_beams=3, max_new_tokens=220, early_stopping=True)
                translated = tokenizer.batch_decode(output, skip_special_tokens=True)
                for source, target, tokens in zip(batch, translated, output, strict=True):
                    if int(tokens[-1]) not in {tokenizer.eos_token_id, tokenizer.pad_token_id}:
                        raise ValueError('Incomplete model output')
                    if not target.strip():
                        # Isolated letters/particles occasionally decode empty.
                        # Retain them visibly for review rather than delete text.
                        target = source
                    cache[source] = target
                    log.write(json.dumps({'source': source, 'translation': target,
                        'model_revision': MODEL_REVISION}, ensure_ascii=False) + '\n')
                log.flush()
                count = min(offset + len(batch), len(pending))
                print(f'translated {count}/{len(pending)} fragments, {time.monotonic() - started:.1f}s', flush=True)
    stats = Counter()
    review_entries = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', encoding='utf8', newline='\n') as stream:
        for entry in entries:
            if entry['source'] in reviewed:
                target = reviewed[entry['source']]
                status = 'curated'
            else:
                parts = [checked_fragment(text, cache[text]) if kind == 'translate' else (text, False)
                         for kind, text in plans[entry['id']]]
                target = ''.join(text for text, _ in parts)
                status = 'machine_draft'
                if any(flag for _, flag in parts):
                    status = 'machine_draft_needs_review'
                    review_entries.append(entry['id'])
            if entry['kind'] == 'choice':
                target = re.sub(r'\s+', '_', target)
            validate(entry['source'], target, single_argument=entry['kind'] == 'choice',
                     preserve_linebreaks=status != 'curated')
            item = {**entry, 'translation': target, 'status': status}
            if target == entry['source']:
                item['status'] = 'retained_for_review'
            item = apply_policy([item])[0]
            stats[item['status']] += 1
            stream.write(json.dumps(item, ensure_ascii=False) + '\n')
    report = {'model': 'Helsinki-NLP/opus-mt-en-zh', 'revision': MODEL_REVISION,
              'source': 'https://huggingface.co/Helsinki-NLP/opus-mt-en-zh',
              'inference': 'local CUDA; no game text sent to external translation services',
              'statuses': dict(stats), 'full_game_localization_complete': False,
              'flagged_entry_ids': review_entries,
              'note': 'Broad text draft. Images, executable strings and remaining review are separate.'}
    args.out.with_suffix('.report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k != 'flagged_entry_ids'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalogue', type=Path, default=PROJECT / 'work/translation/full-catalogue.jsonl')
    p.add_argument('--out', type=Path, default=PROJECT / 'translations/full.zh-CN.jsonl')
    p.add_argument('--batch-size', type=int, default=48)
    args=p.parse_args()
    policy_path=PROJECT/'translations/translation-workflow.json'
    if policy_path.exists() and json.loads(policy_path.read_text('utf8')).get('method')=='current_online_chat_llm':
        p.error('本项目已按用户要求切换到聊天大模型逐条重译，旧本地机翻生成入口已停用。请使用 llm_workflow.py 查看重译队列与进度。')
    main(args)
