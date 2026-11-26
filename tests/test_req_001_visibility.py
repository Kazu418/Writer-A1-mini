import pytest
import pymupdf as fitz
from plotnote.pdf_input import load_pdf
from plotnote.model import PlotNoteError


def test_invisible_text_is_not_drawn(tmp_path):
    d = fitz.open()
    p = d.new_page(width=300, height=300)
    p.insert_text((20, 40), "ABC", render_mode=3)
    p.draw_line((20, 60), (100, 60))
    path = tmp_path / "hidden.pdf"
    d.save(path)
    d.close()
    page = load_pdf(path)[0]
    assert not any(s.source.startswith("text:") for s in page.strokes)


def test_white_text_is_rejected(tmp_path):
    d = fitz.open()
    p = d.new_page(width=300, height=300)
    p.insert_text((20, 40), "ABC", color=(1, 1, 1))
    path = tmp_path / "white.pdf"
    d.save(path)
    d.close()
    with pytest.raises(PlotNoteError, match="white text"):
        load_pdf(path)


def test_clipped_text_is_not_resurrected(tmp_path):
    d = fitz.open()
    p = d.new_page(width=300, height=300)
    p.insert_text((20, 40), "ABC")
    for xref in p.get_contents():
        d.update_stream(xref, b"q 20 20 3 3 re W n\n" + d.xref_stream(xref) + b"\nQ")
    p.draw_line((20, 60), (100, 60))
    path = tmp_path / "clip.pdf"
    d.save(path)
    d.close()
    with pytest.raises(PlotNoteError, match="clipped text|visibility"):
        load_pdf(path)
