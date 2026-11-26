"""Plot five actual personal glyph exemplars below the completed paragraph."""
import hashlib,json,sys
from dataclasses import replace
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'src'))
from plotnote.model import Page,Stroke
from plotnote.profile import Profile
from plotnote.gcode import generate
from plotnote.validate import validate_gcode
from plotnote.package import build_package,read_package
from plotnote.artifacts import svg,png_bytes

SOURCE=HERE.parent/'handwriting-research/personal-stroke-proof.json'
TEXT='生活習慣病'

def setup():
    data=json.loads(SOURCE.read_text())
    page=Page(50,35)
    x=5.;size=2.5;top=26.
    for char in TEXT:
        glyph=data['glyphs'][char]
        for path in glyph['paths']:
            page.strokes.append(Stroke([(x+px*size,top+py*size) for px,py in path], 'personal:'+char))
        x+=glyph['width_em']*size+.35
    p=Profile.load(HERE/'handwriting-30-profile.json')
    p=replace(p,calibration_notes='Actual user handwriting from Goodnotes, five manually segmented exemplars. New row below completed paragraph. User confirms unchanged paper, no rehoming, pen still mounted. Previously verified contactZ5; draw4.9/lift6.5/safe10. Draw30mm/s. Stored stroke sequence not verified as chronological; each decoded path direction retained.')
    return page,p

if __name__=='__main__':
    previous=json.loads((HERE/'live-paragraph-fast-run.json').read_text())
    assert previous.get('outcome')=='completed'
    page,p=setup()
    page.validate()
    points=[p.machine_point(*pt) for s in page.strokes for pt in s.points]
    ink=[(x,y+p.pen_offset_y) for x,y in points]
    bounds=lambda a:[min(x for x,y in a),min(y for x,y in a),max(x for x,y in a),max(y for x,y in a)]
    prior=json.loads((HERE/'paragraph-fast-validation.json').read_text())['pen_bounds_mm']
    assert bounds(ink)[3]+p.pen_width/2+2 < prior[1]-.15, 'Insufficient gap below existing paragraph'
    code,_,report=generate(page,p,homed=True)
    code='\n'.join(line+('\nM400' if line.startswith('G1 Z') else '') for line in code.splitlines())+'\n'
    report=validate_gcode(code,p,page)
    label='07_PERSONAL_LIFESTYLE'
    (HERE/(label+'.gcode')).write_text(code)
    artifact=HERE/(label+'.gcode.3mf')
    artifact.write_bytes(build_package(code,page,p))
    assert read_package(artifact)==code
    (HERE/'personal-word.svg').write_text(svg(page,.25))
    (HERE/'personal-word.png').write_bytes(png_bytes(page,.25))
    report.update(text=TEXT,size_em_mm=2.5,pen_bounds_mm=bounds(ink),nozzle_bounds_mm=bounds(points),
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        source='Original Goodnotes centerlines; no randomized standard glyphs',previous_paragraph_bounds_mm=prior,
        user_confirmed_no_rehoming_and_same_paper=True,stroke_chronology_verified=False)
    (HERE/'personal-word-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    p.save(HERE/'personal-word-profile.json')
    sender=(HERE/'send_handwriting_30_once.py').read_text()
    sender=sender.replace('from prepare_handwritten_test import setup','from prepare_personal_word_test import setup')
    sender=sender.replace('live-handwriting-30-run.json','live-personal-word-run.json')
    sender=sender.replace('06_HANDWRITING_30',label)
    sender=sender.replace('PlotNote HANDWRITING 30mm-s','PlotNote PERSONAL 5 GLYPHS')
    (HERE/'send_personal_word_once.py').write_text(sender)
    print(json.dumps(report,ensure_ascii=False))
