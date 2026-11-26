from dataclasses import replace
import pytest
from plotnote.gcode import generate
from plotnote.model import PlotNoteError
from plotnote.validate import validate_gcode


def test_roundtrip(page, profile):
    code, p, r = generate(page, profile, homed=True)
    assert r["source_geometry_checked"]
    assert "G28" not in code
    assert "G1 X20.000 Y148.000" in code
    assert validate_gcode(code, p, page)["strokes"] == 2


def test_acknowledge(page, profile):
    with pytest.raises(PlotNoteError, match="--homed"):
        generate(page, profile)


def test_air_run(page, profile):
    code, p, r = generate(page, profile, homed=True, air_mm=5)
    assert p.draw_z == 10
    assert "G1 Z15.000" in code
    assert validate_gcode(code, p, page)["valid"]


def test_page_mismatch(page, profile):
    with pytest.raises(PlotNoteError, match="match profile"):
        generate(page, replace(profile, paper_width=140), homed=True)


def test_compensated_bounds(page, profile):
    with pytest.raises(PlotNoteError, match="bounds"):
        generate(page, replace(profile, pen_offset_y=-50), homed=True)
