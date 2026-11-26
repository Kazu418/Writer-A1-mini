"""Build the hand-review queue for the phone app from the LT8 proposals.

Read-only on the font database. Output: a compact queue (normalised, simplified
strokes for display only; original ink in the database is untouched).
Stdlib only.
"""
import argparse
import json
import math
from pathlib import Path
import sqlite3
import zlib

REVIEW_EVIDENCE = {
    'goodnotes_hypothesis+LT8_top1': ('agree_high', 0),
    'goodnotes_hypothesis+LT8_top1_lowconf': ('agree_low', 1),
    'goodnotes_hypothesis+LT8_top5': ('agree_top5', 2),
    'LT8_only_hypothesis_contradicted': ('ai_only', 3),
}


def rdp(points, eps):
    if len(points) < 3:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy)
    best, index = -1.0, 0
    for i in range(1, len(points) - 1):
        x, y = points[i]
        d = (math.hypot(x - x1, y - y1) if norm == 0
             else abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm)
        if d > best:
            best, index = d, i
    if best <= eps:
        return [points[0], points[-1]]
    return rdp(points[:index + 1], eps)[:-1] + rdp(points[index:], eps)


def normalise(paths):
    pts = [p for path in paths for p in path]
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
    x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
    extent = max(x1 - x0, y1 - y0, 1e-6)
    scale = 88.0 / extent
    ox, oy = 6 + (88 - (x1 - x0) * scale) / 2, 6 + (88 - (y1 - y0) * scale) / 2
    out = []
    for path in paths:
        q = [((x - x0) * scale + ox, (y - y0) * scale + oy) for x, y in path]
        q = rdp(q, 0.3) if len(q) > 2 else q
        if len(q) == 1:
            q = q * 2
        out.append([round(v, 1) for point in q for v in point])
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--proposals', type=Path, required=True)
    p.add_argument('--required', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    items = [o for o in json.loads(a.proposals.read_text())['items']
             if o['evidence'] in REVIEW_EVIDENCE]
    required = set(json.loads(a.required.read_text())['characters'])
    accepted_types = {o['goodnotes_label'] for o in json.loads(a.proposals.read_text())['items']
                      if o['status'] == 'accepted'}
    wanted = {o['id'] for o in items}
    uri = 'file:' + str(a.db) + '?mode=ro&immutable=1'
    db = sqlite3.connect(uri, uri=True)
    shapes = {}
    for gid, blob in db.execute('SELECT id,payload FROM exemplars'):
        if gid in wanted:
            shapes[gid] = normalise(json.loads(zlib.decompress(blob))['paths'])
    queue = []
    for o in items:
        kind, rank = REVIEW_EVIDENCE[o['evidence']]
        label = o['proposed_label']
        priority = 2 if label in accepted_types else (0 if label in required else 1)
        queue.append({'id': o['id'], 'label': label, 'goodnotes': o['goodnotes_label'],
                      'kind': kind, 'priority': priority, 'rank': rank,
                      'paths': shapes[o['id']]})
    queue.sort(key=lambda q: (q['priority'], q['label'], q['rank'], q['id']))
    a.output.write_text(json.dumps({'format': 'plotnote-label-queue-v1', 'items': queue},
                                   ensure_ascii=False, separators=(',', ':')))
    by = {}
    for q in queue:
        by[q['priority']] = by.get(q['priority'], 0) + 1
    print(json.dumps({'items': len(queue), 'by_priority': by,
                      'bytes': a.output.stat().st_size}, ensure_ascii=False))


if __name__ == '__main__':
    main()
