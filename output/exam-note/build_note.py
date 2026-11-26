"""A small, legible exam reference: four 148 mm square ordered-stroke pages."""
from dataclasses import dataclass
from pathlib import Path
import json
import math
import sys
import hashlib
import random

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from plotnote.fonts import render_glyph, use_personal_font, personal_font_active
from plotnote.handwriting import text_run
from plotnote.model import Page, Stroke
from plotnote.artifacts import write_artifacts, pdf_document

OUT=Path(__file__).resolve().parent
SIZE=148
BODY=2.5
LEADING=4.0
PEN=.25
HANDWRITTEN=False


def advance(char,size):
    if char.isspace():return size*.38
    if personal_font_active():return size
    if ord(char)<128:return size*.56
    if 'Α'<=char<='ω':return size*.72
    if char in '×÷±≤≥≠≈∑∏∫√→←':return size*.85
    return size


@dataclass
class Box:
    width:float
    height:float
    paths:list
    alt:str=''


def shifted(paths,x,y):return [[(px+x,py+y) for px,py in ps] for ps in paths]


def txt(text,size=3):
    text=text.replace('℃','°C').replace('〜','~')
    if HANDWRITTEN:
        seed=int.from_bytes(hashlib.sha256(text.encode()).digest()[:8],'big')
        run=text_run(text,size,seed=seed,pen_width=PEN)
        return Box(run.width,size,run.paths,text)
    paths=[];x=0;ink_right=None
    for char in text:
        w=advance(char,size)
        glyph=render_glyph(char,(w,0,0,size,0,0))
        points=[p for stroke in glyph for p in stroke]
        if points:
            left=min(p[0] for p in points)
            right=max(p[0] for p in points)
            # Preserve glyph shape; trim side bearings, keeping 0.35mm
            # between neighboring centerline bounding boxes (0.25mm preview pen).
            if ink_right is not None:
                x=max(0,ink_right+.35-left)
            paths+=shifted(glyph,x,0)
            ink_right=x+right
        elif ink_right is not None:
            ink_right+=w*.85
        x+=w*.85
    return Box(max(x,(ink_right or 0)+.15),size,paths,text)


def row(*boxes,gap=.45):
    boxes=[txt(b) if isinstance(b,str) else b for b in boxes]
    h=max(b.height for b in boxes);x=0;paths=[]
    for b in boxes:
        paths+=shifted(b.paths,x,(h-b.height)/2);x+=b.width+gap
    return Box(x-gap,h,paths,''.join(b.alt for b in boxes))


def frac(a,b):
    a=txt(a,2.6) if isinstance(a,str) else a
    b=txt(b,2.6) if isinstance(b,str) else b
    w=max(a.width,b.width)+1.8;bar=a.height+.7
    paths=shifted(a.paths,(w-a.width)/2,0)+[[(0,bar),(w,bar)]]+shifted(b.paths,(w-b.width)/2,bar+1)
    return Box(w,bar+1+b.height,paths,f'({a.alt})/({b.alt})')


def root(a,degree=None):
    a=txt(a,2.8) if isinstance(a,str) else a
    h=a.height+1.1;start=2.8
    paths=[[(0,h*.57),(.7,h*.48),(1.5,h),(2.6,.25),(start+a.width+.5,.25)]]
    paths+=shifted(a.paths,start,.9)
    if degree:paths+=shifted(txt(degree,1.7).paths,0,-.3)
    return Box(start+a.width+.5,h,paths,('sqrt' if not degree else 'root_'+degree)+'('+a.alt+')')


def var(name,sub=None,sup=None,bar=False,size=3):
    b=txt(name,size);paths=b.paths;h=b.height;w=b.width
    if bar:
        paths=shifted(paths,0,.7)+[[(0,.1),(w,.1)]];h+=.7
    if sub:
        q=txt(sub,size*.62);paths+=shifted(q.paths,w,h*.55)
        w+=q.width;h=max(h,h*.55+q.height)
    if sup:
        q=txt(sup,size*.62);paths+=shifted(q.paths,w,-.1);w+=q.width
    return Box(w,h,paths,name+('_'+sub if sub else '')+('^'+sup if sup else '')+('_bar' if bar else ''))


XI=lambda:var('x','i')
XB=lambda:var('x',bar=True)
SX=lambda sup=None:var('S','x',sup)
SUM=lambda:txt('∑',3.2)
DELTA2=lambda:row(txt('('),XI(),txt('−'),XB(),txt(')'),txt('²',3),gap=.18)


class Sheet:
    def __init__(self,index,title,topic):
        self.page=Page(SIZE,SIZE);self.index=index;self.blocks=[];self.lines=[]
        self.text(12,8,f'{index:02d}  {title}',3.9,124)
        self.line([(12,15),(136,15)])
        self.text(12,140,topic,2.1,111)
        self.text(128,140,f'{index}/4' if index else 'TEST',2.1,10)

    def line(self,points):self.page.strokes.append(Stroke(points,'diagram'))

    def put(self,b,x,y,label=None):
        if label is None:label=b.alt
        self.blocks.append({'x':x,'y':y,'w':b.width,'h':b.height,'text':label})
        self.lines.append(label)
        self.page.strokes.extend(Stroke(ps,'note:'+label) for ps in shifted(b.paths,x,y))
        return y+b.height

    def text(self,x,y,text,size=BODY,width=60,leading=None):
        text=text.replace('℃','°C').replace('〜','~')
        if 2.5 < size <= 2.8: size=BODY
        leading=leading or size*(1.24 if HANDWRITTEN else 1.42)
        lines=[];part=''
        for c in text:
            if c=='\n':lines.append(part);part='';continue
            if txt(part+c,size).width>width+.001:
                lines.append(part);part=c
            else:part+=c
        if part:lines.append(part)
        offset=0
        rng=random.Random(int.from_bytes(hashlib.sha256(text.encode()).digest()[:8],'big'))
        last=0
        for s in lines:
            self.put(txt(s,size),x,y+offset)
            last=offset
            offset+=leading+(rng.uniform(-.12,.12) if HANDWRITTEN else 0)
        return y+last+size if lines else y

    def heading(self,x,y,text,width=60):
        self.text(x,y,text,3.15,width)
        self.line([(x,y+4),(x+width,y+4)])

    def formula(self,x,y,b,width=60):
        if b.width>width:raise ValueError(f'Formula too wide: {b.alt}: {b.width}')
        self.put(b,x+(width-b.width)/2,y)

    def table(self,x,y,widths,rows,row_h=6,size=2.6):
        size=min(size,BODY)
        w=sum(widths);h=row_h*len(rows)
        for i in range(len(rows)+1):self.line([(x,y+i*row_h),(x+w,y+i*row_h)])
        xx=x
        for col in range(len(widths)+1):
            self.line([(xx,y),(xx,y+h)])
            if col<len(widths):xx+=widths[col]
        for ri,values in enumerate(rows):
            xx=x
            for cw,value in zip(widths,values):
                b=txt(value,size)
                if b.width>cw-1:raise ValueError(f'Table cell too wide: {value}')
                self.put(b,xx+(cw-b.width)/2,y+ri*row_h+(row_h-size)/2)
                xx+=cw

    def audit(self):
        self.page.validate()
        for b in self.blocks:
            if b['x']<10 or b['x']+b['w']>138 or b['y']<6 or b['y']+b['h']>144:
                raise ValueError(f'Page {self.index} block overflow: {b}')
        collisions=[]
        for i,a in enumerate(self.blocks):
            for b in self.blocks[i+1:]:
                ix=min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x'])
                iy=min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y'])
                if ix>.2 and iy>.2:collisions.append((a['text'],b['text']))
        if collisions:raise ValueError(f'Page {self.index} overlapping text: {collisions}')


def sheet1():
    p=Sheet(1,'全体像と分析の活用','01全体像 / 02データと尺度 / 03代表値 / 04散らばり')
    p.heading(12,21,'Society 5.0')
    p.text(12,28,'サイバー空間とフィジカル空間を高度に融合させ、経済発展と社会的課題の解決を両立する人間中心の社会。')
    p.text(12,48,'IoT(Things)・IoE(Everything)\n→データ収集→ビッグデータ\n→分析→新たな価値の導出\n判断→行動→新データへ循環',2.7)
    p.heading(12,65,'データが重視される背景')
    p.text(12,72,'1 デジタル化：記録できる対象が増えた。\n2 計算資源の向上：大量データを高速処理。\n3 判断の複雑化：直感だけでは難しい。',2.7)
    p.text(12,88,'追記',2.1)
    p.line([(21,91),(72,91)]);p.line([(12,98),(72,98)])
    p.heading(12,104,'Data Scienceの3領域')
    p.text(12,111,'計算技術＋数学・統計＋専門知識\n計算×統計：機械学習（現場知識不足）\n計算×専門：危険地帯（統計的根拠不足）\n統計×専門：従来の研究（計算技術不足）',2.65)
    p.text(12,131,'3領域の重なりがデータサイエンス。',2.7)
    p.heading(76,21,'分析設計の4段階')
    p.text(76,28,'問題解決のため、何を・どう分析し、結果をどう活用するか決める。',2.7)
    p.text(76,40,'1 目的：何を解決するか\n2 収集・加工：分析できる状態へ\n3 手法選択：統計・分析方法を決定\n4 活用：結果を意思決定に使う',2.7)
    p.heading(76,60,'ビジネスでの使い方')
    for i,s in enumerate(['仮説検証：仮説をデータで検証。','知識発見：経験則・洞察を探す。','原因究明：変化の原因を調べる。','判断支援：知見を見やすく提示。','計画策定：生産・販促の計画。','活動代替：定型作業を自動化。','PDCA：Plan→Do→Check→Act']):p.text(76,67+i*4.4,s,2.7)
    p.text(76,97.5,'（計画→実行→評価→改善）',2.6)
    p.text(76,101,'仮説例：YouTubeのサムネ変更で、再生数が増えるかを調べる。',2.65)
    p.text(76,113,'RCT：対象を無作為に群に分け、異なる条件の結果を比較する。\n相関だけでは因果を断定できない。',2.65)
    p.text(76,130,'目的は、より良い意思決定。',3)
    p.line([(76,135),(136,135)])
    return p


def sheet2():
    p=Sheet(2,'データの型と4つの尺度','血液型は質的データ。連続・離散は量的データの区別。')
    p.heading(12,21,'変数と観測値')
    p.table(12,28,[11,16,18,15],[['学生','身長','睡眠','血液型'],['A','170cm','6時間','A型'],['B','165cm','8時間','B型'],['C','180cm','5時間','O型']],6,2.55)
    p.text(12,56,'変数(variable)：観測する項目。\nデータ(data)：実際に得られた値。\nn=3人。IDを除く3変数の観測。',2.65)
    p.heading(12,72,'質的・量的、連続・離散')
    p.text(12,79,'質的：分類や順序を表す。\n量的：数量を表す。\n連続：身長・睡眠時間などの測定量。\n離散：人数・回数など数えられる量。',2.65)
    p.heading(12,104,'尺度で意味を持つ関係')
    p.table(12,111,[16,11,11,11,11],[['尺度','分類','順序','差','比'],['名義','有','無','無','無'],['順序','有','有','無','無'],['間隔','有','有','有','無'],['比率','有','有','有','有']],5.1,2.4)
    p.heading(76,21,'尺度水準＝性質による分類')
    data=[('名義尺度','同じ・違うだけ。順序はない。','例：血液型、地名。'),('順序尺度','順位に意味。差は等間隔でない。','例：満足度、学年、順位。'),('間隔尺度','差に意味。比には意味がない。','例：摂氏温度、西暦、偏差値。'),('比率尺度','差と比に意味。0は量がない。','例：重さ、身長、経過時間。')]
    for i,(name,definition,example) in enumerate(data):
        y=28+i*18.4
        p.text(76,y,name,3);p.text(76,y+4.5,definition,2.6);p.text(76,y+8.4,example,2.6)
        if i<3:p.line([(76,y+15),(136,y+15)])
    p.text(76,103,'20℃は10℃の2倍の温度ではない。',2.6)
    p.table(76,111,[12]*5,[['1','2','3','4','5'],['不満','やや不満','普通','やや満足','満足']],5.5,2.25)
    p.text(76,125,'満足度の数値は順序を表す。\n血液型を1〜4にしても平均は無意味。',2.6)
    return p


def sheet3():
    p=Sheet(3,'代表値と四分位数','Σはi=1からnまで。平均の使い分けと、順序に注目。')
    p.heading(12,21,'算術・幾何・調和平均')
    p.text(12,28,'算術平均 A（相加平均）',3)
    p.formula(12,33,row('A=',frac(row(SUM(),XI()),'n')))
    p.text(12,43,'足し算で積み重なる量に使う。\n例：点数、身長などの平均。',2.65)
    p.text(12,55,'幾何平均 G（相乗平均）',3)
    product=row(var('x','1'),var('x','2'),txt('…'),var('x','n'),gap=.15)
    p.formula(12,60,row('G=',root(product,'n')))
    p.text(12,67,'倍率が掛け合わさる変化に使う。\n例：2倍→0.5倍なら、G=1。\n算術平均1.25では成長率を誤る。',2.65)
    p.text(12,83,'調和平均 H',3)
    p.formula(12,88,row('H=',frac('n',row(SUM(),frac('1',XI())))))
    p.text(12,103,'逆数を平均し、もう一度逆数を取る。\n等距離を20km/hと60km/hで往復。\n平均速度はH=30km/h（40ではない）。',2.65)
    p.formula(12,121,txt('H ≤ G ≤ A',3.2))
    p.text(12,130,'正の数で成立。全て同じなら等号。',2.6)
    p.heading(76,21,'中央値・最頻値')
    p.text(76,27,'代表値：特徴を1つの数値で表す。\n順序統計量：値を小さい順に並べる。\n中央値：並べた中央の値。\n奇数n：(n+1)/2番目。\n偶数n：中央の2値の算術平均。',2.65)
    p.text(76,47,'最頻値：最も多く現れる値。\n同数なら複数の最頻値を持ち得る。',2.65)
    p.heading(76,59,'5数要約と四分位数')
    xs=[79,91.5,104,116.5,129]
    p.line([(xs[0],73),(xs[-1],73)])
    for x,label in zip(xs,['最小','Q1','Q2','Q3','最大']):
        p.line([(x,71.5),(x,74.5)]);b=txt(label,2.5);p.put(b,x-b.width/2,66)
    p.text(76,79,'25%ごとの境界。Q2は中央値。\n四分位数の計算法は授業に従う。',2.6)
    p.text(76,90,'範囲 R = 最大値 − 最小値',2.7)
    p.formula(76,97,row('IQR=',var('Q','3'),txt('−'),var('Q','1')))
    p.formula(76,103,row('QD=',frac('IQR','2')))
    p.text(76,112,'IQRは中央50%の広がり。',2.6)
    p.heading(76,118,'平均偏差 MD')
    absdev=row(txt('|'),XI(),txt('−'),XB(),txt('|'),gap=.1)
    p.formula(76,123,row(var('MD','x'),txt('='),frac(row(SUM(),absdev),'n')),60)
    p.text(76,134,'平均からの距離（絶対値）の平均。',2.5)
    return p


def sheet4():
    p=Sheet(4,'散らばり・比較・標準化','分散はn、不偏分散はn−1。使う標準偏差の定義をそろえる。')
    p.heading(12,21,'偏差 → 分散 → 標準偏差')
    p.formula(12,28,row(var('d','i'),txt('='),XI(),txt('−'),XB()))
    p.text(12,36,'偏差＝各値−平均。偏差の和は0。\nそのまま平均せず、2乗や絶対値を使う。',2.6)
    p.formula(12,49,row(SX('2'),txt('='),frac(row(SUM(),DELTA2()),'n')))
    p.formula(12,61,row(SX(),txt('='),root(SX('2'))))
    p.text(12,70,'分散：偏差の2乗の平均。\n標準偏差：分散の平方根。元の単位。\n例：身長cm → 分散cm²、標準偏差cm。',2.6)
    p.heading(12,87,'不偏分散（母分散の推定）')
    p.formula(12,94,row(var('U','x','2'),txt('='),frac(row(SUM(),DELTA2()),'n−1')))
    p.text(12,106,'標本平均を使うと散らばりを小さく\n見積もりやすいため、n−1で割る。\n標本平均は偏差の2乗和を最小にする。',2.6)
    p.text(12,122,'「不偏標準偏差」はU²の平方根。\nただし、その平方根自体は母標準\n偏差の不偏推定量ではない。n>1。',2.55)
    p.heading(76,21,'変動係数 CV')
    p.formula(76,28,row(var('CV','x'),txt('='),frac(SX(),XB())))
    p.text(76,40,'相対的な散らばりを比較（単位なし）。\nネズミ：5g/20g = 0.25 = 25%\nゾウ：200kg/4000kg = 0.05 = 5%\n体重に対するばらつきはネズミが大。',2.6)
    p.text(76,57,'意味のある0を持つ量、正の平均で\n使う。平均0では定義できない。',2.55)
    p.heading(76,68,'標準化：Zスコア')
    p.formula(76,75,row(var('Z','i'),txt('='),frac(row(XI(),txt('−'),XB()),SX())))
    p.text(76,87,'平均を引き、標準偏差で割る。\n元のSx²をnで定義すると、変換後は\n平均0・分散1。Sx=0では不可。',2.6)
    p.heading(76,103,'質的変動指数 IQV')
    numerator=row('K',txt('('),txt('1−'),SUM(),var('P','k','2'),txt(')'),gap=.1)
    p.formula(76,110,row(var('IQV','x'),txt('='),frac(numerator,'K−1')),60)
    p.text(76,122,'K：カテゴリ数（K>1）。Pk：割合。\nPk≥0、ΣPk=1。\nΣはk=1〜K。範囲は0〜1。\n1種類に集中→0、均等→1。',2.55)
    return p


def pen_test():
    p=Sheet(0,'試し書き','148 x 148 mm / preview pen width 0.25mm')
    # Only a small central region is used for the first contact test.
    for i,size in enumerate([2.6,2.8,3.0,3.2]):
        y=42+i*10
        p.text(35,y,f'{size:.1f}mm  標準偏差',size,92)
    p.line([(55,95),(75,95),(75,115),(55,115),(55,95)])
    p.text(80,101,'20mm正方形',2.8,50)
    p.text(35,126,'note: 2.8mm',2.6,100)
    return p


def main(include_pen_test=True):
    sheets=[sheet1(),sheet2(),sheet3(),sheet4()]
    for p in sheets:p.audit()
    pages=[s.page for s in sheets]
    write_artifacts(pages,OUT/'a1-mini-note',PEN)
    folders=['a1-mini-note']
    if include_pen_test:
        test=pen_test();test.page.validate()
        write_artifacts([test.page],OUT/'pen-test',PEN)
        folders.append('pen-test')
    for folder in folders:
        file=OUT/folder/'preview.html'
        file.write_text(file.read_text().replace('id="travel" type="checkbox" checked','id="travel" type="checkbox"'))
    (OUT/'layout.json').write_text(json.dumps({'page_mm':[SIZE,SIZE],'body_em_mm':BODY,'character_ink_gap_mm':.35,'spacing':'bounded seeded handwriting' if HANDWRITTEN else 'ink bounds; glyph shapes unchanged','handwritten':HANDWRITTEN,'pen_width_preview_mm':PEN,'pages':[s.blocks for s in sheets]},ensure_ascii=False,indent=2))
    (OUT/'note-content.md').write_text('\n\n'.join('## ページ '+str(s.index)+'\n\n'+'\n'.join(s.lines) for s in sheets))
    # Reference imposition only: two square panels on each A4 side, at true scale.
    # 148*sqrt(2) does not fit two squares along A4 height, so panels are scaled to 140 mm.
    # A4 final authoring is a separate later step; this file is not a printer toolpath.
    with pdf_document(pages,PEN) as source:
        import pymupdf as fitz
        a4=fitz.open()
        for side in range(2):
            target=a4.new_page(width=210*72/25.4,height=297*72/25.4)
            for slot in range(2):
                x,y=10,7+slot*143
                rect=fitz.Rect(x*72/25.4,y*72/25.4,(x+140)*72/25.4,(y+140)*72/25.4)
                target.show_pdf_page(rect,source,side*2+slot)
            target.insert_text((156*72/25.4,15*72/25.4),'追記欄',fontname='japan',fontsize=9)
            for y in range(23,289,7):
                target.draw_line((156*72/25.4,y*72/25.4),(200*72/25.4,y*72/25.4),width=.2,color=(.75,.75,.75))
        a4.save(OUT/'a4-duplex-reference.pdf');a4.close()
    print(json.dumps({'pages':len(pages),'summary':[p.summary() for p in pages]},ensure_ascii=False,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,help='New output folder for regeneration')
    parser.add_argument('--handwritten',action='store_true',help='Seeded glyph variation and tighter variable line pitch')
    parser.add_argument('--personal-font',type=Path,help='Reviewed original personal centerline library; missing glyphs fail')
    parser.add_argument('--standard-fallback',default='',help='Only these characters use the standard stroke font (explicit list)')
    args=parser.parse_args()
    HANDWRITTEN=args.handwritten
    if args.personal_font and HANDWRITTEN:
        parser.error('Personal ink is used unchanged; omit --handwritten')
    if args.output:
        OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
    if args.personal_font:
        if not args.output:
            parser.error('Use --output with a new directory for personal-font notes')
        with use_personal_font(json.loads(args.personal_font.read_text()),args.standard_fallback):
            main(include_pen_test=False)
    else:
        main()
