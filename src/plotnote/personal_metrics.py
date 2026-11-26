"""Estimate common source-line cells without changing any original ink points.

These are geometric estimates, independent of label approval. Nearby live ink
supplies scale and line position; printed-only search boxes are never anchors.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from statistics import median
import unicodedata
import zlib


def geometry_digest(sample):
    source = {key: sample[key] for key in ('book', 'page', 'paths', 'stroke_ids')}
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def anchor_from_group(gid, group):
    labels = group.get('labels', [])
    if group.get('live_match') != 'all_live_ids' or not labels:
        return None
    label = labels[0]
    if len(label) != 1 or unicodedata.category(label)[0] not in ('L', 'N'):
        return None
    box = group.get('recognition_box_xywh')
    if not box or len(box) != 4 or not all(math.isfinite(v) for v in box):
        return None
    x, y, w, h = box
    if w <= 0 or h <= 0 or w > 2 * h or not group.get('stroke_ids'):
        return None
    return {'id': gid, 'box': [x, y, x + w, y + h],
            'stroke_ids': tuple(sorted(set(group['stroke_ids'])))}


def estimate_metrics(sample, anchors, minimum_anchors=3):
    """Use one nearby line and reject weak/mixed-size evidence.

    Small punctuation keeps its source size and lower placement because its own
    bounding box is not used as a full em cell. No glyph outline is generated.
    """
    if sample.get('em_height') is not None and not sample.get('metric_reference'):
        return {'status': 'preserved_explicit_reference'}
    x0, y0, x1, y1 = sample['bbox']
    cy = (y0 + y1) / 2
    own_ids = set(sample.get('stroke_ids', []))
    candidates, seen = [], set()
    for anchor in anchors:
        ids = anchor['stroke_ids']
        if ids in seen or own_ids.intersection(ids):
            continue
        seen.add(ids)
        ax0, ay0, ax1, ay1 = anchor['box']
        h = ay1 - ay0
        dx = max(ax0 - x1, x0 - ax1, 0) / h
        vertical_gap = max(ay0 - y1, y0 - ay1, 0) / h
        if dx > 10 or vertical_gap > .45:
            continue
        acy = (ay0 + ay1) / 2
        score = 3 * abs(acy - cy) / h + .15 * dx
        candidates.append((score, anchor))
    if not candidates:
        return {'status': 'no_source_line'}
    _, seed = min(candidates, key=lambda pair: pair[0])
    sx0, sy0, sx1, sy1 = seed['box']
    seed_h, seed_cy = sy1 - sy0, (sy1 + sy0) / 2
    row = []
    for _, anchor in candidates:
        ax0, ay0, ax1, ay1 = anchor['box']
        h = ay1 - ay0
        horizontal_gap = max(ax0 - x1, x0 - ax1, 0)
        if (.6 * seed_h <= h <= 1.65 * seed_h and
            abs((ay0 + ay1) / 2 - seed_cy) <= .4 * seed_h and
            horizontal_gap <= 8 * seed_h):
            row.append(anchor)
    if len(row) < minimum_anchors:
        return {'status': 'insufficient_source_line', 'anchor_count': len(row)}
    heights = [a['box'][3] - a['box'][1] for a in row]
    em = median(heights)
    dispersion = median(abs(h - em) for h in heights) / em
    if dispersion > .25:
        return {'status': 'mixed_source_sizes', 'dispersion': dispersion}
    top = median(a['box'][1] for a in row)
    return {'status': 'estimated_source_line', 'em_height': em, 'line_top': top,
            'metric_reference': {'method': 'nearby_live_ink_median_v1',
                                 'anchor_ids': [a['id'] for a in row],
                                 'anchor_count': len(row),
                                 'relative_height_mad': dispersion,
                                 'label_verification': 'unchanged',
                                 'source_geometry_changed': False}}


def enrich(db):
    db.execute('CREATE INDEX IF NOT EXISTS groups_by_page ON groups(book,page)')
    # Materialized exemplars retain book/page in their payload, including manual
    # references whose page is a decoded page index rather than an archive UUID.
    by_page = {}
    for gid, blob in db.execute('SELECT id,payload FROM exemplars'):
        sample = json.loads(zlib.decompress(blob))
        by_page.setdefault((sample['book'], sample['page']), []).append((gid, sample))
    totals = Counter()
    updates = []
    for (book, page), samples in by_page.items():
        anchors = []
        for gid, blob in db.execute("SELECT id,payload FROM groups WHERE book=? AND page=? "
                                    "AND single_char=1 AND live_match='all_live_ids'", (book, page)):
            group = json.loads(zlib.decompress(blob))
            anchor = anchor_from_group(gid, group)
            if anchor:
                anchors.append(anchor)
        for gid, sample in samples:
            result = estimate_metrics(sample, anchors)
            totals[result['status']] += 1
            if result['status'] != 'estimated_source_line':
                continue
            # Raw source points, stroke IDs, labels and review decisions stay
            # byte-for-byte equal as JSON values; only the cell reference is new.
            sample.update(em_height=result['em_height'], line_top=result['line_top'],
                          metric_reference=result['metric_reference'])
            packed = zlib.compress(json.dumps(sample, ensure_ascii=False,
                                             separators=(',', ':')).encode())
            db.execute('UPDATE exemplars SET payload=? WHERE id=?', (packed, gid))
            updates.append({'id': gid, 'em_height': result['em_height'],
                            'line_top': result['line_top'],
                            'geometry_sha256': geometry_digest(sample),
                            'metric_reference': result['metric_reference']})
        db.commit()
    return dict(totals), updates


def apply_updates(db, updates):
    """Apply only metrics to the same source ink; preserve all review decisions."""
    prepared = []
    for item in updates:
        em, top = item['em_height'], item['line_top']
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (em, top)) or em <= 0:
            raise ValueError('Invalid source-line metrics')
        row = db.execute('SELECT payload FROM exemplars WHERE id=?', (item['id'],)).fetchone()
        if row is None:
            raise ValueError('Unknown metric exemplar: ' + item['id'])
        sample = json.loads(zlib.decompress(row[0]))
        if geometry_digest(sample) != item['geometry_sha256']:
            raise ValueError('Source ink changed; metrics were not applied: ' + item['id'])
        if sample.get('em_height') is not None and not sample.get('metric_reference'):
            raise ValueError('Cannot overwrite an explicit source-line reference')
        sample.update(em_height=em, line_top=top, metric_reference=item['metric_reference'])
        prepared.append((zlib.compress(json.dumps(sample, ensure_ascii=False,
                                                separators=(',', ':')).encode()), item['id']))
    with db:
        db.executemany('UPDATE exemplars SET payload=? WHERE id=?', prepared)
    return len(prepared)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--updates', type=Path, help='Write source-bound metric changes for later application')
    parser.add_argument('--apply-updates', type=Path, help='Apply a previously computed metric patch')
    args = parser.parse_args()
    with sqlite3.connect(args.db) as db:
        if args.apply_updates:
            patch = json.loads(args.apply_updates.read_text())
            if patch.get('format') != 'plotnote-source-metrics-v1':
                parser.error('Unknown metric patch format')
            applied = apply_updates(db, patch['updates'])
            report = {'applied_samples': applied, 'labels_changed': False,
                      'source_ink_changed': False}
            args.report.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report), flush=True)
            return
        if not args.updates:
            parser.error('Provide --updates when estimating metrics')
        totals, updates = enrich(db)
    report = {'sample_outcomes': totals,
              'status': 'Cell metrics are geometric estimates; labels were not approved.'}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    args.updates.write_text(json.dumps({'format': 'plotnote-source-metrics-v1',
                                      'updates': updates}, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
