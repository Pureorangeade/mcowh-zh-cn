'use strict';
function tokens(text) {
  const result = [];
  let i = 0;
  while (i < text.length) {
    const tail = text.slice(i);
    let m = /^(?:\r\r?\n|\r|\n)|^<[^<>\r\n]+>|^\[[A-Z][A-Z_0-9]*\]|^\$[A-Za-z][A-Za-z0-9]*/.exec(tail);
    if (i === 0 || /[\r\n]/.test(text[i - 1])) {
      const directive = /^[ \t]*(?:[@#][^\r\n]*|\/\/[^\r\n]*|\[\/?[A-Za-z][A-Za-z0-9_]*\](?=\r|\n|$)|(?:BGM|SE|Y|X|WAIT|BG|VOICE):[^\r\n]*)/.exec(tail);
      if (directive) m = directive;
    }
    let end;
    if (m) end = i + m[0].length;
    else if (text[i] === '\\') {
      m = /^\\(?:[A-Za-z_]+|.)/.exec(tail);
      if (!m) { i++; continue; }
      end = i + m[0].length;
      if (text[end] === '[') {
        let depth = 0, found = false;
        for (; end < text.length; end++) {
          if (text[end] === '[') depth++;
          if (text[end] === ']') depth--;
          if (depth === 0) { end++; found = true; break; }
        }
        if (!found) throw Error('控制标记的方括号没有配对');
      }
    } else { i++; continue; }
    const token = text.slice(i, end);
    if (!/^[\r\n]+$/.test(token)) result.push(token);
    i = end;
  }
  return result;
}
function menuEntries(text) {
  const lines=text.match(/[^\r\n]*(?:\r\r?\n|\r|\n|$)/g)||[], rows=[];
  if(lines[lines.length-1]==='')lines.pop();
  for(const line of lines){
    const match=/^([^,\r\n]+)(,[ \t]*[+-]?[0-9]+[ \t]*(?:\r\r?\n|\r|\n)?)$/.exec(line);
    if(!match)return null;
    rows.push([match[1],match[2]]);
  }
  return rows.length?rows:null;
}
function validateEdit(item, target) {
  if (typeof target !== 'string' || !target.trim() || target.length > 40000) return '译文不能为空或过长。';
  if (target.includes('\0')) return '译文中有无效的空字符。';
  const menu=menuEntries(item.source);
  if(menu){
    const translated=menuEntries(target);
    if(!translated||JSON.stringify(menu.map(r=>r[1]))!==JSON.stringify(translated.map(r=>r[1])))return '菜单配置中的英文逗号、空格、内部编号和换行必须保持原样，只能修改选项文字。';
  }
  const placeholders=t=>[...t.matchAll(/(?<![A-Za-z0-9_])(?:Lvnum|num)(?![A-Za-z0-9_])/g)].map(m=>m[0]);
  if(JSON.stringify(placeholders(item.source))!==JSON.stringify(placeholders(target)))return 'num 或 Lvnum 是运行时替换标记，请保留原样。';
  if (item.locked && target !== item.source) return item.internal_command?'此条为程序指令，必须保留原样。':'此条按你的偏好保留英文缩写。';
  try {
    if (JSON.stringify(tokens(item.source)) !== JSON.stringify(tokens(target))) return '颜色、变量或图标标记发生变化，请对照英文恢复。';
  } catch (error) { return error.message; }
  const directives = t => t.split(/\r\n|\r|\n/).filter(line => /^[ \t]*[@#]/.test(line));
  if (JSON.stringify(directives(item.source)) !== JSON.stringify(directives(target))) return '程序指令发生变化，请保留原来的指令行。';
  if (item.kind === 'choice' && /\s/.test(target)) return '选项中的空格需要转换为下划线。';
  if (item.kind === 'image' && /[\r\n]/.test(target)) return '界面图片文字请保持一行。';
  return '';
}
function normalizeInput(item, value) {
  if (item.kind === 'choice') return value.replace(/\s+/g, '_');
  const newline = item.source.includes('\r\r\n') ? '\r\r\n' : item.source.includes('\r\n') ? '\r\n' : '\n';
  return value.replace(/\r\r?\n|\r/g, '\n').replace(/\n/g, newline);
}
function parseRevision(payload, byId) {
  if (!payload || payload.schema !== 1 || payload.project !== 'mcowh-zh' || !Array.isArray(payload.entries) || payload.entries.length > 20000) throw Error('不是本项目的译文修订文件。');
  const edits = new Map();
  for (const edit of payload.entries) {
    if (!edit || typeof edit !== 'object') throw Error('无效的修订条目。');
    const item = byId.get(edit.id);
    if (!item || edits.has(edit.id)) throw Error('存在未知或重复条目：' + edit.id);
    if (item.source_sha256 !== edit.source_sha256) throw Error('英文原文版本不匹配：' + edit.id);
    const error = validateEdit(item, edit.translation);
    if (error) throw Error(error + '\n' + edit.id);
    edits.set(edit.id, edit.translation);
  }
  parseReviewDecisions(payload,byId);
  return edits;
}
function parseReviewDecisions(payload,byId) {
  const list=payload.review_decisions===undefined?[]:payload.review_decisions,result=new Map();
  if(!Array.isArray(list)||list.length>20000)throw Error('无效的终审标记列表。');
  for(const d of list){
    const r=d&&byId.get(d.id);
    if(!r||result.has(d.id)||r.locked||d.source_sha256!==r.source_sha256||!['deferred_final','resolved'].includes(d.status)||d.scope!=='entry'||typeof d.reason!=='string'||d.reason.length>2000)throw Error('终审标记无效或原文版本不匹配。');
    result.set(d.id,d);
  }
  return result;
}
function restoreDraft(payload, byId) {
  // Unfinished text may fail control checks; preserve it across browser reloads.
  if (!payload || payload.schema !== 1 || payload.project !== 'mcowh-zh' || !Array.isArray(payload.entries) || payload.entries.length > 20000) throw Error('无效草稿');
  const edits = new Map();
  for (const edit of payload.entries) {
    const item = edit && byId.get(edit.id);
    if(item?.internal_command && edit.source_sha256===item.source_sha256 && !edits.has(edit.id)){
      edits.set(edit.id,item.source);continue;
    }
    if (!item || edits.has(edit.id) || edit.source_sha256 !== item.source_sha256 || typeof edit.translation !== 'string' || edit.translation.length > 40000 || item.locked && edit.translation !== item.source) throw Error('草稿版本不匹配');
    edits.set(edit.id, edit.translation);
  }
  return edits;
}
if (typeof module !== 'undefined') module.exports = {tokens, validateEdit, normalizeInput, parseRevision, restoreDraft, parseReviewDecisions, menuEntries};
