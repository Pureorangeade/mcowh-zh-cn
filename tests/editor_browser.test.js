const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process'),{pathToFileURL}=require('node:url');
const assert=require('node:assert/strict');
const folder=path.resolve(__dirname,'../work/editor-qa');fs.mkdirSync(folder,{recursive:true});
fs.rmSync(path.join(folder,'profile/DevToolsActivePort'),{force:true});
const proc=spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',['--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+path.join(folder,'profile'),'about:blank'],{windowsHide:true,stdio:'ignore'});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
class CDP{
 constructor(socket){this.socket=socket;this.id=0;this.pending=new Map();socket.onmessage=event=>{const m=JSON.parse(event.data);if(m.id){const p=this.pending.get(m.id);if(p){this.pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}}};}
 static async connect(url){const s=new WebSocket(url);await new Promise((r,j)=>{s.onopen=r;s.onerror=j;});return new CDP(s);}
 call(method,params={}){return new Promise((resolve,reject)=>{const id=++this.id;this.pending.set(id,{resolve,reject});this.socket.send(JSON.stringify({id,method,params}));});}
 async value(expression){const result=await this.call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;}
}
(async()=>{
 let client;
 try{
  let lines;for(let i=0;i<100;i++){try{lines=fs.readFileSync(path.join(folder,'profile/DevToolsActivePort'),'utf8').trim().split('\n');break;}catch(_){await delay(100);}}
  if(!lines)throw Error('Browser did not expose its test port');
  const port=lines[0],url=pathToFileURL(path.resolve(__dirname,'../editor/汉化译文编辑器.html')).href;
  const target=await (await fetch('http://127.0.0.1:'+port+'/json/new?'+encodeURIComponent(url),{method:'PUT'})).json();
  client=await CDP.connect(target.webSocketDebuggerUrl);
  await client.call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  for(let i=0;i<100;i++){if(await client.value("document.documentElement?.dataset.editorReady==='true'"))break;await delay(100);}
  assert.equal(await client.value('records.length'),12204);
  assert.equal(await client.value("document.getElementById('source').readOnly"),true);
  assert.equal(await client.value("document.getElementById('japanese').readOnly"),true);
  await client.value("select(byId.get('db/58/140/1'))");
  assert.equal(await client.value("document.getElementById('target').value"),'力量');
  assert.equal(await client.value("document.getElementById('target').readOnly"),false);
  await client.value("select(byId.get('db/6/35/0'))");
  assert.equal(await client.value("document.getElementById('japanese').value"),'堕天の羽根');
  assert.ok((await client.value("document.getElementById('japaneseHint').textContent")).includes('魔王の心臓'));
  assert.ok((await client.value("document.getElementById('japaneseOrigin').textContent")).includes('日版原文'));
  await client.value("select(records.find(r=>r.kind==='image'))");
  assert.ok((await client.value("document.getElementById('japanese').value")).includes('暂无可核验'));
  assert.equal(await client.value("select(records.find(r=>r.internal_command));document.getElementById('target').readOnly"),true);
  assert.equal(await client.value("document.getElementById('target').value"),'reset');
  assert.equal(await client.value("isDeferred(byId.get('db/6/91/3'))"),false);
  assert.ok((await client.value("translated(byId.get('db/6/91/3'))")).includes('停止移动'));
  assert.equal(await client.value("isDeferred(byId.get('db/6/11/3'))"),false);
  await client.value("select(byId.get('db/3/155/1'))");
  assert.ok(await client.value('isDeferred(current)'));
  assert.ok((await client.value("document.getElementById('reviewNote').textContent")).includes('命中+50%'));
  assert.ok((await client.value("document.getElementById('reviewNote').textContent")).includes('当前沿用英文版含义'));
  assert.ok(!(await client.value("document.getElementById('reviewNote').textContent")).includes('undefined'));
  await client.value("localStorage.clear();edits=new Map(bundle.initial_edits.map(e=>[e.id,e.translation]));editMetadata.clear();for(const edit of bundle.initial_edits)editMetadata.set(edit.id,edit);");
  const modelDraftCount=await client.value("bundle.initial_edits.filter(e=>e.translation_method==='current_online_chat_llm').length");
  const modelCount=await client.value("records.filter(r=>reviewState(r)==='llm_translated').length");
  assert.ok(modelCount>0);
  assert.equal(await client.value("document.getElementById('filter').value='llm';search();visible.length"),modelCount);
  assert.equal(await client.value("revision().entries.filter(e=>e.translation_method==='current_online_chat_llm'&&e.human_reviewed===false).length"),modelDraftCount);
  let pendingDraftId=await client.value("records.find(r=>r.review_state==='awaiting_user'&&initialMetadata.get(r.id)?.translation_method==='current_online_chat_llm')?.id");
  const syntheticPending=!pendingDraftId;
  if(syntheticPending){
   pendingDraftId='db/3/0/0';
   await client.value("window.pendingTestOldState=byId.get('db/3/0/0').review_state;byId.get('db/3/0/0').review_state='awaiting_user';pendingIssues.push({entry_ids:['db/3/0/0'],question:'测试：等待明确的术语决定'});");
  }
  await client.value("select(byId.get("+JSON.stringify(pendingDraftId)+"))");
  assert.equal(await client.value('reviewState(current)'),'awaiting_user');
  assert.ok((await client.value("document.getElementById('reviewNote').textContent")).includes('待你判断'));
  assert.ok(await client.value("document.getElementById('filter').value='pending';search();visible.some(r=>r.id==="+JSON.stringify(pendingDraftId)+")"));
  if(syntheticPending)await client.value("byId.get('db/3/0/0').review_state=window.pendingTestOldState;pendingIssues.pop();");
  // A browser cache created before new batches must not hide new embedded translations.
  await client.value("localStorage.setItem(storageKey,JSON.stringify({schema:1,project:'mcowh-zh',entries:[]}));");
  await client.call('Page.reload');
  for(let i=0;i<100;i++){await delay(100);if(await client.value("document.documentElement?.dataset.editorReady==='true'"))break;}
  assert.equal(await client.value("records.filter(r=>reviewState(r)==='llm_translated').length"),modelCount);
  if(!syntheticPending)assert.equal(await client.value("reviewState(byId.get("+JSON.stringify(pendingDraftId)+"))"),'awaiting_user');
  await client.value("select(byId.get('db/3/0/0'));document.getElementById('reviewReason').value='终审测试';document.getElementById('defer').click();");
  assert.equal(await client.value('deferredEntry(current)'),true);
  assert.ok(await client.value("revision().review_decisions.some(d=>d.id===current.id&&d.reason==='终审测试'&&d.status==='deferred_final')"));
  const draftBefore=await client.value('translated(current)');
  await client.call('Page.reload');
  for(let i=0;i<100;i++){await delay(100);if(await client.value("document.documentElement?.dataset.editorReady==='true'"))break;}
  assert.equal(await client.value("select(byId.get('db/3/0/0'));deferredEntry(current)"),true);
  assert.equal(await client.value('translated(current)'),draftBefore);
  assert.ok(await client.value("document.getElementById('filter').value='deferred';search();visible.some(r=>r.id==='db/3/0/0')"));
  await client.value("document.getElementById('resume').click()");
  assert.equal(await client.value('deferredEntry(current)'),false);
  await client.value("select(records.find(r=>r.source==='Longsword'));document.getElementById('target').value='待撤销的修订';saveInput();");
  assert.equal(await client.value('reviewState(current)'),'user_revision');
  await client.value("document.getElementById('reset').click()");
  assert.equal(await client.value('reviewState(current)'),'llm_translated');
  // Stale unchanged model drafts must not overwrite a corrected embedded batch.
  await client.value("const old=initialMetadata.get('db/3/0/0');localStorage.setItem(storageKey,JSON.stringify({schema:1,project:'mcowh-zh',entries:[{...old,translation:'旧浏览器模型稿'}]}));");
  await client.call('Page.reload');
  for(let i=0;i<100;i++){await delay(100);if(await client.value("document.documentElement?.dataset.editorReady==='true'"))break;}
  assert.equal(await client.value("translated(byId.get('db/3/0/0'))===initialMetadata.get('db/3/0/0').translation"),true);
  await client.value("localStorage.clear();edits.clear();document.getElementById('filter').value='all';document.getElementById('search').value='Longsword';search();select(records.find(r=>r.source==='Longsword'));document.getElementById('target').value='测试长剑';saveInput();store();");
  await delay(400);
  assert.equal(await client.value("validateEdit(current,translated(current))"),'');
  fs.writeFileSync(path.join(folder,'editor.png'),Buffer.from((await client.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  const exported=await client.value("(async()=>{URL.createObjectURL=b=>{window.testBlob=b;return 'about:blank';};HTMLAnchorElement.prototype.click=function(){};document.getElementById('export').click();return JSON.parse(await window.testBlob.text());})()");
  assert.equal(exported.entries.length,1);assert.equal(exported.entries[0].translation,'测试长剑');
  await client.call('Page.reload');
  for(let i=0;i<100;i++){await delay(100);if(await client.value("document.documentElement?.dataset.editorReady==='true'"))break;}
  assert.equal(await client.value("translated(records.find(r=>r.source==='Longsword'))"),'测试长剑');
  assert.equal(await client.value("select(byId.get('db/10/35/1'));document.getElementById('target').readOnly"),true);
  assert.equal(await client.value("document.getElementById('target').value===current.source.replace(/\\r\\r?\\n|\\r/g,'\\n')"),true);
  await client.value("select(records.find(r=>r.kind==='message'&&tokens(r.source).length));document.getElementById('target').value='缺少标记';saveInput();store();");
  assert.ok(await client.value("document.getElementById('validation').className==='error'"));
  await client.call('Page.reload');
  for(let i=0;i<100;i++){await delay(100);if(await client.value("document.documentElement?.dataset.editorReady==='true'"))break;}
  assert.equal(await client.value("[...edits.values()].includes('缺少标记')"),true);
  await client.value("document.getElementById('export').click()");
  assert.ok((await client.value("document.getElementById('message').textContent")).startsWith('暂不能导出'));
  const japaneseCount=await client.value("records.filter(r=>r.japanese.availability==='verified_display').length");
  assert.equal(japaneseCount,11951);
  const report={version:'working English/Japanese/Chinese editor',browser:'Microsoft Edge headless, isolated profile',entries:12204,llm_entries:modelCount,japanese_entries:japaneseCount,checks:['page loads','English and Japanese read-only','actual Japanese display source visible','remaining missing Japanese original explicit','internal Japanese hint separated from display original','internal command readonly and preserved','user-resolved phrase translated and removed from final-review filter','confirmed current-version item removed from final-review filter','final-review mark exported and survives reload','final-review filter','cancel deferral preserves Chinese draft','LLM-only filter','translation provenance retained on export','older empty cache preserves new embedded translations','reset restores embedded LLM translation','user edit distinguished from LLM translation','edit and export JSON','browser draft reload','abbreviation locked','invalid controls blocked','unfinished draft retained after reload'],screenshot:'editor.png'};
  report.checks.push('source-version difference flagged with its question and retained English meaning');
  report.llm_draft_entries=modelDraftCount;
  report.checks.push('pending terminology overrides completed-model status','pending question evidence shown in editor');
  report.pending_check_fixture=syntheticPending?'isolated in-page fixture; no real unanswered questions':'current pending questions, including reload';
  fs.writeFileSync(path.join(folder,'report.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
 }finally{if(client){try{await client.call('Browser.close');}catch(_){}}else proc.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
