"""Create raster-only blind sheets and private mappings; no uploads."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from plotnote.personal_review import read_samples
from plotnote.personal_metrics import geometry_digest


def draw_page(samples):
    doc = pymupdf.open()
    page = doc.new_page(width=720, height=800)
    page.insert_text((20,25), 'Japanese handwriting transcription - sample IDs and handwritten text', fontsize=12)
    entries = []
    ink = page.new_shape()
    for i, sample in enumerate(samples):
        left, top = (i % 2)*360, 40+(i//2)*62
        identifier = f'PN-{i+1:03d}'
        page.insert_text((left+16, top+35), identifier+':', fontsize=12)
        x0,y0,x1,y1 = sample['bbox']
        extent = max(x1-x0,y1-y0)
        if extent <= 0:
            raise ValueError('Empty glyph')
        scale = 40/extent
        ox,oy = left+92+(40-(x1-x0)*scale)/2, top+8+(40-(y1-y0)*scale)/2
        for path in sample['paths']:
            points = [(ox+(x-x0)*scale,oy+(y-y0)*scale) for x,y in path]
            if not all(left+91.99 <= x <= left+132.01 and top+7.99 <= y <= top+48.01 for x,y in points):
                raise ValueError('Glyph does not fit its cell')
            ink.draw_polyline(points)
        entries.append({'trial_id':identifier,'expected_label':sample['label'],
                        'exemplar_id':sample['id'],'geometry_sha256':geometry_digest(sample),
                        'previously_accepted':sample['status']=='accepted'})
    ink.finish(color=(0,0,0),width=.8,lineCap=1,lineJoin=1,closePath=False)
    ink.commit()
    png = page.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False).tobytes('png')
    doc.close()
    return png,entries


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--required',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    if list(args.output.glob('batch-*.pdf')):
        parser.error('Campaign already exists; preserve its job identities')
    required=set(json.loads(args.required.read_text())['characters'])
    with sqlite3.connect(args.db) as db:
        samples=read_samples(db)
    # Put one strong candidate of each required character first, then one of
    # every other type, followed by variants. No labels enter uploaded pixels.
    first,rest={},[]
    for sample in samples:
        if sample['label'] not in first:
            first[sample['label']]=sample
        else:
            rest.append(sample)
    ordered=sorted(first.values(),key=lambda s:(s['label'] not in required,s['label']))+rest
    if len({s['id'] for s in ordered}) != len(ordered):
        raise ValueError('Repeated source exemplar')
    page_count=math.ceil(len(ordered)/24)
    if page_count+3>500:
        raise ValueError('Campaign exceeds the authorized FAST threshold')
    batches=[]
    for start in range(0,len(ordered),24*16):
        index=len(batches)+1
        target=args.output/f'batch-{index:03d}.pdf'
        doc=pymupdf.open()
        pages=[]
        batch_samples=ordered[start:start+24*16]
        for offset in range(0,len(batch_samples),24):
            png,entries=draw_page(batch_samples[offset:offset+24])
            page=doc.new_page(width=720,height=800)
            page.insert_image(page.rect,stream=png)
            pages.append({'page_index':len(pages),'glyphs':entries})
            if start==0 and offset==0:
                (args.output/'preview-first.png').write_bytes(png)
        doc.save(target,deflate=True)
        doc.close()
        with pymupdf.open(target) as reopened:
            assert len(reopened)==len(pages)
            assert all(not page.get_text().strip() for page in reopened), 'No expected labels or text layer allowed'
        manifest={'file':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'pages':pages}
        target.with_suffix('.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        batches.append({'file':target.name,'pages':len(pages),'sha256':manifest['sha256']})
        print('Prepared',target.name,len(pages),'pages',flush=True)
    result={'mode':'fast','glyphs':len(ordered),'types':len(first),'ocr_pages':page_count,
            'prior_trial_pages':3,'planned_pages':page_count+3,'batches':batches,
            'approval_policy':'OCR evidence only; no automatic acceptance or source geometry changes'}
    (args.output/'campaign.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='batches'},ensure_ascii=False))


if __name__=='__main__':
    main()
