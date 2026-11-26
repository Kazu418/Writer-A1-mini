import copy
import pytest
from plotnote.fonts import use_standard_font, personal_font_active
from plotnote.keyword_style import fit_standard_keyword
from plotnote.model import PlotNoteError

def test_keyword_stays_in_original_ink_box_and_is_reproducible():
    paths=[[(10.,20.),(20.,23.)],[(11.,21.),(19.,22.)]]
    before=copy.deepcopy(paths)
    a=fit_standard_keyword("分散",2.8,paths)
    assert a==fit_standard_keyword("分散",2.8,paths)
    assert paths==before
    assert all(10-1e-9<=x<=20+1e-9 and 20-1e-9<=y<=23+1e-9 for p in a for x,y in p)
    assert len(a)>2

def test_standard_scope_disables_and_restores_personal_context():
    from plotnote.fonts import _personal
    token=_personal.set(({},frozenset(),{}))
    try:
        assert personal_font_active()
        with use_standard_font():
            assert not personal_font_active()
            with use_standard_font():assert not personal_font_active()
        assert personal_font_active()
        assert fit_standard_keyword("分散",2.8,[[(0,0),(10,3)]])
        assert personal_font_active()
    finally:_personal.reset(token)

@pytest.mark.parametrize("paths",[[],[[(0,0),(0,1)]],[[(0,0),(1,0)]]])
def test_invalid_reference_rejected(paths):
    with pytest.raises(PlotNoteError):fit_standard_keyword("分散",2.8,paths)
