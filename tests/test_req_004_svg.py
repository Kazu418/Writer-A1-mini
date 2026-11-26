import pytest
from plotnote.svg_input import parse_svg
from plotnote.model import PlotNoteError


def svg(body, extra=""):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100" {extra}><g fill="none" stroke="black">{body}</g></svg>'


@pytest.mark.parametrize(
    "body",
    [
        '<path d="M10 10h20v20h-20z"/>',
        '<line x1="10" y1="10" x2="20" y2="20"/>',
        '<circle cx="30" cy="30" r="10"/>',
        '<ellipse cx="30" cy="30" rx="10" ry="5"/>',
        '<rect x="10" y="10" width="20" height="10" rx="3"/>',
        '<polyline points="10,10 20,20 30,10"/>',
        '<polygon points="10,10 20,20 30,10"/>',
        '<path d="M10 10Q20 0 30 10T50 10C60 0 60 20 70 10S80 20 90 10"/>',
    ],
)
def test_primitives(body):
    p = parse_svg(svg(body))
    p.validate()
    assert p.strokes


def test_nested_transform():
    p = parse_svg(
        svg(
            '<g transform="translate(10 20)"><path transform="scale(2)" d="M1 1L3 3"/></g>'
        )
    )
    assert p.strokes[0].points == [(12, 22), (16, 26)]


def test_clipping():
    p = parse_svg(
        svg(
            '<defs><clipPath id="c"><rect x="20" y="20" width="20" height="20"/></clipPath></defs><g clip-path="url(#c)"><path d="M10 30L50 30"/></g>'
        )
    )
    assert p.strokes[0].points == [(20, 30), (40, 30)]


def test_use():
    p = parse_svg(
        svg('<defs><path id="a" d="M1 1L2 2"/></defs><use href="#a" x="10" y="10"/>')
    )
    assert p.strokes[0].points == [(11, 11), (12, 12)]


@pytest.mark.parametrize(
    "body,match",
    [
        ('<image href="https://example.com/a.png"/>', "image"),
        ("<text>Hello</text>", "text"),
        ('<path fill="black" d="M10 10L20 20L20 10Z"/>', "Filled"),
        ('<path stroke-dasharray="2 2" d="M10 10L20 20"/>', "Dashed"),
        ("<script>alert(1)</script>", "script"),
        ('<use href="#missing"/>', "reference"),
        ('<g opacity=".5"><path d="M10 10L20 20"/></g>', "transparency"),
    ],
)
def test_unsupported(body, match):
    with pytest.raises(PlotNoteError, match=match):
        parse_svg(svg(body))


def test_units():
    p = parse_svg(
        '<svg width="1in" height="72pt" viewBox="0 0 10 10"><path fill="none" stroke="black" d="M1 1L9 9"/></svg>'
    )
    assert p.width == pytest.approx(25.4)
    assert p.height == pytest.approx(25.4)
