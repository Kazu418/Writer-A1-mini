import sys;sys.path.insert(0,'/private/tmp/claude-501/-Users-kazuzon/84e7bd32-8e8d-4a9c-9a0e-110b7560cae1/scratchpad')
from lt8_lib import *
import collections,json
acc=[r for r in rows("WHERE status='accepted'")]
idx={c:i for i,c in enumerate(chars)}
inm=[r for r in acc if r[1] in idx]; out=[r for r in acc if r[1] not in idx]
print('accepted samples',len(acc),'types',len({r[1] for r in acc}),'| in model label set',len(inm),'types',len({r[1] for r in inm}))
print('out-of-model types:',''.join(sorted({r[1] for r in out})))
P=predict([render(r[3]['paths']) for r in inm])
top=np.argsort(-P,1)[:,:5];conf=P.max(1)
t1=np.array([chars[top[i,0]]==inm[i][1] for i in range(len(inm))])
t5=np.array([inm[i][1] in [chars[j] for j in top[i]] for i in range(len(inm))])
print(f'top1 {t1.mean():.3f}  top5 {t5.mean():.3f}  n={len(inm)}')
for th in (.5,.7,.9,.97):
    m=conf>=th;print(f'conf>={th}: adopt {m.mean():.2f}  precision {t1[m].mean() if m.any() else 0:.3f}  wrong adopted {int((m&~t1).sum())}')
print('misses (truth->pred conf):',[(inm[i][1],chars[top[i,0]],round(float(conf[i]),2)) for i in range(len(inm)) if not t1[i]][:40])
# out-of-model: how confidently does it hallucinate?
if out:
    Po=predict([render(r[3]['paths']) for r in out]);print('out-of-model max-conf mean',float(Po.max(1).mean()),'>=0.9 share',float((Po.max(1)>=.9).mean()))
# multi-char / non-char negatives: unreviewed split from words are hypotheses; skip
