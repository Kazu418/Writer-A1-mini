import io
import json
import struct
import zipfile
import zlib

import pytest

from plotnote.goodnotes_index import (
    connect, coverage, decode_group, decode_framed_search, import_book, live_stroke_ids, live_recognition_characters, message, records,
)


def varint(n):
    out = bytearray()
    while n >= 128:
        out.append((n & 127) | 128)
        n >>= 7
    out.append(n)
    return bytes(out)


def field(n, value):
    if isinstance(value, int):
        return varint(n << 3) + varint(value)
    if isinstance(value, float):
        return varint((n << 3) | 5) + struct.pack('<f', value)
    if isinstance(value, str):
        value = value.encode()
    return varint((n << 3) | 2) + varint(len(value)) + value


def framed(*items):
    return b''.join(varint(len(item)) + item for item in items)


def group(label='生'):
    pts = [field(1, 3.25) + field(2, 7.5), field(1, 4.5) + field(2, 8.25)]
    stroke = field(3, 'stroke-a') + b''.join(field(4, p) for p in pts)
    return field(3, label) + field(3, label) + field(5, label) + field(7, stroke)


def test_recognition_retains_exact_points_ids_and_unverified_label():
    result = decode_group(group())
    assert result['paths'] == [[[3.25, 7.5], [4.5, 8.25]]]
    assert result['stroke_ids'] == ['stroke-a']
    assert result['label_status'] == 'unreviewed'
    assert result['stroke_order_status'] == 'recognition_order_unverified'


@pytest.mark.parametrize('raw', [b'\x0a\xff', b'\x0a\x05x', b'\x0d\x00', b'\x00', b'\x0b'])
def test_malformed_messages_do_not_silently_truncate(raw):
    with pytest.raises(ValueError):
        message(raw)


def test_truncated_record_rejected():
    with pytest.raises(ValueError):
        list(records(b'\x05x'))


def test_deleted_stroke_excluded_from_live_ids():
    header = field(1, 'stroke-a') + field(3, 1)
    body = field(7, field(1, 'stroke-a'))
    assert live_stroke_ids(framed(header, body)) == set()


def test_import_preserves_words_tracks_missing_ids_and_never_marks_verified(tmp_path):
    stream = io.BytesIO()
    page = '00000000-0000-0000-0000-000000000001'
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('search/' + page,
                         field(5, page) + field(6, group()) + field(6, group('生活')))
        archive.writestr('notes/' + page, b'')
    db = connect(tmp_path / 'index.sqlite3')
    stats = import_book(db, 'test.goodnotes', '1:1', stream.getvalue())
    assert stats['groups'] == 2
    assert stats['mismatch'] == 2
    report = coverage(db, '生活習')
    assert report['required_with_candidates'] == 1
    assert report['required_with_live_id_candidates'] == 0
    assert report['missing_required'] == '活習'
    assert report['verified_characters'] == 0
    data = json.loads(zlib.decompress(db.execute('SELECT payload FROM groups LIMIT 1').fetchone()[0]))
    assert data['label_status'] == 'unreviewed'
    # Reimporting replaces this book rather than accumulating duplicate samples.
    import_book(db, 'test.goodnotes', '1:2', stream.getvalue())
    assert db.execute('SELECT count(*) FROM groups').fetchone()[0] == 2


def test_deleted_page_not_imported(tmp_path):
    stream = io.BytesIO()
    page = '00000000-0000-0000-0000-000000000001'
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('index.events.pb', framed(field(1, page) + field(56, b'')))
        archive.writestr('search/' + page, field(5, page) + field(6, group()))
    db = connect(tmp_path / 'index.sqlite3')
    stats = import_book(db, 'test.goodnotes', '1:1', stream.getvalue())
    assert stats['deleted_pages_skipped'] == 1
    assert db.execute('SELECT count(*) FROM groups').fetchone()[0] == 0


def test_framed_search_uses_utf8_byte_offsets_and_marks_unknown_ink():
    origin = field(1, 12.) + field(2, 15.)
    size = field(1, 5.) + field(2, 7.)
    rectangle = field(1, origin) + field(2, size)
    spans = field(2, field(1, 1) + field(2, 3) + field(3, rectangle))
    result = decode_framed_search(framed(field(1, 'A生B') + field(3, spans)))
    assert result[0]['labels'] == ['生']
    assert result[0]['recognition_box_xywh'] == [12., 15., 5., 7.]
    assert result[0]['paths'] == []
    assert result[0]['ink_membership'] == 'unknown_background_or_handwriting'


def test_all_character_targets_include_words_but_exclude_printed_backgrounds(tmp_path):
    db = connect(tmp_path / 'index.sqlite3')
    for gid, label, state in [('a', '生活', 'all_live_ids'), ('b', 'か\u3099', 'all_live_ids'),
                              ('c', '印刷', 'bbox_only'), ('d', '誤', 'mismatch')]:
        db.execute('INSERT INTO groups(id,label,live_match) VALUES (?,?,?)', (gid, label, state))
    assert live_recognition_characters(db) == set('生活が')
