"""Fit a standard handwritten centerline keyword into its existing ink box."""
from .fonts import use_standard_font
from .handwriting import text_run
from .model import PlotNoteError

def fit_standard_keyword(text, size, reference_paths, *, seed=20261125, pen_width=.3):
    points = [point for path in reference_paths for point in path]
    if not points:
        raise PlotNoteError("A keyword needs an existing ink box")
    left, top = min(x for x,y in points), min(y for x,y in points)
    right, bottom = max(x for x,y in points), max(y for x,y in points)
    with use_standard_font():
        run = text_run(text, size, seed=seed, pen_width=pen_width)
    newpoints = [point for path in run.paths for point in path]
    if not newpoints or right <= left or bottom <= top:
        raise PlotNoteError("Keyword ink box is degenerate")
    x0,y0 = min(x for x,y in newpoints), min(y for x,y in newpoints)
    x1,y1 = max(x for x,y in newpoints), max(y for x,y in newpoints)
    if x1 <= x0 or y1 <= y0:
        raise PlotNoteError("Standard keyword has no two-dimensional ink")
    scale = min((right-left)/(x1-x0), (bottom-top)/(y1-y0))
    dy = top + ((bottom-top)-(y1-y0)*scale)/2
    return [[(left+(x-x0)*scale, dy+(y-y0)*scale) for x,y in path] for path in run.paths]
