import pytest
from plotnote.svg_input import parse_svg
from plotnote.model import PlotNoteError


@pytest.mark.parametrize("size", ["1e999mm", "-1mm", "181mm", "0mm"])
def test_invalid_page_size(size):
    with pytest.raises(PlotNoteError):
        parse_svg(f'<svg width="{size}" height="100mm"><path d="M0 0L1 1"/></svg>')


def test_no_silent_crop():
    p = parse_svg(
        '<svg width="100mm" height="100mm" viewBox="0 0 100 100"><path fill="none" stroke="black" d="M10 10L110 10"/></svg>'
    )
    with pytest.raises(PlotNoteError, match="outside page"):
        p.validate()


def test_degenerate_fill_has_no_visible_area():
    page = parse_svg(
        '<svg width="100mm" height="100mm" viewBox="0 0 100 100"><path d="M10 10L10 20"/><path fill="none" stroke="black" d="M10 10L10 20"/></svg>'
    )
    assert len(page.strokes) == 1


@pytest.mark.parametrize(
    "body",
    [
        '<g transform="translate(1garbage)"><path d="M0 0L1 1"/></g>',
        '<g onload="alert(1)"/>',
        "<defs><script>alert(1)</script></defs>",
        '<path d="M1e999 0L1 1"/>',
    ],
)
def test_bad_transforms_and_scripts(body):
    with pytest.raises(PlotNoteError):
        parse_svg(
            f'<svg width="100mm" height="100mm" viewBox="0 0 100 100">{body}</svg>'
        )
