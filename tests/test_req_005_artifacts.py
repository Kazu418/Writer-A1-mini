import json
import pymupdf as fitz
import pytest
from plotnote.artifacts import write_artifacts
from plotnote.svg_input import parse_svg
from plotnote.model import PlotNoteError


def test_artifacts(page, tmp_path):
    out = write_artifacts([page, page], tmp_path / "out")
    assert (out / "preview.html").read_text().startswith("<!doctype html>")
    assert "requestAnimationFrame" in (out / "preview.html").read_text()
    with fitz.open(out / "preview.pdf") as d:
        assert len(d) == 2
        assert d[0].rect.width * 25.4 / 72 == pytest.approx(148, abs=0.001)
    for i in (1, 2):
        svg = parse_svg(out / f"page-{i:03d}.svg")
        assert len(svg.strokes) == len(page.strokes)
        assert (out / f"page-{i:03d}.png").read_bytes().startswith(b"\x89PNG")
    assert json.loads((out / "report.json").read_text())["scale"] == 1


def test_no_overwrite(page, tmp_path):
    write_artifacts([page], tmp_path / "out")
    with pytest.raises(PlotNoteError, match="already exists"):
        write_artifacts([page], tmp_path / "out")
