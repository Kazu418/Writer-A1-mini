"""102-character paragraph with compact 2.5mm type and faster pen motion."""
import json
import sys
from dataclasses import replace
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'src'))
sys.path.insert(0,str(HERE.parent/'exam-note'))
from build_note import txt
from plotnote.model import Page, Stroke
from plotnote.profile import Profile
from plotnote.gcode import generate
from plotnote.validate import validate_gcode
from plotnote.package import build_package,read_package
from plotnote.artifacts import png_bytes

TEXT='データサイエンスは、集めた情報から意味を見つけ、より良い判断につなげる学問である。平均だけでなく、ばらつきや分布にも注目しよう。目的を明確にして分析し、得られた結果を確かめながら、次の行動へ生かしていく。'

def lines():
    result=[];current=''
    for char in TEXT:
        if current and txt(current+char,2.5).width>40:
            # Avoid beginning a line with closing punctuation.
            if char in '、。':
                carry=current[-1]
                result.append(current[:-1]);current=carry+char
            else:
                result.append(current);current=char
        else:current+=char
    if current:result.append(current)
    assert ''.join(result)==TEXT
    return result

def setup():
    page=Page(50,35)
    for index,line in enumerate(lines()):
        box=txt(line,2.5)
        assert box.width<=40
        page.strokes.extend(Stroke([(x+5,y+3+index*3.8) for x,y in ps], 'paragraph:'+line) for ps in box.paths)
    p=Profile.load(HERE/'central-test-fast-candidate-profile.json')
    p=replace(p,paper_x=65,paper_y=65,paper_width=50,paper_height=35,
        calibration_notes='102-character central paragraph on fresh paper. Requires renewed Z5 contact confirmation after pen remounting before dispatch. Type2.5mm; ink gap0.35mm; drawZ4.9/lift6.5/safe10; draw20/travel40/Z10 mm per second.')
    return page,p

if __name__=='__main__':
    page,p=setup()
    code,_,report=generate(page,p,homed=True)
    code='\n'.join(line+('\nM400' if line.startswith('G1 Z') else '') for line in code.splitlines())+'\n'
    report=validate_gcode(code,p,page)
    label='05_PARAGRAPH_2_5_FAST'
    (HERE/(label+'.gcode')).write_text(code)
    artifact=HERE/(label+'.gcode.3mf')
    artifact.write_bytes(build_package(code,page,p))
    assert read_package(artifact)==code
    (HERE/'paragraph-fast.png').write_bytes(png_bytes(page,.25))
    (HERE/'paragraph-fast.txt').write_text('\n'.join(lines())+'\n')
    points=[p.machine_point(*pt) for s in page.strokes for pt in s.points]
    bounds=lambda points:[min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)]
    summary=page.summary()
    report.update(characters=len(TEXT),lines=lines(),pen_bounds_mm=bounds([(x,y-30.8) for x,y in points]),
        nozzle_bounds_mm=bounds(points),requires_current_z5_contact_confirmation=True,
        ideal_motion_seconds=round(summary['ink_mm']/20+summary['travel_mm']/40+summary['strokes']*2*1.6/10),summary=summary)
    (HERE/'paragraph-fast-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    p.save(HERE/'paragraph-fast-profile.json')
    old=(HERE/'send_write_z5_once.py').read_text()
    old=old.replace('from prepare_absolute_test import setup','from prepare_paragraph_test import setup')
    old=old.replace('live-write-z5-run.json','live-paragraph-fast-run.json')
    old=old.replace('03_WRITE_Z5',label)
    old=old.replace('PlotNote WRITE ABSOLUTE Z5','PlotNote 102 CHAR COMPACT FAST')
    old=old.replace('time.monotonic()+180','time.monotonic()+900')
    old=old.replace('    if type(writing) is not bool:', "    if os.environ.get('PLOTNOTE_Z5_CONFIRMED')!='1':raise SystemExit('Renewed physical Z5 contact confirmation required')\n    if type(writing) is not bool:")
    (HERE/'send_paragraph_fast_once.py').write_text(old)
    print(json.dumps(report,ensure_ascii=False))
