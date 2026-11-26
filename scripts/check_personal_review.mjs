// Execute the actual standalone artifact without a browser or network access.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor(tag='div'){this.tag=tag;this.value='';this.checked=false;this.children=[];}
  append(child){this.children.push(child);}
  replaceChildren(){this.children=[];}
  setAttribute(key,value){this[key]=value;}
  click(){return this.onclick?.();}
}
const nodes=new Map();
const document={getElementById(id){if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);},
  createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
const store=new Map();
let downloaded;
const context={document,window:{},console,Blob,URLSearchParams,
  URL:{createObjectURL(blob){downloaded=blob;return 'blob:review';},revokeObjectURL(){}},
  localStorage:{getItem:key=>store.get(key),setItem:(key,value)=>store.set(key,value)},
  setTimeout:fn=>fn()};
document.getElementById('required').checked=true;
const html=fs.readFileSync(process.argv[2]||'output/personal-font/review-note.html','utf8');
vm.createContext(context);
let legacyTarget;
for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)){
  vm.runInContext(match[1],context);
  if(!legacyTarget&&context.window.PERSONAL_REVIEW){
    const d=context.window.PERSONAL_REVIEW;
    legacyTarget=d.samples.find(s=>s.status==='accepted');
    // Old caches stored every unreviewed sample, including untouched ones.
    // They must not undo newly reviewed source data when artifacts are rebuilt.
    store.set(d.storageKey,JSON.stringify([{id:legacyTarget.id,label:legacyTarget.label,status:'unreviewed'}]));
  }
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
await settle();
assert.equal(context.window.PERSONAL_REVIEW.samples.find(s=>s.id===legacyTarget.id).status,'accepted');
const get=id=>document.getElementById(id);
assert.match(get('summary').textContent,/427字種/);
assert.ok(get('letters').children.length>=400);
const requiredCount=get('letters').children.length;
if(context.window.PERSONAL_REVIEW.samples.some(s=>!context.window.PERSONAL_REVIEW.required.includes(s.label))){
  get('required').checked=false;get('required').onchange();
  assert.ok(get('letters').children.length>requiredCount,'all-character collection must be accessible');
  get('required').checked=true;get('required').onchange();
}
get('find').value='生';get('find').oninput();
assert.equal(get('letters').children.length,1);
await get('letters').children[0].click();
const cards=get('samples').children;
assert.ok(cards.length>=1);
assert.ok(cards[0].children.find(c=>c.tag==='svg').children.length>0);
const label=cards[0].children.find(c=>c.tag==='input');
const accept=cards[0].children.find(c=>c.tag==='button'&&c.textContent==='この文字として登録');
label.value='二文字';await accept.click();
assert.match(get('message').textContent,/1文字/);
label.value='生';await accept.click();
assert.equal(get('message').textContent,'保存しました');
assert.ok(store.has(context.window.PERSONAL_REVIEW.storageKey));
const saved=JSON.parse(store.get(context.window.PERSONAL_REVIEW.storageKey));
assert.equal(saved.format,'plotnote-review-decisions-v2');
assert.equal(saved.reviews.length,1,'only explicit edits should be persisted');
get('save').click();
const decisions=JSON.parse(await downloaded.text());
assert.equal(decisions.format,'plotnote-review-v1');
assert.ok(decisions.reviews.some(r=>r.label==='生'&&r.status==='accepted'));
assert.ok(!decisions.reviews.some(r=>r.label==='二文字'));
const currentCard=get('samples').children[0];
const unreview=currentCard.children.find(c=>c.tag==='button'&&c.textContent==='未確認に戻す');
await unreview.click();get('save').click();
const reverted=JSON.parse(await downloaded.text());
assert.ok(reverted.reviews.some(r=>r.id===saved.reviews[0].id&&r.status==='unreviewed'),
          'explicit reversals must be included in downloaded decisions');
console.log('Offline review: required-character filter, candidate SVG, invalid label rejection, accept, local save and JSON download passed. Database unchanged.');
