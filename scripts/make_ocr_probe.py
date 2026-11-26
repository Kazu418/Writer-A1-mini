"""Prepare one blind, local handwriting OCR trial; never uploads anything."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import sys

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from plotnote.personal_review import read_samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--grid', action='store_true', help='Separate blind glyphs with table borders')
    parser.add_argument('--compact', action='store_true', help='Put small glyphs inline with their blind IDs')
    args = parser.parse_args()
    characters = list('生活習慣病数平均値分のがをにあいうABC012Σ')
    assert len(characters) == 24
    samples = []
    with sqlite3.connect(args.db) as db:
        for char in characters:
            choices = read_samples(db, char)
            if not choices:
                raise ValueError('Missing trial character: ' + char)
            samples.append(choices[0])
    random.Random(20261125).shuffle(samples)
    doc = pymupdf.open()
    page = doc.new_page(width=720, height=800 if args.compact else 1240)
    page.insert_text((20, 25), 'Japanese handwriting transcription - sample IDs and handwritten text', fontsize=12)
    manifest = []
    for i, sample in enumerate(samples):
        col, row = i % (2 if args.compact else 4), i // (2 if args.compact else 4)
        left, top = col * (360 if args.compact else 180), 40 + row * (62 if args.compact else 200)
        if args.grid:
            page.draw_rect(pymupdf.Rect(left, top, left+180, top+200), color=(.3,.3,.3), width=.5)
        identifier = f'PN-{i+1:03d}'
        page.insert_text((left+16, top+(35 if args.compact else 20)), identifier+(':' if args.compact else ''), fontsize=12 if args.compact else 10)
        x0, y0, x1, y1 = sample['bbox']
        extent = max(x1-x0, y1-y0)
        if extent <= 0:
            raise ValueError('Trial glyph has no extent')
        size = 40 if args.compact else 140
        scale = size / extent
        ox = left + (92 if args.compact else 20) + (size-(x1-x0)*scale)/2
        oy = top + (8 if args.compact else 40) + (size-(y1-y0)*scale)/2
        for path in sample['paths']:
            changed = [(ox+(x-x0)*scale, oy+(y-y0)*scale) for x, y in path]
            page.draw_polyline(changed, color=(0,0,0), width=.8 if args.compact else 2.3, lineCap=1, lineJoin=1)
        manifest.append({'trial_id': identifier, 'expected_label': sample['label'],
                         'exemplar_id': sample['id'], 'previously_accepted': sample['status']=='accepted',
                         'source_book': sample['book'], 'source_page': sample['page'],
                         'original_paths': len(sample['paths']),
                         'original_points': sum(len(path) for path in sample['paths'])})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(matrix=pymupdf.Matrix(2,2), alpha=False).save(args.output)
    doc.close()
    result = {'image': args.output.name, 'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
              'layout': {'width': 720, 'height': 800 if args.compact else 1240, 'columns': 2 if args.compact else 4,
                         'cell_width':360 if args.compact else 180, 'cell_height':62 if args.compact else 200,
                         'top':40, 'grid':args.grid, 'compact':args.compact},
              'upload_status': 'not_uploaded', 'trial_glyphs': manifest,
              'protocol': 'The image contains handwritten ink and trial IDs only. '
                          'Expected labels, source names and approval states are local-only.'}
    args.output.with_suffix('.manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'image': str(args.output), 'glyphs': len(samples), 'known_control_glyphs': sum(s['previously_accepted'] for s in manifest),
                      'upload_status': 'not_uploaded', 'bytes': args.output.stat().st_size}, ensure_ascii=False))


if __name__ == '__main__':
    main()
