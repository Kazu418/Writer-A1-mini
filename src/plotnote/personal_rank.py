"""Rank personal ink candidates by shape evidence; never approve their labels.

Reference fonts are used only for comparison. No reference strokes enter the
personal font. Scoring uses a temporary raster and leaves source paths intact.
"""
import argparse
from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path
import sqlite3
import zlib

from .fonts import _standard_glyph_paths as glyph_paths  # always the standard reference, even inside a personal-font scope
from .model import PlotNoteError


def raster(paths, side=32):
    points = [p for path in paths for p in path]
    if not points:
        raise ValueError('No ink to compare')
    x0, y0 = min(p[0] for p in points), min(p[1] for p in points)
    w = max(p[0] for p in points) - x0
    h = max(p[1] for p in points) - y0
    scale = max(w, h)
    if scale <= 0:
        return frozenset({(side // 2) * side + side // 2})
    extent = side - 3
    ox, oy = 1 + extent * (1 - w / scale) / 2, 1 + extent * (1 - h / scale) / 2
    cells = set()
    for path in paths:
        changed = [((x - x0) / scale * extent + ox, (y - y0) / scale * extent + oy) for x, y in path]
        for a, b in zip(changed, changed[1:]):
            steps = max(1, math.ceil(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2))
            for i in range(steps + 1):
                t = i / steps
                x = min(side - 1, max(0, round(a[0] + t * (b[0] - a[0]))))
                y = min(side - 1, max(0, round(a[1] + t * (b[1] - a[1]))))
                cells.add(y * side + x)
        if len(changed) == 1:
            x, y = changed[0]
            cells.add(round(y) * side + round(x))
    return frozenset(cells)


def distance_map(cells, side=32):
    distance = [side * 6] * (side * side)
    for i in cells:
        distance[i] = 0
    for y in range(side):
        for x in range(side):
            i = y * side + x
            value = distance[i]
            if x:
                value = min(value, distance[i - 1] + 3)
            if y:
                value = min(value, distance[i - side] + 3)
                if x:
                    value = min(value, distance[i - side - 1] + 4)
                if x + 1 < side:
                    value = min(value, distance[i - side + 1] + 4)
            distance[i] = value
    for y in range(side - 1, -1, -1):
        for x in range(side - 1, -1, -1):
            i = y * side + x
            value = distance[i]
            if x + 1 < side:
                value = min(value, distance[i + 1] + 3)
            if y + 1 < side:
                value = min(value, distance[i + side] + 3)
                if x:
                    value = min(value, distance[i + side - 1] + 4)
                if x + 1 < side:
                    value = min(value, distance[i + side + 1] + 4)
            distance[i] = value
    return distance


@lru_cache(maxsize=8192)
def reference(char):
    paths = glyph_paths(char)
    cells = raster(paths)
    return cells, distance_map(cells), len(paths)


def score_paths(paths, char):
    target, target_distances, expected_strokes = reference(char)
    cells = raster(paths)
    distances = distance_map(cells)
    shape = (sum(target_distances[i] for i in cells) / len(cells) +
             sum(distances[i] for i in target) / len(target)) / (2 * 32 * 3)
    count = .05 * abs(math.log((len(paths) + 1) / (expected_strokes + 1)))
    return {'score': shape + count, 'shape_distance': shape, 'stroke_penalty': count}


def rank(db, pool='exemplars', required=None, limit=100):
    if pool not in ('exemplars', 'groups'):
        raise ValueError('Unknown ranking pool')
    db.execute('''CREATE TABLE IF NOT EXISTS candidate_scores (
        id TEXT, pool TEXT, label TEXT, score REAL, shape_distance REAL,
        stroke_penalty REAL, error TEXT, PRIMARY KEY(id,pool))''')
    if pool == 'exemplars':
        rows = db.execute('SELECT id,label,payload FROM exemplars').fetchall()
    else:
        labels = sorted(required or {r[0] for r in db.execute('SELECT DISTINCT label FROM groups WHERE single_char=1')})
        rows = []
        for label in labels:
            rows.extend(db.execute("SELECT id,label,payload FROM groups WHERE label=? "
                                   "AND single_char=1 AND live_match='all_live_ids' "
                                   'ORDER BY alternatives_agree DESC,book,page,ordinal LIMIT ?',
                                   (label, limit)).fetchall())
    totals = Counter()
    for gid, label, blob in rows:
        if required is not None and label not in required:
            continue
        sample = json.loads(zlib.decompress(blob))
        try:
            result = score_paths(sample['paths'], label)
            values = (result['score'], result['shape_distance'], result['stroke_penalty'], None)
            totals['scored'] += 1
        except (PlotNoteError, ValueError) as error:
            values = (None, None, None, str(error))
            totals['unscorable'] += 1
        db.execute('INSERT OR REPLACE INTO candidate_scores VALUES (?,?,?,?,?,?,?)',
                   (gid, pool, label, *values))
    db.commit()
    return {'pool': pool, **totals, 'labels_approved': 0,
            'purpose': 'Candidate ordering only; proximity to a reference is not label verification.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--pool', choices=['groups', 'exemplars'], default='exemplars')
    parser.add_argument('--required', type=Path)
    parser.add_argument('--limit-per-character', type=int, default=100)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    required = set(json.loads(args.required.read_text())['characters']) if args.required else None
    with sqlite3.connect(args.db) as db:
        report = rank(db, args.pool, required, args.limit_per_character)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
