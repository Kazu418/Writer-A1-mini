import pytest
import pymupdf as fitz
from plotnote.pdf_input import load_pdf
from plotnote.model import PlotNoteError


def test_real_pdf(make_pdf):
    pages = load_pdf(make_pdf())
    assert len(pages) == 1
    assert pages[0].width == pytest.approx(148, abs=0.001)
    assert any(s.source.startswith("text:三") for s in pages[0].strokes)


@pytest.mark.parametrize(
    "options,match",
    [
        ({"width": 210, "height": 297}, "exceeds"),
        ({"image": True}, "raster"),
        ({"fill": True}, "Filled"),
    ],
)
def test_reject_unsupported(make_pdf, options, match):
    with pytest.raises(PlotNoteError, match=match):
        load_pdf(make_pdf(**options))


def test_aggregate_issues(make_pdf):
    with pytest.raises(PlotNoteError) as exc:
        load_pdf(make_pdf(width=210, image=True, fill=True))
    assert all(word in str(exc.value) for word in ("exceeds", "raster", "Filled"))


def test_annotation(tmp_path):
    d = fitz.open()
    p = d.new_page(width=300, height=300)
    p.add_text_annot((30, 30), "note")
    path = tmp_path / "annot.pdf"
    d.save(path)
    d.close()
    with pytest.raises(PlotNoteError, match="annotations"):
        load_pdf(path)


def test_broken_pdf(tmp_path):
    p = tmp_path / "broken.pdf"
    p.write_bytes(b"%PDF broken")
    with pytest.raises(PlotNoteError, match="Cannot open"):
        load_pdf(p)
