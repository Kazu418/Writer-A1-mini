"""Ordered small-text ladder below the successful first line."""
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'src'))
from plotnote.model import Page, Stroke
from plotnote.fonts import render_glyph
from plotnote.profile import Profile
from plotnote.gcode import generate
from plotnote.validate import validate_gcode
from plotnote.package import build_package, read_package

SIZES=[5,4,3,2.5,2,1.5]
TOPS=[3,11,18,24,29.5,34.5]

def setup():
    page=Page(60,50)
    def text(value,size,x,y):
        for char in value:
            for points in render_glyph(char,(size,0,0,size,x,y)):
                page.strokes.append(Stroke(points,'text:'+char))
            x+=size
    for size,top in zip(SIZES,TOPS):
        text(str(size).removesuffix('.0'),2,8,top+max(0,(size-2)/2))
        text('永あA8',size,20,top)
    profile=Profile(calibrated=True,pen_offset_x=0,pen_offset_y=-30.8,
        paper_x=65,paper_y=30,paper_width=60,paper_height=50,
        nozzle_min_x=40,nozzle_max_x=140,nozzle_min_y=40,nozzle_max_y=150,
        draw_z=4.9,lift_z=8,safe_z=10,draw_feed=600,travel_feed=1200,z_feed=300,
        calibration_notes='One-off central size ladder below previous ink; nominal test canvas, not whole-sheet calibration. User requests below existing line. Contact physically verified Z5; +0.1mm compression at Z4.9.')
    return page,profile

if __name__=='__main__':
    page,profile=setup()
    code,_,report=generate(page,profile,homed=True)
    code='\n'.join(line+('\nM400' if line.startswith('G1 Z') else '') for line in code.splitlines())+'\n'
    report=validate_gcode(code,profile,page)
    points=[profile.machine_point(*p) for s in page.strokes for p in s.points]
    ink=[(x,y-30.8) for x,y in points]
    bounds=lambda p:[min(x for x,y in p),min(y for x,y in p),max(x for x,y in p),max(y for x,y in p)]
    assert max(y for x,y in ink)<80, 'Would overlap preceding successful line at bed Y85..89'
    label='04_SIZE_LADDER'
    (HERE/(label+'.gcode')).write_text(code)
    artifact=HERE/(label+'.gcode.3mf')
    artifact.write_bytes(build_package(code,page,profile))
    assert read_package(artifact)==code
    profile.save(HERE/'size-ladder-profile.json')
    from plotnote.artifacts import png_bytes
    (HERE/'size-ladder.png').write_bytes(png_bytes(page,profile.pen_width))
    report.update(sizes_mm=SIZES,sample='永あA8',labels='mm em size, not exact ink height',pen_bounds_mm=bounds(ink),nozzle_bounds_mm=bounds(points),source_summary=page.summary())
    (HERE/'size-ladder-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    old=(HERE/'send_write_z5_once.py').read_text()
    old=old.replace('from prepare_absolute_test import setup','from prepare_size_test import setup')
    old=old.replace('live-write-z5-run.json','live-size-ladder-run.json')
    old=old.replace('03_WRITE_Z5','04_SIZE_LADDER')
    old=old.replace('PlotNote WRITE ABSOLUTE Z5','PlotNote SIZE LADDER Z4.9')
    old=old.replace('time.monotonic()+180','time.monotonic()+600')
    (HERE/'send_size_ladder_once.py').write_text(old)
    print(json.dumps(report,ensure_ascii=False))
