"""Validate an isolated Japanese fixture and align display text to English IDs."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from editing import base_catalogue
from formats import database_fields,project_context,unpack_scripts,unpack_text_dictionary
from localization import digest,script_spans
from resources import Archive,PROJECT,sha256

VERSION='Steam build 1527978; JP manifest 6676882424485310473'
ORIGIN='Steam Japanese content depot 409003'
REQUIRED=['D3D11/Data/archive.bin','D3D11/Data/data0100.bin','D3D11/Data/data0200.bin',
          'D3D11/Data/data0500.bin','D3D11/Data/data1200.bin']


def decode_script(raw):
    for encoding in ['utf8','cp932']:
        try:return raw.decode(encoding),encoding
        except UnicodeDecodeError:pass
    raise ValueError('Script is neither UTF-8 nor CP932')


def display_spans(text):
    """Japanese choice labels may contain spaces; branch IDs stay outside text."""
    for kind,index,a,b,source in script_spans(text):
        if kind=='choice':
            line_end=text.find('\n',a)
            line_end=len(text) if line_end<0 else line_end
            line=re.sub(r'[ \t]+#.*','',text[a:line_end]).rstrip('\r')
            if line.strip()=='reset':
                yield kind,index,a,b,source
                continue
            label=re.fullmatch(r'(.*?)[ \t]+-?\d+[ \t]*',line)
            if not label:raise ValueError('Unrecognized choice branch')
            source=label[1].rstrip();b=a+len(source)
        yield kind,index,a,b,source


def script_signature(text, ui=False):
    """Check command order and branches, allowing localized text and UI geometry."""
    for kind,index,a,b,source in sorted(display_spans(text),key=lambda s:s[2],reverse=True):
        text=text[:a]+'<TEXT_'+kind+'>'+text[b:]
    lines=[]
    for line in text.lstrip('\ufeff').splitlines():
        line=line.strip()
        if not line or line.startswith(('#','//')):continue
        line=re.sub(r'[ \t]+#.*','',line).rstrip()
        if ui:
            if line.startswith(('Caption:','Text:')):
                name=line.split(':',1)[0]
                line=name+':<TEXT> '+','.join(re.findall(r'\$[A-Za-z][A-Za-z0-9]*',line))
            elif line.startswith('Size:'):line='Size:<GEOMETRY>'
            elif line.startswith('Button:'):
                values=line.split(',')
                if len(values)<6:raise ValueError('Invalid UI button')
                line='Button:<GEOMETRY>,'+','.join(values[4:])
        lines.append(re.sub(r'\s+',' ',line))
    return '\n'.join(lines)


def read(arc,name):
    entry=next((e for e in arc.entries if e.name==name),None)
    if entry is None:raise ValueError('Missing resource '+name)
    return arc.read(entry)


def atomic_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.extracting.tmp')
    with temp.open('x',encoding='utf8') as stream:json.dump(payload,stream,ensure_ascii=False,indent=2)
    temp.replace(path)


def extract(japanese, english, output, report_path):
    japanese=japanese.resolve();english=english.resolve()
    if japanese in {PROJECT.parent.resolve(),english}:
        raise ValueError('Use a separate Japanese fixture, never the live game')
    files=[]
    for name in REQUIRED:
        path=japanese/name
        if not path.is_file():raise ValueError('Missing downloaded file: '+str(path))
        files.append({'path':name,'size':path.stat().st_size,'sha256':sha256(path)})
    ja,en=Archive(japanese),Archive(english)
    # Every selected resource group is complete and decompresses before publishing.
    selected_groups={g['index'] for g in ja.groups if (japanese/'D3D11/Data'/g['name']).exists()}
    checked=0
    for group in selected_groups:
        info=ja.groups[group]
        if (japanese/'D3D11/Data'/info['name']).stat().st_size!=info['size']:
            raise ValueError('Japanese resource group has a wrong length: '+info['name'])
    for entry in ja.entries:
        if entry.group in selected_groups:ja.read(entry);checked+=1
    db_name='d3d11/data/basicdata/database.dat'
    edb,jdb=database_fields(read(en,db_name)),database_fields(read(ja,db_name))
    if [(f.id,f.field_index) for f in edb]!=[(f.id,f.field_index) for f in jdb]:
        raise ValueError('Database storage IDs or field layout differ')
    em,jm=(project_context(read(arc,'d3d11/data/basicdata/database.project')) for arc in [en,ja])
    layout=lambda m:[(t['name'],t['fields'],t['types'],len(t['rows'])) for t in m]
    if layout(em)!=layout(jm):raise ValueError('Database table or field metadata differ')
    edb={f.id:f.text for f in edb};jdb={f.id:f.text for f in jdb}
    if not any(re.search('[\u3040-\u30ff]',jdb.get(key,'')) for key in ['db/3/0/0','db/6/35/0']):
        raise ValueError('Expected Japanese display text is absent')
    records=base_catalogue();entries=[];unmatched=[];counts=Counter();scripts={};script_stats={}

    def add(record,text,resource,method,encoding='utf8',details=None):
        if not text.strip():
            unmatched.append({'id':record['id'],'reason':'Japanese field is empty'});return
        entries.append({'id':record['id'],'source_sha256':record['source_sha256'],'text':text,
            'kind':'verified_display','origin':ORIGIN,'version':VERSION,'resource':resource,
            'japanese_sha256':digest(text),'encoding':encoding,
            'alignment':{'method':method,'semantic_review':'pending',**(details or {})}})
        counts[record['kind']]+=1

    for resource in ['d3d11/data/event/event.pack','d3d11/data/uiscript/uiscript.pack']:
        se,sj=(dict(unpack_scripts(read(arc,resource))) for arc in [en,ja])
        stats=Counter()
        needed={r['location'] for r in records if r['kind'] in {'message','choice','button'} and r['location'] in se}
        for name in sorted(needed):
            if name not in sj:stats['missing_file']+=1;continue
            te,ee=decode_script(se[name]);tj,ej=decode_script(sj[name])
            original=list(script_spans(te));translated=list(display_spans(tj))
            if [s[0] for s in original]!=[s[0] for s in translated]:
                stats['span_sequence_differs']+=1;continue
            if script_signature(te,ui='uiscript' in resource)!=script_signature(tj,ui='uiscript' in resource):
                stats['command_signature_differs']+=1;continue
            for ordinal,(source,target) in enumerate(zip(original,translated)):
                key=f'{source[0]}/{name}/{source[1]}'
                scripts[key]=(source[4],target[4],resource,ej,{'script':name,'slot':ordinal,
                    'japanese_slot_index':target[1],'command_signature_sha256':digest(script_signature(te,ui='uiscript' in resource))})
            stats['aligned_files']+=1;stats['Japanese_'+ej]+=1
        script_stats[resource]=dict(stats)
    system={}
    for filename in ['cdatabase.dat','text_dict.bin','error_code_dict.bin']:
        resource='d3d11/data/'+('basicdata/' if filename=='cdatabase.dat' else '')+filename
        er,jr=read(en,resource),read(ja,resource)
        if filename=='cdatabase.dat':
            ef,jf=database_fields(er),database_fields(jr)
            if [(f.id,f.field_index) for f in ef]!=[(f.id,f.field_index) for f in jf]:
                raise ValueError('System database layout differs')
            a,b={f.id:f.text for f in ef},{f.id:f.text for f in jf}
        else:a,b=dict(unpack_text_dictionary(er)),dict(unpack_text_dictionary(jr))
        system[filename]=(a,b,resource)
    for r in records:
        if r.get('internal_command'):
            unmatched.append({'id':r['id'],'reason':'Internal control directive, not display text'})
        elif r['kind']=='database':
            if edb.get(r['id'])!=r['source']:raise ValueError('English database source differs: '+r['id'])
            add(r,jdb[r['id']],db_name,'database_storage_id_and_matching_table_layout')
        elif r['kind'] in {'message','choice','button'}:
            if r['id'] not in scripts:
                unmatched.append({'id':r['id'],'reason':'No safe script structure alignment'});continue
            source,target,resource,encoding,details=scripts[r['id']]
            if source!=r['source']:raise ValueError('English script source differs: '+r['id'])
            add(r,target,resource,'same_script_command_signature_and_display_slot',encoding,details)
        elif r['kind']=='system':
            _,filename,key=r['id'].split('/',2);a,b,resource=system[filename]
            if a.get(key)!=r['source']:raise ValueError('English system source differs')
            if key in b:add(r,b[key],resource,'same_system_dictionary_key')
            else:unmatched.append({'id':r['id'],'reason':'Missing Japanese dictionary key'})
        else:unmatched.append({'id':r['id'],'reason':'Image caption requires separate visual extraction'})
    report={'schema':1,'checked_date':'2026-11-07','usable':True,'origin':ORIGIN,'version':VERSION,
        'files':files,'resource_index_entries':ja.count,'resource_blocks_decompressed':checked,
        'database_string_fields':len(jdb),'database_layout_matches':True,'database_tables':len(jm),
        'script_alignment':script_stats,'aligned_entries':len(entries),'by_kind':dict(counts),
        'unaligned_entries':len(unmatched),'unmatched':unmatched,
        'note':'These are actual Japanese display sources, structurally aligned. Semantic equivalence and English/Japanese differences still require entry-by-entry review.',
        'game_files_modified':False}
    # All parsing/alignment checks finish before replacing the editor source catalogue.
    atomic_json(output,{'schema':1,'origin':ORIGIN,'version':VERSION,'entries':entries})
    atomic_json(report_path,report)
    print(json.dumps({k:report[k] for k in ['usable','aligned_entries','by_kind','unaligned_entries','resource_blocks_decompressed','script_alignment']},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--japanese',type=Path,default=PROJECT/'work/japanese-fixture')
    p.add_argument('--english',type=Path,default=PROJECT/'work/clean-fixture')
    p.add_argument('--out',type=Path,default=PROJECT/'translations/japanese-sources.json')
    p.add_argument('--report',type=Path,default=PROJECT/'docs/japanese-resource-verification.json')
    a=p.parse_args();extract(a.japanese,a.english,a.out,a.report)
