"""Verified personal centerlines -> text pages accepted by the existing exporter."""
import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sqlite3
import zlib

from .artifacts import write_artifacts
from .model import Page, PlotNoteError, Stroke


def normalize_sample(sample):
    """Uniform translation/scale only; retain the aspect ratio and every point."""
    paths = sample['paths']
    points = [p for path in paths for p in path]
    if not points or any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in points):
        raise PlotNoteError('Invalid personal glyph coordinates')
    x0, y0 = min(p[0] for p in points), min(p[1] for p in points)
    x1, y1 = max(p[0] for p in points), max(p[1] for p in points)
    line_reference = sample.get('em_height')
    scale = line_reference if line_reference is not None else max(x1 - x0, y1 - y0)
    if scale <= 0:
        raise PlotNoteError('Personal glyph has no extent')
    if not math.isfinite(scale):
        raise PlotNoteError('Invalid personal glyph em height')
    line_top = sample.get('line_top', y0)
    if not math.isfinite(line_top):
        raise PlotNoteError('Invalid personal glyph line origin')
    # Keep original data in the library as well. Cell metrics are provisional
    # until full-line comparisons establish the writer's relative character sizes.
    return {'paths': [[[(x - x0) / scale, (y - line_top) / scale] for x, y in (path if len(path)!=1 else path*2)]
                      for path in paths],
            'path_adaptations': [{'path_index': i, 'reason': 'single-point tap represented by a repeated endpoint'}
                                 for i,path in enumerate(paths) if len(path)==1],
            'width_em': (x1 - x0) / scale,
            'height_em': (y1 - y0) / scale,
            'original_paths': paths,
            'source': {k: sample[k] for k in ('id', 'book', 'page', 'stroke_ids')},
            'geometry_source': 'original_live_ink',
            'stroke_order_status': sample['stroke_order_status'],
            'metrics_status': ('estimated_source_line' if sample.get('metric_reference') else
                               'source_line_reference' if line_reference else 'bounding_cell_provisional'),
            'metric_reference': sample.get('metric_reference')}


def add_typographic_forms(glyphs):
    """Explicit forms made only from reviewed ink; never substitute a kanji.

    Original arrays and source IDs remain attached. Derived display paths use
    uniform scale/translation only, and are distinguished from drawn examples.
    """
    rules = {"（": ("(", 1., 0.), "）": (")", 1., 0.),
             "＋": ("+", 1., 0.), "＝": ("=", 1., 0.),
             "∑": ("Σ", 1., 0.), "²": ("2", .6, -.1),
             "。": ("o", .18, .82)}
    added = {}
    for target, (base, scale, dy) in rules.items():
        if target in glyphs or base not in glyphs:
            continue
        variants = []
        for original in glyphs[base]:
            sample = deepcopy(original)
            sample['paths'] = [[[x*scale, y*scale+dy] for x,y in path] for path in original['paths']]
            sample['width_em'] *= scale
            sample['height_em'] *= scale
            sample['geometry_source'] = 'typographic_form_of_original_live_ink'
            sample['derivation'] = {'base_character': base, 'uniform_scale': scale,
                                    'translate_y_em': dy,
                                    'reason': 'small circle punctuation' if target == '。' else
                                              'width variant' if scale == 1 and target != '∑' else
                                              'summation notation' if target == '∑' else 'superscript'}
            variants.append(sample)
        glyphs[target] = variants
        added[target] = base
    # Position the writer's own horizontal stroke and dot as mathematical
    # punctuation. These are explicit compositions, never new drawn samples.
    for target, base, centres in [('−', 'ー', [.5]), ('・', '.', [.5]),
                                   ('：', '.', [.3, .75])]:
        if target in glyphs or base not in glyphs:
            continue
        variants = []
        for original in glyphs[base]:
            ys = [y for path in original['paths'] for x,y in path]
            centre = (min(ys)+max(ys))/2
            sample = deepcopy(original)
            sample['paths'] = [[[x,y-centre+cy] for x,y in path]
                               for cy in centres for path in original['paths']]
            sample['height_em'] = max(centres)-min(centres)+max(ys)-min(ys)
            sample['geometry_source'] = 'typographic_form_of_original_live_ink'
            sample['derivation'] = {'base_character': base, 'uniform_scale': 1.,
                                    'source_centre_y_em': centre, 'target_centres_y_em': centres,
                                    'reason': 'positioned punctuation', 'copies': len(centres)}
            variants.append(sample)
        glyphs[target] = variants
        added[target] = base
    return added


def export_library(db, output, *, typographic_forms=False):
    """Only confirmed exemplars enter the runnable library; retain variants."""
    glyphs = {}
    for gid, label, blob in db.execute(
            "SELECT id,label,payload FROM exemplars WHERE status='accepted' ORDER BY id"):
        if len(label) != 1 or label.isspace():
            raise PlotNoteError('Accepted exemplar labels must contain exactly one character')
        sample = json.loads(zlib.decompress(blob))
        glyphs.setdefault(label, []).append(normalize_sample(sample))
    if not glyphs:
        raise PlotNoteError('No confirmed personal glyphs; review candidates first')
    derived = add_typographic_forms(glyphs) if typographic_forms else {}
    result = {'format': 'plotnote-personal-centerlines-v1', 'glyphs': glyphs,
              'typographic_forms': derived,
              'label_status': 'reviewed', 'standard_font_fallback': False}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    return result


def text_page(text, library, *, width=148, height=148, margin=8, size=2.5, gap=.35,
              line_pitch=3.5, row_gap=.35):
    """Strict personal-only text layout; missing characters fail before export."""
    glyphs = library['glyphs']
    missing = sorted({c for c in text if not c.isspace() and c not in glyphs})
    if missing:
        raise PlotNoteError('Personal glyphs missing: ' + ''.join(missing))
    if not all(math.isfinite(v) for v in (width, height, margin, size, gap, line_pitch, row_gap)):
        raise PlotNoteError('Nonfinite personal text layout')
    if size <= 0 or gap <= 0 or row_gap <= 0 or margin <= 0 or line_pitch < size or min(width, height) <= 2 * margin + size:
        raise PlotNoteError('Invalid personal text layout dimensions')
    page = Page(width, height)
    x = margin
    rows, row = [], []
    occurrences = {}
    for char in text:
        if char == '\n':
            rows.append(row)
            row, x = [], margin
            continue
        if char.isspace():
            x += size * .4
            continue
        variants = glyphs[char]
        n = occurrences.get(char, 0)
        occurrences[char] = n + 1
        sample = variants[n % len(variants)]
        span = sample['width_em'] * size
        if span > width - 2 * margin:
            raise PlotNoteError('Personal glyph is wider than the available line')
        if x + span > width - margin:
            rows.append(row)
            row, x = [], margin
        # Cell metrics remain provisional until source-line calibration.
        for path in sample['paths']:
            if len(path) < 2:
                raise PlotNoteError('Personal glyph contains a one-point path')
            row.append(Stroke([(x + px * size, py * size) for px, py in path],
                              'personal:' + char + ':' + sample['source']['id']))
        x += span + gap
    if row:
        rows.append(row)
    origin_y, previous_bottom = margin, None
    for row in rows:
        if not row:
            origin_y += line_pitch
            continue
        lo = min(y for stroke in row for x, y in stroke.points)
        hi = max(y for stroke in row for x, y in stroke.points)
        origin_y = max(origin_y, margin - lo)
        if previous_bottom is not None:
            origin_y = max(origin_y, previous_bottom + row_gap - lo)
        if origin_y + hi > height - margin:
            raise PlotNoteError('Personal text overflows; split into pages')
        page.strokes.extend(Stroke([(x, y + origin_y) for x, y in stroke.points], stroke.source)
                            for stroke in row)
        previous_bottom = origin_y + hi
        origin_y += line_pitch
    page.validate()
    return page


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('export-library')
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('-o', '--output', type=Path, required=True)
    p.add_argument('--typographic-forms', action='store_true',
                   help='Include explicit width, summation and superscript variants of reviewed ink')
    p = sub.add_parser('preview')
    p.add_argument('--font', type=Path, required=True)
    p.add_argument('--text', required=True)
    p.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'export-library':
        with sqlite3.connect(args.db) as db:
            result = export_library(db, args.output, typographic_forms=args.typographic_forms)
        print(json.dumps({'characters': len(result['glyphs']), 'output': str(args.output)}))
    else:
        library = json.loads(args.font.read_text())
        page = text_page(args.text, library)
        write_artifacts([page], args.output, .25)
        print(json.dumps(page.summary()))


if __name__ == '__main__':
    main()
