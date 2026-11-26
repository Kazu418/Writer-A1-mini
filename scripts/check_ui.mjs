// Execute generated UI JavaScript with a small DOM test double; no browser/network required.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

class Element {
  constructor(){this.value='';this.checked=false;this.children=[];this.style={};this.files=[];}
  add(option){this.children.push(option);if(this.children.length===1)this.value=option.value;}
  append(el){this.children.push(el);}
  replaceChildren(){this.children=[];}
  setAttribute(name,value){this[name]=value;}
  click(){this.onclick?.();}
}
function dom(){const elements=new Map();return {elements,document:{
  getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},
  createElementNS(){return new Element();},createElement(){return new Element();}
}};}
function script(path){const html=fs.readFileSync(path,'utf8');return html.match(/<script>([\s\S]*?)<\/script>/)[1];}
const preview=process.argv[2]||'examples/japanese-note-preview/preview.html';
const d=dom();let frame;
d.document.getElementById('travel').checked=true;
d.document.getElementById('speed').value='20';
vm.runInNewContext(script(preview),{document:d.document,Option:class{constructor(text,value){this.value=value;}},requestAnimationFrame:f=>{frame=f;}});
const el=id=>d.document.getElementById(id);
assert.match(el('status').textContent,/\d+ \/ \d+画/);
el('play').onclick();assert.equal(el('progress').value,0,'play at end must restart');
frame(1000);assert.ok(el('progress').value>0,'playback must advance');
el('reset').onclick();assert.equal(el('progress').value,0);
el('progress').value=3;el('progress').oninput();assert.match(el('status').textContent,/^3 \/ /);
el('travel').checked=false;el('travel').onchange();
if(el('page').children.length>1){el('page').value='1';el('page').onchange();assert.ok(el('progress').value>0);}

const w=dom();const get=id=>w.document.getElementById(id);const requests=[];
const fetch=async(path,options)=>{
  requests.push({path,options});
  const data=path==='/api/profile'?{calibrated:false}:
    path.startsWith('/api/convert')?{job:'test',preview:'/preview.html',pdf:'/preview.pdf',download:'/download.zip',pages:[{width_mm:148,height_mm:148,strokes:20,ink_mm:100,travel_mm:20,warnings:[]}]}:
    {download:'/export.zip'};
  return {ok:true,json:async()=>data};
};
vm.runInNewContext(script('src/plotnote/data/workbench.html'),{document:w.document,fetch,Blob,URL,setTimeout});
await new Promise(resolve=>setImmediate(resolve));
get('file').files=[{name:'note.pdf',arrayBuffer:async()=>new ArrayBuffer(1)}];
await get('convert').onclick();
assert.equal(get('preview').src,'/preview.html');assert.equal(get('previewbox').hidden,false);
assert.equal(get('air').disabled,false);assert.match(get('summary').textContent,/148\.000/);
get('profile').value=JSON.stringify({calibrated:true});get('homed').checked=true;
await get('air').onclick();
assert.equal(JSON.parse(requests.at(-1).options.body).air_mm,5);
assert.equal(get('exports').children.length,1);
get('homed').checked=false;await get('export').onclick();
assert.match(get('error').textContent,/ホーム/);
console.log('UI JavaScript: syntax, playback, reset, seek, page selection, upload, air export and acknowledgment gates passed.');
