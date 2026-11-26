"""One-line test using a physically established CURRENT paper-contact reference.

No absolute Z is assumed or reset. This mode is deliberately restricted to a
small central test, and is not the full notebook exporter.
"""

import math
import re
from .fonts import render_glyph
from .model import Page, Stroke, PlotNoteError
from .package import _package_bytes

OFFSET_X = 0.0
OFFSET_Y = -30.8
LIFT = 3.0
FINISH = 5.0
DRAW_FEED = 600.0
TRAVEL_FEED = 1200.0
Z_FEED = 120.0


def test_page():
    page = Page(180, 180)
    x = 75.0
    for char in "テストです。":
        for points in render_glyph(char, (5, 0, 0, 5, x, 90)):
            page.strokes.append(Stroke(points, "text:" + char))
        x += 5
    page.warnings.append(
        "Canvas is nominal bed XY, not a measured paper rectangle. Cover the indicated central writing area with flat paper."
    )
    return page


def machine_point(point):
    x, y = point
    return x - OFFSET_X, 180 - y - OFFSET_Y


def check_source(page):
    page.validate()
    if page.width != 180 or page.height != 180 or len(page.strokes) > 100:
        raise PlotNoteError(
            "Current-contact mode is restricted to a small 180mm-bed test canvas"
        )
    if sum(len(s.points) for s in page.strokes) > 5000:
        raise PlotNoteError("Current-contact test is too complex")
    for stroke in page.strokes:
        for x, y in stroke.points:
            if not (70 <= x <= 110 and 80 <= 180 - y <= 100):
                raise PlotNoteError(
                    "Test must stay in the small central paper area X70..110, Y80..100"
                )
            nx, ny = machine_point((x, y))
            if not (40 <= nx <= 140 and 40 <= ny <= 150):
                raise PlotNoteError("Compensated nozzle leaves the central test area")


def generate(page, *, air=False, contact_confirmed=False, homed=False):
    if not contact_confirmed or not homed:
        raise PlotNoteError(
            "Requires prior homing without pen and current light paper contact; no startup motion may change that reference"
        )
    check_source(page)
    draw = 2.0 if air else 0.0
    lines = [
        "; PlotNote current-contact test. A1 mini. ONE LINE ONLY.",
        "; START: paper lightly touching pen NOW; XYZ already homed.",
        "; No homing or startup macros may be added. Absolute Z is unknown.",
        "; Pen offset X=0, Y=-30.8 mm. All Z moves are RELATIVE.",
        "; END: 5mm above starting contact. Restore light contact BEFORE EVERY next file.",
        "; AIR ONLY +2mm above contact"
        if air
        else "; CONTACT WRITING at starting paper surface",
        "G21",
        "G90",
        "M104 S0",
        "M140 S0",
        "M106 S0",
    ]

    def move_z(delta):
        lines.extend(["G91", f"G1 Z{delta:.3f} F{Z_FEED:.3f}", "M400", "G90"])

    move_z(LIFT)
    for i, stroke in enumerate(page.strokes, 1):
        x, y = machine_point(stroke.points[0])
        lines.extend([f"; stroke {i}", f"G1 X{x:.3f} Y{y:.3f} F{TRAVEL_FEED:.3f}"])
        move_z(draw - LIFT)
        for point in stroke.points[1:]:
            x, y = machine_point(point)
            lines.append(f"G1 X{x:.3f} Y{y:.3f} F{DRAW_FEED:.3f}")
        move_z(LIFT - draw)
    move_z(FINISH - LIFT)
    lines.extend(
        ["M400", "; Do not replay until the pen is lightly touching paper again."]
    )
    code = "\n".join(lines) + "\n"
    report = validate(code, page, air=air)
    return code, report


def validate(code, page, *, air=False):
    """Independent state parser, including exact stroke order and source matching."""
    check_source(page)
    draw = 2.0 if air else 0.0
    absolute = None
    units = False
    z = 0.0
    xy = None
    active = None
    strokes = []
    off = set()
    settled = False
    moves = 0
    minimum_z = float("inf")
    maximum_z = -float("inf")
    for number, raw in enumerate(code.splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue

        def fail(message):
            raise PlotNoteError(f"Contact-test line {number}: {message}")

        tokens = line.split()
        cmd = tokens[0]
        params = {}
        if cmd not in ("G21", "G90", "G91", "G1", "M104", "M140", "M106", "M400"):
            fail("Forbidden command: " + cmd)
        for token in tokens[1:]:
            match = re.fullmatch(r"([XYZFS])([-+]?(?:\d+(?:\.\d*)?|\.\d+))", token)
            if not match or match[1] in params:
                fail("Invalid/duplicate parameter")
            value = float(match[2])
            if not math.isfinite(value):
                fail("Non-finite number")
            params[match[1]] = value
        if cmd in ("G21", "G90", "G91", "M400"):
            if params:
                fail("Unexpected parameter")
            if cmd == "G21":
                units = True
            elif cmd == "G90":
                absolute = True
            elif cmd == "G91":
                absolute = False
            else:
                settled = True
            continue
        if cmd in ("M104", "M140", "M106"):
            if params != {"S": 0}:
                fail("Heaters and fans must be off")
            off.add(cmd)
            continue
        if not units or off != {"M104", "M140", "M106"}:
            fail("Units/heaters must be set before motion")
        if "F" not in params or params["F"] <= 0:
            fail("Explicit positive feed required")
        axes = set(params) - {"F"}
        if axes == {"Z"}:
            if absolute is not False:
                fail("Absolute Z is forbidden; contact absolute height is unknown")
            if params["F"] > Z_FEED:
                fail("Z feed too high")
            target = z + params["Z"]
            if not any(abs(target - h) < 0.00051 for h in (draw, LIFT, FINISH)):
                fail("Unexpected relative height or movement below paper reference")
            if moves == 0 and abs(target - LIFT) > 0.00051:
                fail("First movement must lift")
            if abs(target - draw) < 0.00051:
                if xy is None or active is not None or z < LIFT - 0.00051:
                    fail("Invalid pen-down transition")
                active = [xy]
            elif active is not None:
                if len(active) < 2:
                    fail("Empty stroke")
                strokes.append(active)
                active = None
            z = target
            settled = False
            minimum_z = min(minimum_z, z)
            maximum_z = max(maximum_z, z)
        elif axes == {"X", "Y"}:
            if absolute is not True:
                fail("Relative XY motion is forbidden")
            if not settled or moves == 0:
                fail("XY movement before completed Z lift/lower")
            position = params["X"], params["Y"]
            nx, ny = position
            px, py = nx + OFFSET_X, ny + OFFSET_Y
            if not (
                40 <= nx <= 140
                and 40 <= ny <= 150
                and 70 <= px <= 110
                and 80 <= py <= 100
            ):
                fail("Nozzle or pen leaves central test area")
            if active is not None:
                if params["F"] > DRAW_FEED:
                    fail("Draw feed too high")
                active.append(position)
            elif z < LIFT - 0.00051 or params["F"] > TRAVEL_FEED:
                fail("Travel without raised pen or excessive feed")
            xy = position
        else:
            fail("Motion must be Z-only or X/Y-only")
        moves += 1
    if active is not None or not absolute or not settled or abs(z - FINISH) > 0.00051:
        raise PlotNoteError(
            "Contact test must finish in absolute XY mode, settled, 5mm above initial contact"
        )
    if len(strokes) != len(page.strokes):
        raise PlotNoteError("Contact test stroke count differs from source")
    for actual, source in zip(strokes, page.strokes):
        expected = [machine_point(p) for p in source.points]
        if len(actual) != len(expected) or any(
            math.dist(a, b) > 0.00072 for a, b in zip(actual, expected)
        ):
            raise PlotNoteError(
                "Contact test drawing differs from source geometry/order"
            )
    return {
        "valid": True,
        "strokes": len(strokes),
        "moves": moves,
        "relative_z_min_mm": minimum_z,
        "relative_z_max_mm": maximum_z,
        "finish_above_initial_contact_mm": z,
        "absolute_z_known": False,
        "air_only": bool(air),
        "source_geometry_checked": True,
    }


def package(code, page, *, air=False):
    validate(code, page, air=air)
    summary = page.summary()
    stroke_z = 2 * (LIFT - (2 if air else 0))
    seconds = math.ceil(
        summary["ink_mm"] / DRAW_FEED * 60
        + summary["travel_mm"] / TRAVEL_FEED * 60
        + (len(page.strokes) * stroke_z + FINISH) / Z_FEED * 60
    )
    return _package_bytes(code, page, 0.3, seconds)
