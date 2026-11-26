"""Remove selected formula strokes without reflowing the proven A4 layout."""
from pathlib import Path
import sys,json,inspect,pickle,difflib
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_a4_note as b
from plotnote.fonts import use_personal_font
from plotnote.gcode import generate
from plotnote.profile import Profile
BASE=Path(__file__).resolve().parent
WORK=BASE/'a4-v4-formula-work'
WORK.mkdir(exist_ok=True)
layout=json.loads((BASE/'a4-v4/layout.json').read_text())
font=json.loads((BASE/'../personal-font/personal-font-with-forms.json').read_text())
source=inspect.getsource(b.build_units)
source=source.replace("block['paths'] += fp", "block['formula_indices'] = list(range(len(block['paths']), len(block['paths']) + len(fp)))\n                block['paths'] += fp")
needle="'gap': 1.0, 'alt': b.alt}"
assert source.count(needle)==2
source=source.replace(needle,"'gap': 1.0, 'alt': b.alt, 'formula_indices': list(range(len(b.paths)))}")
source=source.replace("'gap': 0, 'alt': lines[n][0]}", "'gap': 0, 'alt': lines[n][0], 'paragraph': val, 'text_parts': [(lines[n][0], lines[n][1], sz, 0)]}")
source=source.replace("'gap': 1.2, 'alt': text[:30]}", "'gap': 1.2, 'alt': text[:30], 'paragraph': val, 'text_parts': [(ln, st, sz, n * lead) for n, (ln, st) in enumerate(lines)]}")
exec(compile(source,'<formula-tracked-build-units>','exec'),b.__dict__)
print('Rebuilding original layout with formula-stroke metadata.',flush=True)
with use_personal_font(font,layout['standard_font_fallback']):
 units,placed,over,used=b.run(layout['font_size_mm'],layout['leading_k'])
 assert over==0
 pages=b.make_tiles(placed)
 for name,page in zip(('face1-pass1','face1-pass2','face2-pass1','face2-pass2'),pages):
  p=Profile.load(BASE/f'a4-v4-pressure/gcode/{name}-profile.json')
  code,_,_=generate(page,p,homed=True)
  old=(BASE/f'a4-v4-pressure/gcode/{name}.gcode').read_text()
  if code!=old:
   print(''.join(list(difflib.unified_diff(old.splitlines(True),code.splitlines(True)))[:16]),flush=True)
   raise SystemExit('Original layout reproduction mismatch; no output for printing created')
  print(name,'original G-code reproduced byte-for-byte',flush=True)
 with (WORK/'original-layout.pkl').open('wb') as f:pickle.dump({'placed':placed,'pages':pages,'units':units,'layout':layout},f)
 print('Original coordinate mapping saved.',flush=True)
