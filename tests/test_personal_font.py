import json
import sqlite3
import zlib

import pytest

from plotnote.cli import export_pages
from plotnote.model import PlotNoteError
from plotnote.personal_font import add_typographic_forms, export_library, text_page
from plotnote.personal_review import read_samples, review
from plotnote.svg_input import parse_svg
from plotnote.artifacts import svg
from plotnote.fonts import glyph_paths, use_personal_font


def sample(gid='a'):
    return {'id': gid, 'book': 'mine.goodnotes', 'page': 'page-1',
            'paths': [[[100., 200.], [103., 204.], [106., 200.]],
                      [[102., 202.], [104., 202.]]],
            'stroke_ids': ['one', 'two'], 'stroke_order_status': 'layer_order_not_temporal'}


def database(tmp_path):
    db = sqlite3.connect(tmp_path / 'font.sqlite3')
    db.execute('CREATE TABLE exemplars(id TEXT PRIMARY KEY,label TEXT,status TEXT,payload BLOB)')
    for gid in ['a', 'b']:
        db.execute('INSERT INTO exemplars VALUES (?,?,?,?)',
                   (gid, '字', 'unreviewed', zlib.compress(json.dumps(sample(gid)).encode())))
    db.commit()
    return db


def test_unreviewed_originals_cannot_leak_into_runnable_font(tmp_path):
    db = database(tmp_path)
    with pytest.raises(PlotNoteError, match='No confirmed'):
        export_library(db, tmp_path / 'font.json')
    review(db, 'a', '木', 'accepted')
    font = export_library(db, tmp_path / 'font.json')
    assert set(font['glyphs']) == {'木'}
    assert font['glyphs']['木'][0]['original_paths'] == sample()['paths']
    with pytest.raises(PlotNoteError, match='missing: 字'):
        text_page('木字', font)


def test_multiple_real_exemplars_and_reversible_review(tmp_path):
    db = database(tmp_path)
    review(db, 'a', '字', 'accepted')
    review(db, 'b', '字', 'accepted')
    font = export_library(db, tmp_path / 'font.json')
    assert len(font['glyphs']['字']) == 2
    page = text_page('字字', font)
    assert [s.source for s in page.strokes] == ['personal:字:a'] * 2 + ['personal:字:b'] * 2
    review(db, 'a', '字', 'rejected')
    font = export_library(db, tmp_path / 'font.json')
    assert len(font['glyphs']['字']) == 1


@pytest.mark.parametrize('label,status', [('ab', 'accepted'), (' ', 'accepted'), ('字', 'invented')])
def test_invalid_review_cannot_change_database(tmp_path, label, status):
    db = database(tmp_path)
    with pytest.raises(ValueError):
        review(db, 'a', label, status)
    assert db.execute('SELECT status FROM exemplars WHERE id="a"').fetchone()[0] == 'unreviewed'


def test_personal_centerlines_survive_svg_and_existing_gcode_export(tmp_path, profile):
    db = database(tmp_path)
    review(db, 'a', '字', 'accepted')
    font = export_library(db, tmp_path / 'font.json')
    page = text_page('字字', font, margin=12)
    reparsed = parse_svg(svg(page, .25))
    assert len(reparsed.strokes) == len(page.strokes) == 4
    for a, b in zip(page.strokes, reparsed.strokes):
        assert len(a.points) == len(b.points)
        for pa, pb in zip(a.points, b.points):
            assert pa == pytest.approx(pb, abs=.001)
    out = export_pages([page], profile, tmp_path / 'gcode', homed=True)
    assert (out / 'page-001.gcode').is_file()
    assert (out / 'page-001.gcode.3mf').is_file()
    assert json.loads((out / 'validation.json').read_text())['pages']


def test_personal_font_scope_never_reuses_cached_standard_glyphs(tmp_path):
    original = glyph_paths('字')
    db = database(tmp_path)
    review(db, 'a', '字', 'accepted')
    font = export_library(db, tmp_path / 'font.json')
    with use_personal_font(font):
        fitted = glyph_paths('字')
        assert fitted != original
        # Re-sized to the standard glyph's typographic box, centred on it.
        xs = [x for path in fitted for x, _ in path]; ys = [y for path in fitted for _, y in path]
        sx = [x for path in original for x, _ in path]; sy = [y for path in original for _, y in path]
        assert (min(xs) + max(xs)) / 2 == pytest.approx((min(sx) + max(sx)) / 2, abs=1e-6)
        assert (min(ys) + max(ys)) / 2 == pytest.approx((min(sy) + max(sy)) / 2, abs=1e-6)
        assert len(fitted) == len(font['glyphs']['字'][0]['paths'])   # same strokes, same order
        with pytest.raises(PlotNoteError, match='Personal glyph missing'):
            glyph_paths('木')
        assert glyph_paths(' ') == []
    assert glyph_paths('字') == original


def test_review_preserves_confirmed_exemplars_ahead_of_shape_scores(tmp_path):
    db = database(tmp_path)
    db.execute('CREATE TABLE candidate_scores(id TEXT,pool TEXT,label TEXT,score REAL,error TEXT)')
    db.execute('INSERT INTO candidate_scores VALUES (?,?,?,?,?)', ('a', 'exemplars', '字', .5, None))
    db.execute('INSERT INTO candidate_scores VALUES (?,?,?,?,?)', ('b', 'exemplars', '字', .01, None))
    db.commit()
    assert [s['id'] for s in read_samples(db, '字')] == ['b', 'a']
    review(db, 'a', '字', 'accepted')
    assert [s['id'] for s in read_samples(db, '字')] == ['a', 'b']
    review(db, 'b', '木', 'unreviewed')
    assert read_samples(db, '木')[0]['ranking_score'] is None


def test_ocr_agreement_prioritizes_review_without_approving_or_surviving_label_correction(tmp_path):
    db = database(tmp_path)
    db.execute('CREATE TABLE independent_ocr(exemplar_id TEXT,expected_label TEXT,reading TEXT,status TEXT)')
    db.execute('INSERT INTO independent_ocr VALUES (?,?,?,?)', ('b','字','字','match'))
    samples = read_samples(db,'字')
    assert samples[0]['id']=='b'
    assert samples[0]['status']=='unreviewed'
    assert samples[0]['ocr_reading']=='字'
    review(db,'a','字','accepted')
    assert read_samples(db,'字')[0]['id']=='a'
    review(db,'b','木','unreviewed')
    assert 'ocr_status' not in read_samples(db,'木')[0]


def test_typographic_forms_keep_writer_geometry_and_never_fill_missing_kanji(tmp_path):
    db=database(tmp_path)
    review(db,'a','2','accepted')
    font=export_library(db,tmp_path/'font.json',typographic_forms=True)
    base=font['glyphs']['2'][0]
    raised=font['glyphs']['²'][0]
    assert raised['original_paths']==base['original_paths']==sample()['paths']
    assert raised['source']==base['source']
    for actual,original in zip(raised['paths'],base['paths']):
        for point,source in zip(actual,original):
            assert point==pytest.approx([source[0]*.6,source[1]*.6-.1])
    assert font['typographic_forms']=={'²':'2'}
    text_page('2²',font)
    with pytest.raises(PlotNoteError,match='missing: 授'):
        text_page('授',font)


def test_width_and_sum_forms_preserve_exact_display_paths(tmp_path):
    db=database(tmp_path)
    review(db,'a','(','accepted')
    review(db,'b','Σ','accepted')
    font=export_library(db,tmp_path/'font.json',typographic_forms=True)
    assert font['glyphs']['（'][0]['paths']==font['glyphs']['('][0]['paths']
    assert font['glyphs']['∑'][0]['paths']==font['glyphs']['Σ'][0]['paths']
    assert font['glyphs']['（'][0]['derivation']['base_character']=='('


def test_punctuation_repositions_and_repeats_personal_ink_without_synthetic_lines(tmp_path):
    db=database(tmp_path)
    review(db,'a','.','accepted')
    review(db,'b','ー','accepted')
    font=export_library(db,tmp_path/'font.json',typographic_forms=True)
    base=font['glyphs']['.'][0]
    colon=font['glyphs']['：'][0]
    assert colon['original_paths']==base['original_paths']
    assert len(colon['paths'])==2*len(base['paths'])
    for a,b in zip(colon['paths'][:2],colon['paths'][2:]):
        for point,shifted in zip(a,b):
            assert shifted==pytest.approx([point[0],point[1]+.45])
    minus=font['glyphs']['−'][0]
    ys=[y for path in minus['paths'] for x,y in path]
    assert (max(ys)+min(ys))/2==pytest.approx(.5)
    assert minus['original_paths']==font['glyphs']['ー'][0]['original_paths']


def _font(char, paths):
    return {'format': 'plotnote-personal-centerlines-v1', 'label_status': 'reviewed',
            'glyphs': {char: [{'paths': paths, 'width_em': 1., 'source': {'id': 'x'}}]}}


def test_prolonged_sound_mark_sits_at_standard_height_not_at_the_top():
    # Provisional cells put flat marks at the top; the standard places ー mid-height.
    flat_at_top = [[[0., 0.], [1., 0.02]]]
    with use_personal_font(_font('ー', flat_at_top)):
        ys = [y for path in glyph_paths('ー') for _, y in path]
    assert .4 < sum(ys) / len(ys) < .6


def test_every_size_class_lands_in_its_standard_box_and_keeps_proportions():
    tall = [[[0., 0.], [.1, 1.]]]
    with use_personal_font(_font('比', [[[0., 0.], [1., 1.]], [[.2, .5], [.9, .1]]])):
        fitted = glyph_paths('比')
    xs = [x for path in fitted for x, _ in path]; ys = [y for path in fitted for _, y in path]
    sx = [x for path in glyph_paths_standard('比') for x, _ in path]
    assert (max(xs) - min(xs)) <= 1.15 * (max(sx) - min(sx)) + 1e-9
    assert max(ys) - min(ys) > 0.3                       # not collapsed to a mark
    # uniform scale: the aspect ratio of the writer's glyph is unchanged
    assert (max(xs) - min(xs)) / (max(ys) - min(ys)) == pytest.approx(1.0, rel=1e-6)


def test_characters_without_a_standard_reference_are_used_as_stored():
    stored = [[[0., 0.], [.5, .5]]]
    with use_personal_font(_font('\ue000', stored)):
        assert glyph_paths('\ue000') == stored


def test_dots_stay_visible():
    with use_personal_font(_font('・', [[[0., 0.], [.3, .3]]])):
        xs = [x for path in glyph_paths('・') for x, _ in path]
    assert max(xs) - min(xs) >= .07


def glyph_paths_standard(char):
    from plotnote.fonts import _standard_glyph_paths
    return _standard_glyph_paths(char)
