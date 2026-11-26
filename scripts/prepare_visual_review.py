"""Prepare the next blind original-ink candidate for each unconfirmed character."""
import argparse
import json
from pathlib import Path
import sqlite3

from prepare_ocr_campaign import draw_page
from plotnote.personal_review import read_samples


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--required',type=Path,required=True)
    p.add_argument('--exclude',type=Path,action='append',default=[])
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    excluded=set()
    for file in args.exclude:
        manifest=json.loads(file.read_text())
        excluded.update(g['exemplar_id'] for page in manifest['pages'] for g in page['glyphs'])
    with sqlite3.connect(args.db,timeout=30) as db:
        samples=read_samples(db)
    confirmed={s['label'] for s in samples if s['status']=='accepted'}
    needed=set(json.loads(args.required.read_text())['characters'])-confirmed
    selected={}
    for sample in samples:
        if (sample['label'] in needed and sample['label'] not in selected and
                sample['id'] not in excluded and sample['status']!='rejected'):
            selected[sample['label']]=sample
    ordered=sorted(selected.values(),key=lambda s:(s.get('ocr_status')!='match',s['label']))
    args.output.mkdir(parents=True,exist_ok=True)
    if (args.output/'manifest.json').exists():
        p.error('Review already exists; preserve the mapping')
    pages=[]
    for i in range(0,len(ordered),24):
        png,entries=draw_page(ordered[i:i+24])
        filename=f'page-{len(pages)+1:03d}.png'
        (args.output/filename).write_bytes(png)
        pages.append({'image':filename,'page_index':len(pages),'glyphs':entries})
    (args.output/'manifest.json').write_text(json.dumps({'pages':pages,
        'unconfirmed_characters':len(needed),'selected':len(ordered)},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'selected':len(ordered),'pages':len(pages),
                      'no_fresh_candidate':''.join(sorted(needed-selected.keys()))},ensure_ascii=False))


if __name__=='__main__':
    main()
