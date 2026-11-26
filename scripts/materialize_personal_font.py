"""Recover original ink (not search-index approximations) for font candidates.

Uses the locally inspected goodparse snapshot. All outputs remain candidates
until their labels and segmentation have been checked. Does not operate printers.
"""
import argparse
from collections import defaultdict
import io
import json
from pathlib import Path
import sqlite3
import sys
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'output/handwriting-research/source/goodparse-main/src'))
from goodparse.records import read_page_objects
from goodparse.page import _parse_stroke
from plotnote.goodnotes_index import connect


def select(db, targets=None, limit=3, ranked=False):
    selected = defaultdict(list)
    seen = defaultdict(set)
    query = """SELECT id,label,book,page,payload FROM groups
               WHERE single_char=1 AND live_match='all_live_ids'
               ORDER BY alternatives_agree DESC, book, page, ordinal"""
    if ranked:
        query = """SELECT g.id,g.label,g.book,g.page,g.payload FROM groups g
                   JOIN candidate_scores s ON g.id=s.id AND s.pool='groups'
                   WHERE g.single_char=1 AND g.live_match='all_live_ids' AND s.error IS NULL
                   ORDER BY g.label,s.score,g.book,g.page,g.ordinal"""
    for gid, label, book, page, payload in db.execute(query):
        if targets is not None and label not in targets:
            continue
        if len(selected[label]) < limit:
            if ranked:
                group = json.loads(zlib.decompress(payload))
                fingerprint = tuple(sorted(set(group['stroke_ids'])))
                key = (book, page, fingerprint)
                if key in seen[label]:
                    continue
                seen[label].add(key)
            selected[label].append((gid, label, book, page, payload))
    return [row for rows in selected.values() for row in rows]


def materialize(db, outer, selected):
    by_book = defaultdict(lambda: defaultdict(list))
    for row in selected:
        by_book[row[2]][row[3]].append(row)
    totals = defaultdict(int)
    db.execute('''CREATE TABLE IF NOT EXISTS exemplars (
        id TEXT PRIMARY KEY, label TEXT, status TEXT, payload BLOB)''')
    for book, pages in by_book.items():
        with zipfile.ZipFile(io.BytesIO(outer.read(book))) as archive:
            for page, rows in pages.items():
                objects = read_page_objects(archive.read('notes/' + page))
                by_id = {obj.id: obj for obj in objects if obj.kind == 7}
                # Drawing/layer order only; never assert it is temporal pen order.
                rank = {obj.id: i for i, obj in enumerate(reversed(objects))}
                for gid, label, _, _, payload in rows:
                    group = json.loads(zlib.decompress(payload))
                    ids = group['stroke_ids']
                    if not all(sid in by_id for sid in ids):
                        totals['missing_ids'] += 1
                        continue
                    paths, path_ids, widths = [], [], []
                    for sid in sorted(dict.fromkeys(ids), key=rank.__getitem__):
                        for stroke in _parse_stroke(by_id[sid].fields):
                            if len(stroke.points) < 2:
                                continue
                            paths.append([[x, y] for x, y, width in stroke.points])
                            widths.append([width for x, y, width in stroke.points])
                            path_ids.append(sid)
                    if not paths or set(path_ids) != set(ids):
                        totals['incomplete_geometry'] += 1
                        continue
                    pts = [p for path in paths for p in path]
                    bbox = [min(p[0] for p in pts), min(p[1] for p in pts),
                            max(p[0] for p in pts), max(p[1] for p in pts)]
                    sample = {'id': gid, 'label': label, 'book': book, 'page': page,
                              'paths': paths, 'widths': widths, 'stroke_ids': path_ids,
                              'bbox': bbox, 'label_status': 'unreviewed',
                              'recognition_candidates': group['labels'],
                              'geometry_source': 'original_live_ink',
                              'stroke_order_status': 'layer_order_not_temporal',
                              'normalization': 'none; original Goodnotes canvas coordinates'}
                    blob = zlib.compress(json.dumps(sample, ensure_ascii=False,
                                                   separators=(',', ':')).encode())
                    cursor = db.execute('INSERT OR IGNORE INTO exemplars VALUES (?,?,?,?)',
                                        (gid, label, 'unreviewed', blob))
                    totals['samples'] += cursor.rowcount
                    if cursor.rowcount:
                        totals['points'] += len(pts)
        db.commit()
        print(json.dumps({'book': book, **totals}, ensure_ascii=False), flush=True)
    return dict(totals)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--required', type=Path)
    parser.add_argument('--per-character', type=int, default=3)
    parser.add_argument('--ranked', action='store_true', help='Prefer shape-ranked candidates; never auto-approve')
    args = parser.parse_args()
    db = connect(args.db)
    targets = None
    if args.required:
        raw = args.required.read_text()
        if args.required.suffix == '.json':
            raw = json.loads(raw)['characters']
        targets = set(c for c in raw if not c.isspace())
    chosen = select(db, targets, args.per_character, args.ranked)
    with zipfile.ZipFile(args.archive) as outer:
        result = materialize(db, outer, chosen)
    result['selected_groups'] = len(chosen)
    result['unique_characters'] = db.execute('SELECT count(DISTINCT label) FROM exemplars').fetchone()[0]
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
