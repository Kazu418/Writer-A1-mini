"""Import original ink from a completed one-page Goodnotes worksheet, locally."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'output/handwriting-research/source/goodparse-main/src'))
from goodparse.archive import _read_deleted_pages, _read_page_meta
from goodparse.records import read_page_objects
from goodparse.page import _parse_stroke
from plotnote.personal_capture import extract_cells,store_samples
import pymupdf


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--canvas-width',type=float,help='Only when verified separately; never infer from ink bounds')
    args=p.parse_args();manifest=json.loads(args.manifest.read_text())
    if manifest.get('format')!='plotnote-capture-sheet-v1':p.error('Unknown capture sheet')
    with zipfile.ZipFile(args.archive) as z:
        names=z.namelist();deleted=set(_read_deleted_pages(z.read,names))
        members=[n for n in names if n.startswith('notes/') and n not in deleted and not n.endswith('/')]
        if len(members)!=1:p.error('Expected a separate one-page worksheet notebook')
        template=False
        for name in names:
            if not name.startswith('attachments/'):continue
            raw=z.read(name)
            if not raw.startswith(b'%PDF'):continue
            with pymupdf.open(stream=raw,filetype='pdf') as pdf:
                if any(manifest['sheet_id'] in page.get_text() for page in pdf):template=True
        if not template:p.error('The worksheet ID was not found in its PDF background')
        meta=_read_page_meta(z.read,names,members)
        canvas=next((m.canvas for m in meta if m.member==members[0] and m.canvas),None)
        if args.canvas_width:
            canvas=(args.canvas_width,args.canvas_width*manifest['page_pt'][1]/manifest['page_pt'][0])
        if canvas is None:p.error('Canvas metadata unavailable; inspect it before supplying --canvas-width')
        strokes=[]
        for obj in reversed(read_page_objects(z.read(members[0]))):
            if obj.kind!=7:continue
            for stroke in _parse_stroke(obj.fields):
                if not stroke.points:continue
                strokes.append({'id':obj.id,'points':[[x,y] for x,y,width in stroke.points]})
    samples,report=extract_cells(strokes,canvas,manifest,book=args.archive.name,
        page=members[0].split('/')[-1],archive_sha=hashlib.sha256(args.archive.read_bytes()).hexdigest())
    with sqlite3.connect(args.db) as db:report['inserted']=store_samples(db,samples)
    report['canvas']=canvas;report['source_archive']=str(args.archive)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
