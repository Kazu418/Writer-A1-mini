"""Read-only source probe: no OCR upload, no font training, no printer actions."""
import io,json,math,sys,zipfile,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent
SRC=ROOT/'source/goodparse-main/src'
sys.path.insert(0,str(SRC))
from goodparse.archive import _read_page_members,_collect_attachments
ARCHIVE=Path.home()/'Downloads/GoodNote_BackUp_ALL.zip'

def main():
    report={'archive':str(ARCHIVE),'bytes':ARCHIVE.stat().st_size,'parser_source':'https://github.com/franzthiemann/goodparse','parser_snapshot_sha256':hashlib.sha256((ROOT/'source/goodparse.tar.gz').read_bytes()).hexdigest(),'license_observation':'LICENSE=GPL-3.0; pyproject license=MIT (conflict)','samples':[]}
    with zipfile.ZipFile(ARCHIVE) as outer:
        entries=[i for i in outer.infolist() if not i.is_dir() and not i.filename.startswith('__MACOSX/')]
        report['extensions']=dict(Counter(Path(i.filename).suffix.lower() or '(none)' for i in entries))
        for name in ['1st Grade/Math Self.goodnotes','1st Grade/Health.goodnotes']:
            with zipfile.ZipFile(io.BytesIO(outer.read(name))) as z:
                names=z.namelist()
                pages=_read_page_members(z.read,names,_collect_attachments(z.read,names))
                strokes=[s for p in pages for s in p.strokes]
                info={'member':name,'note_members':len([n for n in names if n.startswith('notes/') and not n.endswith('/')]),'parsed_pages':len(pages),'strokes':len(strokes),'points':sum(len(s.points) for s in strokes),'kinds':dict(Counter(s.kind for s in strokes)),'page_strokes':[len(p.strokes) for p in pages],'typed_text_boxes':sum(len(p.texts) for p in pages),'search_members':len([n for n in names if n.startswith('search/')])}
                assert strokes and all(math.isfinite(v) for s in strokes for pt in s.points for v in pt)
                index=max(range(len(pages)),key=lambda i:len(pages[i].strokes))
                page=pages[index]
                # A stroke-only local view: background worksheets/images excluded.
                import xml.etree.ElementTree as ET
                points=[pt for s in page.strokes for pt in s.points]
                xmin=min(pt[0] for pt in points);ymin=min(pt[1] for pt in points)
                xmax=max(pt[0] for pt in points);ymax=max(pt[1] for pt in points)
                svg=ET.Element('svg',xmlns='http://www.w3.org/2000/svg',viewBox=f'{xmin-10} {ymin-10} {xmax-xmin+20} {ymax-ymin+20}',width='1200',height='1600')
                ET.SubElement(svg,'rect',x=str(xmin-10),y=str(ymin-10),width=str(xmax-xmin+20),height=str(ymax-ymin+20),fill='white')
                for stroke in page.strokes:
                    if not stroke.points:continue
                    color=stroke.color
                    attrs={'fill':'none','stroke':f'rgb({round(color[0]*255)},{round(color[1]*255)},{round(color[2]*255)})','stroke-opacity':str(color[3]),'stroke-width':str(max(.3,sum(pt[2] for pt in stroke.points)/len(stroke.points))),'stroke-linecap':'round','stroke-linejoin':'round'}
                    path='M '+' L '.join(f'{x:.3f},{y:.3f}' for x,y,w in stroke.points)
                    ET.SubElement(svg,'path',d=path,**attrs)
                label='math' if 'Math' in name else 'japanese'
                data=ET.tostring(svg,encoding='unicode')
                (ROOT/(label+'-strokes.svg')).write_text(data)
                import pymupdf
                with pymupdf.open(stream=data.encode(),filetype='svg') as doc:
                    doc[0].get_pixmap(matrix=pymupdf.Matrix(.75,.75),alpha=False).save(ROOT/(label+'-strokes.png'))
                info['illustrated_page_index']=index
                info['illustrated_page_strokes']=len(page.strokes)
                # Raw points kept only locally, separate from any character/font mapping.
                raw={'source_member':name,'page_index':index,'coordinate_space':'Goodnotes canvas, as decoded','strokes':[{'points':s.points,'color':s.color,'kind':s.kind} for s in page.strokes]}
                (ROOT/(label+'-raw-strokes.json')).write_text(json.dumps(raw,separators=(',',':')))
                report['samples'].append(info)
                print(json.dumps(info,ensure_ascii=False),flush=True)
    (ROOT/'archive-probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
