"""Route trophy predicates to the already normalized, local flag snapshot.

0.3.4 normalized cself[8], but only the class-unlock gate read that variable.
All actual badge predicates still inspected global S0. Patch only their string
variable operands; do not modify S0, saved data, predicates, or icon generation.
"""
import hashlib
import struct
from common_events import parse

EVENTS = {741: 15, 806: 15, 846: 15}
GLOBAL_FLAGS = 0x20000000 | 3000000
LOCAL_FLAGS = 0x20000000 | 1600008


def patch(data):
    events = parse(data)
    out = bytearray(data)
    changes = []
    for event in events:
        if event['id'] not in EVENTS:
            continue
        count = 0
        for index, command in enumerate(event['commands']):
            if command['cid'] != 112 or GLOBAL_FLAGS not in command['args'][1:]:
                continue
            args = command['args']
            assert len(args) - 1 == (args[0] & 15)
            assert len(command['strings']) == 4
            assert all(s.startswith('[\\cself[') and '<\\s[41]>' in s
                       for s in command['strings'][:len(args)-1])
            assert all(a == GLOBAL_FLAGS for a in args[1:])
            operands = []
            for operand in range(1, len(args)):
                # Byte operand-count, uint32 opcode, then uint32 operands.
                at = command['offset'] + 5 + 4 * operand
                assert struct.unpack_from('<I', out, at)[0] == GLOBAL_FLAGS
                struct.pack_into('<I', out, at, LOCAL_FLAGS)
                operands.append(operand)
            changes.append({'event': event['id'], 'command': index,
                            'operand_indexes': operands,
                            'strings': command['strings']})
            count += 1
        assert count == EVENTS[event['id']], (event['id'], count)
    assert len(changes) == sum(EVENTS.values())
    result = bytes(out)
    after = parse(result)
    changed_keys = {(c['event'], c['command']) for c in changes}
    for before_event, after_event in zip(events, after, strict=True):
        assert len(before_event['commands']) == len(after_event['commands'])
        if before_event['id'] not in EVENTS:
            assert data[before_event['offset']:before_event['end']] == result[after_event['offset']:after_event['end']]
        for i, (old, new) in enumerate(zip(before_event['commands'], after_event['commands'], strict=True)):
            if (before_event['id'], i) in changed_keys:
                expected = dict(old, args=[old['args'][0]] + [LOCAL_FLAGS] * (len(old['args'])-1))
                assert new == expected
            else:
                assert old == new
    return result, {
        'source_sha256': hashlib.sha256(data).hexdigest(),
        'target_sha256': hashlib.sha256(result).hexdigest(),
        'changed_events': sorted(EVENTS), 'changed_predicates': len(changes),
        'changed_operands': sum(len(c['operand_indexes']) for c in changes),
        'source_variable': 'S0', 'target_variable': 'cself[8]',
        'changes': changes, 'length_unchanged': len(data) == len(result),
        'all_other_event_bytes_unchanged': True,
        'global_variables_and_save_records_not_written': True,
        'runtime_verified': False,
    }
