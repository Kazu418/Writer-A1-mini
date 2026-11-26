"""Seeded whole-glyph variation; ordered centerlines remain the execution data."""

from dataclasses import dataclass
import math
import random

from .fonts import render_glyph
from .model import Page, Stroke, PlotNoteError


@dataclass
class TextRun:
    paths: list
    width: float
    top: float
    bottom: float
    characters: list


def text_run(text, size=2.5, *, seed=20261125, pen_width=.25):
    """Vary each glyph coherently, retaining every stroke's order/direction.

    No independent point noise: curves stay smooth. Bounding boxes include the
    changed slant/rotation, so narrower spacing never overlaps adjacent ink.
    """
    if not (math.isfinite(size) and .5 <= size <= 20):
        raise PlotNoteError('Handwriting size must be 0.5..20 mm')
    if not (math.isfinite(pen_width) and .05 <= pen_width <= 2):
        raise PlotNoteError('Invalid handwriting pen width')
    rng = random.Random(seed)
    paths = []
    characters = []
    right = None
    cursor = 0.0
    for char in text:
        if char == '\n':
            raise PlotNoteError('Use paragraph() for multiline text')
        if char.isspace():
            cursor = (right if right is not None else cursor) + size * .38
            right = cursor
            continue
        width = size * (.56 if ord(char) < 128 else .72 if 'Α' <= char <= 'ω' else 1)
        sx, sy = rng.uniform(.96, 1.04), rng.uniform(.98, 1.02)
        angle = math.radians(rng.uniform(-1.5, 1.5))
        slant = rng.uniform(.015, .055)
        dy = rng.uniform(-.07, .07) * size / 2.5
        co, si = math.cos(angle), math.sin(angle)
        glyph = render_glyph(char, (width, 0, 0, size, 0, 0))
        changed = []
        for stroke in glyph:
            transformed = []
            for x, y in stroke:
                # Rotate/shear around the glyph center, not the page origin.
                u = (x - width / 2) * sx + slant * (size / 2 - y)
                v = (y - size / 2) * sy
                transformed.append((co*u - si*v + width/2,
                                    si*u + co*v + size/2 + dy))
            changed.append(transformed)
        points = [p for stroke in changed for p in stroke]
        left = min(x for x, y in points)
        glyph_right = max(x for x, y in points)
        gap = pen_width + rng.uniform(.04, .16)
        origin = max(0.0, -left) if right is None else right + gap - left
        placed = [[(x + origin, y) for x, y in stroke] for stroke in changed]
        paths.extend(placed)
        right = origin + glyph_right
        characters.append({'char': char, 'left': origin + left, 'right': right,
                           'top': min(y for x, y in points),
                           'bottom': max(y for x, y in points),
                           'stroke_count': len(glyph)})
        cursor = right
    points = [p for stroke in paths for p in stroke]
    return TextRun(paths, cursor + pen_width/2 if points else cursor,
                   min((y for x, y in points), default=0),
                   max((y for x, y in points), default=0), characters)


def paragraph(text, *, width=50, height=35, size=2.5, line_pitch=3.1,
              margin=2, seed=20261125, pen_width=.25):
    """Wrap seeded text and vary row pitch while checking actual ink clearance."""
    if not text or not all(math.isfinite(v) for v in (width, height, line_pitch, margin)):
        raise PlotNoteError('Invalid handwriting paragraph dimensions')
    if margin < pen_width/2 or width <= margin*2 or height <= margin*2 or line_pitch < size:
        raise PlotNoteError('Handwriting margins/line pitch are too small')
    rng = random.Random(seed)
    page = Page(width, height)
    rows = []
    available = width - 2*margin
    pending = text.split('\n')
    top = margin
    previous_bottom = None
    for segment in pending:
        remaining = segment
        if not remaining:
            top += line_pitch
            continue
        while remaining:
            row_seed = rng.randrange(2**63)
            count = 0
            while count < len(remaining):
                candidate = text_run(remaining[:count+1], size, seed=row_seed, pen_width=pen_width)
                if candidate.width > available:
                    break
                count += 1
            if not count:
                raise PlotNoteError('A handwriting glyph is wider than the available line')
            if count < len(remaining) and remaining[count] in '、。）」』】':
                count -= 1
                if not count:
                    raise PlotNoteError('Line too narrow for closing punctuation')
            value, remaining = remaining[:count], remaining[count:]
            run = text_run(value, size, seed=row_seed, pen_width=pen_width)
            # Small row drift, plus a strict ink-to-ink clearance check.
            slope = rng.uniform(-.002, .002)
            paths = [[(x+margin, y+slope*x) for x, y in s] for s in run.paths]
            lo = min(y for s in paths for x, y in s)
            hi = max(y for s in paths for x, y in s)
            top = max(top, margin-lo)
            if previous_bottom is not None:
                top = max(top, previous_bottom + pen_width + .20 - lo)
            if top + hi + pen_width/2 > height-margin:
                raise PlotNoteError('Handwriting paragraph overflows the page; enlarge it')
            page.strokes.extend(Stroke([(x, y+top) for x, y in s], 'handwriting:'+value) for s in paths)
            rows.append({'text': value, 'origin_y': top, 'ink_top': top+lo,
                         'ink_bottom': top+hi, 'seed': row_seed})
            previous_bottom = top+hi
            top += line_pitch + rng.uniform(-.12, .12)
    page.validate()
    return page, {'seed': seed, 'size_mm': size, 'nominal_line_pitch_mm': line_pitch,
                  'pen_width_mm': pen_width, 'rows': rows,
                  'stroke_order_preserved': True}
