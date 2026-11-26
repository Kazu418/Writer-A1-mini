"""Replace only underlined keywords on the unprinted back face; retain all other coordinates."""
from pathlib import Path
import sys,json,pickle,hashlib,zipfile
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_a4_note as b
import pymupdf as fitz
from plotnote.fonts import use_personal_font
from plotnote.keyword_style import fit_standard_keyword
from plotnote.model import Page,Stroke
from plotnote.profile import Profile
from plotnote.gcode import generate
from plotnote.package import read_package
from plotnote.artifacts import svg
from plotnote.handoff import _face_content
BASE=Path(__file__).resolve().parent
DATA=pickle.loads((BASE/'a4-v4-formula-work/original-layout.pkl').read_bytes())
OUT=BASE/'a4-v5-standard-keywords';OUT.mkdir(exist_ok=False);(OUT/'gcode').mkdir();(OUT/'preview').mkdir()
names=('face1-pass1','face1-pass2','face2-pass1','face2-pass2')
pages=[Page(165,127.5) for _ in range(4)];mapping=[[] for _ in range(4)];offset=[0]*4;changes=[]
font=json.loads((BASE/'../personal-font/personal-font-with-forms.json').read_text())
with use_personal_font(font,DATA['layout']['standard_font_fallback']):
 for slot,y,u in DATA['placed']:
  side,col,half=slot//4,(slot%4)//2,slot%2;idx=side*2+half
  formula=set(u.get('formula_indices',[])) if idx>=1 else set()
  replacements={};cursor=0;paragraph=u.get('paragraph','')
  _,spans=b.mark(paragraph)
  if idx>=2:
   for ln,st,sz,yy in u.get('text_parts',[]):
    ps=b.txt(ln,sz).paths+b.underline(ln,st,spans,sz)
    assert b.shifted(ps,0,yy)==u['paths'][cursor:cursor+len(ps)]
    for a,z in spans:
     lo=max(a,st)-st;hi=min(z,st+len(ln))-st
     if hi<=lo:continue
     start=cursor+len(b.txt(ln[:lo],sz).paths);end=cursor+len(b.txt(ln[:hi],sz).paths)
     reference=u['paths'][start:end]
     if not reference:continue
     text=ln[lo:hi];seed=int.from_bytes(hashlib.sha256((paragraph[a:z]+'|'+text).encode()).digest()[:8],'big')
     replacement=fit_standard_keyword(text,sz,reference,seed=seed,pen_width=.3)
     assert not set(range(start,end))&formula
     assert start not in replacements
     replacements[start]=(end,replacement,text)
     changes.append({'tile':names[idx],'keyword':paragraph[a:z],'segment':text,'old_strokes':end-start,'new_strokes':len(replacement),'underline_unchanged':True})
    cursor+=len(ps)
  n=0
  while n<len(u['paths']):
   if n in replacements:
    end,paths,text=replacements[n]
    pages[idx].strokes.extend(Stroke(p,'standard-keyword:'+text) for p in b.shifted(paths,b.COL_X[col],y))
    mapping[idx].extend([None]*len(paths));n=end
   else:
    if n not in formula:
     pages[idx].strokes.append(Stroke(b.shifted([u['paths'][n]],b.COL_X[col],y)[0],u['alt']))
     mapping[idx].append(offset[idx]+n)
    n+=1
  offset[idx]+=len(u['paths'])

def blocks(text):
 result=[];current=None
 for line in text.splitlines():
  if line.startswith('; stroke '):
   if current is not None:result.append(current)
   current=[]
  elif current is not None:
   if line.startswith('G1 Z10.000'):break
   current.append(line)
 if current is not None:result.append(current)
 return result
rows=[]
for idx in (2,3):
 name=names[idx];page=pages[idx];profile=Profile.load(BASE/f'a4-v4-display-formula-blanks/gcode/{name}-profile.json')
 code,_,validation=generate(page,profile,homed=True)
 oldblocks=blocks((BASE/f'a4-v4-pressure/gcode/{name}.gcode').read_text());newblocks=blocks(code)
 assert len(newblocks)==len(mapping[idx])
 for new,original in zip(newblocks,mapping[idx]):
  if original is not None:assert new==oldblocks[original], 'Non-keyword drawing changed'
 (OUT/f'gcode/{name}.gcode').write_text(code);profile.save(OUT/f'gcode/{name}-profile.json')
 vector=svg(page,.3);(OUT/f'preview/{name}.svg').write_text(vector)
 with fitz.open(stream=vector.encode(),filetype='svg') as d:png=d[0].get_pixmap(dpi=72).tobytes('png')
 stats=page.summary();seconds=round((stats['ink_mm']/profile.draw_feed+stats['travel_mm']/profile.travel_feed+len(page.strokes)*2*(profile.lift_z-profile.draw_z)/profile.z_feed)*60)
 with zipfile.ZipFile(BASE/f'a4-v4-display-formula-blanks/gcode/{name}.gcode.3mf') as zin,zipfile.ZipFile(OUT/f'gcode/{name}.gcode.3mf','w',zipfile.ZIP_DEFLATED) as zout:
  for entry in zin.infolist():
   data=zin.read(entry.filename)
   if entry.filename=='Metadata/plate_1.gcode':data=code.encode()
   elif entry.filename=='Metadata/plate_1.gcode.md5':data=(hashlib.md5(code.encode()).hexdigest().upper()+'\n').encode()
   elif entry.filename=='Metadata/plate_1.png':data=png
   elif entry.filename=='Metadata/slice_info.config':
    tree=ET.fromstring(data)
    for element in tree.iter('metadata'):
     if element.get('key')=='prediction':element.set('value',str(seconds))
    data=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
   zout.writestr(entry.filename,data)
 assert read_package(OUT/f'gcode/{name}.gcode.3mf')==code
 rows.append({'tile':name,'strokes':len(page.strokes),'minutes_est':round(seconds/60,1),'keyword_segments':sum(x['tile']==name for x in changes),'non_keyword_commands_identical':True,'validation':validation})
 print(name,'validated',rows[-1],flush=True)
passes=[]
for idx,name in enumerate(names):
 if idx==0:folder=BASE/'a4-v4-pressure'
 elif idx==1:folder=BASE/'a4-v4-display-formula-blanks'
 else:folder=OUT
 passes.append({'face':idx//2+1,'pass':idx%2+1,'gcode':str((folder/f'gcode/{name}.gcode').relative_to(ROOT))})
doc=fitz.open();pt=72/25.4
for face in (1,2):
 page=doc.new_page(width=210*pt,height=297*pt);xref=doc.get_new_xref();doc.update_object(xref,'<<>>');doc.update_stream(xref,_face_content(ROOT,passes,face));page.set_contents(xref)
doc.set_metadata({'title':'A4 preview - standard handwritten keywords on back face','subject':'Unchanged printed front; underlines and non-keyword commands retained; displayed formulas blank'})
doc.save(OUT/'a4-both-sides-preview.pdf',garbage=4,deflate=True);doc.close()
with fitz.open(OUT/'a4-both-sides-preview.pdf') as d:d[1].get_pixmap(dpi=120).save(OUT/'preview/back-check.png')
(OUT/'gcode/summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));(OUT/'keyword-changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
(OUT/'style-contract.json').write_text(json.dumps({'font':'Bundled KanjiVG/Hershey standard centerlines with deterministic handwriting variation','scope':'Only underlined body keywords on back-face passes','printed_front_unchanged':True,'underlines_unchanged':True,'non_keyword_commands_identical':True,'fit':'Uniformly fit each keyword segment inside its existing ink bounding box; no paragraph reflow','formulas':'Dedicated displayed formulas remain blank; every inline expression retained','draw_z':4.8,'lift_z':6.5,'safe_z':10},ensure_ascii=False,indent=2))
sender=(BASE/'a4-v4-display-formula-blanks/send_pass_once.py').read_text().replace("['face1-pass2','face2-pass1','face2-pass2']","['face2-pass1','face2-pass2']").replace('PlotNote A4 display formula blanks ','PlotNote standard keywords ')
(OUT/'send_pass_once.py').write_text(sender)
print('DONE',OUT,flush=True)
