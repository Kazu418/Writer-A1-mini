"""Independent strict parser for PlotNote's intentionally small G-code dialect."""

import math
import re
from .model import PlotNoteError


def validate_gcode(text, profile, expected_page=None):
    profile.validate()
    xy = None
    z = None
    absolute = False
    millimetres = False
    feed = None
    active = []
    strokes = []
    moves = 0
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue

        def fail(message):
            raise PlotNoteError(f"G-code line {line_no}: {message}")

        tokens = line.split()
        cmd = tokens[0]
        if cmd not in ("G21", "G90", "G1", "M104", "M140", "M106", "M400"):
            fail(
                f"Forbidden command {cmd}; no homing, heating, extrusion or unknown macros allowed"
            )
        params = {}
        for token in tokens[1:]:
            m = re.fullmatch(r"([XYZFS])([-+]?(?:\d+(?:\.\d*)?|\.\d+))", token)
            if not m:
                fail(f"Invalid parameter {token}")
            if m[1] in params:
                fail(f"Duplicate {m[1]} parameter")
            value = float(m[2])
            if not math.isfinite(value):
                fail("Non-finite number")
            params[m[1]] = value
        if cmd == "G21":
            if params:
                fail("G21 takes no parameters")
            millimetres = True
            continue
        if cmd == "G90":
            if params:
                fail("G90 takes no parameters")
            absolute = True
            continue
        if cmd in ("M104", "M140", "M106"):
            if params != {"S": 0}:
                fail("Heaters/fans must be explicitly off")
            continue
        if cmd == "M400":
            if params:
                fail("M400 takes no parameters")
            continue
        if not absolute or not millimetres:
            fail("G21/G90 must precede all motion")
        if not set(params) <= set("XYZF"):
            fail("Invalid motion parameter")
        if "F" in params:
            feed = params["F"]
        if feed is None or feed <= 0:
            fail("Positive feed is required before motion")
        axes = set(params) & set("XYZ")
        if axes == {"Z"}:
            zz = params["Z"]
            if feed > profile.z_feed + 0.001:
                fail("Z feed exceeds profile")
            allowed = (profile.draw_z, profile.lift_z, profile.safe_z)
            if not any(abs(zz - a) <= 0.00051 for a in allowed):
                fail("Z is not a calibrated draw/lift/safe height")
            if z is None and abs(zz - profile.safe_z) > 0.00051:
                fail("First movement must lift to safe_z")
            down = abs(zz - profile.draw_z) <= 0.00051
            if down:
                if xy is None:
                    fail("Cannot lower before a positioned pen-up travel")
                if active:
                    fail("Repeated pen-down command")
                active = [xy]
            elif active:
                if len(active) < 2:
                    fail("Empty pen-down stroke")
                strokes.append(active)
                active = []
            z = zz
        elif axes == {"X", "Y"}:
            new = params["X"], params["Y"]
            if z is None:
                fail("XY movement before safe lift")
            if not (
                profile.nozzle_min_x <= new[0] <= profile.nozzle_max_x
                and profile.nozzle_min_y <= new[1] <= profile.nozzle_max_y
            ):
                fail("Nozzle XY outside calibrated bounds")
            px, py = new[0] + profile.pen_offset_x, new[1] + profile.pen_offset_y
            if not (
                profile.paper_x <= px <= profile.paper_x + profile.paper_width
                and profile.paper_y <= py <= profile.paper_y + profile.paper_height
            ):
                fail("Pen XY outside paper")
            if active:
                if feed > profile.draw_feed + 0.001:
                    fail("Drawing feed exceeds profile")
                active.append(new)
            else:
                if z < profile.lift_z - 0.00051:
                    fail("Travel without lifted pen")
                if feed > profile.travel_feed + 0.001:
                    fail("Travel feed exceeds profile")
            xy = new
        else:
            fail("Motion must be Z-only or X/Y-only, never mixed")
        moves += 1
    if active or z is None or abs(z - profile.safe_z) > 0.00051:
        raise PlotNoteError("G-code must end with pen raised to safe_z")
    if not strokes:
        raise PlotNoteError("G-code contains no drawing strokes")
    if expected_page is not None:
        if len(strokes) != len(expected_page.strokes):
            raise PlotNoteError("G-code stroke count differs from source")
        for i, (actual, source) in enumerate(zip(strokes, expected_page.strokes), 1):
            wanted = [profile.machine_point(x, y) for x, y in source.points]
            if len(actual) != len(wanted) or any(
                math.dist(a, b) > 0.00072 for a, b in zip(actual, wanted)
            ):
                raise PlotNoteError(
                    f"G-code stroke {i} differs from source order/direction/geometry"
                )
    return {
        "valid": True,
        "moves": moves,
        "strokes": len(strokes),
        "source_geometry_checked": expected_page is not None,
    }
