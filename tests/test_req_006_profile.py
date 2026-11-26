from dataclasses import replace
import pytest
from plotnote.profile import Profile
from plotnote.model import PlotNoteError


def test_offset_sign(profile):
    p = replace(profile, pen_offset_x=3, pen_offset_y=-22)
    assert p.machine_point(20, 30) == (27, 150)
    p.check_page(
        __import__("plotnote.cli", fromlist=["calibration_page"]).calibration_page(p)
    )


def test_no_guessed_calibration():
    with pytest.raises(PlotNoteError, match="uncalibrated"):
        Profile().validate()


@pytest.mark.parametrize(
    "changes",
    [
        {"draw_z": 0},
        {"draw_z": 8},
        {"lift_z": 5.1},
        {"safe_z": 31},
        {"travel_feed": 6001},
        {"draw_feed": float("nan")},
        {"pen_offset_x": float("inf")},
        {"paper_width": 200},
        {"nozzle_min_x": -1},
        {"nozzle_max_y": 181},
        {"calibrated": "true"},
        {"pen_width": 0},
    ],
)
def test_invalid_profiles(profile, changes):
    with pytest.raises(PlotNoteError):
        replace(profile, **changes).validate()


def test_profile_roundtrip(profile, tmp_path):
    p = tmp_path / "p.json"
    profile.save(p)
    assert Profile.load(p) == profile
