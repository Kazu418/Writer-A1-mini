"""SVG paths flattened after transformation, in physical millimetres."""

import math
import re
from fontTools.pens.basePen import BasePen
from fontTools.svgLib.path import parse_path
from .model import PlotNoteError

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def point(m, p):
    a, b, c, d, e, f = m
    result = (a * p[0] + c * p[1] + e, b * p[0] + d * p[1] + f)
    if not all(math.isfinite(v) and abs(v) <= 1e6 for v in result):
        raise PlotNoteError("Non-finite or excessively large geometry coordinate")
    return result


def compose(a, b):
    aa, ab, ac, ad, ae, af = a
    ba, bb, bc, bd, be, bf = b
    return (
        aa * ba + ac * bb,
        ab * ba + ad * bb,
        aa * bc + ac * bd,
        ab * bc + ad * bd,
        aa * be + ac * bf + ae,
        ab * be + ad * bf + af,
    )


def numbers(s):
    pattern = r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?"
    if re.sub(pattern, "", s).strip(" ,\t\r\n"):
        raise PlotNoteError(f"Invalid numeric list: {s}")
    result = [float(n) for n in re.findall(pattern, s)]
    if not all(math.isfinite(v) for v in result):
        raise PlotNoteError("Non-finite numeric list")
    return result


def transform(s):
    m = IDENTITY
    remainder = re.sub(r"([a-zA-Z]+)\s*\(([^)]*)\)", "", s)
    if remainder.strip(" ,\t\n"):
        raise PlotNoteError(f"Invalid transform: {s}")
    for name, raw in re.findall(r"([a-zA-Z]+)\s*\(([^)]*)\)", s):
        v = numbers(raw)
        if name == "matrix" and len(v) == 6:
            t = tuple(v)
        elif name == "translate" and len(v) in (1, 2):
            t = (1, 0, 0, 1, v[0], v[1] if len(v) == 2 else 0)
        elif name == "scale" and len(v) in (1, 2):
            t = (v[0], 0, 0, v[-1], 0, 0)
        elif name == "rotate" and len(v) in (1, 3):
            a = math.radians(v[0])
            c, sn = math.cos(a), math.sin(a)
            t = (c, sn, -sn, c, 0, 0)
            if len(v) == 3:
                t = compose(
                    compose((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2])
                )
        elif name in ("skewX", "skewY") and len(v) == 1:
            k = math.tan(math.radians(v[0]))
            t = (1, 0, k, 1, 0, 0) if name == "skewX" else (1, k, 0, 1, 0, 0)
        else:
            raise PlotNoteError(f"Unsupported transform: {name}({raw})")
        m = compose(m, t)
    if not all(math.isfinite(x) for x in m):
        raise PlotNoteError("Non-finite transform")
    return m


def _distance_line(p, a, b):
    length = math.dist(a, b)
    return (
        abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1])) / length
        if length
        else math.dist(p, a)
    )


def collinear(points):
    if len(points) < 3:
        return True
    a = points[0]
    b = next((p for p in points[1:] if math.dist(a, p) > 1e-9), a)
    return all(_distance_line(p, a, b) < 1e-9 for p in points)


class FlattenPen(BasePen):
    def __init__(self, matrix=IDENTITY, tolerance=0.025):
        super().__init__(None)
        if not math.isfinite(tolerance) or not 0.001 <= tolerance <= 0.25:
            raise PlotNoteError("Curve tolerance must be between 0.001 and 0.25 mm")
        self.matrix, self.tolerance = matrix, tolerance
        self.paths, self.current = [], []

    def _finish(self):
        if len(self.current) > 1:
            self.paths.append(self.current)
        self.current = []

    def _moveTo(self, p):
        self._finish()
        self.current = [point(self.matrix, p)]

    def _lineTo(self, p):
        p = point(self.matrix, p)
        if self.current and p != self.current[-1]:
            self.current.append(p)

    def _curveToOne(self, p1, p2, p3):
        pts = [self.current[-1]] + [point(self.matrix, p) for p in (p1, p2, p3)]

        def subdivide(ps, depth=0):
            if len(self.current) > 200_000:
                raise PlotNoteError("Curve complexity limit exceeded")
            if depth >= 24 or (
                max(_distance_line(p, ps[0], ps[-1]) for p in ps[1:3]) <= self.tolerance
                and sum(math.dist(a, b) for a, b in zip(ps, ps[1:]))
                - math.dist(ps[0], ps[-1])
                <= self.tolerance
            ):
                self.current.append(ps[-1])
                return
            a, b, c, d = ps
            mid = lambda x, y: ((x[0] + y[0]) / 2, (x[1] + y[1]) / 2)
            ab, bc, cd = mid(a, b), mid(b, c), mid(c, d)
            abc, bcd = mid(ab, bc), mid(bc, cd)
            center = mid(abc, bcd)
            subdivide([a, ab, abc, center], depth + 1)
            subdivide([center, bcd, cd, d], depth + 1)

        subdivide(pts)

    def _closePath(self):
        if self.current and self.current[-1] != self.current[0]:
            self.current.append(self.current[0])
        self._finish()

    def _endPath(self):
        self._finish()


def flatten(d, matrix=IDENTITY, tolerance=0.025):
    if not isinstance(d, str) or len(d) > 5_000_000:
        raise PlotNoteError("Invalid or oversized path")
    pen = FlattenPen(matrix, tolerance)
    try:
        parse_path(d, pen)
        pen._finish()
    except (ValueError, IndexError, AssertionError, TypeError) as e:
        raise PlotNoteError(f"Invalid SVG path: {e}") from e
    if sum(map(len, pen.paths)) > 2_000_000:
        raise PlotNoteError("Path complexity limit exceeded")
    return pen.paths


def clip_polyline(ps, rect):
    """Liang-Barsky clipping; returns ordered disconnected visible portions."""
    out, active = [], []
    xmin, ymin, xmax, ymax = rect
    for a, b in zip(ps, ps[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        lo, hi = 0.0, 1.0
        for p, q in zip(
            (-dx, dx, -dy, dy), (a[0] - xmin, xmax - a[0], a[1] - ymin, ymax - a[1])
        ):
            if abs(p) < 1e-14:
                if q < 0:
                    lo, hi = 1.0, 0.0
                    break
            elif p < 0:
                lo = max(lo, q / p)
            else:
                hi = min(hi, q / p)
        if lo <= hi:
            aa = (a[0] + lo * dx, a[1] + lo * dy)
            bb = (a[0] + hi * dx, a[1] + hi * dy)
            if active and math.dist(active[-1], aa) > 1e-8:
                if len(active) > 1:
                    out.append(active)
                active = []
            if not active:
                active = [aa]
            if math.dist(aa, bb) > 1e-10:
                active.append(bb)
        elif active:
            if len(active) > 1:
                out.append(active)
            active = []
    if len(active) > 1:
        out.append(active)
    return out
