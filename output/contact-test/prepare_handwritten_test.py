"""Handwriting-style candidate; preparation sends no command to the printer."""
import json
import sys
from pathlib import Path
from dataclasses import replace
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'src'))
from prepare_paragraph_test import TEXT, setup as regular_setup
from plotnote.handwriting import paragraph
from plotnote.artifacts import png_bytes,svg
from plotnote.gcode import generate
from plotnote.validate import validate_gcode
from plotnote.package import build_package,read_package


def setup():
    page,_=paragraph(TEXT,width=50,height=35,size=2.5,line_pitch=3.1,
                     margin=3,seed=20261125,pen_width=.25)
    _,p=regular_setup()
    p=replace(p,draw_feed=1800,
        calibration_notes='Handwriting candidate: 102 characters, size2.5mm, pitch3.1mm +/-0.12 with collision clearance; draw30mm/s, travel40, Z10. ContactZ5 physical calibration must still be valid. Preview/package use identical seeded paths. New quality not physically verified.')
    return page,p

if __name__=='__main__':
    page,p=setup()
    _,style=paragraph(TEXT,width=50,height=35,size=2.5,line_pitch=3.1,
                     margin=3,seed=20261125,pen_width=.25)
    code,_,report=generate(page,p,homed=True)
    code='\n'.join(line+('\nM400' if line.startswith('G1 Z') else '') for line in code.splitlines())+'\n'
    report=validate_gcode(code,p,page)
    label='06_HANDWRITING_30'
    (HERE/(label+'.gcode')).write_text(code)
    artifact=HERE/(label+'.gcode.3mf')
    artifact.write_bytes(build_package(code,page,p))
    assert read_package(artifact)==code
    (HERE/'handwriting-30.png').write_bytes(png_bytes(page,.25))
    (HERE/'handwriting-30.svg').write_text(svg(page,.25))
    style.update(report,characters=len(TEXT),draw_mm_s=30,travel_mm_s=40,z_mm_s=10,
                 draw_z_mm=4.9,lift_z_mm=6.5,safe_z_mm=10,
                 physical_result='not yet executed',summary=page.summary())
    (HERE/'handwriting-30-validation.json').write_text(json.dumps(style,ensure_ascii=False,indent=2)+'\n')
    p.save(HERE/'handwriting-30-profile.json')
    sender=(HERE/'send_paragraph_fast_once.py').read_text()
    sender=sender.replace('from prepare_paragraph_test import setup','from prepare_handwritten_test import setup')
    sender=sender.replace('live-paragraph-fast-run.json','live-handwriting-30-run.json')
    sender=sender.replace('05_PARAGRAPH_2_5_FAST',label)
    sender=sender.replace('PlotNote 102 CHAR COMPACT FAST','PlotNote HANDWRITING 30mm-s')
    (HERE/'send_handwriting_30_once.py').write_text(sender)
    print(json.dumps({'characters':len(TEXT),'rows':style['rows'],'validation':report},ensure_ascii=False))
