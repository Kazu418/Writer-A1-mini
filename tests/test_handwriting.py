import pytest

from plotnote.fonts import render_glyph
from plotnote.handwriting import paragraph, text_run
from plotnote.model import PlotNoteError
from plotnote.profile import Profile
from plotnote.gcode import generate


TEXT = 'データサイエンスは、集めた情報から意味を見つけ、より良い判断につなげる学問である。'


def test_preview_execution_are_reproducible_and_seeds_change_the_ink():
    a, report = paragraph(TEXT, seed=42)
    b, again = paragraph(TEXT, seed=42)
    c, _ = paragraph(TEXT, seed=43)
    assert a == b and report == again
    assert a.strokes != c.strokes
    assert ''.join(r['text'] for r in report['rows']) == TEXT
    profile = Profile(calibrated=True, paper_x=65, paper_y=65,
                      paper_width=50, paper_height=35, pen_offset_y=-30.8,
                      draw_z=4.9, lift_z=6.5, safe_z=10,
                      draw_feed=1800, travel_feed=2400, z_feed=600)
    _, _, validation = generate(a, profile, homed=True)
    assert validation['source_geometry_checked']


def test_transform_never_loses_reorders_or_reverses_stroke_points():
    run = text_run('永あA8永あ', seed=17)
    original = [s for char in '永あA8永あ'
                for s in render_glyph(char, (1, 0, 0, 1, 0, 0))]
    assert [len(s) for s in run.paths] == [len(s) for s in original]
    # For each stroke a coherent affine transform maps points at the same
    # indices; a reversed/reordered stroke would not retain these ratios.
    for source, target in zip(original, run.paths):
        for i in range(1, len(source)-1):
            a,b,c = source[i-1:i+2]
            if abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])) > 1e-6:
                aa,bb,cc = target[i-1:i+2]
                assert ((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])) * ((bb[0]-aa[0])*(cc[1]-aa[1])-(bb[1]-aa[1])*(cc[0]-aa[0])) > 0


def test_random_spacing_does_not_overlap_actual_ink_and_varies():
    run = text_run('永永永永永永', seed=99)
    gaps = [b['left']-a['right'] for a,b in zip(run.characters, run.characters[1:])]
    assert min(gaps) >= .29-1e-9
    assert max(gaps)-min(gaps) > .01
    assert text_run('永 永',seed=99).width > text_run('永永',seed=99).width
    _, report = paragraph(TEXT*2, width=35, height=70)
    for a,b in zip(report['rows'],report['rows'][1:]):
        assert b['ink_top']-a['ink_bottom'] >= .45-1e-9
    assert len({round(b['origin_y']-a['origin_y'],3) for a,b in zip(report['rows'],report['rows'][1:])}) > 1


def test_overflow_and_narrow_pages_fail_before_export():
    with pytest.raises(PlotNoteError, match='overflows'):
        paragraph(TEXT*10, width=30, height=12)
    with pytest.raises(PlotNoteError, match='wider'):
        paragraph('永',width=5,height=20,margin=2)
