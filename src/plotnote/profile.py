"""Measured A1 mini setup, with a precisely defined pen/nozzle coordinate convention."""

from dataclasses import dataclass, asdict
import json
import math
from pathlib import Path
from .model import PlotNoteError


@dataclass
class Profile:
    printer: str = "a1-mini"
    calibrated: bool = False
    pen_offset_x: float = 0.0
    pen_offset_y: float = 0.0
    paper_x: float = 10.0
    paper_y: float = 10.0
    paper_width: float = 148.0
    paper_height: float = 148.0
    nozzle_min_x: float = 5.0
    nozzle_max_x: float = 175.0
    nozzle_min_y: float = 5.0
    nozzle_max_y: float = 175.0
    draw_z: float = 5.0
    lift_z: float = 7.0
    safe_z: float = 10.0
    draw_feed: float = 1200.0
    travel_feed: float = 3000.0
    z_feed: float = 300.0
    pen_width: float = 0.3
    calibration_notes: str = ""

    def validate(self, *, require_calibrated=True):
        if self.printer != "a1-mini":
            raise PlotNoteError("Only the a1-mini profile is supported")
        if type(self.calibrated) is not bool:
            raise PlotNoteError("calibrated must be a JSON boolean")
        if require_calibrated and not self.calibrated:
            raise PlotNoteError(
                "Profile is uncalibrated. Follow docs/CALIBRATION.md and enter measured values before G-code export."
            )
        for key, value in asdict(self).items():
            if key in ("printer", "calibrated", "calibration_notes"):
                continue
            if type(value) not in (float, int) or not math.isfinite(value):
                raise PlotNoteError(f"Profile {key} must be a finite number")
        if not (
            0 <= self.nozzle_min_x < self.nozzle_max_x <= 180
            and 0 <= self.nozzle_min_y < self.nozzle_max_y <= 180
        ):
            raise PlotNoteError("Nozzle bounds must be ordered and inside 0..180 mm")
        if not (
            0 <= self.paper_x < 180
            and 0 <= self.paper_y < 180
            and self.paper_width > 0
            and self.paper_height > 0
            and self.paper_x + self.paper_width <= 180
            and self.paper_y + self.paper_height <= 180
        ):
            raise PlotNoteError(
                "Paper rectangle must fit the physical 180 x 180 mm bed"
            )
        if not (
            1 <= self.draw_z < self.lift_z <= self.safe_z <= 30
            and self.lift_z - self.draw_z >= 0.5
        ):
            raise PlotNoteError(
                "Require 1 <= draw_z < lift_z <= safe_z <= 30 mm, and at least 0.5 mm pen clearance"
            )
        if not (
            1 <= self.draw_feed <= 3000
            and 1 <= self.travel_feed <= 6000
            and 1 <= self.z_feed <= 1200
        ):
            raise PlotNoteError(
                "Feed limits: draw 1..3000, travel 1..6000, Z 1..1200 mm/min"
            )
        if not 0.05 <= self.pen_width <= 2:
            raise PlotNoteError("Pen width must be 0.05..2 mm")
        if abs(self.pen_offset_x) > 60 or abs(self.pen_offset_y) > 60:
            raise PlotNoteError(
                "Measured pen offset exceeds 60 mm; check units and sign"
            )
        return self

    @classmethod
    def load(cls, path):
        try:
            data = json.loads(Path(path).read_text())
            p = cls(**data)
        except (OSError, ValueError, TypeError) as e:
            raise PlotNoteError(f"Invalid profile: {e}") from e
        return p.validate(require_calibrated=False)

    def save(self, path):
        self.validate(require_calibrated=False)
        Path(path).write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"
        )

    def machine_point(self, x, y):
        return (
            self.paper_x + x - self.pen_offset_x,
            self.paper_y + self.paper_height - y - self.pen_offset_y,
        )

    def reachable_page_rect(self):
        # Result in page coordinates (top-left origin, Y down).
        xmin = max(0, self.nozzle_min_x + self.pen_offset_x - self.paper_x)
        xmax = min(
            self.paper_width, self.nozzle_max_x + self.pen_offset_x - self.paper_x
        )
        ymin = max(
            0, self.paper_y + self.paper_height - self.nozzle_max_y - self.pen_offset_y
        )
        ymax = min(
            self.paper_height,
            self.paper_y + self.paper_height - self.nozzle_min_y - self.pen_offset_y,
        )
        return (xmin, ymin, xmax, ymax)

    def check_page(self, page):
        self.validate()
        page.validate()
        if (
            abs(page.width - self.paper_width) > 0.01
            or abs(page.height - self.paper_height) > 0.01
        ):
            raise PlotNoteError(
                f"Page {page.width:.3f} x {page.height:.3f} mm must match profile paper {self.paper_width:.3f} x {self.paper_height:.3f} mm. No automatic rotate/scale."
            )
        for i, s in enumerate(page.strokes):
            for px, py in s.points:
                x, y = self.machine_point(px, py)
                if not (
                    self.nozzle_min_x <= x <= self.nozzle_max_x
                    and self.nozzle_min_y <= y <= self.nozzle_max_y
                ):
                    raise PlotNoteError(
                        f"Stroke {i + 1}: compensated nozzle ({x:.3f}, {y:.3f}) mm exceeds calibrated bounds; reachable page rectangle is {self.reachable_page_rect()}"
                    )
                r = self.pen_width / 2
                if not (r <= px <= page.width - r and r <= py <= page.height - r):
                    raise PlotNoteError(
                        f"Stroke {i + 1}: ink width crosses paper edge; add margins"
                    )
