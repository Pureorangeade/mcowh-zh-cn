# SPDX-License-Identifier: MPL-2.0
# Format reader adapted from wolftrans by elizagamedev and contributors.
# Source: https://github.com/elizagamedev/wolftrans (MPL-2.0).
"""Lossless structural reader for this build's WOLF common events.

The command layout was cross-checked against wolftrans's documented reader:
https://github.com/elizagamedev/wolftrans/blob/master/lib/wolfrpg/command.rb
All untouched event bytes remain verbatim; only explicitly selected command
sequences and their command counts can be replaced. Not a general serializer.
"""
import struct

MAGIC=bytes.fromhex('005700004f4c004643008f')

def parse(data):
    b=data;p=len(MAGIC)
    if not b.startswith(MAGIC):raise ValueError('Unsupported common events')


    def take(n):
        nonlocal p
        if n<0 or p+n>len(b):raise ValueError('Truncated common event')
        value=b[p:p+n]
        p+=n
        return value

    def integer():return struct.unpack('<I',take(4))[0]
    def byte():return take(1)[0]
    def expect(value):
        if take(len(value))!=value:raise ValueError(f'Unexpected event marker at {p:#x}')

    def string():
        size=integer()
        if not 1<=size<=len(b)-p:raise ValueError('Invalid common-event string size')
        value=take(size)
        if value[-1:]!=b'\0':raise ValueError('Missing common-event string terminator')
        return value[:-1].decode('utf8')

    def command():
        start=p
        size=byte()
        if size<1:raise ValueError('Invalid command operand count')
        cid=integer()
        args=[integer() for _ in range(size-1)]
        indent=byte()
        strings=[string() for _ in range(byte())]
        tail=byte()
        if tail==1:
            take(6)
            for _ in range(integer()):
                byte()
                take(4*byte())
                expect(b'\x01\0')
        elif tail!=0:raise ValueError('Unsupported command tail')
        return {'offset':start,'end':p,'cid':cid,'args':args,'indent':indent,'strings':strings}

    count=integer()
    if count!=1000:raise ValueError('Unsupported common-event count')
    events=[]
    for _ in range(count):
        start=p
        expect(b'\x8e')
        eid=integer()
        integer()
        take(7)
        name=string()
        count_offset=p
        commands=[command() for _ in range(integer())]
        string();string();expect(b'\x8f')
        expect(b'\x0a\0\0\0')
        for _ in range(10):string()
        expect(b'\x0a\0\0\0');take(10)
        expect(b'\x0a\0\0\0')
        for _ in range(10):
            for _ in range(integer()):string()
        expect(b'\x0a\0\0\0')
        for _ in range(10):take(integer()*4)
        take(29)
        for _ in range(100):string()
        expect(b'\x91');string()
        end=byte()
        if end==0x92:
            string();integer();expect(b'\x92')
        elif end!=0x91:raise ValueError('Unsupported common-event metadata tail')
        events.append({'id':eid,'name':name,'offset':start,'end':p,
                       'count_offset':count_offset,'commands':commands})
    expect(b'\x8f')
    if p!=len(b):raise ValueError('Unexpected common-event trailer')
    if len({e['id'] for e in events})!=count:raise ValueError('Duplicate common-event ID')
    return events


def encode_command(cid,args=(),strings=(),indent=0):
    if not 0<=indent<=255 or not 0<len(args)+1<=255 or len(strings)>255:
        raise ValueError('Invalid common-event command')
    result=bytes([len(args)+1])+struct.pack('<I',cid)
    result+=b''.join(struct.pack('<I',v & 0xffffffff) for v in args)
    result+=bytes([indent,len(strings)])
    for text in strings:
        raw=text.encode('utf8')
        if b'\0' in raw:raise ValueError('NUL in common-event string')
        result+=struct.pack('<I',len(raw)+1)+raw+b'\0'
    return result+b'\0'


def insert_before(data,insertions):
    """Map (event ID, original command index) to already encoded commands."""
    events=parse(data);changes=[]
    for event in events:
        added=0
        for i,c in enumerate(event['commands']):
            extra=insertions.get((event['id'],i),[])
            if extra:changes.append((c['offset'],c['offset'],b''.join(extra)));added+=len(extra)
        if added:
            at=event['count_offset']
            changes.append((at,at+4,struct.pack('<I',len(event['commands'])+added)))
    expected=set(insertions)
    actual={(e['id'],i) for e in events for i in range(len(e['commands'])) if (e['id'],i) in insertions}
    if expected!=actual:raise ValueError('Unknown command insertion point')
    out=data
    for a,z,replacement in sorted(changes,reverse=True):out=out[:a]+replacement+out[z:]
    updated=parse(out)
    # Every original command retains its opcode, operands, strings and nesting.
    for before,after in zip(events,updated,strict=True):
        cursor=0
        for i,c in enumerate(before['commands']):
            cursor+=len(insertions.get((before['id'],i),[]))
            assert all(c[k]==after['commands'][cursor][k] for k in ['cid','args','strings','indent'])
            cursor+=1
        assert cursor==len(after['commands'])
    return out
