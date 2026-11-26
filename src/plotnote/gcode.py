from dataclasses import replace
import math
from .model import PlotNoteError
from .validate import validate_gcode


def effective_profile(profile, air_mm=0):
    if not math.isfinite(air_mm) or air_mm < 0 or air_mm > 10:
        raise PlotNoteError("Air-run lift must be 0..10 mm")
    p = replace(
        profile,
        draw_z=profile.draw_z + air_mm,
        lift_z=profile.lift_z + air_mm,
        safe_z=profile.safe_z + air_mm,
    )
    p.validate()
    return p


def generate(page, profile, *, homed=False, air_mm=0):
    if not homed:
        raise PlotNoteError(
            "Export requires --homed: confirm the workflow home without pen, raise Z, mount pen, then run without rehoming. Read docs/CALIBRATION.md."
        )
    p = effective_profile(profile, air_mm)
    p.check_page(page)
    lines = [
        "; PlotNote A1 mini ordered pen strokes",
        "; REQUIRES manual homing BEFORE pen insertion. Do not rehome with lowered pen.",
        "; No start/end macro may be added by a slicer.",
        f"; AIR RUN +{air_mm:g} mm"
        if air_mm
        else "; CONTACT PLOT: measured calibrated profile required",
        "; Units mm, absolute machine/nozzle coordinates",
        "G21",
        "G90",
        "M104 S0",
        "M140 S0",
        "M106 S0",
        f"G1 Z{p.safe_z:.3f} F{p.z_feed:.3f}",
    ]
    for i, s in enumerate(page.strokes, 1):
        x, y = p.machine_point(*s.points[0])
        lines.extend(
            [
                f"; stroke {i}",
                f"G1 X{x:.3f} Y{y:.3f} F{p.travel_feed:.3f}",
                f"G1 Z{p.draw_z:.3f} F{p.z_feed:.3f}",
            ]
        )
        for x, y in (p.machine_point(*pt) for pt in s.points[1:]):
            lines.append(f"G1 X{x:.3f} Y{y:.3f} F{p.draw_feed:.3f}")
        lines.append(f"G1 Z{p.lift_z:.3f} F{p.z_feed:.3f}")
    lines.extend(
        [
            f"G1 Z{p.safe_z:.3f} F{p.z_feed:.3f}",
            "M400",
            "; End: pen raised; remove pen before homing or normal printing.",
        ]
    )
    text = "\n".join(lines) + "\n"
    report = validate_gcode(text, p, page)
    return text, p, report
