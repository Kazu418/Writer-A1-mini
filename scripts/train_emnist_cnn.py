import gzip,struct,numpy as np,torch,torch.nn as nn,time,sys,json,sqlite3,zlib
from PIL import Image,ImageDraw
D="/Users/kazuzon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Kosen/データサイエンス/PlotNote/output/datasets/emnist-byclass/"
def idx(p):
    with gzip.open(p) as f:
        magic,n=struct.unpack('>II',f.read(8));nd=(magic&255)-1
        dims=[struct.unpack('>I',f.read(4))[0] for _ in range(nd)]
        return np.frombuffer(f.read(),np.uint8).reshape([n]+dims)
Xtr=idx(D+'emnist-byclass-train-images-idx3-ubyte.gz').transpose(0,2,1);ytr=idx(D+'emnist-byclass-train-labels-idx1-ubyte.gz')
Xte=idx(D+'emnist-byclass-test-images-idx3-ubyte.gz').transpose(0,2,1);yte=idx(D+'emnist-byclass-test-labels-idx1-ubyte.gz')
cls=[chr(int(l.split()[1])) for l in open(D+'emnist-byclass-mapping.txt').read().split('\n') if l.strip()]
assert len(cls)==62
dev='mps' if torch.backends.mps.is_available() else 'cpu'
net=nn.Sequential(nn.Conv2d(1,32,3,padding=1),nn.ReLU(),nn.Conv2d(32,32,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
 nn.Conv2d(32,64,3,padding=1),nn.ReLU(),nn.Conv2d(64,64,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
 nn.Flatten(),nn.Dropout(.3),nn.Linear(64*49,256),nn.ReLU(),nn.Dropout(.3),nn.Linear(256,62)).to(dev)
opt=torch.optim.Adam(net.parameters(),1e-3)
def tens(x):return torch.from_numpy(x.astype(np.float32)/255.).unsqueeze(1)
def evaluate(X,y):
    net.eval();c=0
    with torch.no_grad():
        for i in range(0,len(X),4096):
            c+=(net(tens(X[i:i+4096]).to(dev)).argmax(1).cpu().numpy()==y[i:i+4096]).sum()
    return c/len(X)
t=time.time()
for ep in range(3):
    net.train();perm=np.random.permutation(len(Xtr))
    for i in range(0,len(perm),512):
        b=perm[i:i+512];x=tens(Xtr[b]).to(dev);y=torch.from_numpy(ytr[b].astype(np.int64)).to(dev)
        # light augmentation: random shift
        if np.random.rand()<.5:x=torch.roll(x,shifts=(np.random.randint(-2,3),np.random.randint(-2,3)),dims=(2,3))
        opt.zero_grad();nn.functional.cross_entropy(net(x),y).backward();opt.step()
    print('epoch',ep+1,'test acc',round(float(evaluate(Xte,yte)),4),'t',round(time.time()-t),flush=True)
torch.save({'state':net.state_dict(),'classes':cls},D+'../cnn62.pt')
# --- your own verified handwriting, rendered EMNIST-style
DB="file:/Users/kazuzon/Library/Mobile Documents/com~apple~CloudDocs/Documents/Kosen/データサイエンス/PlotNote/output/personal-font/goodnotes.sqlite3?mode=ro&immutable=1"
db=sqlite3.connect(DB,uri=True);S=set(cls);xs=[];ys=[]
def render(paths):
    pts=[p for q in paths for p in q];x0=min(p[0] for p in pts);x1=max(p[0] for p in pts);y0=min(p[1] for p in pts);y1=max(p[1] for p in pts)
    e=max(x1-x0,y1-y0,1e-6);sc=19.0/e;ox=4+(20-(x1-x0)*sc)/2;oy=4+(20-(y1-y0)*sc)/2
    im=Image.new('L',(28,28),0);d=ImageDraw.Draw(im)
    for q in paths:
        z=[((x-x0)*sc+ox,(y-y0)*sc+oy) for x,y in q]
        if len(z)==1:z=z*2
        d.line(z,fill=255,width=2)
    return np.asarray(im.filter(__import__('PIL.ImageFilter',fromlist=['x']).GaussianBlur(.6)))
for gid,label,status,blob in db.execute("SELECT id,label,status,payload FROM exemplars WHERE status='accepted'"):
    if label in S:xs.append(render(json.loads(zlib.decompress(blob))['paths']));ys.append(cls.index(label))
X=np.stack(xs);y=np.array(ys);net.eval()
with torch.no_grad():p=torch.softmax(net(tens(X).to(dev)),1).cpu().numpy()
pred=p.argmax(1);fold=lambda c:c.lower()
exact=(pred==y).mean();ci=np.mean([fold(cls[a])==fold(cls[b]) for a,b in zip(pred,y)])
top3=np.mean([b in np.argsort(-pp)[:3] for pp,b in zip(p,y)])
print(f'own accepted alnum samples n={len(y)}  exact {exact:.3f}  case-insensitive {ci:.3f}  top3 {top3:.3f}')
print('misses:',[(cls[b],cls[a],round(float(p[i].max()),2)) for i,(a,b) in enumerate(zip(pred,y)) if a!=b][:30])
