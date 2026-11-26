"""Independent local OCR audit of original ink candidates; never auto-accept."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zlib

import pymupdf


def render(sample, path):
    x0, y0, x1, y1 = sample['bbox']
    side = max(x1 - x0, y1 - y0)
    if side <= 0:
        raise ValueError('Zero-size glyph')
    pad = side * .2
    root = ET.Element('svg', xmlns='http://www.w3.org/2000/svg',
                      viewBox=f'{x0-pad} {y0-pad} {side+2*pad} {side+2*pad}',
                      width='384', height='384')
    ET.SubElement(root, 'rect', x=str(x0-pad), y=str(y0-pad),
                  width=str(side+2*pad), height=str(side+2*pad), fill='white')
    for ps in sample['paths']:
        ET.SubElement(root, 'path', d='M ' + ' L '.join(f'{x} {y}' for x, y in ps),
                      fill='none', stroke='black', **{'stroke-width': str(side*.018),
                      'stroke-linecap': 'round', 'stroke-linejoin': 'round'})
    with pymupdf.open(stream=ET.tostring(root), filetype='svg') as doc:
        doc[0].get_pixmap().save(path)


def recognize(job):
    gid, label, path = job
    proc = subprocess.run(['tesseract', str(path.resolve()), 'stdout', '-l', 'jpn+eng',
                           '--psm', '10', 'tsv'], capture_output=True, timeout=30)
    if proc.returncode:
        return gid, '', 0., proc.stderr.decode(errors='replace')[:500]
    rows = list(csv.DictReader(io.StringIO(proc.stdout.decode()), delimiter='\t'))
    words = [row for row in rows if row.get('text', '').strip()]
    content = ''.join(row['text'].strip() for row in words)
    score = min((float(row['conf']) for row in words), default=0.)
    return gid, content, score, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--required', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    required = set(json.loads(args.required.read_text())['characters'])
    db = sqlite3.connect(args.db)
    db.execute('''CREATE TABLE IF NOT EXISTS ocr_audits (
      id TEXT PRIMARY KEY, engine TEXT, recognized TEXT, confidence REAL,
      agrees INTEGER, error TEXT)''')
    old = set(row[0] for row in db.execute('SELECT id FROM ocr_audits WHERE error IS NULL'))
    labels = {}
    with tempfile.TemporaryDirectory(prefix='plotnote-ocr-') as directory:
        jobs = []
        for gid, label, blob in db.execute('SELECT id,label,payload FROM exemplars'):
            if label not in required or gid in old:
                continue
            sample = json.loads(zlib.decompress(blob))
            path = Path(directory) / (hashlib.sha256(gid.encode()).hexdigest() + '.png')
            render(sample, path)
            jobs.append((gid, label, path))
            labels[gid] = label
        print(json.dumps({'local_ocr_jobs': len(jobs), 'workers': args.workers}), flush=True)
        with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 8))) as executor:
            futures = [executor.submit(recognize, job) for job in jobs]
            for i, future in enumerate(as_completed(futures), 1):
                gid, recognized, confidence, error = future.result()
                db.execute('INSERT OR REPLACE INTO ocr_audits VALUES (?,?,?,?,?,?)',
                           (gid, 'tesseract-jpn+eng-psm10', recognized, confidence,
                            int(recognized == labels[gid]), error))
                if i % 100 == 0:
                    db.commit()
                    print(json.dumps({'completed': i, 'total': len(jobs)}), flush=True)
        db.commit()
    rows = db.execute('SELECT e.label,a.agrees,a.confidence,a.error FROM exemplars e '
                      'JOIN ocr_audits a ON e.id=a.id').fetchall()
    agreed = set(c for c, yes, confidence, error in rows if yes and error is None)
    report = {'audited_samples': len(rows), 'agreement_samples': sum(bool(y) for c, y, s, e in rows),
              'required_with_independent_ocr_agreement': len(required & agreed),
              'errors': sum(e is not None for c, y, s, e in rows),
              'status': 'Machine agreement is evidence for ranking, not verified labels. '
                        'No candidate was accepted by this audit.'}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
