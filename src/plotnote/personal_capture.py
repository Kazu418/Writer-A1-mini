"""Recover whole original strokes from known handwriting worksheet cells."""
import hashlib
import json
import math
import zlib


def extract_cells(strokes, canvas, manifest, *, book, page, archive_sha):
    """Known cell labels replace OCR; every returned sample still needs review."""
    width,height=canvas
    if not all(math.isfinite(v) and v>0 for v in canvas):
        raise ValueError('Invalid source canvas')
    expected=manifest['page_pt'][0]/manifest['page_pt'][1]
    if abs(width/height/expected-1)>.005:
        raise ValueError('Source page aspect ratio differs from capture sheet')
    assigned={cell['cell_id']:[] for cell in manifest['cells']}
    outside=0
    for stroke in strokes:
        points=stroke['points']
        if not points or any(len(p)!=2 or not all(math.isfinite(v) for v in p) for p in points):
            raise ValueError('Invalid original ink points')
        destinations=[]
        for cell in manifest['cells']:
            x0,y0,x1,y1=cell['ink_rect_normalized']
            inside=[x0*width<=x<=x1*width and y0*height<=y<=y1*height for x,y in points]
            overlap=(max(x for x,y in points)>=x0*width and min(x for x,y in points)<=x1*width and
                     max(y for x,y in points)>=y0*height and min(y for x,y in points)<=y1*height)
            if overlap and not all(inside):
                raise ValueError('Stroke crosses writing-box boundary; no ink imported')
            if all(inside):destinations.append(cell['cell_id'])
        if len(destinations)>1:
            raise ValueError('Overlapping capture cells')
        if destinations:assigned[destinations[0]].append(stroke)
        else:outside+=1
    samples=[]
    for cell in manifest['cells']:
        items=assigned[cell['cell_id']]
        if not items:continue
        paths=[item['points'] for item in items]
        points=[p for path in paths for p in path]
        if max(p[0] for p in points)==min(p[0] for p in points) and max(p[1] for p in points)==min(p[1] for p in points):
            raise ValueError('A kanji cell contains only a dot')
        gid=hashlib.sha256((archive_sha+page+manifest['sheet_id']+cell['cell_id']).encode()).hexdigest()
        samples.append({'id':gid,'label':cell['label'],'label_status':'unreviewed',
            'book':book,'page':page,'paths':paths,'stroke_ids':[s['id'] for s in items],
            'bbox':[min(p[0] for p in points),min(p[1] for p in points),
                    max(p[0] for p in points),max(p[1] for p in points)],
            'geometry_source':'original_live_ink','stroke_order_status':'layer_order_not_temporal',
            'normalization':'none; original Goodnotes canvas coordinates',
            'recognition_candidates':[cell['label']], 'label_source':'known_capture_cell_not_ocr',
            'capture_sheet':manifest['sheet_id'],'capture_cell':cell['cell_id'],
            'source_archive_sha256':archive_sha})
    return samples,{'missing_cells':[cell['cell_id'] for cell in manifest['cells'] if not assigned[cell['cell_id']]],
                    'outside_strokes_ignored':outside,'samples':len(samples),'labels_approved':0}


def store_samples(db, samples):
    db.execute('CREATE TABLE IF NOT EXISTS exemplars(id TEXT PRIMARY KEY,label TEXT,status TEXT,payload BLOB)')
    inserted=0
    for sample in samples:
        blob=zlib.compress(json.dumps(sample,ensure_ascii=False,separators=(',',':')).encode())
        inserted+=db.execute('INSERT OR IGNORE INTO exemplars VALUES (?,?,?,?)',
                            (sample['id'],sample['label'],'unreviewed',blob)).rowcount
    db.commit()
    return inserted
