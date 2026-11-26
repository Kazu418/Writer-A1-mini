"""Strict physical-size SVG importer with transforms and rectangular clipping."""

from pathlib import Path
import math
import re
import xml.etree.ElementTree as ET
from .geometry import compose, transform, numbers, flatten, clip_polyline, collinear
from .model import Page, Stroke, PlotNoteError


def tag(el):
    return el.tag.rsplit("}", 1)[-1]


def length(value):
    m = re.fullmatch(
        r"\s*([-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?)\s*(mm|cm|in|pt|pc|px)?\s*",
        value or "",
    )
    if not m:
        raise PlotNoteError(f"Expected absolute SVG length, got {value!r}")
    return (
        float(m[1])
        * {
            "mm": 1,
            "cm": 10,
            "in": 25.4,
            "pt": 25.4 / 72,
            "pc": 25.4 / 6,
            "px": 25.4 / 96,
            None: 25.4 / 96,
        }[m[2]]
    )


def attrs(el, inherited):
    a = dict(inherited)
    a.update(el.attrib)
    for entry in el.get("style", "").split(";"):
        if ":" in entry:
            k, v = entry.split(":", 1)
            a[k.strip()] = v.strip()
    return a


def shape_path(el):
    a = el.attrib
    t = tag(el)
    n = lambda k, d=0: float(a.get(k, d))
    if t == "path":
        return a.get("d", "")
    if t == "line":
        return f"M{n('x1')} {n('y1')}L{n('x2')} {n('y2')}"
    if t in ("polyline", "polygon"):
        ps = numbers(a.get("points", ""))
        if len(ps) % 2:
            raise PlotNoteError("Odd SVG points coordinate count")
        return (
            ("M" + " ".join(map(str, ps)) + ("Z" if t == "polygon" else ""))
            if ps
            else ""
        )
    if t == "rect":
        x, y, w, h = n("x"), n("y"), n("width"), n("height")
        if w < 0 or h < 0:
            raise PlotNoteError("Negative rectangle dimensions")
        rx = min(max(n("rx", a.get("ry", 0)), 0), w / 2)
        ry = min(max(n("ry", a.get("rx", 0)), 0), h / 2)
        if rx and ry:
            return f"M{x + rx} {y}H{x + w - rx}A{rx} {ry} 0 0 1 {x + w} {y + ry}V{y + h - ry}A{rx} {ry} 0 0 1 {x + w - rx} {y + h}H{x + rx}A{rx} {ry} 0 0 1 {x} {y + h - ry}V{y + ry}A{rx} {ry} 0 0 1 {x + rx} {y}Z"
        return f"M{x} {y}H{x + w}V{y + h}H{x}Z"
    if t in ("circle", "ellipse"):
        cx, cy = n("cx"), n("cy")
        rx = n("r") if t == "circle" else n("rx")
        ry = n("r") if t == "circle" else n("ry")
        if rx <= 0 or ry <= 0:
            return ""
        return f"M{cx - rx} {cy}A{rx} {ry} 0 1 0 {cx + rx} {cy}A{rx} {ry} 0 1 0 {cx - rx} {cy}Z"
    raise PlotNoteError(f"Unsupported SVG element <{t}>")


def parse_svg(source, *, pdf_points=False, ignore_text=False, tolerance=0.025):
    if isinstance(source, Path):
        source = source.read_text()
    if (
        len(source) > 30_000_000
        or "<!ENTITY" in source.upper()
        or "<!DOCTYPE" in source.upper()
    ):
        raise PlotNoteError("SVG entities/DOCTYPE or oversized input are not supported")
    try:
        root = ET.fromstring(source)
    except ET.ParseError as e:
        raise PlotNoteError(f"Invalid SVG XML: {e}") from e
    if tag(root) != "svg":
        raise PlotNoteError("Expected SVG root")
    stack = [(root, 0)]
    while stack:
        element, depth = stack.pop()
        if depth > 128:
            raise PlotNoteError("SVG nesting exceeds 128 groups")
        if tag(element) in ("script", "style") or any(
            k.lower().startswith("on") for k in element.attrib
        ):
            raise PlotNoteError(
                "SVG scripts, event handlers and stylesheet elements are unsupported; use inline stroke attributes"
            )
        stack.extend((child, depth + 1) for child in element)
    width = length(root.get("width", ""))
    height = length(root.get("height", ""))
    if pdf_points:
        width = float(root.get("width")) * 25.4 / 72
        height = float(root.get("height")) * 25.4 / 72
    if not all(math.isfinite(v) and 0 < v <= 180.001 for v in (width, height)):
        raise PlotNoteError(f"SVG page {width:g} x {height:g} mm must fit 180 x 180 mm")
    view = numbers(root.get("viewBox", f"0 0 {width * 96 / 25.4} {height * 96 / 25.4}"))
    if (
        len(view) != 4
        or not all(math.isfinite(v) for v in view)
        or view[2] <= 0
        or view[3] <= 0
    ):
        raise PlotNoteError("Invalid SVG viewBox")
    sx, sy = width / view[2], height / view[3]
    aspect = root.get("preserveAspectRatio", "xMidYMid meet").split()
    if aspect[0] != "none":
        if aspect[0] not in (
            "xMinYMin",
            "xMidYMin",
            "xMaxYMin",
            "xMinYMid",
            "xMidYMid",
            "xMaxYMid",
            "xMinYMax",
            "xMidYMax",
            "xMaxYMax",
        ):
            raise PlotNoteError("Unsupported preserveAspectRatio")
        s = max(sx, sy) if len(aspect) > 1 and aspect[1] == "slice" else min(sx, sy)
        ox = (width - view[2] * s) * (
            0 if "xMin" in aspect[0] else 1 if "xMax" in aspect[0] else 0.5
        )
        oy = (height - view[3] * s) * (
            0 if "YMin" in aspect[0] else 1 if "YMax" in aspect[0] else 0.5
        )
        sx = sy = s
    else:
        ox = oy = 0
    matrix = (sx, 0, 0, sy, ox - view[0] * sx, oy - view[1] * sy)
    page = Page(width, height)
    ids = {el.get("id"): el for el in root.iter() if el.get("id")}
    shapes = {"path", "line", "rect", "circle", "ellipse", "polyline", "polygon"}
    inherited_keys = {
        "fill",
        "stroke",
        "stroke-width",
        "fill-opacity",
        "stroke-opacity",
        "visibility",
        "display",
        "stroke-dasharray",
    }

    def clip_rect(value, m):
        match = re.fullmatch(r"url\(#([^)]*)\)", value)
        if not match or match[1] not in ids:
            raise PlotNoteError(f"Invalid clip-path {value}")
        clip = ids[match[1]]
        if (
            clip.get("clipPathUnits", "userSpaceOnUse") != "userSpaceOnUse"
            or len(clip) != 1
        ):
            raise PlotNoteError(
                "Only single rectangular userSpaceOnUse clipping paths are supported"
            )
        el = clip[0]
        cm = compose(
            compose(m, transform(clip.get("transform", ""))),
            transform(el.get("transform", "")),
        )
        ps = flatten(shape_path(el), cm, tolerance)
        if len(ps) != 1 or len(ps[0]) != 5 or ps[0][0] != ps[0][-1]:
            raise PlotNoteError("Only rectangular clipping paths are supported")
        xs = [p[0] for p in ps[0]]
        ys = [p[1] for p in ps[0]]
        box = min(xs), min(ys), max(xs), max(ys)
        if any(
            abs(a[0] - b[0]) > 1e-7 and abs(a[1] - b[1]) > 1e-7
            for a, b in zip(ps[0], ps[0][1:])
        ):
            raise PlotNoteError(
                "Rotated clipping rectangle is not supported; flatten clipping in source"
            )
        return box

    def visit(el, m, style, clips, stack=()):
        t = tag(el)
        if t in ("defs", "metadata", "title", "desc", "clipPath"):
            return
        if t in ("text", "tspan") and ignore_text:
            return
        a = attrs(el, style)
        if a.get("display") == "none" or a.get("visibility") in ("hidden", "collapse"):
            return
        if float(a.get("opacity", "1")) == 0:
            return
        for effect in ("filter", "mask", "marker-start", "marker-mid", "marker-end"):
            if a.get(effect, "none") != "none":
                raise PlotNoteError(f"Unsupported SVG {effect} on <{t}>")
        if float(a.get("opacity", "1")) != 1:
            raise PlotNoteError("SVG transparency is not supported")
        m = compose(m, transform(el.get("transform", "")))
        clips = list(clips)
        if a.get("clip-path", "none") != "none":
            clips.append(clip_rect(a["clip-path"], m))
        if t == "use":
            href = el.get("href", el.get("{http://www.w3.org/1999/xlink}href", ""))
            if not href.startswith("#") or href[1:] not in ids:
                raise PlotNoteError("External/missing SVG use reference")
            if href in stack or len(stack) > 20:
                raise PlotNoteError("Cyclic SVG use reference")
            visit(
                ids[href[1:]],
                compose(m, (1, 0, 0, 1, float(el.get("x", 0)), float(el.get("y", 0)))),
                {k: v for k, v in a.items() if k in inherited_keys},
                clips,
                stack + (href,),
            )
            return
        if t in ("svg", "g", "a"):
            if t == "svg" and el is not root:
                raise PlotNoteError(
                    "Nested SVG viewport is unsupported; flatten source"
                )
            for child in el:
                visit(
                    child,
                    m,
                    {k: v for k, v in a.items() if k in inherited_keys},
                    clips,
                    stack,
                )
            return
        if t not in shapes:
            raise PlotNoteError(
                f"Unsupported SVG element <{t}>; use vector strokes and Unicode PDF text"
            )
        paths = flatten(shape_path(el), m, tolerance)
        fill = a.get("fill", "black")
        stroke = a.get("stroke", "none")
        # Some PDF writers paint and stroke a two-point tick path. Its fill has no area.
        if paths and all(collinear(ps) for ps in paths):
            fill = "none"
        if (
            fill not in ("none", "transparent")
            and float(a.get("fill-opacity", "1")) != 0
        ):
            if (
                fill.lower() in ("white", "#fff", "#ffffff", "rgb(255,255,255)")
                and not page.strokes
            ):
                # Only a whole-page white background can safely disappear.
                flat = [p for ps in paths for p in ps]
                if (
                    flat
                    and min(p[0] for p in flat) <= 0
                    and min(p[1] for p in flat) <= 0
                    and max(p[0] for p in flat) >= width
                    and max(p[1] for p in flat) >= height
                ):
                    if stroke == "none":
                        return
                else:
                    raise PlotNoteError(
                        "White knockout/fill is unsupported; use an unfilled diagram"
                    )
            elif t != "line":
                raise PlotNoteError(
                    f'Filled <{t}> cannot be reproduced by centerlines; use fill="none" and explicit strokes'
                )
        if stroke == "none" or float(a.get("stroke-opacity", "1")) == 0:
            return
        if float(a.get("stroke-opacity", "1")) != 1:
            raise PlotNoteError("Transparent SVG stroke is unsupported")
        if a.get("stroke-dasharray", "none") not in ("none", ""):
            raise PlotNoteError(
                "Dashed strokes must be expanded into separate vector segments"
            )
        for ps in paths:
            portions = [ps]
            for box in clips:
                portions = [part for p in portions for part in clip_polyline(p, box)]
            page.strokes.extend(Stroke(p) for p in portions)

    # A standalone SVG must fit its declared page; do not silently crop it.
    visit(root, matrix, {}, [(0, 0, width, height)] if pdf_points else [])
    return page
