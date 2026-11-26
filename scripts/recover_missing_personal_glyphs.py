"""Recover missing required glyph candidates from recognition words and boxes."""
import argparse
from collections import defaultdict
import io
import json
from pathlib import Path
import sys
import unicodedata
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'output/handwriting-research/source/goodparse-main/src'))
from goodparse.records import read_page_objects
from goodparse.page import _parse_stroke
from plotnote.goodnotes_index import connect, live_recognition_characters
from plotnote.personal_segment import split_word


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--required', type=Path)
    parser.add_argument('--all-characters', action='store_true', help='Recover character hypotheses from every live-ink word')
    parser.add_argument('--target-list', type=Path, help='Save the all-character target hypotheses')
    parser.add_argument('--include-alternatives', action='store_true',
                        help='Also propose glyphs from lower-ranked recognition hypotheses')
    parser.add_argument('--unconfirmed', action='store_true',
                        help='Recover fresh word candidates for characters without accepted exemplars')
    parser.add_argument('--candidates-per-missing', type=int, default=5)
    args = parser.parse_args()
    db = connect(args.db)
    if args.all_characters:
        required = live_recognition_characters(db)
    elif args.required:
        required = set(json.loads(args.required.read_text())['characters'])
    else:
        parser.error('Provide --required or --all-characters')
    if args.target_list:
        args.target_list.write_text(json.dumps({'characters': ''.join(sorted(required)),
            'status': 'unreviewed recognition hypotheses from live ink'}, ensure_ascii=False, indent=2) + '\n')
    existing_query = 'SELECT DISTINCT label FROM exemplars'
    if args.unconfirmed:
        existing_query += " WHERE status='accepted'"
    existing = set(c for (c,) in db.execute(existing_query))
    missing = required - existing
    selected = defaultdict(lambda: defaultdict(list))
    uses = defaultdict(int)
    for gid, label, book, page, blob, match in db.execute('''
            SELECT id,label,book,page,payload,live_match FROM groups
            WHERE live_match IN ('bbox_only','all_live_ids')
            ORDER BY alternatives_agree DESC,length(label),book,page,ordinal'''):
        if args.all_characters and match != 'all_live_ids':
            continue
        label = unicodedata.normalize('NFC', label)
        # Existing single-group samples already supply candidates; this pass
        # specifically seeks new evidence in words rather than revisiting them.
        if args.unconfirmed and len(label) == 1:
            continue
        needed = missing & set(label)
        if not needed or len(label) > 12 or any(c.isspace() for c in label):
            continue
        if not any(uses[c] < args.candidates_per_missing for c in needed):
            continue
        if match == 'bbox_only' and len(label) != 1:
            continue
        selected[book][page].append((gid, label, blob, match))
        for c in needed:
            uses[c] += 1
    if args.include_alternatives:
        needles = {c: c.encode() for c in missing}
        for gid, book, page, blob, match in db.execute('''
                SELECT id,book,page,payload,live_match FROM groups
                WHERE live_match IN ('bbox_only','all_live_ids')'''):
            active = {c for c in missing if uses[c] < args.candidates_per_missing}
            if not active:
                break
            raw = zlib.decompress(blob)
            if not any(needles[c] in raw for c in active):
                continue
            group = json.loads(raw)
            hypotheses = group['labels'] + group['secondary_labels'] + group['other_labels']
            for label in sorted(set(hypotheses), key=len):
                needed = active & set(label)
                if not needed or not 0 < len(label) <= 12 or any(c.isspace() for c in label):
                    continue
                if match == 'bbox_only' and len(label) != 1:
                    continue
                # Record the selected hypothesis in the new sample. Original
                # recognition candidates remain attached for review.
                selected[book][page].append((gid + ':alternative:' + label, label, blob, match))
                for c in needed:
                    uses[c] += 1
                break
    counts = defaultdict(int)
    with zipfile.ZipFile(args.archive) as outer:
        for book, pages in selected.items():
            with zipfile.ZipFile(io.BytesIO(outer.read(book))) as archive:
                for page, rows in pages.items():
                    if 'notes/' + page not in archive.namelist():
                        counts['no_live_page_member'] += 1
                        continue
                    objects = read_page_objects(archive.read('notes/' + page))
                    rank = {obj.id: i for i, obj in enumerate(reversed(objects))}
                    by_id = {obj.id: obj for obj in objects if obj.kind == 7}
                    cache = {}
                    def ink(sid):
                        if sid not in cache:
                            cache[sid] = _parse_stroke(by_id[sid].fields)
                        return cache[sid]
                    for gid, label, blob, match in rows:
                        group = json.loads(zlib.decompress(blob))
                        paths, ids = [], []
                        if match == 'bbox_only':
                            box = group.get('recognition_box_xywh')
                            if not box:
                                continue
                            x, y, w, h = box
                            if w <= 0 or h <= 0:
                                continue
                            crossing = False
                            for sid in sorted(by_id, key=rank.__getitem__):
                                for stroke in ink(sid):
                                    p = [[px, py] for px, py, _ in stroke.points]
                                    if len(p) < 2:
                                        continue
                                    inside = [x - .01 <= px <= x + w + .01 and y - .01 <= py <= y + h + .01 for px, py in p]
                                    if all(inside):
                                        paths.append(p)
                                        ids.append(sid)
                                    elif any(inside):
                                        crossing = True
                            if crossing or not paths:
                                counts['bbox_ambiguous'] += 1
                                continue
                            partitions = [list(range(len(paths)))]
                            method = 'recognition_bbox_whole_live_strokes'
                        else:
                            wanted = group['stroke_ids']
                            if not all(sid in by_id for sid in wanted):
                                continue
                            for sid in sorted(dict.fromkeys(wanted), key=rank.__getitem__):
                                for stroke in ink(sid):
                                    p = [[x, y] for x, y, _ in stroke.points]
                                    if len(p) >= 2:
                                        paths.append(p)
                                        ids.append(sid)
                            if set(ids) != set(wanted):
                                continue
                            if len(label) == 1:
                                partitions = [list(range(len(paths)))]
                                method = 'whole_normalized_recognition_group'
                            else:
                                split = split_word(paths, label)
                                if split is None:
                                    counts['word_unsplittable'] += 1
                                    continue
                                partitions = split['partitions']
                                method = 'word_geometry_hypothesis'
                        for i, (char, partition) in enumerate(zip(label, partitions)):
                            if char not in missing:
                                continue
                            ps = [paths[j] for j in partition]
                            points = [p for path in ps for p in path]
                            bbox = [min(p[0] for p in points), min(p[1] for p in points),
                                    max(p[0] for p in points), max(p[1] for p in points)]
                            sid = gid + ':split:' + str(i)
                            sample = {'id': sid, 'label': char, 'book': book, 'page': page,
                                      'paths': ps, 'stroke_ids': [ids[j] for j in partition],
                                      'bbox': bbox, 'recognition_candidates': group['labels'],
                                      'source_word': label, 'parent_group_id': gid,
                                      'label_status': 'unreviewed', 'segmentation_method': method,
                                      'geometry_source': 'original_live_ink',
                                      'stroke_order_status': 'layer_order_not_temporal',
                                      'normalization': 'none; original Goodnotes canvas coordinates'}
                            packed = zlib.compress(json.dumps(sample, ensure_ascii=False,
                                                             separators=(',', ':')).encode())
                            # Re-running recovery must not overwrite review decisions.
                            cursor = db.execute('INSERT OR IGNORE INTO exemplars VALUES (?,?,?,?)',
                                                (sid, char, 'unreviewed', packed))
                            counts['new_samples'] += cursor.rowcount
            db.commit()
            print(json.dumps({'book': book, **counts}, ensure_ascii=False), flush=True)
    covered = set(c for (c,) in db.execute('SELECT DISTINCT label FROM exemplars'))
    print(json.dumps({'required_unique': len(required), 'with_original_candidates': len(required & covered),
                      'missing_required': ''.join(sorted(required - covered)), **counts}, ensure_ascii=False))


if __name__ == '__main__':
    main()
