import json
import sqlite3
import zlib

import pytest

from plotnote.personal_font import normalize_sample, text_page
from plotnote.personal_metrics import anchor_from_group, apply_updates, enrich, estimate_metrics, geometry_digest


def anchors(top=10, height=20):
    return [{'id': str(i), 'box': [x, top, x + 15, top + height],
             'stroke_ids': (str(i),)} for i, x in enumerate((10, 30, 50, 70))]


def punctuation():
    return {'id': 'dot', 'book': 'mine', 'page': 'one', 'label': '。',
            'bbox': [92, 27, 95, 30], 'paths': [[[92., 27.], [95., 30.], [92., 27.]]],
            'stroke_ids': ['dot'], 'stroke_order_status': 'stored_order_not_temporal'}


def test_punctuation_keeps_small_size_and_lower_source_line_position():
    sample = punctuation()
    result = estimate_metrics(sample, anchors())
    assert result['status'] == 'estimated_source_line'
    sample.update(em_height=result['em_height'], line_top=result['line_top'],
                  metric_reference=result['metric_reference'])
    glyph = normalize_sample(sample)
    assert glyph['width_em'] == pytest.approx(.15)
    assert glyph['paths'][0] == [[0., .85], [.15, 1.], [0., .85]]
    assert glyph['original_paths'] == punctuation()['paths']
    assert glyph['metrics_status'] == 'estimated_source_line'


def test_nearby_body_line_is_used_instead_of_large_heading():
    result = estimate_metrics(punctuation(), anchors() + anchors(top=-80, height=60))
    assert result['em_height'] == 20
    assert result['line_top'] == 10


def test_printed_search_boxes_cannot_be_metric_anchors():
    group = {'labels': ['数'], 'live_match': 'bbox_only',
             'recognition_box_xywh': [10, 10, 15, 20], 'stroke_ids': ['a']}
    assert anchor_from_group('a', group) is None


def test_self_reference_and_insufficient_neighbors_do_not_invent_metrics():
    sample = punctuation()
    refs = anchors()[:2]
    refs.append({'id': 'same', 'box': [92, 27, 95, 30], 'stroke_ids': ('dot',)})
    assert estimate_metrics(sample, refs)['status'] == 'insufficient_source_line'
    sample.update(em_height=26, line_top=81)
    assert estimate_metrics(sample, anchors())['status'] == 'preserved_explicit_reference'


def test_metric_enrichment_does_not_change_ink_or_accept_a_label():
    db = sqlite3.connect(':memory:')
    db.executescript('CREATE TABLE groups(id TEXT,book TEXT,page TEXT,single_char INTEGER,live_match TEXT,payload BLOB);'
                     'CREATE TABLE exemplars(id TEXT,label TEXT,status TEXT,payload BLOB);')
    for a in anchors():
        x0, y0, x1, y1 = a['box']
        group = {'labels': ['数'], 'live_match': 'all_live_ids',
                 'recognition_box_xywh': [x0, y0, x1-x0, y1-y0], 'stroke_ids': list(a['stroke_ids'])}
        db.execute('INSERT INTO groups VALUES (?,?,?,?,?,?)',
                   (a['id'], 'mine', 'one', 1, 'all_live_ids', zlib.compress(json.dumps(group).encode())))
    sample = punctuation()
    db.execute('INSERT INTO exemplars VALUES (?,?,?,?)',
               ('dot', '。', 'unreviewed', zlib.compress(json.dumps(sample).encode())))
    counts, updates = enrich(db)
    assert counts['estimated_source_line'] == 1
    assert len(updates) == 1
    label, status, blob = db.execute('SELECT label,status,payload FROM exemplars').fetchone()
    enriched = json.loads(zlib.decompress(blob))
    assert (label, status) == ('。', 'unreviewed')
    assert enriched['paths'] == sample['paths']
    assert enriched['stroke_ids'] == sample['stroke_ids']


def test_rows_use_actual_ink_bounds_including_ascenders_and_descenders():
    glyph = {'paths': [[[0., -.3], [1., 1.4]]], 'width_em': 1., 'source': {'id': 'tall'}}
    page = text_page('字\n字', {'glyphs': {'字': [glyph]}}, size=2.5, line_pitch=2.5,
                     row_gap=.4, margin=8)
    first, second = page.strokes
    assert min(y for x, y in first.points) == 8
    assert min(y for x, y in second.points) - max(y for x, y in first.points) == pytest.approx(.4)
    assert len(first.points) == len(second.points) == 2


def test_metric_patch_preserves_label_corrections_and_rejects_changed_geometry():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE exemplars(id TEXT,label TEXT,status TEXT,payload BLOB)')
    sample = punctuation()
    db.execute('INSERT INTO exemplars VALUES (?,?,?,?)',
               ('dot', '・', 'accepted', zlib.compress(json.dumps(sample).encode())))
    db.commit()
    patch = {'id': 'dot', 'em_height': 20., 'line_top': 10.,
             'geometry_sha256': geometry_digest(sample),
             'metric_reference': {'method': 'nearby_live_ink_median_v1'}}
    assert apply_updates(db, [patch]) == 1
    assert db.execute('SELECT label,status FROM exemplars').fetchone() == ('・', 'accepted')
    bad = dict(patch, geometry_sha256='changed')
    with pytest.raises(ValueError, match='Source ink changed'):
        apply_updates(db, [dict(patch, em_height=99.), bad])
    restored = json.loads(zlib.decompress(db.execute('SELECT payload FROM exemplars').fetchone()[0]))
    assert restored['em_height'] == 20.
