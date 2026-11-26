import pytest
import pymupdf as fitz
from plotnote.pdf_input import load_pdf
from plotnote.fonts import glyph_paths


def test_strokes_and_vectors(make_pdf):
    p = load_pdf(make_pdf(text="木"))[0]
    strokes = [s for s in p.strokes if s.source.startswith("text:木")]
    assert len(strokes) == 4
    assert len([s for s in p.strokes if s.source == "vector"]) == 3
    assert max(x for s in strokes for x, y in s.points) < 20
    assert max(y for s in strokes for x, y in s.points) < 18


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_page_rotation(make_pdf, rotation):
    p = load_pdf(make_pdf(rotation=rotation))[0]
    p.validate()
    assert len([s for s in p.strokes if s.source.startswith("text:三")]) == 3


def test_vector_dimensions(make_pdf):
    p = load_pdf(make_pdf())[0]
    line = p.strokes[0].points
    assert line[0] == pytest.approx((25 * 25.4 / 72, 60 * 25.4 / 72))
    assert line[-1] == pytest.approx((200 * 25.4 / 72, 60 * 25.4 / 72))


def test_character_positions(tmp_path):
    d = fitz.open()
    p = d.new_page(width=300, height=300)
    p.insert_text((25, 40), "A", fontsize=12)
    p.insert_text((100, 80), "A", fontsize=12)
    path = tmp_path / "positions.pdf"
    d.save(path)
    d.close()
    page = load_pdf(path)[0]
    ss = [s for s in page.strokes if s.source.startswith("text:A")]
    count = len(glyph_paths("A"))
    a = ss[0].points[0]
    b = ss[count].points[0]
    assert (b[0] - a[0], b[1] - a[1]) == pytest.approx(
        (75 * 25.4 / 72, 40 * 25.4 / 72), abs=0.001
    )
