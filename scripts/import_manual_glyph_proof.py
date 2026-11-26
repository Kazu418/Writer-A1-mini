"""Seed the five previously manually labeled original Goodnotes exemplars."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from plotnote.goodnotes_index import connect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / 'output/handwriting-research'
    proof = json.loads((source / 'personal-stroke-proof.json').read_text())
    raw = json.loads((source / 'japanese-raw-strokes.json').read_text())
    assert raw['source_member'] == proof['source']
    assert raw['page_index'] == proof['source_page_index']
    db = connect(args.db)
    for char, glyph in proof['glyphs'].items():
        indices = glyph['source_stroke_indices']
        paths = [[[x, y] for x, y, width in raw['strokes'][i]['points']] for i in indices]
        # Verify that the old manually labeled proof is exactly these original
        # paths with its documented translation/scale, without drawing anew.
        x0 = min(x for path in paths for x, y in path)
        transformed = [[[(x - x0) / 26, (y - 81) / 26] for x, y in path] for path in paths]
        assert transformed == glyph['paths']
        points = [p for path in paths for p in path]
        gid = 'manual-proof-' + hashlib.sha256(char.encode()).hexdigest()
        sample = {'id': gid, 'label': char, 'book': proof['source'],
                  'page': 'decoded-page-index:' + str(proof['source_page_index']),
                  'paths': paths,
                  'stroke_ids': ['decoded-path-index:' + str(i) for i in indices],
                  'stroke_id_kind': 'decoded_page_path_index',
                  'source_stroke_indices': indices,
                  'bbox': [min(p[0] for p in points), min(p[1] for p in points),
                           max(p[0] for p in points), max(p[1] for p in points)],
                  'label_status': 'accepted', 'geometry_source': 'original_live_ink',
                  'stroke_order_status': 'stored_order_not_temporal',
                  'recognition_candidates': [char], 'em_height': 26., 'line_top': 81.,
                  'review_provenance': 'Previously manually transcribed and segmented title; '
                                       'see personal-stroke-proof.json label_method'}
        blob = zlib.compress(json.dumps(sample, ensure_ascii=False, separators=(',', ':')).encode())
        db.execute('INSERT OR IGNORE INTO exemplars VALUES (?,?,?,?)', (gid, char, 'accepted', blob))
    db.commit()
    print(json.dumps({'previously_manually_labeled_glyphs': list(proof['glyphs'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
