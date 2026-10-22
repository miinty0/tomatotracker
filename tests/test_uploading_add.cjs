const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync('index.html', 'utf8');
const ctx = vm.createContext({Set, String});
vm.runInContext(html.slice(html.indexOf('function applyUploadingEntries('), html.indexOf('async function submitInlineUpdates(')), ctx);
const original = {wiki_id:'wikiA', fanqie_id:'7626209917593996312', uploaded_chapters:30, vi_title:'Keep title', note:'Keep note', status:'连载中', fanqie_chapters:100, last_updated:'keep'};
const entry = (wiki, fq, ch) => ({wiki_id:wiki, fanqie_id:fq, uploaded_chapters:ch, vi_title:null});
let list = [{...original}];
let r = ctx.applyUploadingEntries(list, [entry('wikiA', original.fanqie_id, 60)]);
assert.equal(r.updated,1); assert.equal(r.added,0); assert.equal(r.errors.length,0);
assert.deepEqual(list[0], {...original, uploaded_chapters:60});
for (const e of [entry('wrong', original.fanqie_id,99), entry('wikiA','other',99), entry(null, original.fanqie_id,99)]) {
  list = [{...original}]; r = ctx.applyUploadingEntries(list,[e]);
  assert.equal(r.errors.length,1); assert.deepEqual(list,[original]);
}
list = [{...original},entry('wikiB','other',20)];
r = ctx.applyUploadingEntries(list,[entry('wikiB',original.fanqie_id,99)]);
assert.equal(r.errors.length,1); assert.equal(list[0].uploaded_chapters,30); assert.equal(list[1].uploaded_chapters,20);
list = [{...original}];
r = ctx.applyUploadingEntries(list,[entry('wikiA', original.fanqie_id,60), entry('wikiB','new',10), entry('wikiB','new',20), entry('wikiB','bad',99)]);
assert.equal(r.added,1); assert.equal(r.updated,1); assert.equal(r.errors.length,1);
assert.equal(list.length,2); assert.equal(list[1].uploaded_chapters,20);
list = [entry(null,'no-wiki',5)];
r = ctx.applyUploadingEntries(list,[entry(null,'no-wiki',10),entry(null,'new-no-wiki',1)]);
assert.equal(r.errors.length,0); assert.equal(r.added,1); assert.equal(r.updated,1);
// Fresh data on retry may have changed the pair: never overwrite the other book.
const intent = entry('wikiA',original.fanqie_id,90);
list = [{...original, wiki_id:'changed-on-server'}];
r = ctx.applyUploadingEntries(list,[intent]);
assert.equal(r.errors.length,1); assert.equal(list[0].uploaded_chapters,30);
assert.equal(intent.uploaded_chapters,90);
for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
console.log('PASS: matching-pair update, either-ID mismatch, cross-book conflict, mixed/repeated batch, optional wiki, fresh-data recheck, metadata preservation, script syntax');
(async () => {
  const nodes = new Map();
  const messages = [];
  ctx.CFG = {repo:'test', token:'test'};
  ctx.pendingUpdates = new Map(); ctx.pendingTransNotes = new Map();
  ctx.pendingNotes = new Map(); ctx.pendingWaitingUpdates = new Map();
  ctx.waitingList = []; ctx.uploadingList = [{...original}];
  ctx.document = {getElementById(id) {
    if (!nodes.has(id)) nodes.set(id,{value:'', classList:{remove(){}}});
    return nodes.get(id);
  }};
  ctx.toast = (...args) => messages.push(args);
  ctx.updateSaveBar = ctx.renderUploading = ctx.renderWaiting = () => {};
  ctx.saveUploading = async patch => {
    // Simulate a conflict retry. Counters/warnings must describe only the saved attempt.
    patch(structuredClone(ctx.uploadingList));
    ctx.uploadingList = patch(structuredClone(ctx.uploadingList));
  };
  vm.runInContext(html.slice(html.indexOf('async function submitInlineUpdates('),html.indexOf('function discardInlineUpdates(')),ctx);
  ctx.document.getElementById('uploading-input').value = `wikiA | 75 | ${original.fanqie_id}\nwikiB | 10 | 111\nwrong | 99 | ${original.fanqie_id}`;
  await ctx.submitInlineUpdates();
  assert.equal(ctx.uploadingList.length,2);
  assert.equal(ctx.uploadingList[0].uploaded_chapters,75);
  assert.equal(ctx.uploadingList[0].note,original.note);
  const message = messages.at(-1)[0];
  assert.match(message,/Thêm 1 truyện/);
  assert.match(message,/cập nhật chương cho 1 truyện từ \+Add/);
  assert.match(message,/Input bị bỏ qua \(1\)/);
  assert.equal(messages.at(-1)[1],'error');
  console.log('PASS: +Add submission saves matching updates/new books, reports mismatches, counts correctly after retry');
})().catch(e => {console.error(e);process.exitCode=1;});
