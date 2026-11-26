from pathlib import Path
import pytest
from plotnote.pdf_input import load_pdf
from plotnote.artifacts import svg
from plotnote.svg_input import parse_svg


def test_real_matplotlib_pdf():
    # Created with Matplotlib PDF Type 42, transparent background and clipped sine curve.
    path = Path(__file__).with_name("fixtures") / "matplotlib-note.pdf"
    page = load_pdf(path)[0]
    assert page.width == pytest.approx(148, abs=0.001)
    assert any(s.source.startswith("text:−") for s in page.strokes)
    assert any(len(s.points) > 100 and s.source == "vector" for s in page.strokes)
    again = parse_svg(svg(page))
    again.validate()
    assert len(again.strokes) == len(page.strokes)
