from dataclasses import dataclass, field
import math

Point = tuple[float, float]


class PlotNoteError(ValueError):
    """Actionable input or safety failure."""


@dataclass
class Stroke:
    points: list[Point]
    source: str = "vector"


@dataclass
class Page:
    width: float
    height: float
    strokes: list[Stroke] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def validate(self):
        if not all(
            math.isfinite(x) and 0 < x <= 180 for x in (self.width, self.height)
        ):
            raise PlotNoteError(
                f"Page size {self.width:g} x {self.height:g} mm must fit 180 x 180 mm; automatic scaling is disabled."
            )
        for i, s in enumerate(self.strokes):
            if len(s.points) < 2:
                raise PlotNoteError(f"Stroke {i + 1} has fewer than two points")
            for x, y in s.points:
                if not (math.isfinite(x) and math.isfinite(y)):
                    raise PlotNoteError(f"Stroke {i + 1}: non-finite coordinate")
                if not (
                    -0.001 <= x <= self.width + 0.001
                    and -0.001 <= y <= self.height + 0.001
                ):
                    raise PlotNoteError(
                        f"Stroke {i + 1}: ({x:.3f}, {y:.3f}) mm outside page {self.width:g} x {self.height:g}"
                    )
        if not self.strokes:
            raise PlotNoteError("Page has no drawable strokes")

    def summary(self):
        ink = sum(
            math.dist(a, b)
            for s in self.strokes
            for a, b in zip(s.points, s.points[1:])
        )
        travel = sum(
            math.dist(a.points[-1], b.points[0])
            for a, b in zip(self.strokes, self.strokes[1:])
        )
        return {
            "width_mm": self.width,
            "height_mm": self.height,
            "strokes": len(self.strokes),
            "points": sum(len(s.points) for s in self.strokes),
            "ink_mm": round(ink, 3),
            "travel_mm": round(travel, 3),
            "warnings": self.warnings,
        }
