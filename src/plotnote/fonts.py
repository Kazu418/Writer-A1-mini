"""Centerline glyphs: KanjiVG stroke order and Hershey Roman/Greek."""

from functools import lru_cache
from contextlib import contextmanager
from contextvars import ContextVar
from importlib.resources import files
import json
import unicodedata
from .geometry import flatten
from .model import PlotNoteError


_personal = ContextVar('plotnote_personal_font', default=None)


_METRIC_RANK = {'source_line_reference': 0, 'estimated_source_line': 1}


@contextmanager
def use_personal_font(library, standard_fallback=''):
    """Scoped personal-only rendering.

    Missing glyphs raise, EXCEPT characters the caller explicitly lists in
    `standard_fallback`; only those are drawn with the standard stroke font.
    """
    if library.get('format') != 'plotnote-personal-centerlines-v1' or library.get('label_status') != 'reviewed':
        raise PlotNoteError('Expected a reviewed personal centerline library')
    fallback = frozenset(standard_fallback)
    overlap = fallback & set(library['glyphs'])
    if overlap:
        raise PlotNoteError('Fallback characters already exist in the personal font: ' + ''.join(sorted(overlap)))
    # Prefer exemplars whose size/line position is measured over bounding-cell guesses.
    glyphs = {c: sorted(v, key=lambda s: _METRIC_RANK.get(s.get('metrics_status'), 2))
              for c, v in library['glyphs'].items()}
    token = _personal.set((glyphs, fallback, {}))
    try:
        yield
    finally:
        _personal.reset(token)


@contextmanager
def use_standard_font():
    """Temporarily use the bundled standard centerline glyphs, even inside a personal-font context."""
    token = _personal.set(None)
    try:
        yield
    finally:
        _personal.reset(token)


def personal_font_active():
    return _personal.get() is not None


def _bbox(paths):
    xs = [x for p in paths for x, _ in p]
    ys = [y for p in paths for _, y in p]
    return min(xs), min(ys), max(xs), max(ys)


def fit_to_standard(paths, standard):
    """Re-size/re-position handwriting to the typographic box of the standard glyph.

    Uniform scale only, so the writer's proportions, slant and stroke order are
    unchanged; the glyph is centred on the standard glyph's box. Squarish glyphs
    are matched by area, flat ones by width, tall ones by height, and the result
    never exceeds the standard box by more than 15%.
    """
    px0, py0, px1, py1 = _bbox(paths)
    sx0, sy0, sx1, sy1 = _bbox(standard)
    pw, ph = max(px1 - px0, 1e-6), max(py1 - py0, 1e-6)
    sw, sh = sx1 - sx0, sy1 - sy0
    if max(sw, sh) < 0.1:                        # dots and tiny marks: keep them visible
        scale = 0.1 / max(pw, ph)
    else:
        ratio = (sw + 1e-9) / (sh + 1e-9)
        if 0.6 < ratio < 1.67:
            scale = (max(sw * sh, 1e-9) / (pw * ph)) ** 0.5
        elif sw > sh:
            scale = sw / pw
        else:
            scale = sh / ph
        if sw > 0.02:
            scale = min(scale, 1.15 * sw / pw)
        if sh > 0.02:
            scale = min(scale, 1.15 * sh / ph)
    cpx, cpy = (px0 + px1) / 2, (py0 + py1) / 2
    csx, csy = (sx0 + sx1) / 2, (sy0 + sy1) / 2
    return [[(csx + (x - cpx) * scale, csy + (y - cpy) * scale) for x, y in p] for p in paths]


def _personal_glyph(char, glyphs, cache):
    if char in cache:
        return cache[char]
    variants = glyphs[char]
    try:
        standard = _standard_glyph_paths(char)
    except PlotNoteError:
        standard = None
    if not standard:
        cache[char] = variants[0]['paths']          # no typographic reference: use as stored
        return cache[char]
    if len(variants) > 1:                            # choose the exemplar closest to the standard shape
        from .personal_rank import score_paths
        best = min(variants, key=lambda s: score_paths(s['paths'], char)['score'])
    else:
        best = variants[0]
    cache[char] = fit_to_standard(best['paths'], standard)
    return cache[char]


def glyph_paths(char):
    personal = _personal.get()
    if personal is not None and not char.isspace():
        glyphs, fallback, cache = personal
        if char in fallback:
            return _standard_glyph_paths(char)
        if char not in glyphs:
            raise PlotNoteError(f'Personal glyph missing: {char!r}')
        return _personal_glyph(char, glyphs, cache)
    return _standard_glyph_paths(char)


@lru_cache
def datasets():
    base = files("plotnote").joinpath("data")
    return (
        json.loads(base.joinpath("kanjivg.json").read_text()),
        json.loads(base.joinpath("hershey.json").read_text()),
    )


# Hand-authored centerlines in a 0..1 em cell. Distinct subpaths are distinct strokes.
SYMBOLS = {
    "−": "M.1 .5H.9",
    "–": "M.1 .5H.9",
    "—": "M0 .5H1",
    "×": "M.15 .15L.85 .85M.85 .15L.15 .85",
    "÷": "M.1 .5H.9M.48 .2H.52M.48 .8H.52",
    "±": "M.15 .35H.85M.5 .05V.65M.15 .85H.85",
    "≤": "M.85 .1L.15 .4L.85 .7M.15 .9H.85",
    "≥": "M.15 .1L.85 .4L.15 .7M.15 .9H.85",
    "≠": "M.1 .35H.9M.1 .65H.9M.7 .1L.3 .9",
    "≈": "M.1 .35Q.3 .1 .5 .35T.9 .35M.1 .7Q.3 .45 .5 .7T.9 .7",
    "∞": "M.5 .5C.1 -.1 -.1 1.1 .5 .5C1.1 -.1 1.1 1.1 .5 .5",
    "∑": "M.9 .05H.1L.55 .5L.1 .95H.9",
    "∏": "M.1 .05H.9M.25 .05V.95M.75 .05V.95",
    "∫": "M.8 .1C.35 -.2 .65 1.2 .2 .9",
    "∂": "M.3 .1C1 -.1 .9 1.1 .3 .9C-.1 .65 .6 .1 .8 .5",
    "√": "M.02 .55L.2 .5L.4 .95L.65 .05H1",
    "∈": "M.85 .1C-.1 -.05 -.1 1.05 .85 .9M.15 .5H.75",
    "∉": "M.85 .1C-.1 -.05 -.1 1.05 .85 .9M.15 .5H.75M.75 .05L.25 .95",
    "∅": "M.5 .1C-.05 .1 -.05 .9 .5 .9C1.05 .9 1.05 .1 .5 .1M.8 0L.2 1",
    "∇": "M.1 .1H.9L.5 .9Z",
    "∀": "M.1 .05L.5 .95L.9 .05M.25 .6H.75",
    "∃": "M.1 .1H.9V.9H.1M.3 .5H.9",
    "∝": "M.9 .2L.35 .8C-.1 1 -.1 0 .35 .2L.9 .8",
    "→": "M.05 .5H.95M.65 .2L.95 .5L.65 .8",
    "←": "M.95 .5H.05M.35 .2L.05 .5L.35 .8",
    "↔": "M.05 .5H.95M.35 .2L.05 .5L.35 .8M.65 .2L.95 .5L.65 .8",
    "⇒": "M.05 .35H.7M.05 .65H.7M.6 .1L.95 .5L.6 .9",
    "⇔": "M.3 .35H.7M.3 .65H.7M.4 .1L.05 .5L.4 .9M.6 .1L.95 .5L.6 .9",
    "↑": "M.5 .95V.05M.2 .35L.5 .05L.8 .35",
    "↓": "M.5 .05V.95M.2 .65L.5 .95L.8 .65",
    "⋅": "M.48 .5H.52",
    "·": "M.48 .5H.52",
    "…": "M.1 .75H.14M.48 .75H.52M.86 .75H.9",
    "°": "M.5 .1C.1 .1 .1 .5 .5 .5C.9 .5 .9 .1 .5 .1",
    "′": "M.6 .1L.4 .4",
    "″": "M.4 .1L.2 .4M.8 .1L.6 .4",
    "ℓ": "M.15 .8C.8 .4 .85 -.2 .45 .15C.2 .5 .2 1 .8 .8",
    "ℏ": "M.2 0V1M.2 .55C.5 .2 .8 .35 .8 .6V1M.05 .2H.5",
    "。": "M.2 .75C0 .75 0 .95 .2 .95C.4 .95 .4 .75 .2 .75",
    "、": "M.1 .7L.3 .95",
    "・": "M.48 .5H.52",
    "ー": "M.1 .5L.9 .48",
    "「": "M.6 .1H.2V.6",
    "」": "M.4 .9H.8V.4",
    "『": "M.7 .05H.15V.65M.7 .2H.3V.65",
    "』": "M.3 .95H.85V.35M.3 .8H.7V.35",
    "【": "M.7 .05H.3V.95H.7M.3 .05Q.65 .5 .3 .95",
    "】": "M.3 .05H.7V.95H.3M.7 .05Q.35 .5 .7 .95",
}
GREEK = dict(zip("ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ", "ABGDEZHQIKLMNXOPRSTUFCYW"))
GREEK.update(dict(zip("αβγδεζηθικλμνξοπρστυφχψω", "abgdezhqiklmnxoprstufcyw")))
GREEK["ς"] = "s"
SUPERSCRIPT = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ", "0123456789+-=()ni"))
SUBSCRIPT = dict(
    zip("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ", "0123456789+-=()aehijklmnoprstuvx")
)


@lru_cache(maxsize=8192)
def _standard_glyph_paths(char):
    """Return paths in em coordinates relative to top-left, with baseline y=0.8."""
    if char.isspace():
        return []
    if char in SUPERSCRIPT or char in SUBSCRIPT:
        base = (SUPERSCRIPT if char in SUPERSCRIPT else SUBSCRIPT)[char]
        dy = 0 if char in SUPERSCRIPT else 0.5
        return [
            [(0.15 + 0.65 * x, dy + 0.65 * y) for x, y in ps]
            for ps in glyph_paths(base)
        ]
    kvg, hershey = datasets()
    # Japanese punctuation and symbols need intentional tiny-dot strokes.
    if char in SYMBOLS:
        return flatten(SYMBOLS[char], tolerance=0.001)
    if char in kvg:
        return [
            p
            for d in kvg[char]
            for p in flatten(d, (1 / 109, 0, 0, 1 / 109, 0, 0), 0.001)
        ]
    normalized = unicodedata.normalize("NFKC", char)
    if len(normalized) == 1 and normalized != char:
        return glyph_paths(normalized)
    decomposed = unicodedata.normalize("NFD", char)
    if len(decomposed) == 2 and decomposed[1] in ("\u3099", "\u309a"):
        paths = glyph_paths(decomposed[0])
        marks = (
            "M.78 .08L.86 .16M.9 .04L.98 .12"
            if decomposed[1] == "\u3099"
            else "M.87 .03C.72 .03 .72 .2 .87 .2C1.02 .2 1.02 .03 .87 .03"
        )
        return paths + flatten(marks, tolerance=0.001)
    font, c = ("greek", GREEK[char]) if char in GREEK else ("futural", char)
    if not 33 <= ord(c) <= 126:
        raise PlotNoteError(
            f"Unsupported glyph {char!r} (U+{ord(char):04X}); use supported Unicode text or explicit centerline geometry"
        )
    data = hershey[font]["chars"][ord(c) - 33]
    # Hershey uses y=22 for baseline and y=1 for capital top; retain relative lowercase height.
    advance = 2 * data["o"]
    return flatten(data["d"], (1 / advance, 0, 0, 1 / 30, 0, 0.1 - 1 / 30), 0.001)


def render_glyph(char, matrix):
    return [
        [
            (
                matrix[0] * x + matrix[2] * y + matrix[4],
                matrix[1] * x + matrix[3] * y + matrix[5],
            )
            for x, y in ps
        ]
        for ps in glyph_paths(char)
    ]
