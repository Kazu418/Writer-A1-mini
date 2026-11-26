"""Generate the one-line test for the current user-reported paper contact."""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from plotnote import contact_test as ct
from plotnote.artifacts import write_artifacts


def main():
    out = ROOT / "output/contact-test"
    if out.exists():
        raise SystemExit(f"Refusing to overwrite existing test: {out}")
    page = ct.test_page()
    payload = []
    for label, air in [("01_AIR", True), ("02_WRITE", False)]:
        code, report = ct.generate(page, air=air, homed=True, contact_confirmed=True)
        payload.append((label, code, ct.package(code, page, air=air), report))
    out.mkdir(parents=True)
    write_artifacts([page], out / "preview", 0.3)
    points = [(x, 180 - y) for s in page.strokes for x, y in s.points]
    bounds = [
        min(x for x, y in points),
        min(y for x, y in points),
        max(x for x, y in points),
        max(y for x, y in points),
    ]
    machine = [ct.machine_point(p) for s in page.strokes for p in s.points]
    nozzle_bounds = [
        min(x for x, y in machine),
        min(y for x, y in machine),
        max(x for x, y in machine),
        max(y for x, y in machine),
    ]
    for label, code, package, report in payload:
        (out / (label + ".gcode")).write_text(code)
        (out / (label + ".gcode.3mf")).write_bytes(package)
    info = {
        "text": "テストです。",
        "em_size_mm": 5,
        "canvas": "180x180mm nominal bed, not paper size",
        "user_reported": {
            "pen_offset_x_mm": 0,
            "pen_offset_y_mm": -30.8,
            "contact_reference": "User adjusted pen mounting after homing to touch paper; absolute Z unknown",
        },
        "paper_must_cover_pen_bounds_mm": bounds,
        "nozzle_bounds_mm": nozzle_bounds,
        "draw_speed_mm_s": 10,
        "travel_speed_mm_s": 20,
        "z_speed_mm_s": 2,
        "lift_above_current_contact_mm": 3,
        "finish_above_current_contact_mm": 5,
        "files": {label: report for label, _, _, report in payload},
        "warning": "Start EVERY run from the same light paper contact. No homing/start/end macros may be added. Do not replay from the raised finishing height.",
    }
    (out / "settings-and-validation.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
