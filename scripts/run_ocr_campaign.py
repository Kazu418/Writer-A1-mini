"""Resume a prepared <=500-page FAST campaign; never retry uncertain uploads."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from plotnote.personal_ocr import audit, store_audit
from datalab_ocr import save
import sqlite3


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('campaign',type=Path)
    p.add_argument('--db',type=Path,required=True)
    args=p.parse_args()
    plan=json.loads((args.campaign/'campaign.json').read_text())
    if (plan['mode']!='fast' or plan['planned_pages']>500 or
        sum(b['pages'] for b in plan['batches'])+plan['prior_trial_pages']!=plan['planned_pages']):
        raise ValueError('Invalid campaign page budget')
    for batch in plan['batches']:
        file=args.campaign/batch['file']
        if hashlib.sha256(file.read_bytes()).hexdigest()!=batch['sha256']:
            raise ValueError('Campaign file changed')
    def run(batch):
        file=args.campaign/batch['file']
        command=[sys.executable,str(ROOT/'scripts/datalab_ocr.py'),str(file),
                 '--state',str(file.with_suffix('.job.json')),'--planned-pages',str(plan['planned_pages'])]
        result=subprocess.run(command,capture_output=True,text=True)
        print(file.name, result.stdout.strip(),result.stderr[-400:] if result.returncode else '',flush=True)
        return file,result.returncode
    results=[]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures=[]
        for batch in plan['batches']:
            file=args.campaign/batch['file']
            state=file.with_suffix('.job.json')
            if state.exists() and json.loads(state.read_text()).get('status')=='complete':
                results.append((file,0))
                continue
            futures.append(executor.submit(run,batch))
            # At most 7.5 new submissions/minute; polling does not consume OCR pages.
            time.sleep(8)
        results += [future.result() for future in as_completed(futures)]
    totals={}
    with sqlite3.connect(args.db) as db:
        for file,code in results:
            if code:
                continue
            result=json.loads(file.with_suffix('.job.result.json').read_text())
            if result.get('success') is not True or result.get('status')!='complete':
                raise ValueError('Unsuccessful OCR result')
            manifest=json.loads(file.with_suffix('.manifest.json').read_text())
            report=audit(manifest,result)
            save(file.with_suffix('.audit.json'),report)
            store_audit(db,report['rows'],manifest['sha256'])
            for key,value in report['counts'].items():
                totals[key]=totals.get(key,0)+value
    summary={'completed_batches':sum(code==0 for _,code in results),
             'failed_or_uncertain_batches':[file.name for file,code in results if code],
             'counts':totals,'planned_pages':plan['planned_pages'],
             'review_decisions_changed':0}
    save(args.campaign/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if summary['failed_or_uncertain_batches']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
