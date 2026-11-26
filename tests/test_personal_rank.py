from copy import deepcopy
import json
import sqlite3
import zlib

import pytest

from plotnote.fonts import glyph_paths
from plotnote.personal_rank import rank, score_paths


def test_shape_score_is_invariant_to_source_position_and_uniform_scale():
    paths = glyph_paths('数')
    changed = [[(x * 37 + 180, y * 37 + 220) for x, y in path] for path in paths]
    assert score_paths(changed, '数')['score'] == pytest.approx(0, abs=.002)


def test_complete_glyph_ranks_before_an_incomplete_single_line():
    complete = glyph_paths('数')
    assert score_paths(complete, '数')['score'] < score_paths([[(0, 0), (0, 1)]], '数')['score']


def test_ranking_preserves_original_geometry_and_never_approves_a_label():
    paths = glyph_paths('数')
    before = deepcopy(paths)
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE exemplars(id TEXT,label TEXT,status TEXT,payload BLOB)')
    blob = zlib.compress(json.dumps({'paths': paths}).encode())
    db.execute('INSERT INTO exemplars VALUES (?,?,?,?)', ('mine', '数', 'unreviewed', blob))
    report = rank(db)
    assert report['scored'] == 1
    assert report['labels_approved'] == 0
    assert db.execute('SELECT status,payload FROM exemplars').fetchone() == ('unreviewed', blob)
    assert paths == before
