"""Supplement the stroke index with the alternate Goodnotes search schema."""
import argparse
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from plotnote.goodnotes_index import connect, decode_framed_search, deleted_page_prefixes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--db', type=Path, required=True)
    args = parser.parse_args()
    db = connect(args.db)
    db.execute('CREATE TABLE IF NOT EXISTS framed_pages(book TEXT,member TEXT,groups_count INTEGER,error TEXT,PRIMARY KEY(book,member))')
    todo = defaultdict(list)
    for book, member in db.execute("SELECT book,member FROM issues WHERE member LIKE 'search/%' AND instr(member,'#')=0"):
        todo[book].append(member)
    count = 0
    with zipfile.ZipFile(args.archive) as outer:
        for book, members in todo.items():
            with zipfile.ZipFile(io.BytesIO(outer.read(book))) as archive:
                try:
                    deleted = deleted_page_prefixes(archive)
                except ValueError as error:
                    print(json.dumps({'book': book, 'skipped': 'Unknown page deletion state', 'error': str(error)}), flush=True)
                    continue
                for member in members:
                    page = member.split('/')[-1]
                    if page[:32] in deleted:
                        db.execute('DELETE FROM groups WHERE book=? AND page=?', (book, page))
                        db.execute('INSERT OR REPLACE INTO framed_pages VALUES (?,?,?,?)',
                                   (book, member, 0, 'deleted_page_skipped'))
                        continue
                    if db.execute('SELECT 1 FROM framed_pages WHERE book=? AND member=?', (book, member)).fetchone():
                        continue
                    try:
                        groups = decode_framed_search(archive.read(member))
                    except (ValueError, UnicodeError) as error:
                        db.execute('INSERT OR REPLACE INTO framed_pages VALUES (?,?,?,?)',
                                   (book, member, 0, str(error)))
                        continue
                    for ordinal, group in enumerate(groups):
                        label = group['labels'][0]
                        group.update(book=book, page=page, ordinal=ordinal, live_match='bbox_only')
                        gid = hashlib.sha256(f'{book}\0{page}\0framed\0{ordinal}'.encode()).hexdigest()
                        blob = zlib.compress(json.dumps(group, ensure_ascii=False, separators=(',', ':')).encode())
                        db.execute('INSERT OR IGNORE INTO groups VALUES (?,?,?,?,?,?,?,?,?,?)',
                                   (gid, book, page, ordinal, label, int(len(label) == 1), 0,
                                    'bbox_only', blob, 'unreviewed'))
                    db.execute('INSERT OR REPLACE INTO framed_pages VALUES (?,?,?,?)',
                               (book, member, len(groups), None))
                    count += len(groups)
            db.commit()
            print(json.dumps({'book': book, 'added_box_candidates': count}, ensure_ascii=False), flush=True)
    print(json.dumps({'framed_page_outcomes': db.execute('SELECT error IS NULL,count(*),sum(groups_count) FROM framed_pages GROUP BY error IS NULL').fetchall()}))


if __name__ == '__main__':
    main()
