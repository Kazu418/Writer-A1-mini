"""Local, resumable extraction of Goodnotes recognition groups and centerlines.

Observed search schema, not an official Goodnotes API. Recognition hypotheses
are candidates, never verified labels. Coordinates are retained losslessly as
decoded float32 values; recognition point order is not assumed to be ink order.
"""

import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import struct
import unicodedata
import zipfile
import zlib


def varint(data, offset):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise ValueError('Truncated varint')
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError('Oversized varint')


def message(data):
    result = {}
    offset = 0
    while offset < len(data):
        key, offset = varint(data, offset)
        field, wire = key >> 3, key & 7
        if not field:
            raise ValueError('Invalid protobuf field zero')
        if wire == 0:
            value, offset = varint(data, offset)
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            if offset + size > len(data):
                raise ValueError('Truncated float')
            value = struct.unpack_from('<d' if size == 8 else '<f', data, offset)[0]
            offset += size
        elif wire == 2:
            size, offset = varint(data, offset)
            if offset + size > len(data):
                raise ValueError('Truncated bytes')
            value = data[offset:offset + size]
            offset += size
        else:
            raise ValueError(f'Unsupported protobuf wire {wire}')
        result.setdefault(field, []).append(value)
    return result


def records(data):
    offset = 0
    while offset < len(data):
        size, offset = varint(data, offset)
        if offset + size > len(data):
            raise ValueError('Truncated record')
        yield data[offset:offset + size]
        offset += size


def text(value):
    return value.decode('utf-8') if isinstance(value, bytes) else ''


def point(raw):
    fields = message(raw)
    xy = [fields.get(k, [0.0])[0] for k in (1, 2)]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in xy):
        raise ValueError('Nonfinite coordinate')
    return xy


def decode_group(raw):
    fields = message(raw)
    labels = [text(v) for v in fields.get(3, [])]
    secondary = [text(v) for v in fields.get(5, [])]
    paths, ids = [], []
    for item in fields.get(7, []):
        stroke = message(item)
        pts = [point(p) for p in stroke.get(4, [])]
        if pts:
            paths.append(pts)
            ids.append(text(stroke.get(3, [b''])[0]))
    box = None
    if fields.get(1):
        placement = message(fields[1][0])
        if placement.get(1) and placement.get(2):
            box = point(placement[1][0]) + point(placement[2][0])
    if not labels or (not paths and box is None):
        return None
    return {'labels': labels, 'secondary_labels': secondary,
            'other_labels': [text(v) for v in fields.get(10, [])],
            'paths': paths, 'stroke_ids': ids, 'recognition_box_xywh': box,
            'language': text(fields.get(11, [b''])[0]),
            'label_status': 'unreviewed',
            'stroke_order_status': 'recognition_order_unverified'}


def decode_framed_search(data):
    """Observed alternate search format: UTF-8 byte spans and rectangles.

    This may index printed backgrounds as well as handwriting. A matching
    recognition box alone does not establish personal ink membership.
    """
    groups = []
    for raw in records(data):
        fields = message(raw)
        content = fields.get(1, [b''])[0]
        if not isinstance(content, bytes):
            raise ValueError('Unrecognized framed text')
        content.decode('utf-8')
        for collection in fields.get(3, []):
            for item in message(collection).get(2, []):
                span = message(item)
                start = span.get(1, [0])[0]
                length = span.get(2, [0])[0]
                if not isinstance(start, int) or not isinstance(length, int) or start + length > len(content):
                    raise ValueError('Invalid UTF-8 search span')
                label = content[start:start + length].decode('utf-8')
                if not label.strip() or not span.get(3):
                    continue
                box = message(span[3][0])
                if not box.get(1) or not box.get(2):
                    continue
                groups.append({'labels': [label], 'secondary_labels': [], 'other_labels': [],
                               'paths': [], 'stroke_ids': [],
                               'recognition_box_xywh': point(box[1][0]) + point(box[2][0]),
                               'language': '', 'label_status': 'unreviewed',
                               'stroke_order_status': 'not_available',
                               'search_format': 'framed_utf8_text_spans',
                               'ink_membership': 'unknown_background_or_handwriting'})
    return groups


def live_stroke_ids(data):
    """Match object IDs against the live page log, excluding deleted ink."""
    live = set()
    header = {}
    for raw in records(data):
        fields = message(raw)
        if len(fields) == 1:
            kind = next(iter(fields))
            body = fields[kind][0]
            if isinstance(body, bytes):
                body = message(body)
                oid = text(body.get(1, [b''])[0])
                same_header = text(header.get(1, [b''])[0]) == oid
                deleted = body.get(14, [0])[0] == 1 or (
                    same_header and header.get(3, [0])[0] == 1)
                if kind == 7 and oid and not deleted:
                    live.add(oid)
                header = {}
                continue
        header = fields
    return live


def deleted_page_prefixes(archive):
    if 'index.events.pb' not in archive.namelist():
        return set()
    result = set()
    for raw in records(archive.read('index.events.pb')):
        # Event index uses deprecated protobuf group markers on some versions.
        # The existing checked parser handles those; unknown events are recorded
        # by the caller rather than treating unknown deletion state as live.
        fields = message(raw)
        if 56 in fields:
            result.add(text(fields.get(1, [b''])[0])[:32])
    return result


def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS books (
        name TEXT PRIMARY KEY, signature TEXT, status TEXT, stats TEXT);
      CREATE TABLE IF NOT EXISTS groups (
        id TEXT PRIMARY KEY, book TEXT, page TEXT, ordinal INTEGER,
        label TEXT, single_char INTEGER, alternatives_agree INTEGER,
        live_match TEXT, payload BLOB, status TEXT DEFAULT 'unreviewed');
      CREATE INDEX IF NOT EXISTS by_label ON groups(label, single_char);
      CREATE INDEX IF NOT EXISTS by_book ON groups(book);
      CREATE TABLE IF NOT EXISTS issues (
        book TEXT, member TEXT, error TEXT);
    ''')
    return db


def import_book(db, name, signature, data):
    counts = Counter()
    db.execute('DELETE FROM groups WHERE book=?', (name,))
    db.execute('DELETE FROM issues WHERE book=?', (name,))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        try:
            deleted = deleted_page_prefixes(archive)
            deletion_known = True
        except ValueError as error:
            deleted, deletion_known = set(), False
            db.execute('INSERT INTO issues VALUES (?,?,?)',
                       (name, 'index.events.pb', str(error)))
            counts['deletion_index_unknown'] += 1
        for member in names:
            if not member.startswith('search/') or member.endswith('/'):
                continue
            page = member.split('/')[-1]
            if page[:32] in deleted:
                counts['deleted_pages_skipped'] += 1
                continue
            raw = archive.read(member)
            try:
                fields = message(raw)
                groups = fields.get(6, [])
                # Plain search files carry the page id in field 5. Newer
                # framed files use a different schema: keep explicit issues.
                if not isinstance(fields.get(5, [None])[0], bytes):
                    raise ValueError('Unrecognized search schema')
            except ValueError as error:
                counts['unsupported_search_pages'] += 1
                db.execute('INSERT INTO issues VALUES (?,?,?)', (name, member, str(error)))
                continue
            counts['search_pages'] += 1
            note = 'notes/' + page
            try:
                live = live_stroke_ids(archive.read(note)) if note in names else None
            except ValueError:
                live = None
                counts['live_object_index_unknown'] += 1
            for ordinal, group_raw in enumerate(groups):
                try:
                    group = decode_group(group_raw)
                except (ValueError, UnicodeError, TypeError) as error:
                    counts['invalid_groups'] += 1
                    db.execute('INSERT INTO issues VALUES (?,?,?)',
                               (name, f'{member}#{ordinal}', str(error)))
                    continue
                if group is None:
                    counts['empty_groups'] += 1
                    continue
                label = group['labels'][0]
                if not label.strip():
                    counts['whitespace_groups'] += 1
                    continue
                ids = group['stroke_ids']
                match = ('bbox_only' if not ids else
                         'all_live_ids' if live is not None and all(i and i in live for i in ids)
                         else 'mismatch' if live is not None else 'unknown')
                if not deletion_known:
                    match = 'page_deletion_unknown'
                group.update(book=name, page=page, ordinal=ordinal, live_match=match)
                gid = hashlib.sha256(f'{name}\0{page}\0{ordinal}'.encode()).hexdigest()
                db.execute('INSERT INTO groups VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (gid, name, page, ordinal, label, int(len(label) == 1),
                            int(len(set(group['labels'])) == 1), match,
                            zlib.compress(json.dumps(group, ensure_ascii=False,
                                                    separators=(',', ':')).encode()),
                            'unreviewed'))
                counts['groups'] += 1
                counts['single_char_groups'] += len(label) == 1
                counts['strokes'] += len(ids)
                counts[match] += 1
    db.execute('INSERT OR REPLACE INTO books VALUES (?,?,?,?)',
               (name, signature, 'imported', json.dumps(counts)))
    db.commit()
    return dict(counts)


def live_recognition_characters(db):
    """Character hypotheses from live ink, including letters inside words."""
    return {char for (label,) in db.execute(
        "SELECT DISTINCT label FROM groups WHERE live_match='all_live_ids'")
        for char in unicodedata.normalize('NFC', label)
        if char.isprintable() and not char.isspace()}


def coverage(db, required):
    counts = dict(db.execute('SELECT label,count(*) FROM groups '
                            'WHERE single_char=1 GROUP BY label'))
    matched = dict(db.execute("SELECT label,count(*) FROM groups WHERE single_char=1 "
                             "AND live_match='all_live_ids' GROUP BY label"))
    target = set(c for c in required if not c.isspace())
    reviewed = set()
    original = set()
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='exemplars'").fetchone():
        original = set(c for (c,) in db.execute('SELECT DISTINCT label FROM exemplars'))
        reviewed = set(c for (c,) in db.execute("SELECT DISTINCT label FROM exemplars WHERE status='accepted'"))
    return {'required_unique': len(target), 'candidate_unique': len(counts),
            'required_with_candidates': len(target & counts.keys()),
            'required_with_live_id_candidates': len(target & matched.keys()),
            'missing_required': ''.join(sorted(target - counts.keys())),
            'unverified_candidate_counts': {c: counts.get(c, 0) for c in sorted(target)},
            'original_ink_candidate_unique': len(original),
            'required_with_original_ink_candidates': len(target & original),
            'missing_original_ink_candidates': ''.join(sorted(target - original)),
            'verified_characters': len(reviewed),
            'required_verified_characters': len(target & reviewed),
            'warning': 'Recognition candidates are not verified character labels. '
                       'Live IDs validate membership, not geometry, order or OCR correctness.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--required', type=Path)
    parser.add_argument('--book', action='append', help='Exact member; omit for all books')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--refresh', action='store_true', help='Reparse imported books after decoder changes')
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    db = connect(args.db)
    with zipfile.ZipFile(args.archive) as outer:
        for info in outer.infolist():
            if not info.filename.endswith('.goodnotes') or info.filename.startswith('__MACOSX/'):
                continue
            if args.book and info.filename not in args.book:
                continue
            signature = f'{info.CRC}:{info.file_size}'
            old = db.execute('SELECT signature,status FROM books WHERE name=?', (info.filename,)).fetchone()
            if old == (signature, 'imported') and not args.refresh:
                print(json.dumps({'book': info.filename, 'resumed': True}), flush=True)
                continue
            result = import_book(db, info.filename, signature, outer.read(info))
            print(json.dumps({'book': info.filename, **result}, ensure_ascii=False), flush=True)
    required = args.required.read_text() if args.required else ''
    if args.required:
        if args.required.suffix == '.json':
            required = json.loads(required)['characters']
        else:
            required = '\n'.join(line for line in required.splitlines() if not line.startswith('#'))
    report = coverage(db, required)
    report['books'] = db.execute('SELECT count(*) FROM books').fetchone()[0]
    report['groups'] = db.execute('SELECT count(*) FROM groups').fetchone()[0]
    report['issues'] = db.execute('SELECT count(*) FROM issues').fetchone()[0]
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    db.close()


if __name__ == '__main__':
    main()
