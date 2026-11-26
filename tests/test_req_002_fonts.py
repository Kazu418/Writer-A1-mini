import pytest
from plotnote.fonts import glyph_paths, datasets
from plotnote.model import PlotNoteError


def test_known_stroke_order():
    ps = glyph_paths("三")
    assert len(ps) == 3
    assert all(p[0][0] < p[-1][0] for p in ps)
    assert ps[0][0][1] < ps[1][0][1] < ps[2][0][1]


@pytest.mark.parametrize(
    "char", list("あいうえおアイウエオがぱ漢字ABCxyz0123αβΓΔ∑∫√∞≤→。、")
)
def test_japanese_latin_math(char):
    ps = glyph_paths(char)
    assert ps and all(len(p) > 1 for p in ps)


def test_complete_japanese_dataset():
    k, _ = datasets()
    assert len(k) >= 6984
    for c in k:
        assert glyph_paths(c), f"Missing/empty glyph: {c}"


def test_no_fallback_outline():
    with pytest.raises(PlotNoteError, match=r"U\+1F600"):
        glyph_paths("😀")


def test_space():
    assert glyph_paths(" ") == []
