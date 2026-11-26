"""Extract PDF Unicode text and visible vector geometry without rasterisation."""

import math
from collections import Counter
import xml.etree.ElementTree as ET
import pymupdf as fitz
from .fonts import render_glyph
from .geometry import collinear
from .model import Page, Stroke, PlotNoteError
from .svg_input import parse_svg

MM = 25.4 / 72


def load_pdf(path):
    try:
        doc = fitz.open(path)
    except (RuntimeError, ValueError) as e:
        raise PlotNoteError(f"Cannot open PDF: {e}") from e
    if not doc.is_pdf or doc.needs_pass:
        doc.close()
        raise PlotNoteError("Input must be an unencrypted PDF")
    if len(doc) > 200:
        doc.close()
        raise PlotNoteError("PDF exceeds 200-page limit; split into smaller jobs")
    pages = []
    errors = []
    with doc:
        for index, p in enumerate(doc):
            label = f"Page {index + 1}"
            w, h = p.rect.width * MM, p.rect.height * MM
            page = Page(w, h)
            if w > 180.001 or h > 180.001:
                errors.append(
                    f"{label}: {w:.3f} x {h:.3f} mm exceeds 180 x 180 mm; regenerate the PDF at the intended physical size"
                )
            if list(p.annots() or []) or list(p.widgets() or []):
                errors.append(
                    f"{label}: annotations/form fields are unsupported; bake their intended visible content into ordinary text/vector graphics"
                )
            if p.get_image_info():
                errors.append(
                    f"{label}: raster image found; export diagrams as vectors and remove images"
                )
            if any(entry[0] == "fill-shade" for entry in p.get_bboxlog()):
                errors.append(
                    f"{label}: gradient/shading found; use plain unfilled paths"
                )
            for drawing in p.get_drawings():
                if (
                    drawing.get("type") in ("f", "fs")
                    and drawing.get("fill") is not None
                    and drawing.get("fill_opacity", 1) > 0
                ):
                    color = drawing["fill"]
                    rect = drawing["rect"]
                    white = all(c > 0.999 for c in color)
                    background = (
                        white
                        and rect.contains(p.cropbox)
                        and drawing.get("seqno", 0) == 0
                    )
                    items = drawing.get("items", [])
                    zero_area = all(item[0] == "l" for item in items) and collinear(
                        [tuple(p) for item in items for p in item[1:]]
                    )
                    if not background and not zero_area:
                        errors.append(
                            f"{label}: Filled vector at ({rect.x0 * MM:.2f}, {rect.y0 * MM:.2f}) mm; use unfilled strokes"
                        )
            try:
                source_svg = p.get_svg_image(text_as_path=False)

                # TextTrace does not expose text clipping; rejecting it prevents hidden text from reappearing.
                def check_text_clip(el, clipped=False):
                    clipped = (
                        clipped
                        or el.get("clip-path", "none") != "none"
                        or "clip-path:" in el.get("style", "")
                    )
                    if el.tag.rsplit("}", 1)[-1] == "text" and clipped:
                        errors.append(
                            f"{label}: clipped text is unsupported; remove text clipping in the source PDF"
                        )
                    for child in el:
                        check_text_clip(child, clipped)

                svg_root = ET.fromstring(source_svg)
                check_text_clip(svg_root)
                visible = "".join(
                    "".join(el.itertext())
                    for el in svg_root.iter()
                    if el.tag.rsplit("}", 1)[-1] == "text"
                    and float(el.get("opacity", 1)) > 0
                    and (
                        float(el.get("fill-opacity", 1)) > 0
                        or el.get("stroke", "none") != "none"
                    )
                )
                traced = "".join(
                    chr(ch[0])
                    for span in p.get_texttrace()
                    if span["type"] != 3 and span.get("opacity", 1) > 0
                    for ch in span["chars"]
                    if 0 <= ch[0] <= 0x10FFFF
                )
                if Counter(c for c in visible if not c.isspace()) != Counter(
                    c for c in traced if not c.isspace()
                ):
                    errors.append(
                        f"{label}: PDF text visibility/Unicode extraction mismatch; remove clipped or multiply-painted text"
                    )
                vectors = parse_svg(source_svg, pdf_points=True, ignore_text=True)
                page.strokes.extend(vectors.strokes)
            except PlotNoteError as e:
                errors.append(f"{label}: {e}")
            # TextTrace carries Unicode, actual origins, writing direction and painted/invisible status.
            for span in p.get_texttrace():
                if span["type"] == 3 or span.get("opacity", 1) == 0:
                    continue
                if span.get("opacity", 1) != 1:
                    errors.append(f"{label}: transparent text is unsupported")
                    continue
                if all(c >= 0.999 for c in span.get("color", (0, 0, 0))):
                    errors.append(
                        f"{label}: white text is unsupported; remove hidden/knockout text"
                    )
                    continue
                if span.get("wmode", 0) != 0:
                    errors.append(
                        f"{label}: vertical writing is unsupported; use horizontal text"
                    )
                    continue
                dx, dy = span["dir"]
                size = span["size"]
                if size <= 0 or not math.isfinite(size):
                    errors.append(f"{label}: invalid text size")
                    continue
                if size * MM < 2:
                    page.warnings.append(
                        f"Text size {size * MM:.2f} mm is small; use a fine pen and inspect the preview"
                    )
                for ci, entry in enumerate(span["chars"]):
                    cp, gid, origin, bbox = entry
                    if not 0 <= cp <= 0x10FFFF:
                        errors.append(f"{label}: invalid Unicode {cp}")
                        continue
                    char = chr(cp)
                    if char.isspace():
                        continue
                    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    # MuPDF texttrace char boxes use em-height = font size, independently of font ascenders.
                    advance = (
                        (bw - size * abs(dy)) / abs(dx)
                        if abs(dx) >= abs(dy)
                        else (bh - size * abs(dx)) / abs(dy)
                    )
                    if advance <= 0 or not math.isfinite(advance):
                        errors.append(
                            f"{label}: invalid advance for {char!r} at {origin}"
                        )
                        continue
                    # Transform local glyph em to original PDF baseline and text direction.
                    matrix = (
                        advance * dx * MM,
                        advance * dy * MM,
                        -size * dy * MM,
                        size * dx * MM,
                        (origin[0] + 0.8 * size * dy) * MM,
                        (origin[1] - 0.8 * size * dx) * MM,
                    )
                    try:
                        paths = render_glyph(char, matrix)
                    except PlotNoteError as e:
                        errors.append(
                            f"{label}, text ({origin[0] * MM:.2f}, {origin[1] * MM:.2f}) mm: {e}"
                        )
                        continue
                    for ps in paths:
                        if p.rotation:
                            ps = [
                                tuple(fitz.Point(x / MM, y / MM) * p.rotation_matrix)
                                for x, y in ps
                            ]
                            ps = [(x * MM, y * MM) for x, y in ps]
                        # Reject truncation of substituted glyphs; do not silently crop a character.
                        if any(
                            not (-0.001 <= x <= w + 0.001 and -0.001 <= y <= h + 0.001)
                            for x, y in ps
                        ):
                            errors.append(
                                f"{label}: stroke glyph {char!r} extends outside page at {origin}"
                            )
                            continue
                        page.strokes.append(
                            Stroke(ps, f"text:{char}:char-{span['seqno']}-{ci}")
                        )
            try:
                page.validate()
            except PlotNoteError as e:
                errors.append(f"{label}: {e}")
            page.warnings = list(dict.fromkeys(page.warnings))
            pages.append(page)
    if errors:
        raise PlotNoteError(
            "PDF preflight failed:\n" + "\n".join(dict.fromkeys(errors))
        )
    return pages
