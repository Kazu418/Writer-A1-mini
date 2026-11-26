"""Local review of original Goodnotes ink, labels, and alternate exemplars."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlsplit
import zlib


def read_samples(db, char=None):
    ranks = {}
    ocr = {}
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='independent_ocr'").fetchone():
        for gid, expected, reading, status in db.execute(
                'SELECT exemplar_id,expected_label,reading,status FROM independent_ocr'):
            previous = ocr.get(gid)
            if previous is None or status == 'match':
                ocr[gid] = (expected, reading, status)
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='candidate_scores'").fetchone():
        ranks = {gid: (label, score) for gid, label, score in db.execute(
            "SELECT id,label,score FROM candidate_scores WHERE pool='exemplars' AND error IS NULL")}
    query = 'SELECT label,status,payload FROM exemplars'
    rows = db.execute(query + ' WHERE label=?', (char,)) if char is not None else db.execute(query)
    samples = []
    for label, status, blob in rows:
        sample = json.loads(zlib.decompress(blob))
        rank_label, score = ranks.get(sample['id'], (None, None))
        sample.update(label=label, status=status,
                      ranking_score=score if rank_label == label else None)
        expected, reading, ocr_status = ocr.get(sample['id'], (None, None, None))
        if expected == label:
            sample.update(ocr_reading=reading, ocr_status=ocr_status)
        samples.append(sample)
    samples.sort(key=lambda s: (s['label'], s['status'] != 'accepted', s['status'] == 'rejected',
                               s.get('ocr_status') != 'match',
                               s['ranking_score'] if s['ranking_score'] is not None else float('inf'), s['id']))
    return samples


def review(db, gid, label, status):
    if status not in ('accepted', 'rejected', 'unreviewed'):
        raise ValueError('Invalid review status')
    if len(label) != 1 or label.isspace() or not label.isprintable():
        raise ValueError('Label must contain exactly one visible character')
    row = db.execute('SELECT payload FROM exemplars WHERE id=?', (gid,)).fetchone()
    if row is None:
        raise ValueError('Unknown exemplar')
    sample = json.loads(zlib.decompress(row[0]))
    sample['reviewed_label'] = label
    sample['label_status'] = status
    db.execute('UPDATE exemplars SET label=?,status=?,payload=? WHERE id=?',
               (label, status, zlib.compress(json.dumps(sample, ensure_ascii=False,
                                                      separators=(',', ':')).encode()), gid))
    db.commit()


HTML = '''<!doctype html><html lang="ja"><meta charset="utf-8">
<title>PlotNote 本人筆跡の字庫</title><style>
body{font:16px system-ui;margin:24px;background:#f7f7f4;color:#202522}h1{font-size:24px}
button,input{font:inherit;padding:8px}button{cursor:pointer}#letters{display:flex;flex-wrap:wrap;gap:5px;margin:20px 0}
.letter{min-width:42px;border:1px solid #ccc;border-radius:6px;background:white}.done{background:#c9ead6}
#samples{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
.card{padding:18px;border:1px solid #ddd;border-radius:12px;background:white}.card svg{width:100%;height:160px}
.meta{font-size:12px;color:#666;overflow-wrap:anywhere}.accepted{border:2px solid #378858}.rejected{opacity:.5}
.reference{font-size:25px}label{display:block;margin:8px 0}.status{margin:10px 0;color:#46534b}
</style><h1>Goodnotesの筆跡を、君の字庫へ</h1>
<p>元の筆跡を見て、文字と切り分けが正しい見本を登録します。下の文字名は認識候補です。</p>
<p>ここで登録した字だけが出力用字庫に入ります。同じ文字の別の書き方も登録できます。</p>
<label><input type="checkbox" id="required" checked>今回のノートに必要な文字を優先</label>
<label>文字を探す <input id="find" size="12" placeholder="文字を入力"></label>
<button id="save" hidden>確認結果をJSONで保存</button>
<div id="summary" class="status"></div><div id="letters"></div><h2 id="heading"></h2>
<div id="message" role="status"></div><div id="samples"></div>
<script>
let chars=[], current='';
function el(tag,txt,cls){let n=document.createElement(tag);if(txt!==undefined)n.textContent=txt;if(cls)n.className=cls;return n}
async function api(path,body){
 if(window.PERSONAL_REVIEW){let d=window.PERSONAL_REVIEW;
 if(path==='/api/summary'){let by=new Map();for(let s of d.samples){let c=by.get(s.label)||{char:s.label,count:0,accepted:0};c.count++;c.accepted+=s.status==='accepted';by.set(s.label,c)}
 let characters=[...by.values()].sort((a,b)=>a.char.localeCompare(b.char));return {characters,accepted:characters.filter(c=>c.accepted).length,required:d.required}}
 if(path.startsWith('/api/samples?'))return d.samples.filter(s=>s.label===new URLSearchParams(path.split('?')[1]).get('char')).sort((a,b)=>Number(b.status==='accepted')-Number(a.status==='accepted')||Number(a.status==='rejected')-Number(b.status==='rejected')||Number(b.ocr_status==='match')-Number(a.ocr_status==='match')||(a.ranking_score??Infinity)-(b.ranking_score??Infinity));
 if(path==='/api/review'){if([...body.label].length!==1||!body.label.trim())throw Error('文字は1文字で入力してください');let s=d.samples.find(s=>s.id===body.id);if(!s)throw Error('Unknown exemplar');if(s.label!==body.label){s.ranking_score=null;delete s.ocr_status;delete s.ocr_reading;}Object.assign(s,body);d.decisions.set(s.id,{id:s.id,label:s.label,status:s.status});localStorage.setItem(d.storageKey,JSON.stringify({format:'plotnote-review-decisions-v2',reviews:[...d.decisions.values()]}));return {saved:true}}
 throw Error('Unknown request')}
 let r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});let j=await r.json();if(!r.ok)throw Error(j.error||r.status);return j}
async function load(){let s=await api('/api/summary');chars=s.characters;document.getElementById('summary').textContent=
 `元の筆跡あり ${chars.length}字種 ／ 確認済み ${s.accepted}字種 ／ 今回のノート ${s.required.length}字種（未発見を含む）`;
 window.requiredChars=new Set(s.required);letters()}
function letters(){let box=document.getElementById('letters');box.replaceChildren();let query=document.getElementById('find').value;
 for(let c of chars){if(document.getElementById('required').checked&&!window.requiredChars.has(c.char))continue;if(query&&!query.includes(c.char))continue;
 let b=el('button',c.char,'letter'+(c.accepted?' done':''));b.title=`${c.count}見本`;b.onclick=()=>show(c.char);box.append(b)}}
async function show(char){current=char;document.getElementById('heading').textContent=`「${char}」の見本`;
 let values=await api('/api/samples?char='+encodeURIComponent(char));let box=document.getElementById('samples');box.replaceChildren();
 for(let s of values){let card=el('div',undefined,'card '+s.status);card.append(el('div',s.label,'reference'));card.append(el('p',s.status==='accepted'?'登録済み':s.status==='rejected'?'使用しない':'未確認','meta'));
 let svg=document.createElementNS('http://www.w3.org/2000/svg','svg');let [x0,y0,x1,y1]=s.bbox;
 let pad=Math.max(x1-x0,y1-y0)*.12||1;svg.setAttribute('viewBox',`${x0-pad} ${y0-pad} ${x1-x0+pad*2} ${y1-y0+pad*2}`);
 for(let ps of s.paths){let path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',(ps.length===1?[ps[0],ps[0]]:ps).map((p,i)=>(i?'L':'M')+p.join(' ')).join(' '));
 path.setAttribute('fill','none');path.setAttribute('stroke','#202522');path.setAttribute('stroke-width',Math.max(x1-x0,y1-y0)*.012);path.setAttribute('stroke-linecap','round');path.setAttribute('stroke-linejoin','round');svg.append(path)}card.append(svg);
 if(s.em_height&&Number.isFinite(s.line_top)){let cell=document.createElementNS(svg.namespaceURI,'svg');let em=s.em_height,top=s.line_top,cw=Math.max(x1-x0,em),p=em*.15;
 cell.setAttribute('viewBox',`${x0-p} ${top-p} ${cw+2*p} ${em+2*p}`);
 for(let yy of [top,top+em]){let guide=document.createElementNS(svg.namespaceURI,'path');guide.setAttribute('d',`M ${x0-p} ${yy} H ${x0+cw+p}`);guide.setAttribute('stroke','#cbd2cc');guide.setAttribute('stroke-width',em*.006);cell.append(guide)}
 for(let ps of s.paths){let path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',(ps.length===1?[ps[0],ps[0]]:ps).map((p,i)=>(i?'L':'M')+p.join(' ')).join(' '));path.setAttribute('fill','none');path.setAttribute('stroke','#202522');path.setAttribute('stroke-width',em*.012);path.setAttribute('stroke-linecap','round');path.setAttribute('stroke-linejoin','round');cell.append(path)}
 card.append(el('p',s.metric_reference?'行内の大きさ・位置（周囲の筆跡から推定）':'行内の大きさ・位置（共通の基準）','meta'));card.append(cell)}
 if(s.ranking_score!==null&&s.ranking_score!==undefined)card.append(el('p','字形の比較スコアを表示順に使っています。','meta'));
 if(s.ocr_status)card.append(el('p','独立OCR：'+(s.ocr_reading||'読取なし')+' ／ '+(s.ocr_status==='match'?'候補と一致（OCRのみでは確定しません）':'候補とは不一致・要確認'),'meta'));
 card.append(el('p',s.book+' ／ '+s.page,'meta'));card.append(el('p','認識候補：'+s.recognition_candidates.join(' / '),'meta'));
 let label=el('input');label.value=s.label;label.size=3;label.setAttribute('aria-label','正しい文字');card.append(label);
 for(let [txt,status] of [['この文字として登録','accepted'],['使わない','rejected'],['未確認に戻す','unreviewed']]){
 let b=el('button',txt);b.onclick=async()=>{try{await api('/api/review',{id:s.id,label:label.value,status});document.getElementById('message').textContent='保存しました';await load();await show(current)}catch(e){document.getElementById('message').textContent=e.message}};card.append(b)}box.append(card)}}
document.getElementById('find').oninput=letters;document.getElementById('required').onchange=letters;
if(window.PERSONAL_REVIEW){let d=window.PERSONAL_REVIEW;d.decisions=new Map();try{let raw=localStorage.getItem(d.storageKey),saved=JSON.parse(raw||'{}');let legacy=Array.isArray(saved);if(legacy&&raw&&!localStorage.getItem(d.storageKey+'-legacy-snapshot'))localStorage.setItem(d.storageKey+'-legacy-snapshot',raw);let reviews=legacy?saved.filter(s=>s.status==='accepted'||s.status==='rejected'):(saved.format==='plotnote-review-decisions-v2'?saved.reviews:[]);for(let item of reviews)if(item&&typeof item.id==='string'&&typeof item.label==='string'&&[...item.label].length===1&&item.label.trim()&&['accepted','rejected','unreviewed'].includes(item.status))d.decisions.set(item.id,{id:item.id,label:item.label,status:item.status});for(let s of d.samples)if(d.decisions.has(s.id)){let decision=d.decisions.get(s.id);if(s.label!==decision.label){s.ranking_score=null;delete s.ocr_status;delete s.ocr_reading;}Object.assign(s,decision)}}catch(e){}
let b=document.getElementById('save');b.hidden=false;b.onclick=()=>{let data=d.samples.filter(s=>s.status!=='unreviewed'||d.decisions.has(s.id)).map(s=>({id:s.id,label:s.label,status:s.status}));let a=el('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({format:'plotnote-review-v1',reviews:data},null,2)],{type:'application/json'}));a.download='personal-font-reviews.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}}
load().catch(e=>document.getElementById('message').textContent=e.message);
</script></html>'''


def handler(db_path, required):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, data, content_type='application/json; charset=utf-8'):
            raw = data.encode() if isinstance(data, str) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/':
                return self.send(200, HTML, 'text/html; charset=utf-8')
            with sqlite3.connect(db_path, timeout=30) as db:
                if url.path == '/api/summary':
                    rows = db.execute("SELECT label,count(*),sum(status='accepted') "
                                      'FROM exemplars GROUP BY label ORDER BY label').fetchall()
                    return self.send(200, {'characters': [{'char': c, 'count': n, 'accepted': a}
                                                         for c, n, a in rows],
                                           'accepted': sum(bool(a) for c, n, a in rows),
                                           'required': sorted(required)})
                if url.path == '/api/samples':
                    char = parse_qs(url.query).get('char', [''])[0]
                    return self.send(200, read_samples(db, char))
            self.send(404, {'error': 'Not found'})

        def do_POST(self):
            if self.path != '/api/review':
                return self.send(404, {'error': 'Not found'})
            if self.headers.get('Content-Type') != 'application/json':
                return self.send(415, {'error': 'Expected application/json'})
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.send(403, {'error': 'Cross-origin request rejected'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('Invalid review size')
                data = json.loads(self.rfile.read(length))
                with sqlite3.connect(db_path, timeout=30) as db:
                    review(db, data['id'], data['label'], data['status'])
                self.send(200, {'saved': True})
            except (ValueError, KeyError, TypeError) as error:
                self.send(400, {'error': str(error)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--required', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--standalone', type=Path, help='Write offline review HTML instead of serving')
    parser.add_argument('--all-characters', action='store_true', help='Include the entire original-ink collection in offline HTML')
    parser.add_argument('--import-reviews', type=Path, help='Import decisions saved by offline review')
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error('Import and materialize the original ink first')
    required = set(json.loads(args.required.read_text())['characters'])
    if args.import_reviews:
        data = json.loads(args.import_reviews.read_text())
        if data.get('format') != 'plotnote-review-v1':
            parser.error('Unknown review file format')
        with sqlite3.connect(args.db) as db:
            # Validate the entire batch before applying any decisions.
            for item in data['reviews']:
                if (item.get('status') not in ('accepted', 'rejected', 'unreviewed') or
                    len(item.get('label', '')) != 1 or not item['label'].isprintable() or
                    item['label'].isspace() or db.execute('SELECT id FROM exemplars WHERE id=?',
                                                       (item.get('id'),)).fetchone() is None):
                    parser.error('Invalid decision in review batch; no changes applied')
            for item in data['reviews']:
                review(db, item['id'], item['label'], item['status'])
        print(json.dumps({'imported_reviews': len(data['reviews'])}))
        return
    if args.standalone:
        samples = []
        with sqlite3.connect(args.db) as db:
            for sample in read_samples(db):
                label, status = sample['label'], sample['status']
                if not args.all_characters and label not in required:
                    continue
                samples.append({k: sample[k] for k in ('id', 'book', 'page', 'bbox', 'recognition_candidates')})
                samples[-1].update(label=label, status=status,
                    paths=[[[round(x, 3), round(y, 3)] for x, y in path] for path in sample['paths']])
                for key in ('em_height', 'line_top', 'metric_reference', 'ranking_score', 'ocr_reading', 'ocr_status'):
                    if key in sample:
                        samples[-1][key] = sample[key]
        data = {'samples': samples, 'required': sorted(required),
                'storageKey': 'plotnote-review-' + str(args.db.resolve())}
        # Escape '<' in embedded data so note titles cannot terminate a script.
        embedded = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
        html = HTML.replace('<script>', '<script>window.PERSONAL_REVIEW=' + embedded + ';</script><script>', 1)
        args.standalone.write_text(html)
        print(json.dumps({'html': str(args.standalone), 'samples': len(samples),
                          'characters': len(set(s['label'] for s in samples))}))
        return
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(args.db, required))
    print(f'Personal font review: http://127.0.0.1:{server.server_port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
