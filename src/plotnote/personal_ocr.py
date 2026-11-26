"""Independent OCR evidence, kept separate from reviewed glyph decisions."""
import argparse
from collections import Counter, defaultdict
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
import zlib

from .personal_metrics import geometry_digest


def plain_text(html):
    return unescape(re.sub(r'<[^>]*>', ' ', html))


def normalize_reading(text):
    # Limited representation conversion, never confusable-character folding.
    text = text.strip().strip('$').strip()
    math = {'\\Sigma':'Σ', '\\sum':'∑', '\\alpha':'α', '\\beta':'β',
            '\\pi':'π', '\\mu':'μ', '\\sigma':'σ', '\\times':'×',
            '\\div':'÷', '\\theta':'θ', '\\Delta':'Δ', '\\leq':'≤', '\\geq':'≥'}
    if text in math:
        text = math[text]
    return unicodedata.normalize('NFC', re.sub(r'\s+', '', text))


def page_readings(page):
    readings = defaultdict(list)
    def visit(block):
        if block.get('children'):
            for child in block['children']:
                visit(child)
            return
        text = plain_text(block.get('html') or '')
        matches = list(re.finditer(r'PN\s*[-–]\s*(\d{3,})\s*[:：]?', text))
        for i, match in enumerate(matches):
            end = matches[i+1].start() if i+1 < len(matches) else len(text)
            identifier = 'PN-' + match[1]
            readings[identifier].append(normalize_reading(text[match.end():end]))
    visit(page)
    return dict(readings)


def audit(manifest, result):
    pages = result.get('json', {}).get('children', [])
    by_page = {}
    for page in pages:
        match = re.search(r'/page/(\d+)/', page.get('id', ''))
        index = int(match[1]) if match else len(by_page)
        by_page[index] = page_readings(page)
    rows = []
    for page in manifest['pages']:
        readings = by_page.get(page['page_index'], {})
        for glyph in page['glyphs']:
            found = readings.get(glyph['trial_id'], [])
            value = found[0] if len(found)==1 else ''
            status = ('ambiguous' if len(found)>1 else 'missing' if not found or not value else
                      'match' if value==unicodedata.normalize('NFC',glyph['expected_label']) else
                      'different_single' if len(value)==1 else 'multiple_or_unreadable')
            rows.append({**glyph,'page_index':page['page_index'],'reading':value,
                         'all_readings':found,'ocr_status':status})
    return {'rows':rows,'counts':dict(Counter(r['ocr_status'] for r in rows)),
            'warning':'OCR agreement is evidence, not review approval. Original ink remains unchanged.'}


def store_audit(db, rows, job_sha):
    db.execute('''CREATE TABLE IF NOT EXISTS independent_ocr
        (exemplar_id TEXT, provider TEXT, job_sha TEXT, expected_label TEXT,
         geometry_sha TEXT, reading TEXT, status TEXT, payload TEXT,
         PRIMARY KEY(exemplar_id,provider,job_sha))''')
    for row in rows:
        existing=db.execute('SELECT payload FROM exemplars WHERE id=?',(row['exemplar_id'],)).fetchone()
        if existing is None:
            raise ValueError('OCR source exemplar no longer exists')
        sample=json.loads(zlib.decompress(existing[0]))
        if geometry_digest(sample)!=row['geometry_sha256']:
            raise ValueError('OCR source geometry changed; refusing stale evidence')
    for row in rows:
        db.execute('INSERT OR REPLACE INTO independent_ocr VALUES (?,?,?,?,?,?,?,?)',
                   (row['exemplar_id'],'datalab-fast',job_sha,row['expected_label'],
                    row['geometry_sha256'],row['reading'],row['ocr_status'],json.dumps(row,ensure_ascii=False)))
    db.commit()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--result',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--db',type=Path)
    args=p.parse_args()
    manifest=json.loads(args.manifest.read_text())
    source=args.manifest.parent/manifest['file']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=manifest['sha256']:
        raise ValueError('Uploaded source does not match local mapping')
    result=json.loads(args.result.read_text())
    if result.get('status')!='complete' or result.get('success') is not True:
        raise ValueError('OCR result has not completed successfully')
    report=audit(manifest,result)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if args.db:
        with sqlite3.connect(args.db) as db:
            store_audit(db,report['rows'],manifest['sha256'])
    print(json.dumps(report['counts'],ensure_ascii=False))


if __name__=='__main__':
    main()
