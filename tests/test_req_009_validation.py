import pytest
from plotnote.gcode import generate
from plotnote.validate import validate_gcode
from plotnote.model import PlotNoteError


@pytest.mark.parametrize(
    "command",
    [
        "G28",
        "G29",
        "G92 X0",
        "G91",
        "M104 S140",
        "M140 S60",
        "M109 S0",
        "G1 E10 F100",
        "M211 X0",
        "M970.3 Q0",
        "G1 Xnan Y2",
        "G1 X20 Y20 X21",
    ],
)
def test_forbidden(page, profile, command):
    code, _, _ = generate(page, profile, homed=True)
    with pytest.raises(PlotNoteError):
        validate_gcode(code + command + "\n", profile)


@pytest.mark.parametrize(
    "old,new",
    [
        ("G1 X20.000 Y148.000", "G1 X181.000 Y148.000"),
        ("G1 Z10.000 F300.000", "G1 Z5.000 F300.000"),
        ("G1 Z5.000 F300.000", "G1 Z0.000 F300.000"),
        ("F1200.000", "F6000.000"),
    ],
)
def test_corrupted_motion(page, profile, old, new):
    code, _, _ = generate(page, profile, homed=True)
    with pytest.raises(PlotNoteError):
        validate_gcode(code.replace(old, new, 1), profile, page)


def test_direction_corruption(page, profile):
    code, _, _ = generate(page, profile, homed=True)
    code = code.replace("G1 X40.000 Y148.000", "G1 X41.000 Y148.000")
    with pytest.raises(PlotNoteError, match="differs"):
        validate_gcode(code, profile, page)
