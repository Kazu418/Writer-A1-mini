"""Keep the exact proven layout; omit formula strokes only on passes 2-4."""
from pathlib import Path
import sys,json,pickle,hashlib,zipfile,math
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_a4_note as b
import pymupdf
from plotnote.fonts import use_personal_font
from plotnote.profile import Profile
from plotnote.model import Page
from plotnote.gcode import generate
from plotnote.package import read_package
from plotnote.artifacts import svg
BASE=Path(__file__).resolve().parent
DATA=pickle.loads((BASE/'a4-v4-formula-work/original-layout.pkl').read_bytes())
OUT=BASE/'a4-v4-display-formula-blanks'
OUT.mkdir(exist_ok=False);(OUT/'gcode').mkdir();(OUT/'preview').mkdir()
NAMES=('face1-pass1','face1-pass2','face2-pass1','face2-pass2')
# Explicit formulas embedded in prose. Numeric examples and variable descriptions remain.
INLINE=[]  # Preserve every inline expression and all explanatory text.

remove=[set() for _ in range(4)];offset=[0]*4;manifest=[]
font=json.loads((BASE/'../personal-font/personal-font-with-forms.json').read_text())
with use_personal_font(font,DATA['layout']['standard_font_fallback']):
 for slot,y,u in DATA['placed']:
  side,col,half=slot//4,(slot%4)//2,slot%2
  idx=side*2+half;marked=set(u.get('formula_indices',[]));reasons=[]
  if marked:reasons.append('display formula')
  paragraph=u.get('paragraph','');spans=[]
  for expression in INLINE:
   start=0
   while (where:=paragraph.find(expression,start))>=0:
    spans.append((where,where+len(expression),expression));start=where+len(expression)
  cursor=0
  for ln,st,sz,yy in u.get('text_parts',[]):
   textpaths=b.txt(ln,sz).paths
   _,unders=b.mark(paragraph)
   paths=textpaths+b.underline(ln,st,unders,sz)
   assert b.shifted(paths,0,yy)==u['paths'][cursor:cursor+len(paths)], ('Text mapping mismatch',u['alt'])
   for begin,end,expression in spans:
    lo=max(begin,st)-st;hi=min(end,st+len(ln))-st
    if hi>lo:
     a=len(b.txt(ln[:lo],sz).paths);z=len(b.txt(ln[:hi],sz).paths)
     marked.update(range(cursor+a,cursor+z));reasons.append(expression)
   cursor+=len(paths)
  if idx!=0 and marked:
   remove[idx].update(offset[idx]+i for i in marked)
   points=[pt for i in marked for pt in u['paths'][i]]
   manifest.append({'tile':NAMES[idx],'source':u['alt'],'formulas':list(dict.fromkeys(reasons)),
    'removed_strokes':len(marked),'bounds_tile_mm':[round(min(p[0] for p in points)+b.COL_X[col],3),round(min(p[1] for p in points)+y,3),round(max(p[0] for p in points)+b.COL_X[col],3),round(max(p[1] for p in points)+y,3)]})
  offset[idx]+=len(u['paths'])
rows=[]
for idx,name in enumerate(NAMES):
 oldpage=DATA['pages'][idx]
 assert len(oldpage.strokes)==offset[idx]
 if idx==0:
  assert not remove[idx]
  continue
 page=Page(oldpage.width,oldpage.height,[s for n,s in enumerate(oldpage.strokes) if n not in remove[idx]])
 profile=Profile.load(BASE/f'a4-v4-pressure/gcode/{name}-profile.json')
 code,_,validation=generate(page,profile,homed=True)
 # Every kept stroke has identical geometry; omission never causes any reflow.
 oldcode=(BASE/f'a4-v4-pressure/gcode/{name}.gcode').read_text()
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
 previous=blocks(oldcode);current=blocks(code)
 assert current==[stroke for n,stroke in enumerate(previous) if n not in remove[idx]], 'Kept command changed'
 profile.save(OUT/f'gcode/{name}-profile.json');(OUT/f'gcode/{name}.gcode').write_text(code)
 preview=svg(page,profile.pen_width);(OUT/f'preview/{name}.svg').write_text(preview)
 print(name,'coordinates verified;',len(remove[idx]),'formula strokes removed',flush=True)
 with pymupdf.open(stream=preview.encode(),filetype='svg') as doc:thumbnail=doc[0].get_pixmap(dpi=72).tobytes('png')
 stats=page.summary()
 seconds=round((stats['ink_mm']/profile.draw_feed+stats['travel_mm']/profile.travel_feed+len(page.strokes)*2*(profile.lift_z-profile.draw_z)/profile.z_feed)*60)
 with zipfile.ZipFile(BASE/f'a4-v4-pressure/gcode/{name}.gcode.3mf') as zin,zipfile.ZipFile(OUT/f'gcode/{name}.gcode.3mf','w',zipfile.ZIP_DEFLATED) as zout:
  for entry in zin.infolist():
   data=zin.read(entry.filename)
   if entry.filename=='Metadata/plate_1.gcode':data=code.encode()
   elif entry.filename=='Metadata/plate_1.gcode.md5':data=(hashlib.md5(code.encode()).hexdigest().upper()+'\n').encode()
   elif entry.filename=='Metadata/plate_1.png':data=thumbnail
   elif entry.filename=='Metadata/slice_info.config':
    tree=ET.fromstring(data)
    for element in tree.iter('metadata'):
     if element.get('key')=='prediction':element.set('value',str(seconds))
    data=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
   zout.writestr(entry.filename,data)
 assert read_package(OUT/f'gcode/{name}.gcode.3mf')==code
 rows.append({'tile':name,'original_strokes':len(oldpage.strokes),'removed_formula_strokes':len(remove[idx]),'remaining_strokes':len(page.strokes),'minutes_est':round(seconds/60,1),'validation':validation,'retained_commands_identical':True})
 print(name,'package verified',flush=True)
(OUT/'gcode/summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
(OUT/'removed-formulas.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(OUT/'layout-verification.json').write_text(json.dumps({'source':'a4-v4-pressure','original_all_four_passes_reproduced_byte_for_byte':True,'first_pass_unchanged_and_omitted_from_new_print_files':True,'text_figure_coordinates_unchanged':True,'no_reflow':True,'draw_z':4.8,'lift_z':6.5,'safe_z':10,'inline_expressions':INLINE},ensure_ascii=False,indent=2))
sender=(BASE/'a4-v4-pressure/send_pass_once.py').read_text()
sender=sender.replace("['face1-pass1','face1-pass2','face2-pass1','face2-pass2']","['face1-pass2','face2-pass1','face2-pass2']")
sender=sender.replace('PlotNote A4 v4 ','PlotNote A4 display formula blanks ')
(OUT/'send_pass_once.py').write_text(sender)
print('DONE',str(OUT),flush=True)
