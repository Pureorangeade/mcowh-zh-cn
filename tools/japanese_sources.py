"""Never mistake Japanese project labels for aligned Japanese display text."""
import json
from resources import PROJECT

SOURCES=PROJECT/'translations/japanese-sources.json'


def annotate_japanese(records, path=SOURCES):
    payload=json.loads(path.read_text('utf8')) if path.exists() else {'schema':1,'entries':[]}
    if payload.get('schema')!=1 or not isinstance(payload.get('entries'),list):
        raise ValueError('Invalid Japanese source catalogue')
    by_id={r['id']:r for r in records}; aligned={}
    for source in payload['entries']:
        key=source.get('id'); record=by_id.get(key)
        if not record or key in aligned or source.get('source_sha256')!=record['source_sha256']:
            raise ValueError('Japanese source alignment differs: '+str(key))
        if source.get('kind')!='verified_display' or not all(isinstance(source.get(k),str) and source[k].strip() for k in ['text','origin','version']):
            raise ValueError('Japanese display text needs provenance: '+key)
        aligned[key]=source
    for record in records:
        context=record.get('context',{})
        hint=' / '.join(str(context[k]) for k in ['table','row','field'] if context.get(k))
        source=aligned.get(record['id'])
        record['japanese']={'text':source['text'] if source else '',
            'availability':'verified_display' if source else 'missing',
            'origin':source['origin'] if source else '', 'version':source['version'] if source else '',
            'alignment':source.get('alignment',{}) if source else {},
            'internal_hint':hint, 'hint_origin':'English build database.project internal labels' if hint else '',
            'note':('已从日版显示资源提取，按结构对齐；英日含义差异仍需逐条核对。' if source else '暂无可核验的对应日文显示文本。')+
                   (' 内部标签可能来自旧版本，仅供查证。' if hint else '')}
