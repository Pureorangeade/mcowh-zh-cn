'use strict';
const bundle = JSON.parse(document.getElementById('catalogue').textContent);
const records = bundle.records, byId = new Map(records.map(r => [r.id, r]));
const $ = id => document.getElementById(id);
const editMetadata = new Map(bundle.initial_edits.map(e => [e.id,e]));
const initialMetadata = new Map(editMetadata);
const reviewDecisions=new Map((bundle.initial_review_decisions||[]).map(d=>[d.id,d]));
const termIssues=bundle.final_review_issues.filter(q=>q.scope!=='entry');
const pendingIssues=bundle.pending_questions||[];
let edits = new Map(bundle.initial_edits.map(e => [e.id,e.translation]));
let visible = records, current = null, page = 0, previewing = false, timer;
const storageKey = 'mcowh-zh-edits-' + bundle.source_fingerprint;
function revision(includeUnchanged=true) { const selected=[...edits].filter(([id,translation])=>includeUnchanged||!initialMetadata.has(id)||initialMetadata.get(id).translation!==translation);
  return {schema:1,project:'mcowh-zh',editor_version:bundle.version,entries:selected.map(([id,translation]) => {
  const previous=editMetadata.get(id), unchanged=previous&&previous.translation===translation;
  return {...previous,id,source_sha256:byId.get(id).source_sha256,translation,...(unchanged?{}:{translation_method:'user_edit',review_status:'user_revision',human_reviewed:false})};
}),review_decisions:[...reviewDecisions.values()]}; }
function message(text) { $('message').textContent = text; }
function store() { try { localStorage.setItem(storageKey, JSON.stringify(revision(false))); } catch (_) { message('浏览器未能保存草稿，请及时使用“导出修订 JSON”保存文件。'); } }
try { const saved = localStorage.getItem(storageKey); if (saved) {const payload=JSON.parse(saved),savedEdits=restoreDraft(payload,byId),savedReviews=parseReviewDecisions(payload,byId);for(const edit of payload.entries){const fresh=initialMetadata.get(edit.id);if(edit.translation_method==='current_online_chat_llm'&&fresh?.translation_method==='current_online_chat_llm'&&(edit.batch||'')<=(fresh.batch||''))continue;edits.set(edit.id,savedEdits.get(edit.id));editMetadata.set(edit.id,edit);}for(const [id,d] of savedReviews)reviewDecisions.set(id,d);} } catch (_) { message('旧草稿与当前原文不符，已保留本版内容；可以手动导入修订文件检查。'); }
const translated = r => edits.has(r.id) ? edits.get(r.id) : r.translation;
const deferredEntry=r=>reviewDecisions.get(r.id)?.status==='deferred_final';
const issuesFor=r=>termIssues.filter(q=>q.entry_ids.includes(r.id));
const pendingFor=r=>pendingIssues.filter(q=>q.entry_ids.includes(r.id));
const isDeferred=r=>deferredEntry(r)||issuesFor(r).length>0;
function reviewState(r) {
  const metadata=editMetadata.get(r.id);
  if(r.internal_command)return 'retained_command';
  if(r.locked)return 'retained_english';
  if(r.review_state==='awaiting_user')return 'awaiting_user';
  if(edits.has(r.id)&&metadata&&metadata.translation_method==='user_confirmed_retention'&&edits.get(r.id)===r.source)return 'retained_original';
  if(edits.has(r.id))return metadata&&metadata.translation_method==='current_online_chat_llm'&&metadata.translation===edits.get(r.id)?'llm_translated':'user_revision';
  return r.review_state==='awaiting_user'?'awaiting_user':'awaiting_retranslation';
}
function stateLabel(r) {return (isDeferred(r)?'暂缓终审 · ':'')+{retained_command:'程序指令 · 保留原样',retained_english:'按约定保留英文缩写',retained_original:'按你的决定保留原文',llm_translated:'本聊天模型已重译 · 待验收',user_revision:'我的修订',awaiting_user:'待你判断',awaiting_retranslation:'旧稿 · 尚未逐条重译'}[reviewState(r)];}
for (const name of [...new Set(records.map(r => r.category))]) { const o=document.createElement('option');o.value=name;o.textContent=name;$('category').append(o); }
function rowList() {
  $('list').replaceChildren();
  for (const item of visible.slice(page*100,(page+1)*100)) {
    const b=document.createElement('button');b.className='item'+(current && item.id===current.id?' selected':'');b.dataset.entryId=item.id;
    const title=document.createElement('strong');title.textContent=translated(item).replace(/\s+/g,' ').slice(0,70);
    const desc=document.createElement('small');desc.textContent=stateLabel(item)+' · '+item.source.replace(/\s+/g,' ').slice(0,40);
    b.append(title,desc);b.onclick=()=>select(item);$('list').append(b);
  }
  $('page').textContent=(visible.length?page+1:0)+' / '+Math.max(1,Math.ceil(visible.length/100));
  $('prevPage').disabled=page===0;$('nextPage').disabled=(page+1)*100>=visible.length;
  $('count').textContent=visible.length.toLocaleString()+' 条 · 修订 '+edits.size;
}
function search() {
  const q=$('search').value.toLocaleLowerCase(), cat=$('category').value, filter=$('filter').value;
  visible=records.filter(r=>(!cat||r.category===cat)&&(!q||[r.source,translated(r),r.location,r.id,r.japanese.text,r.japanese.internal_hint].some(t=>t.toLocaleLowerCase().includes(q)))&&(filter==='all'||filter==='edited'&&reviewState(r)==='user_revision'||filter==='locked'&&r.locked&&!r.internal_command||filter==='review'&&reviewState(r)==='awaiting_retranslation'||filter==='llm'&&reviewState(r)==='llm_translated'||filter==='pending'&&reviewState(r)==='awaiting_user'||filter==='deferred'&&isDeferred(r)));
  page=0;rowList();
}
function plain(text) { let value=text;for(const token of tokens(text)){value=value.split(token).join('');}return value; }
function refreshPreview() { if (!current) return;try {$('sourcePreview').textContent=plain(current.source);$('japanesePreview').textContent=current.japanese.text||'暂无可核验的对应日文原文';$('targetPreview').textContent=plain(translated(current));}catch(_){$('targetPreview').textContent=translated(current);} }
function select(item) {
  current=item;$('source').value=item.source;$('target').value=translated(item);$('target').readOnly=!!item.locked;
  const jp=item.japanese;$('japanese').value=jp.text||'暂无可核验的对应日文原文。\n下方内部标签仅供查证。';
  $('japaneseOrigin').textContent=jp.availability==='verified_display'?'日版原文 · 按结构对齐 · '+jp.version:'缺少正式日文正文';
  $('japaneseHint').textContent=jp.note+'\n'+(jp.internal_hint?'日文内部标签（可能为旧版）\n'+jp.internal_hint:'此条暂无日文内部标签。');
  $('reviewReason').value=reviewDecisions.get(item.id)?.reason||'';
  $('defer').disabled=!!item.locked;$('resume').disabled=!deferredEntry(item);
  $('reviewNote').textContent=(deferredEntry(item)?'整条暂缓：保留中文草稿；合入后构建使用英文原文。':'')+pendingFor(item).map(q=>'待你判断：'+q.question+' 候选稿保留，尚未记录为用户决定。').join(' ')+issuesFor(item).map(q=>q.scope==='source_difference'?'英日差异：'+q.question+' 当前沿用英文版含义，留待最后终审。':'术语 '+q.term+' 暂保留英文，留待最后终审。').join(' ');
  $('section').textContent=item.category;$('state').textContent=stateLabel(item);
  $('location').textContent=item.location+'\n'+item.id;
  $('controlTokens').textContent='需保留：'+(tokens(item.source).join('  ')||'无控制标记')+(menuEntries(item.source)?'；菜单配置：保留末尾英文逗号、空格、编号和换行，只修改选项文字。':'');
  updateValidation();refreshPreview();rowList();
}
function updateValidation() {
  if (!current) return;
  const text=translated(current), error=validateEdit(current,text);
  $('validation').textContent=error|| (current.internal_command?'程序指令不是翻译内容，已锁定并保留原样。':current.locked?'此条恢复为原版英文缩写，编辑已锁定。':'标记检查通过。修改会自动存入浏览器草稿，导出后才能用于更新补丁。');
  $('validation').className=error?'error':'';
  $('sourceLength').textContent=current.source.length+' 字符';$('targetLength').textContent=text.length+' 字符';
}
function saveInput() {
  if (!current||current.locked) return;
  const target=normalizeInput(current,$('target').value);
  if (target===current.translation&&!initialMetadata.has(current.id)) edits.delete(current.id);else edits.set(current.id,target);
  $('state').textContent=stateLabel(current);
  updateValidation();clearTimeout(timer);timer=setTimeout(()=>{store();rowList();},300);refreshPreview();
}
function move(direction) {
  if (!current||!visible.length) return;
  const i=visible.findIndex(r=>r.id===current.id), n=Math.max(0,Math.min(visible.length-1,i+direction));
  page=Math.floor(n/100);select(visible[n]);
}
$('search').oninput=search;$('category').onchange=search;$('filter').onchange=search;
$('target').oninput=saveInput;$('previous').onclick=()=>move(-1);$('next').onclick=()=>move(1);
$('prevPage').onclick=()=>{page--;rowList();};$('nextPage').onclick=()=>{page++;rowList();};
$('reset').onclick=()=>{if(current){const initial=initialMetadata.get(current.id);if(initial){edits.set(current.id,initial.translation);editMetadata.set(current.id,initial);}else{edits.delete(current.id);editMetadata.delete(current.id);}store();select(current);}};
$('preview').onclick=()=>{previewing=!previewing;for(const name of ['source','japanese','target']){$(name).style.display=previewing?'none':'block';$(name+'Preview').style.display=previewing?'block':'none';}$('preview').textContent=previewing?'返回编辑':'阅读预览';refreshPreview();};
function markReview(status){if(!current||current.locked)return;reviewDecisions.set(current.id,{id:current.id,source_sha256:current.source_sha256,scope:'entry',status,reason:$('reviewReason').value.slice(0,2000)||'语境或术语尚不确定，留待最终判断。'});store();select(current);message(status==='deferred_final'?'本条已暂缓；中文草稿保留，合入后的构建将使用英文原文。':'已取消整条暂缓，中文草稿恢复参与构建；术语级问题仍按原决定保留。');}
$('defer').onclick=()=>markReview('deferred_final');$('resume').onclick=()=>markReview('resolved');
$('export').onclick=()=>{
  try {parseRevision(revision(),byId);}catch(error){message('暂不能导出：'+error.message);return;}
  store();const file=new Blob([JSON.stringify(revision(),null,2)],{type:'application/json;charset=utf-8'}), a=document.createElement('a');
  a.href=URL.createObjectURL(file);a.download='汉化译文修订.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),5000);
  message('已导出 '+edits.size+' 条修订及 '+reviewDecisions.size+' 条终审标记。请保留此文件；发回聊天即可合入补丁，修改不会自动写入游戏。');
};
$('import').onclick=()=>$('importFile').click();
$('importFile').onchange=async event=>{
  try {const file=event.target.files[0];if(!file)return;const payload=JSON.parse(await file.text()),incoming=parseRevision(payload,byId),reviews=parseReviewDecisions(payload,byId);for(const [id,text] of incoming)edits.set(id,text);for(const edit of payload.entries)editMetadata.set(edit.id,edit);for(const [id,d] of reviews)reviewDecisions.set(id,d);store();search();if(current)select(current);message('已导入 '+incoming.size+' 条修订及 '+reviews.size+' 条终审标记。');}
  catch(error){message('导入未完成：'+error.message);}finally{event.target.value='';}
};
document.addEventListener('keydown',event=>{if(event.ctrlKey&&event.key.toLowerCase()==='s'){event.preventDefault();saveInput();store();message('浏览器草稿已保存；请导出 JSON 文件用于合并补丁。');}if(event.ctrlKey&&event.key==='Enter'){event.preventDefault();saveInput();move(1);}});
window.addEventListener('beforeunload',store);
search();select(records.find(r=>r.source==='Longsword')||records[0]);
document.documentElement.dataset.editorReady='true';
