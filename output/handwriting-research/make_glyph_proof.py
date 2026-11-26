"""Five manually labeled glyph exemplars, for feasibility only, not a full font."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[1]/'src'))
from plotnote.model import Page,Stroke
from plotnote.fonts import render_glyph
from plotnote.artifacts import svg,png_bytes
raw=json.loads((ROOT/'japanese-raw-strokes.json').read_text())
regions=[('生',50,68),('活',68,90),('習',90,110),('慣',110,140.4),('病',140.4,164)]
glyphs={}
for char,lo,hi in regions:
    found=[]
    for i,s in enumerate(raw['strokes']):
        p=s['points']
        if not p:continue
        x0=min(pt[0] for pt in p);y0=min(pt[1] for pt in p)
        x1=max(pt[0] for pt in p);y1=max(pt[1] for pt in p)
        if lo<=x0 and x1<=hi and 78<=y0 and y1<=109:
            found.append((i,s))
    assert found
    xmin=min(pt[0] for i,s in found for pt in s['points'])
    xmax=max(pt[0] for i,s in found for pt in s['points'])
    glyphs[char]={'label_method':'Manual visual transcription of title and bounding region; prototype only',
        'source_stroke_indices':[i for i,s in found],
        'width_em':(xmax-xmin)/26,
        'paths':[[( (x-xmin)/26,(y-81)/26 ) for x,y,w in s['points']] for i,s in found]}
proof={'source':raw['source_member'],'source_page_index':raw['page_index'],
       'status':'5 glyph feasibility sample only. One exemplar each. Whole-stroke ordering NOT yet validated; points within decoded strokes retained.',
       'normalization':'Common title height 26 canvas units; aspect ratios and connected paths preserved',
       'glyphs':glyphs}
(ROOT/'personal-stroke-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
page=Page(80,50)
def regular(text,x,y,size):
    for char in text:
        for path in render_glyph(char,(size,0,0,size,x,y)):
            page.strokes.append(Stroke(path,'reference:'+char))
        x+=size
regular('従来',4,3,3)
regular('生活習慣病',8,10,7)
regular('本人の筆跡',4,26,3)
x=8
for char in '生活習慣病':
    g=glyphs[char]
    for path in g['paths']:
        page.strokes.append(Stroke([(x+px*7,32+py*7) for px,py in path],'personal:'+char))
    x+=g['width_em']*7+1
page.validate()
(ROOT/'personal-vs-standard.svg').write_text(svg(page,.25))
(ROOT/'personal-vs-standard.png').write_bytes(png_bytes(page,.25))
print(json.dumps({'glyphs':list(glyphs),'strokes_per_glyph':{c:len(g['paths']) for c,g in glyphs.items()},'complete_font':False},ensure_ascii=False))
