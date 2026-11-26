"""Small central test only: confirmed physical contact at absolute Z5."""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'src'))
from plotnote.contact_test import test_page
from plotnote.model import Page, Stroke
from plotnote.profile import Profile
from plotnote.gcode import generate
from plotnote.validate import validate_gcode
from plotnote.package import build_package, read_package

def setup():
    original = test_page()
    page = Page(40, 20, [Stroke([(x-70, y-80) for x,y in s.points], s.source) for s in original.strokes])
    profile = Profile(calibrated=True, pen_offset_x=0, pen_offset_y=-30.8,
        paper_x=70, paper_y=80, paper_width=40, paper_height=20,
        nozzle_min_x=40, nozzle_max_x=140, nozzle_min_y=40, nozzle_max_y=150,
        draw_z=5, lift_z=8, safe_z=10, draw_feed=600, travel_feed=1200, z_feed=120,
        calibration_notes='Central test canvas only, not full sheet calibration. User confirmed pen contact at commanded absolute Z5 after pen-removed positioning. No rehoming since.')
    return page, profile

if __name__ == '__main__':
    page, profile = setup()
    code, _, report = generate(page, profile, homed=True)
    # Flush Z movements before XY; preserve the validated ordered geometry.
    code = '\n'.join(line + ('\nM400' if line.startswith('G1 Z') else '') for line in code.splitlines()) + '\n'
    report = validate_gcode(code, profile, page)
    target = HERE / '03_WRITE_Z5.gcode.3mf'
    (HERE / '03_WRITE_Z5.gcode').write_text(code)
    target.write_bytes(build_package(code, page, profile))
    assert read_package(target) == code
    profile.save(HERE / 'central-test-z5-profile.json')
    (HERE / 'absolute-z5-validation.json').write_text(json.dumps(report, indent=2)+'\n')
    old = (HERE / 'send_air_only.py').read_text()
    old = old.replace('from plotnote import contact_test', 'from plotnote import contact_test\nfrom prepare_absolute_test import setup\nfrom plotnote.validate import validate_gcode')
    old = old.replace("'live-write-run.json' if writing", "'live-write-z5-run.json' if writing")
    old = old.replace("label='02_WRITE' if writing", "label='03_WRITE_Z5' if writing")
    old = old.replace('validation=contact_test.validate(code,contact_test.test_page(),air=not writing)', 'page, profile = setup()\n    validation=validate_gcode(code,profile,page)')
    old = old.replace('PlotNote WRITE ONE LINE', 'PlotNote WRITE ABSOLUTE Z5')
    old = old.replace('main())', 'main(writing=True))')
    (HERE / 'send_write_z5_once.py').write_text(old)
    print(json.dumps(report))
