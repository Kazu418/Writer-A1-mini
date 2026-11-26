"""Verify note assets and export geometry in memory; never creates executable G-code."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from plotnote.cli import load_input
from plotnote.profile import Profile
from plotnote.gcode import generate
from plotnote.package import build_package
import pymupdf as fitz


def main():
    r=Path(__file__).resolve().parent
    result={'calibration':'not measured','executable_files_created':False,'physical_drawing_verified':False,'content_layout':'4 square pages, 2.8mm body em','pages':[]}
    # Synthetic fixture. Do not save it or use these numbers as a printer calibration.
    profile=Profile(calibrated=True,pen_offset_y=-22,pen_width=.25,
                    calibration_notes='SYNTHETIC SOFTWARE CHECK ONLY - NOT USER CALIBRATION')
    for folder in ['a1-mini-note','pen-test']:
        info=json.loads((r/folder/'report.json').read_text())
        paths=sorted((r/folder).glob('page-*.svg'))
        assert len(paths)==len(info['pages'])
        for i,path in enumerate(paths):
            page=load_input(path)[0];page.validate()
            assert len(page.strokes)==info['pages'][i]['strokes']
            code,effective,validation=generate(page,profile,homed=True,air_mm=5)
            assert validation['source_geometry_checked']
            with zipfile.ZipFile(io.BytesIO(build_package(code,page,effective))) as z:
                data=z.read('Metadata/plate_1.gcode')
                assert hashlib.md5(data).hexdigest()==z.read('Metadata/plate_1.gcode.md5').decode().strip().lower()
            points=[point for s in page.strokes for point in s.points]
            summary=page.summary()
            summary.update({'file':str(path.relative_to(r)),
                'bounds_mm':[round(min(x for x,y in points),3),round(min(y for x,y in points),3),round(max(x for x,y in points),3),round(max(y for x,y in points),3)],
                'export_check':'passed using synthetic profile, in memory only',
                'model_minutes':round(summary['ink_mm']/1200+summary['travel_mm']/3000+len(page.strokes)*2*(7-5)/300,1)})
            result['pages'].append(summary)
        with fitz.open(r/folder/'preview.pdf') as d:
            assert len(d)==len(paths)
            assert all(abs(pg.rect.width*25.4/72-148)<.001 and abs(pg.rect.height*25.4/72-148)<.001 for pg in d)
            assert all(not pg.get_image_info() for pg in d)
    with fitz.open(r/'a4-duplex-reference.pdf') as d:
        assert len(d)==2
        for i,page in enumerate(d):
            assert abs(page.rect.width*25.4/72-210)<.001 and abs(page.rect.height*25.4/72-297)<.001
            page.get_pixmap(dpi=110).save(r/f'a4-reference-side-{i+1}.png')
    blocked=r/'should-not-exist'
    command=[sys.executable,str(r/'prepare_gcode.py'),'--profile',str(r/'printer-profile-measure-first.json'),'--stage','test-air','--homed','-o',str(blocked)]
    run=subprocess.run(command,capture_output=True,text=True)
    assert run.returncode==2 and 'uncalibrated' in run.stderr and not blocked.exists()
    result['uncalibrated_export_gate']='passed: blocked before output'
    result['notes_model_total_minutes']=round(sum(x['model_minutes'] for x in result['pages'] if x['file'].startswith('a1-mini-note')),1)
    (r/'preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'verified_pages':len(result['pages']),'notes_model_minutes':result['notes_model_total_minutes'],
        'pen_test_model_minutes':result['pages'][-1]['model_minutes'],'uncalibrated_export':'blocked'},ensure_ascii=False))


if __name__=='__main__':main()
