"""Display-only compatibility for historical English clear flags and death text."""
from collections import defaultdict
import hashlib
from common_events import parse,encode_command,insert_before

TROPHY_EVENTS={741,806,846}
DEATH_EVENTS={372,598}

def replacement(variable,source,target,indent=0):
    return encode_command(122,[variable,2304],[source,target],indent)


def class_aliases(english,current):
    result=[]
    for row in range(101,126):
        key=f'db/28/{row}/0';source=english[key];target=current[key]
        assert source and target and all(c not in source+target for c in ['[',']','\\','\n'])
        if source!=target:result.append((source,target,row))
    # Match a complete class prefix, never a substring such as Knight in Dark Knight.
    return sorted(result,key=lambda x:(-len(x[0]),x[0]))


def enemy_aliases(english,current):
    values=defaultdict(set)
    for key,source in english.items():
        if key.startswith('db/22/') and key.endswith('/0') and source and current[key]!=source:
            values[source].add(current[key])
    # Ambiguous labels remain visible in English rather than picking a wrong enemy.
    safe=[(a,next(iter(bs))) for a,bs in values.items() if len(bs)==1
          and not any(c in a+next(iter(bs)) for c in ['\\','<','>','\n','\r'])]
    return sorted(safe,key=lambda x:(-len(x[0]),x[0]))


def patch(data,english,current):
    events=parse(data);insertions={};classes=class_aliases(english,current)
    monsters=enemy_aliases(english,current)
    static=[(english[f'db/32/{r}/3'],current[f'db/32/{r}/3']) for r in range(1,17)]
    generic='been killed by \\c[51]'
    proofs=[]
    for event in events:
        eid=event['id'];commands=event['commands']
        if eid in TROPHY_EVENTS:
            command=commands[4]
            assert command['cid']==221 and command['args']==[1600008,1600009,3000000,0]
            assert commands[6]['strings']==['[初期]']
            extra=[replacement(1600008,'['+a+'で','['+z+'で',command['indent']) for a,z,_ in classes]
            insertions[(eid,5)]=extra
            proofs.append({'event':eid,'name':event['name'],'after_original_command':4,
                'variable':'cself[8] (local loaded flag string)','added_commands':len(extra),'writes_save':False})
        if eid in DEATH_EVENTS:
            for i,command in enumerate(commands):
                if command['cid']!=122 or command['strings']!=['$dead','\\s[5]']:continue
                variable=command['args'][0];indent=command['indent']
                assert command['args'][1]==2304 and variable in {1600007,1600008}
                extra=[replacement(variable,a,z,indent) for a,z in static if a!=z]
                # Only legacy, generic English death messages enter the monster loop.
                extra.extend([encode_command(112,[1,0x20000000|variable],[generic,'','',''],indent),
                              encode_command(401,[1],[],indent)])
                extra.append(replacement(variable,generic,'死于\\c[51]',indent+1))
                extra.extend(replacement(variable,'\\c[51]'+a+'\\c[0]','\\c[51]'+z+'\\c[0]',indent+1) for a,z in monsters)
                extra.extend([encode_command(0,[],[],indent+1),encode_command(499,[],[],indent)])
                insertions[(eid,i+1)]=extra
                proofs.append({'event':eid,'name':event['name'],'after_original_command':i,
                    'variable':f'cself[{variable-1600000}] (local rendered message)','added_commands':len(extra),
                    'writes_save':False,'system_s5_unchanged':True})
    assert len([p for p in proofs if p['event'] in TROPHY_EVENTS])==3
    assert len([p for p in proofs if p['event'] in DEATH_EVENTS])==4
    modified=insert_before(data,insertions)
    return modified,{'source_sha256':hashlib.sha256(data).hexdigest(),
        'target_sha256':hashlib.sha256(modified).hexdigest(),'events':proofs,
        'class_aliases':classes,'legacy_static_death_templates':len(static),
        'unambiguous_enemy_aliases':len(monsters),'game_or_save_files_modified':False,
        'runtime_verified':False,'note':'Only local strings are changed. Existing and new Chinese flags both match; unknown enemy names stay visible.'}
