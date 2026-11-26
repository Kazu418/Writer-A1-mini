import sys;sys.path.insert(0,'/private/tmp/claude-501/-Users-kazuzon/84e7bd32-8e8d-4a9c-9a0e-110b7560cae1/scratchpad')
from lt8_lib import *
import random,collections,time,json,unicodedata
idx={c:i for i,c in enumerate(chars)}
t=time.time();R=[];B=[]
allr=list(rows(''))
print('samples',len(allr),flush=True)
res=[]
for i in range(0,len(allr),512):
    chunk=allr[i:i+512];P=predict([render(r[3]['paths']) for r in chunk])
    for r,p in zip(chunk,P):
        top=np.argsort(-p)[:5]
        res.append({'id':r[0],'label':r[1],'status':r[2],'in_model':r[1] in idx,'top5':[chars[j] for j in top],'p5':[round(float(p[j]),4) for j in top],'p_label':round(float(p[idx[r[1]]]),4) if r[1] in idx else None,
                    'n_paths':len(r[3]['paths'])})
print('time',round(time.time()-t),'s',flush=True)
import os;os.makedirs(S+'/out',exist_ok=True);json.dump(res,open(S+'/out/lt8_all.json','w'),ensure_ascii=False)
# discriminability: accepted truth in top5 vs random wrong label in top5
acc=[x for x in res if x['status']=='accepted' and x['in_model']]
random.seed(1);accl=[x['label'] for x in acc]
wrong_in=0
for x in acc:
    w=random.choice([c for c in accl if c!=x['label']]);wrong_in+= (w in x['top5'])
print(f"accepted truth in top5: {sum(x['label'] in x['top5'] for x in acc)/len(acc):.3f} | random wrong label in top5: {wrong_in/len(acc):.3f} (n={len(acc)})")
# whole pool
c=collections.Counter()
for x in res:
    if not x['in_model']:c['label_not_in_model']+=1
    elif x['top5'][0]==x['label']:c['top1_agree']+=1
    elif x['label'] in x['top5']:c['top5_agree']+=1
    else:c['disagree']+=1
print(dict(c))
types=collections.defaultdict(list)
for x in res:types[x['label']].append(x)
print('label types',len(types),'| in model',sum(1 for k in types if k in idx))
need='授掛断替険頻'
for ch in need:
    xs=types.get(ch,[]);print(ch,'samples',len(xs),'top1_agree',sum(x['top5'][0]==ch for x in xs),'top5',sum(ch in x['top5'] for x in xs),'in_model',ch in idx)
acc_types={x['label'] for x in res if x['status']=='accepted'}
good={k for k,v in types.items() if k not in acc_types and any(x['top5'][0]==k and x['p5'][0]>=.9 for x in v)}
print('unaccepted types with a >=0.9 top1-agreeing sample:',len(good))
print('unaccepted types total (in model):',sum(1 for k in types if k not in acc_types and k in idx))
