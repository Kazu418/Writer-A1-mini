import json, zlib, sqlite3, numpy as np, onnxruntime as ort
from PIL import Image, ImageDraw
S='/private/tmp/claude-501/-Users-kazuzon/84e7bd32-8e8d-4a9c-9a0e-110b7560cae1/scratchpad/lt8/'
DB="file:/Users/kazuzon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Kosen/データサイエンス/PlotNote/output/personal-font/goodnotes.sqlite3?mode=ro&immutable=1"
labels=json.load(open(S+'labels.json')); chars=[e['char'] for e in labels]
sess=ort.InferenceSession(S+'model.int8.onnx',providers=['CPUExecutionProvider'])
def render(paths, side=160, pad=14, wfrac=0.035):
    pts=[p for path in paths for p in path]
    x0=min(p[0] for p in pts);x1=max(p[0] for p in pts);y0=min(p[1] for p in pts);y1=max(p[1] for p in pts)
    e=max(x1-x0,y1-y0,1e-6);sc=(side-2*pad)/e
    ox=pad+((side-2*pad)-(x1-x0)*sc)/2; oy=pad+((side-2*pad)-(y1-y0)*sc)/2
    im=Image.new('L',(side,side),255);d=ImageDraw.Draw(im);w=max(2,int(side*wfrac))
    for path in paths:
        q=[((x-x0)*sc+ox,(y-y0)*sc+oy) for x,y in path]
        if len(q)==1:q=q*2
        d.line(q,fill=0,width=w,joint='curve')
        for x,y in (q[0],q[-1]): d.ellipse([x-w/2,y-w/2,x+w/2,y+w/2],fill=0)
    # pad to square already; resize to 128 like predict.py
    return np.asarray(im.resize((128,128),Image.BILINEAR),np.float32)[None,None]
def predict(batch):
    x=np.concatenate(batch);out=[]
    for i in range(0,len(x),64):
        lg=sess.run(['logits'],{'input':x[i:i+64]})[0].astype(np.float64)
        e=np.exp(lg-lg.max(1,keepdims=True));out.append(e/e.sum(1,keepdims=True))
    return np.concatenate(out)
def rows(where):
    db=sqlite3.connect(DB,uri=True)
    for gid,label,status,blob in db.execute(f'SELECT id,label,status,payload FROM exemplars {where}'):
        yield gid,label,status,json.loads(zlib.decompress(blob))
