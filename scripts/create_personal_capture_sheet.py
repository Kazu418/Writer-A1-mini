"""Create one local Goodnotes worksheet for the remaining handwritten kanji."""
import argparse
import hashlib
import json
from pathlib import Path
import pymupdf


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    target=args.output/'additional-six-characters.pdf'
    if target.exists():p.error('Capture sheet already exists; preserve its ID and geometry')
    characters='授掛断替険頻'
    sheet_id='PN-CAPTURE-'+hashlib.sha256(characters.encode()).hexdigest()[:12]
    w,h=595.275590551,841.88976378
    doc=pymupdf.open();page=doc.new_page(width=w,height=h)
    font=next(Path('/System/Library/Fonts').glob('ヒラ* W3.ttc'))
    page.insert_font(fontname='jp',fontfile=str(font))
    def text(x,y,value,size=11,color=(.1,.15,.15)):
        page.insert_text((x,y),value,fontname='jp',fontsize=size,color=color)
    text(40,42,'本人の筆跡を追加する6文字',19)
    text(40,65,'Goodnotesに新しいノートとして読み込み、各枠に1文字ずつ書いてください。')
    text(40,84,'黒いペンで、普段と同じ書き方で。見本はなぞらず、枠の中央へ。')
    text(40,103,'書き終えたら、1ページのノートを「Goodnotes形式」で書き出してください。',10)
    cells=[]
    for i,char in enumerate(characters):
        left=40+(i%2)*267;top=130+(i//2)*218
        text(left+5,top+30,char,26)
        page.insert_text((left+180,top+24),f'GN-{i+1:02d}',fontsize=10,color=(.4,.4,.4))
        box=pymupdf.Rect(left+5,top+44,left+230,top+190)
        page.draw_rect(box,color=(.55,.6,.6),width=.6)
        page.draw_line((box.x0,box.y0+box.height/2),(box.x1,box.y0+box.height/2),color=(.88,.9,.9),width=.3,dashes='[2 4]')
        cells.append({'cell_id':f'GN-{i+1:02d}','label':char,
                      'ink_rect_pt':list(box),'ink_rect_normalized':[box.x0/w,box.y0/h,box.x1/w,box.y1/h]})
    page.insert_text((40,818),sheet_id,fontsize=9,color=(.45,.45,.45))
    doc.set_metadata({'title':'PlotNote - six additional handwritten characters','subject':sheet_id,'author':'PlotNote'})
    doc.save(target,deflate=True);doc.close()
    with pymupdf.open(target) as check:
        assert len(check)==1 and all(c in check[0].get_text() for c in characters)
        check[0].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False).save(args.output/'capture-preview.png')
    manifest={'format':'plotnote-capture-sheet-v1','sheet_id':sheet_id,'file':target.name,
              'pdf_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'page_pt':[w,h],
              'cells':cells,'ink_source':'Native Goodnotes pen strokes only; printed prompts are excluded',
              'label_status':'known cell hypotheses; visual verification required before acceptance'}
    target.with_suffix('.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(target)


if __name__=='__main__':main()
