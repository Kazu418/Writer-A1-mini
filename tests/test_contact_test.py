import io
import hashlib
import zipfile
import pytest
from plotnote import contact_test as ct
from plotnote.model import PlotNoteError


@pytest.mark.parametrize("air", [False, True])
def test_relative_contact_modes(air):
    page = ct.test_page()
    code, report = ct.generate(page, air=air, contact_confirmed=True, homed=True)
    assert report["finish_above_initial_contact_mm"] == 5
    assert report["relative_z_min_mm"] == (2 if air else 0)
    assert not report["absolute_z_known"]
    assert ct.machine_point((90, 90)) == (90, 120.8)
    with zipfile.ZipFile(io.BytesIO(ct.package(code, page, air=air))) as z:
        data = z.read("Metadata/plate_1.gcode")
        assert data.decode() == code
        assert (
            z.read("Metadata/plate_1.gcode.md5").decode().strip().lower()
            == hashlib.md5(data).hexdigest()
        )


def test_require_current_reference():
    with pytest.raises(PlotNoteError):
        ct.generate(ct.test_page(), homed=True)
    with pytest.raises(PlotNoteError):
        ct.generate(ct.test_page(), contact_confirmed=True)


@pytest.mark.parametrize(
    "bad", ["G28", "G92 Z0", "G29", "M104 S140", "G1 E1 F100", "M211 X0"]
)
def test_reject_unsafe_commands(bad):
    page = ct.test_page()
    code, _ = ct.generate(page, contact_confirmed=True, homed=True)
    with pytest.raises(PlotNoteError):
        ct.validate(code + "\n" + bad, page)


@pytest.mark.parametrize(
    "old,new",
    [
        ("G91\nG1 Z3.000", "G90\nG1 Z3.000"),
        ("G1 Z-3.000", "G1 Z-4.000"),
        ("G1 X", "G91\nG1 X"),
        ("M400\nG90", "G90"),
        ("F600.000", "F6000.000"),
    ],
)
def test_reject_bad_transitions(old, new):
    page = ct.test_page()
    code, _ = ct.generate(page, contact_confirmed=True, homed=True)
    with pytest.raises(PlotNoteError):
        ct.validate(code.replace(old, new, 1), page)


def test_reject_source_mismatch():
    page = ct.test_page()
    code, _ = ct.generate(page, contact_confirmed=True, homed=True)
    first = ct.machine_point(page.strokes[0].points[1])
    old = f"G1 X{first[0]:.3f} Y{first[1]:.3f} F600.000"
    new = f"G1 X{first[0] + 1:.3f} Y{first[1]:.3f} F600.000"
    assert old in code
    with pytest.raises(PlotNoteError):
        ct.validate(code.replace(old, new, 1), page)
