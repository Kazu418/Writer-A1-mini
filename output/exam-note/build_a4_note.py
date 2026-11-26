"""A4 two-sided note drawn by the A1 mini in tiles (A4 portrait: width in one pass, height in two).

Each A4 face = two tiles (TILE_W x TILE_H mm) printed one after the other, the paper moved between the passes
between them. Text keeps the source note's wording. Line art only, no fills.
Run: PYTHONPATH=src .venv/bin/python output/exam-note/build_a4_note.py --personal-font <font.json> --output <new dir>
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_note as bn                                   # formula/layout parts of the existing note
from build_note import txt, row, frac, root, var, SUM, XI, XB, SX, DELTA2, Box, shifted
from plotnote.artifacts import write_artifacts
from plotnote.fonts import use_personal_font
from plotnote.model import Page, PlotNoteError, Stroke

A4_W, A4_H = 210.0, 297.0
# Printing method (user's): A4 long side = machine Y. Pass 1: A4 top edge flush with the plate's back edge.
# Pass 2: A4 bottom edge flush with the plate's front edge. The pen sits 30.8 mm in front of the nozzle, so with
# nozzle Y <= 175 the pen reaches at most 144.2 mm from the front edge: the top 35.8 mm of the A4 stays blank.
BED_Y = 180.0
NOZZLE_MIN, NOZZLE_MAX = 5.0, 175.0
PEN_OFFSET_Y = -30.8
TILE_W, TILE_H = 165.0, 127.5
WIN_Y = (36.5, 164.5)                   # A4 y of the top edge of the pass-1 and pass-2 windows (each TILE_H tall)
MARGIN_X = 4.0
COL_W = 76.5
COL_X = (MARGIN_X, TILE_W - MARGIN_X - COL_W)
TOP, BOTTOM = 2.0, TILE_H - 2.0
PAPER_X0 = (A4_W - TILE_W) / 2           # window x on the A4 when the A4 is centred on the 180 mm plate
PROVEN_PROFILE = ROOT / 'output/contact-test/handwriting-30-profile.json'


# ---------------------------------------------------------------- drawing primitives (line only)
def circle(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]


def arrow(x1, y1, x2, y2, head=1.4):
    a = math.atan2(y2 - y1, x2 - x1)
    l = [(x1, y1), (x2, y2)]
    return [l,
            [(x2 - head * math.cos(a - .45), y2 - head * math.sin(a - .45)), (x2, y2),
             (x2 - head * math.cos(a + .45), y2 - head * math.sin(a + .45))]]


def put(paths, box_paths, x, y):
    paths.extend(shifted(box_paths, x, y))


def label(paths, text, x, y, size, anchor='l'):
    b = txt(text, size)
    dx = {'l': 0, 'c': -b.width / 2, 'r': -b.width}[anchor]
    put(paths, b.paths, x + dx, y)
    return b


# ---------------------------------------------------------------- figures (small, line only)
def fig_iot(w, s):
    paths, t = [], s - .3
    paths.append(rect(0, 0, 21, t * 2 + 2))
    label(paths, 'IoT (Things)', 1, .7, t - .3)
    label(paths, 'IoE (Everything)', 1, t + 1.1, t - .3)
    paths += arrow(22, t + 1, 30, t + 1)
    label(paths, '収集', 26, -.2, t - .6, 'c')
    label(paths, 'ビッグデータ', 31.5, t * .5 + .3, t)
    paths += arrow(47, t * 1.9 + 1.2, 47, t * 1.9 + 5.5)
    label(paths, '分析', 50, t * 1.9 + 1.8, t - .6)
    label(paths, '新たな価値の導出', 31.5, t * 1.9 + 6.2, t)
    return Box(w, t * 2.9 + 7.4, paths, '図:IoT/IoE→ビッグデータ→新たな価値')


def fig_venn(w, s):
    r, paths = 7.2, []
    cx, cy = 17, r + .6
    for ox, oy in ((-4.5, 0), (4.5, 0), (0, 6.5)):
        paths.append(circle(cx + ox, cy + oy, r))
    t = s - .8
    label(paths, '計算', cx - 7.5, cy - 4, t, 'c')
    label(paths, '数学・統計', cx + 12.5, cy - 4, t, 'l')
    label(paths, '専門知識', cx + 10, cy + 10.5, t, 'l')
    label(paths, 'DS', cx, cy + 1.6, t, 'c')
    return Box(w, 2 * r + 7.5, paths, '図:ベン図(計算・数学統計・専門知識)')


def table_box(widths, rows, row_h, size, alt):
    paths, w, h = [], sum(widths), row_h * len(rows)
    for i in range(len(rows) + 1):
        paths.append([(0, i * row_h), (w, i * row_h)])
    xx = 0
    for col in range(len(widths) + 1):
        paths.append([(xx, 0), (xx, h)])
        if col < len(widths):
            xx += widths[col]
    for ri, values in enumerate(rows):
        xx = 0
        for cw, value in zip(widths, values):
            b = txt(value, size)
            put(paths, b.paths, xx + (cw - b.width) / 2, ri * row_h + (row_h - size) / 2)
            xx += cw
    return Box(w, h, paths, alt)


def fig_scale(w, s):
    paths, y, t = [], 0, s - .5
    for name, bw, note in (('名義', 14, '分類'), ('順序', 22, '分類+順序'), ('間隔', 31, '分類+順序+差'), ('比率', 40, '分類+順序+差+比')):
        paths.append(rect(0, y, bw, t + 1.2))
        label(paths, name, 1, y + .6, t)
        label(paths, note, bw + 1.2, y + .6, t)
        y += t + 1.9
    return Box(w, y, paths, '図:尺度の包含(下ほど扱える情報が増える)')


def fig_satisfaction(w, s):
    paths, t = [], s - .6
    xs = [8 + i * (w - 16) / 4 for i in range(5)]
    for x, n, nm in zip(xs, '12345', ['不満', 'やや不満', '普通', 'やや満足', '満足']):
        label(paths, n + nm, x, 0, t, 'c')
    paths += arrow(2, t + 2.2, w - 2, t + 2.2, 1.3)
    return Box(w, t + 4, paths, '図:満足度1〜5')


def fig_cross(w, s):
    rows = [['性別', '文系', '理系', '周辺度数'], ['男性', '30', '120', '150'],
            ['女性', '100', '50', '150'], ['周辺度数', '130', '170', '300']]
    return table_box([13, 13, 13, 18], rows, s + .3, s - .7, '図:分割表(男女×文理)')


def fig_students(w, s):
    rows = [['学生', '身長', '睡眠時間', '血液型'], ['A', '170cm', '6時間', 'A型'],
            ['B', '165cm', '8時間', 'B型'], ['C', '180cm', '5時間', 'O型']]
    return table_box([10, 15, 17, 14], rows, s + .3, s - .7, '図:学生A,B,Cの表')


def fig_band(w, s):
    paths, y, t = [], 0, s - .8
    for name, cuts in (('A', (0.5, 0.8)), ('B', (0.3, 0.7))):
        label(paths, name, 0, y, t)
        x0, bw = 4, 30
        paths.append(rect(x0, y, bw, t + .8))
        for c in cuts:
            paths.append([(x0 + c * bw, y), (x0 + c * bw, y + t + .8)])
        y += t + 1.8
    return Box(w, y, paths, '図:帯グラフ(2グループ)')


def fig_pareto(w, s):
    paths, t = [], s - 1
    ww, hh, ox, oy = 22, 12, 1, .5
    paths.append([(ox, oy), (ox, oy + hh), (ox + ww, oy + hh)])
    heights, bw = [0.9, 0.55, 0.35, 0.18, 0.08], ww / 5
    cum, tot, pts = 0, sum(heights), []
    for i, hgt in enumerate(heights):
        paths.append(rect(ox + i * bw, oy + hh - hh * hgt, bw, hh * hgt))
        cum += hgt
        pts.append((ox + i * bw + bw / 2, oy + hh - hh * cum / tot))
    paths.append(pts)
    label(paths, '棒=度数', ox + ww + 2, oy + 2, t)
    label(paths, '折れ線=累積比率', ox + ww + 2, oy + 2 + t + .8, t)
    return Box(w, hh + 1.5, paths, '図:パレート図')


def fig_box_violin(w, s):
    paths, t = [], s - 1
    bx = 7
    paths += [[(bx, .5), (bx, 3.5)], [(bx - 2, .5), (bx + 2, .5)], rect(bx - 3, 3.5, 6, 6), [(bx - 3, 6.5), (bx + 3, 6.5)],
              [(bx, 9.5), (bx, 13.5)], [(bx - 2, 13.5), (bx + 2, 13.5)]]
    label(paths, '箱ひげ図', bx, 14.2, t, 'c')
    vx, pts = 30, []
    for i in range(0, 14):
        y = .5 + i
        wd = .8 + 4 * math.exp(-((y - 6) / 3.2) ** 2) + 1.2 * math.exp(-((y - 10.5) / 2) ** 2)
        pts.append((vx - wd, y))
    paths.append(pts + [(2 * vx - x, y) for x, y in reversed(pts)] + [pts[0]])
    paths.append([(vx, .5), (vx, 13.5)])
    label(paths, 'バイオリンプロット', vx, 14.2, t, 'c')
    return Box(w, 14.5 + t + 1, paths, '図:箱ひげ図とバイオリンプロット')


# ---------------------------------------------------------------- formulas
def F(*parts, gap=.45):
    return row(*parts, gap=gap)


f_geo_ex = lambda: F(frac('2+0.5', '2'), txt('='), txt('1.25'))
f_geo_ok = lambda: F(var('G'), txt('='), root('2×0.5'), txt('='), txt('1'))
f_G = lambda: F(var('G'), txt('='), root(F(var('x', '1'), var('x', '2'), txt('…'), var('x', 'n')), 'n'))
f_h_bad = lambda: F(frac('20+60', '2'), txt('='), txt('40 km/h'))
f_h_ok = lambda: F(var('H'), txt('='), frac('2', F(frac('1', '20'), txt('+'), frac('1', '60'))), txt('='), txt('30'))
f_H = lambda: F(var('H'), txt('='), frac('n', F(SUM(), frac('1', XI()))))
f_IQR = lambda: F(var('IQR'), txt('='), var('Q', '3'), txt('−'), var('Q', '1'))
f_QD = lambda: F(var('QD'), txt('='), frac('IQR', '2'))
f_dev = lambda: F(txt('偏差'), txt('='), XI(), txt('−'), XB())
f_S2 = lambda: F(SX('2'), txt('='), frac('1', 'n'), SUM(), DELTA2())
f_S = lambda: F(SX(), txt('='), root(SX('2')))
f_MD = lambda: F(var('MD', 'x'), txt('='), frac('1', 'n'), SUM(), F(txt('|'), XI(), txt('−'), XB(), txt('|'), gap=.1))
f_U2 = lambda: F(var('U', 'x', '2'), txt('='), frac('1', 'n−1'), SUM(), DELTA2())
f_CV = lambda: F(var('CV', 'x'), txt('='), frac(SX(), XB()))
f_IQV = lambda: F(var('IQV', 'x'), txt('='), frac(F(txt('K'), txt('('), txt('1−'), SUM(), var('P', 'k', '2'), txt(')'), gap=.1), 'K−1'))
f_Z = lambda: F(var('Z', 'i'), txt('='), frac(F(XI(), txt('−'), XB()), SX()))
f_sxy = lambda: F(var('s', 'xy'), txt('='), frac('1', 'n'), SUM(), F(txt('('), XI(), txt('−'), XB(), txt(')('), var('y', 'i'), txt('−'), var('y', bar=True), txt(')'), gap=.1))
f_r = lambda: F(var('r', 'xy'), txt('='), frac(var('s', 'xy'), F(SX(), var('S', 'y'))))
f_b2 = lambda: F(var('b', sup='2'), txt('='), frac('1', 'n'), SUM(), var('n', 'j'), F(txt('('), var('y', 'j', bar=True), txt('−'), var('y', bar=True), txt(')²'), gap=.1))
f_W2 = lambda: F(var('W', sup='2'), txt('='), frac(F(var('n', 'A'), var('W', 'A', '2'), txt('+'), var('n', 'B'), var('W', 'B', '2')), F(var('n', 'A'), txt('+'), var('n', 'B'))))
f_eta = lambda: F(var('η', sup='2'), txt('='), frac(var('b', sup='2'), var('S', sup='2')), txt('='), txt('1−'), frac(var('W', sup='2'), var('S', sup='2')))
f_k = lambda: txt('k=log₂n+1', 3)

# ---------------------------------------------------------------- content (md wording kept)
H = lambda t: ('H', t)
H2 = lambda t: ('H2', t)
P = lambda t, k=1.0: ('P', t, k)
FM = lambda fn: ('F', fn)
FG = lambda fn: ('G', fn)

CONTENT = [
    H('Society 5.0'),
    P('「サイバー空間とフィジカル空間を高度に融合させたシステムにより、経済発展と社会的課題の解決を両立する人間中心の社会」'),
    H2('より良い意思決定が目的'),
    P('データ収集 → 分析 → 判断 → 行動 → 新たなデータ → …(循環します)'),
    FG(fig_iot),
    P('デジタル化:あらゆるデータが記録可能になった 計算資源の向上:膨大なデータを高速に処理できるようになった 意思決定の複雑化:人の直感だけでは対応できない課題が増えた'),
    FG(fig_venn),
    P('計算×数学・統計:機械学習(現場の知識不足) 計算×専門知識:危険地帯(統計的根拠不足) 数学・統計×専門知識:従来の研究(計算技術不足) 3つの重なりがデータサイエンス'),
    H('分析設計'),
    P('分析設計とはデータを使って問題を解決するために、何を、どのように分析し、その結果をどう活用するかを設計すること'),
    P('(1) 目的の設定:何を解決したいのか (2) データの収集・加工:必要なデータを集め、分析できる状態にする (3) 手法の選択:どの統計・分析手法を使うか決める (4) 活用:分析結果を意思決定に使う'),
    H('ビジネスでの使い方'),
    P('a. 仮説検証:仮説を立て、その仮説が正しいか検証すること。例えば、YouTubeで「サムネイルを変更すると再生数が増えるのではないか」という仮説を立て、実際のデータで確認'),
    P('b. 知識発見:データの中から、経験則や意思決定に役立つ洞察を見つけること。'),
    P('c. 原因究明:変化が起きたとき、その原因となる事象を解明すること。ランダム化比較試験 対象をランダムに2つ以上のグループに分けて、異なる実験を行って結果を比較 (相関だけでは因果を断定できない)'),
    P('d. 判断支援:a〜cで得られた知見をもとに、人間の意思決定を支援すること。'),
    P('e. 計画策定:中長期の計画を策定すること。例えば、販売データをもとに、来年の生産計画やキャンペーンを計画すること'),
    P('f. 活動代替:単純作業やパターンが決まっている作業を機械で自動化し、全体の効率を向上させること。'),
    P('g. 仮説検証サイクル(PDCA):plan do check action'),

    H('データと尺度水準'),
    FG(fig_students),
    P('変数(variable)が項目 データ(data)が、実際に得られた値 連続データ 睡眠時間 無限に値が存在 離散データ 人数とか。 N変数データ (N)に数が入る さっきのやつだと、3変数データ'),
    P('尺度水準:データの性質に基づいてデータを分類する基準のこと A~AB型を1,2,3,4ってして、平均とってもなんか意味ある？'),
    FG(fig_scale),
    P('名義尺度 分類するだけのデータ 順序関係なし 血液型とか、地名とかも。同じか違うかだけに価値がある。 順序尺度 順序付けが必要なデータ。大小関係に価値がある。数値の差は一定じゃない。'),
    FG(fig_satisfaction),
    P('顧客満足度とかは数値だけど、1から4が1から2の2倍とは限らない 学年とか、順位とかも。'),
    P('間隔尺度 違いが重要なデータ。差に意味がある 比率計算にはできない 摂氏温度とか。20℃は10℃の2倍の温度というのは価値なし。0℃も温度が存在しないという意味ではないからです。時刻、西暦、偏差値とかがそう'),
    P('比率尺度 値の差にも比率にも意味があり、「0が何もない」を表す。重さ、経過時間、身長、湿度 0kgは重さなし。1kgと2kgは2倍'),
    H2('間隔尺度と比率尺度の違いは、意味のある絶対的なゼロが存在するかどうか'),

    H('代表値'),
    P('複数のデータの特徴を、一つの数値で代表させたもの 算術平均 = 相加平均 普通の平均 足し算で積み重なるデータに使用する'),
    P('幾何平均 = 相乗平均 割合で変化するものの平均 会社の売上が1年目に2倍、2年目に0.5倍 算術平均だと、'),
    FM(lambda: F(f_geo_ex(), txt('  正しくは  '), f_geo_ok())),
    P('これだと、実際には成長してないのに年間1.25倍成長していることになる'),
    FM(f_G),
    P('調和平均 逆数の算術平均のその逆数 自転車で、行きは時速20km、帰りは時速60kmで同じ距離を移動 普通の算術平均では、'),
    FM(f_h_bad),
    P('調和平均を使えば、と、正しい平均速度が来る。保存したいものが逆数とき。'),
    FM(f_h_ok),
    FM(f_H),
    P('正の数に対して 調和平均 ≤ 幾何平均 ≤ 算術平均'),
    P('順序統計量 データを大きさ順に並び替えて得られる統計量 Xme 中央値 大きい順の中の真ん中の値(奇数nは(n+1)/2番目、偶数nは中央2値の算術平均) Xmo 最頻値 範囲(Range) 最大値-最小値'),
    P('5数要約 中央値がデータを半分に。25パーセントごと分ける。最小値 → 第一四分位数(25%) → 第二四分位数(中央値) → 第三四分位数(75%) → 最大値'),
    P('四分位範囲(IQR) データの中央50%がどれくらいの範囲に広がってる？ IQR=Q3−Q1  四分位偏差 QD はIQR/2'),

    H('散らばり'),
    P('偏差が基本。平均値から、どれくらい離れてる？ 偏差をそのまま平均すると、必ず0になる。だから、2乗or絶対値を取る方法'),
    FM(f_dev),
    P('2乗のバージョン 分散 偏差を二乗したものの平均 分散の問題は、2乗しちゃってよくわかんなくなる。だから、平方根を取る → 標準偏差'),
    FM(lambda: F(f_S2(), txt('   '), f_S())),
    P('絶対値を取ってみるバージョン 平均偏差 平均値からの距離の平均'),
    FM(f_MD),
    P('不偏分散 標本調査のときに、分散が小さくなりやすい性質を補正する。標本平均は、その標本の偏差の二乗和が最も小さくなる位置'),
    FM(f_U2),
    P('不偏標準偏差 不偏偏差にルートを取ったもの(その平方根自体は母標準偏差の不偏推定量ではない)'),
    P('ネズミ:平均体重20 g 標準偏差5 g vs ゾウ:平均体重4,000 kg 標準偏差200 kg ゾウにとっての200kgの差と、ネズミにとっての5gはどっちが大きい？ → 変動係数 標準偏差を平均値で割る (平均0では定義できない)'),
    FM(f_CV),
    H('質的変動指数'),
    FM(f_IQV),
    P('K カテゴリ(グループ)の数(K>1) Pk 各カテゴリが占める割合 範囲は0~1。1種類に集中→0、均等→1'),
    P('標準化 平均が0,分散が1になるようにデータを変換すること。Zスコア 平均を引いて、標準偏差で割るだけ (Sx=0では不可)'),
    FM(f_Z),

    H('2変数のデータ'),
    P('ここまでは1変数のデータに対してどう扱うか。今後は2変数のデータをどう扱うか 尺度水準の組み合わせによって変わってくる'),
    P('量的×量的 ex 身長と体重 共分散を使う。どのように一緒に変化するかを測る。'),
    FM(f_sxy),
    P('これがプラスだと、Aが上がればBも上がる。マイナスだと、Aが上がるとBは下がる。単位が変わるだけで共分散が変わるのが欠点 比較には不向き → ここで相関係数'),
    FM(f_r),
    P('共分散をそれぞれの標準偏差の積で割る。単位なし(無次元)となり、単位依存しなくなる。Zスコアの共分散ってこと。-1~1の量になる 線形関係のみしか測れない。曲線的な関係は正しく捉えられない。'),
    P('質的×量的 ex 学科ごとのテスト結果とか 群データが基本 データを質的データで分けたもの 群平均:各グループの平均 総平均:全データの平均 全分散:全データのばらつき 群内分散:各グループ内部のばらつき 群間分散:各グループの平均同士のばらつき'),
    FM(f_b2),
    P('n=全体の人数 nj=グループjの人数 yj=jグループの平均 y=全体の平均 群内分散＋群間分散＝全体分散 全体の群内分散'),
    FM(f_W2),
    P('相関比 質的データ(グループ分け)が量的データのばらつきをどれくらい説明できてる？っていうの指標'),
    FM(f_eta),
    P('S² 全分散 W² 群内分散 b² 群間分散 η² 相関比の二乗 0~1までの値になる。0で、グループ間の違いはなし。1で、グループによって、量的データの違いを完全に説明可能'),
    P('質的×質的 下の表だと、人数だけど、度数or比率でいい'),
    FG(fig_cross),
    P('期待度数は、それぞれの変数が独立であると考えて、各セルに期待される人数のこと リスク 要因に占める、ある事象が起きた確率 オッズ 要因の結果の比 発生した人数/発生しなかった人数'),

    H('可視化の目的'),
    P('一次分析:データをそのまま集計・可視化・要約すること(探索的分析(EDA)でも使用) データの傾向を見て、直感的に理解できる 誤解を避けるための正確な情報伝達 説得力を増すための視覚的表現 比較することができて、構成・分布・変化を見ることができる'),
    H('一変数で質的'),
    P('棒グラフ 比較 円グラフ 構成 全体に占める割合 帯グラフ 構成 複数のグループの構成比 パレート図 比較＋構成'),
    FG(fig_band),
    FG(fig_pareto),
    H('一変数で量的'),
    P('折れ線グラフ 変化・推移 温度とか ヒストグラム 分布 テストの点とか。棒グラフとの違いは、横軸が連続した数値の階級であること 階級数は k=log2 n+1 (nはデータ数)'),
    P('箱ひげ図 5数要約を使う。箱の長さは四分位範囲 バイオリンプロット ハコヒゲの進化 曲線で分布 左右対称'),
    FG(fig_box_violin),
    H('多変数'),
    P('質的:積み上げ棒グラフ 度数 層別帯グラフ 割合 モザイクプロット 性別×専攻分野 ヒートマップ 項目の組み合わせセルの数値の大小を色の濃淡で表現する 量的:散布図・散布図行列・対散布図・レーダーチャート'),
    H('不適切なデータの可視化'),
    P('一部分のみ拡大(データの切り取り) 目盛り幅が不均一 円グラフの形状や中心の位置の変更 立体グラフ 偏見を含むラベルの使用'),
    P('GIS : geographic information system 位置情報を活用し、地理空間情報を収集・管理・表示するシステム 活用分野:都市計画・防災 環境調査 マーケティング 交通'),

    H('ビッグデータとデータエンジニアリング'),
    P('データサイエンス:情報工学・統計学・専門分野の知識を組み合わせ、データの価値を見出し、意思決定の根拠を引き出す学問分野。 データエンジニアリング:大量のデータを管理し、分析可能な形に変換する技術や仕組み。→ データサイエンスの前段階。'),
    P('ICT:情報通信技術。ネットワークなどの通信技術を活用して情報を活用する技術の総称。→ 大量のデータ(ビッグデータ)が取得可能に。'),
    P('ビッグデータの特徴【3V】Volume(量)・Variety(多様性)・Velocity(速度)【5V＝3V＋以下の2つ】Veracity(正確さ)・Value(価値)'),
    P('収集方法 クローリング:インターネットを自動巡回して情報収集(広く浅く)。 スクレイピング:得られた情報から必要なデータを抽出。 オープンデータ:インターネット上で公開されているデータ。→ EBPM:証拠に基づく政策決定。'),
    P('データガバナンス 企業や組織が保有するデータを安全に効果的に活用するための仕組みやルール。 正確なデータを維持する。個人情報を安全に管理する。データ管理の責任を明確にする。組織内でルールを統一する。目的:価値の最大化・リスクの最小化。'),
    P('構造化データ:表形式(行・列)、検索・集計が容易。→ 関係データベース(RDB)で管理。 非構造化データ:形式が決まっていない。例:画像、動画、音、文章、SNS投稿。'),
    P('IoT:モノのインターネット化。 IoE:全てのもののインターネット化(人・データ・サービスも含む)。 IoA:能力のインターネット化。'),
    H('データ収集と加工'),
    P('データの収集 自分でデータを作る:アンケート・実験・観察。 他人のデータを使う:公開データ・スクレイピング・Webクローラー。 サンプリング:全体から一部を抽出し、分析対象を偏りなく選ぶ。'),
    P('データの問題 → データクレンジングによって処理する。 欠損値:あるべきデータが記録されていない。→ 削除・補完。 異常値:現実に起こり得ない値。→ 修正・削除。 外れ値:統計的に他の値から大きく外れた値。→ 除外・保持を判断。'),
    P('外れ値の検出 IQR: 下限 = Q1 - 1.5 × IQR 上限 = Q3 + 1.5 × IQR 標準偏差(±3σ): 下限 = 平均 - 3σ 上限 = 平均 + 3σ → 範囲外を外れ値(の候補)とする。'),
    P('バイアス 母集団を正しく反映していない偏り。サンプリングバイアス:標本抽出の偏り。 選択バイアス:対象の選択による偏り。 測定バイアス:測定方法による偏り。対策:幅広い属性を含めたデータの収集。公平性・代表性を意識する。'),
    P('データクレンジング:データの問題を処理して分析可能な状態に整える。 アノテーション:補足情報や説明を加える。 結合処理:共通するキーを用いて複数のデータを結合する。→ キーの不一致・重複データに注意。'),
    H('データ表現'),
    P('数値:整数・実数など。 文字:文字コードで表現。 画像:ピクセルごとの数値表現。 音声:波形を数値化。 1 byte = 8 bit n bit = 2^n 通りの表現が可能。 2^10 = 1,024 2^20 = 1,048,576'),
    P('文字 → 文字コード → バイト列 符号化:文字を数値(2進数)に変換すること。 ASCII:英数字・記号(A=65、B=66)。 JIS X 0208:日本語。 Unicode:国際的な文字コード規格。 Shift-JIS、UTF-8、UTF-16、UTF-32。'),
    H('数理最適化と意思決定'),
    P('数理最適化:制約条件の中で目的関数を最小化または最大化する方法。→ 最適な意思決定。 目的関数:最適化したいことに関する関数。 決定変数:目的関数への入力変数。 制約条件:守らなければならない条件。 連続最適化問題:決定変数が実数値を取り、連続的に変化可能。 離散最適化問題:解候補が離散的。代表例:組合せ最適化問題。'),
]


# ---------------------------------------------------------------- layout engine
TERMS = ['不偏標準偏差', '算術平均', '相加平均', '幾何平均', '相乗平均', '調和平均', '順序統計量', '中央値', '最頻値', '範囲(Range)',
         '5数要約', '四分位範囲(IQR)', '四分位偏差', '平均偏差', '標準偏差', '不偏分散', '群間分散', '群内分散', '全分散', '分散', '偏差', '変動係数',
         '標準化', 'Zスコア', '共分散', '相関係数', '群データ', '群平均', '総平均', '相関比', '期待度数', 'リスク', 'オッズ', '尺度水準',
         '名義尺度', '順序尺度', '間隔尺度', '比率尺度', '変数(variable)', 'データ(data)', '連続データ', '離散データ', '仮説検証サイクル',
         '仮説検証', '知識発見', '原因究明', '判断支援', '計画策定', '活動代替', '分析設計', 'ランダム化比較試験', '一次分析', '棒グラフ',
         '円グラフ', '帯グラフ', 'パレート図', '折れ線グラフ', 'ヒストグラム', '箱ひげ図', 'バイオリンプロット', '積み上げ棒グラフ',
         '層別帯グラフ', 'モザイクプロット', 'ヒートマップ', '散布図', 'レーダーチャート', 'データサイエンス', 'データエンジニアリング',
         'ビッグデータ', 'クローリング', 'スクレイピング', 'オープンデータ', 'EBPM', 'データガバナンス', '非構造化データ', '構造化データ',
         'IoT', 'IoE', 'IoA', 'サンプリング', 'データクレンジング', '欠損値', '異常値', '外れ値', 'バイアス', 'アノテーション', '結合処理',
         '符号化', '数理最適化', '目的関数', '決定変数', '制約条件', '連続最適化問題', '離散最適化問題', 'GIS', 'ICT']
HANG = '、。，．）」』】,.)！？:'


def mark(text):
    """Return (text, underline spans) for key terms (longest first, no overlaps)."""
    taken = [False] * len(text)
    spans = []
    for term in sorted(TERMS, key=len, reverse=True):
        start = 0
        while (i := text.find(term, start)) >= 0:
            if not any(taken[i:i + len(term)]):
                spans.append((i, i + len(term)))
                for j in range(i, i + len(term)):
                    taken[j] = True
            start = i + len(term)
    return text, sorted(spans)


def wrap(text, size, width):
    """width may be a number or a function of the line index (for text beside a side formula)."""
    W = width if callable(width) else (lambda i: width)
    lines, part, start = [], '', 0
    for idx, c in enumerate(text):
        if not part:
            if c.isspace():
                continue
            part, start = c, idx
            continue
        trial = part + c
        w = W(len(lines))
        if txt(trial, size).width > w + .001:
            if c in HANG and txt(trial, size).width < w + size * .9:
                part = trial
                continue
            lines.append((part, start))
            part, start = ('', idx) if c.isspace() else (c, idx)
        else:
            part = trial
    if part.strip():
        lines.append((part, start))
    return lines


def underline(part, start, spans, size):
    out = []
    for a, b in spans:
        i, j = max(a, start) - start, min(b, start + len(part)) - start
        if j <= i:
            continue
        x0 = (txt(part[:i], size).width + .25) if i > 0 else 0
        x1 = txt(part[:j], size).width
        out.append([(x0, size * 1.04 + .1), (x1, size * 1.04 + .1)])
    return out


FIGK = 0.72          # figures and tables are drawn this much smaller than their natural size
FMK = 0.8            # formulas likewise (relative to the 3 mm formula base)


def scale_box(b, k):
    return Box(b.width * k, b.height * k, [[(x * k, y * k) for x, y in path] for path in b.paths], b.alt)


def build_units(size, leading_k):
    units, late = [], False
    items = list(CONTENT)
    i = 0
    while i < len(items):
        item = items[i]
        i += 1
        kind, val = item[0], item[1]
        if kind in ('H', 'H2'):
            late = late or val.startswith('ビッグデータ')
            hs = size + (.6 if kind == 'H' else .25)
            paths, y = [], 0
            for ln, _ in wrap(val, hs, COL_W):
                put(paths, txt(ln, hs).paths, 0, y)
                y += hs * 1.25
            if kind == 'H':
                paths.append([(0, y - .15), (COL_W, y - .15)])
            units.append({'h': y + .5, 'paths': paths, 'keep': True, 'gap': 1.2, 'alt': val})
        elif kind == 'P':
            sz = size * (0.9 if late else 1.0) * item[2]
            lead = sz * leading_k
            side = []
            while i < len(items) and items[i][0] == 'F':        # formulas that follow belong beside this paragraph
                side.append(scale_box(items[i][1](), FMK * sz / 2.8))
                i += 1
            wide = [b for b in side if b.width > COL_W * .52]
            side = [b for b in side if b.width <= COL_W * .52]
            text, spans = mark(val)
            sw = max((b.width for b in side), default=0)
            sh = sum(b.height for b in side) + .8 * max(len(side) - 1, 0)
            nside = math.ceil((sh + .4) / lead) if side else 0
            wf = (lambda n: (COL_W - sw - 1.6) if n < nside else COL_W)
            lines = wrap(text, sz, wf)
            para = []
            for n, (ln, st) in enumerate(lines):
                para.append((0, n * lead, list(txt(ln, sz).paths) + underline(ln, st, spans, sz)))
            h = max(len(lines) * lead, sh + .4)
            for n, (x, y, ps) in enumerate(para):
                paths = ps
                units.append({'h': lead, 'paths': paths, 'keep': False, 'gap': 0, 'alt': lines[n][0]})
            if side:                                   # draw the formulas as part of the paragraph's first line unit
                yy = 0
                fp = []
                for b in side:
                    fp += shifted(b.paths, COL_W - sw + (sw - b.width) / 2, yy)
                    yy += b.height + .8
                # make the paragraph one block so lines and formula stay together
                block = {'h': h, 'paths': [], 'keep': False, 'gap': 1.2, 'alt': text[:30]}
                for n, (x, y, ps) in enumerate(para):
                    block['paths'] += shifted(ps, 0, y)
                block['paths'] += fp
                del units[len(units) - len(lines):]
                units.append(block)
            else:
                units[-1]['gap'] = 1.2
            for b in wide:
                units.append({'h': b.height + .8, 'paths': shifted(b.paths, (COL_W - b.width) / 2, .3), 'keep': False, 'gap': 1.0, 'alt': b.alt})
        elif kind == 'F':                              # formula with no paragraph before it
            b = scale_box(val(), FMK * size / 2.8)
            units.append({'h': b.height + .8, 'paths': shifted(b.paths, (COL_W - b.width) / 2, .3), 'keep': False, 'gap': 1.0, 'alt': b.alt})
        elif kind == 'G':
            b = scale_box(val(COL_W / FIGK, size / FIGK), FIGK)
            if b.width > COL_W + .01:
                raise PlotNoteError(f'Too wide for the column: {b.alt} {b.width:.1f}mm')
            units.append({'h': b.height + .8, 'paths': shifted(b.paths, 0, .3), 'keep': False, 'gap': 1.0, 'alt': b.alt, 'float': True})
    return units


def flow(units):
    """Fill 8 column slots in reading order. A figure that does not fit is carried to the next column
    while the text after it fills the gap. Returns [(slot, y, unit)] and the number of units left over."""
    placed, slot, y = [], 0, TOP
    queue = list(units)
    held = []
    while queue or held:
        if held and y == TOP:                          # a new column starts with the held figure
            u = held.pop(0)
            if y + u['h'] > BOTTOM + .01:
                return placed, len(queue) + len(held) + 1
            placed.append((slot, y, u))
            y += u['h'] + u['gap']
            continue
        if not queue:                                  # only held figures remain: open a new column
            slot, y = slot + 1, TOP
            if slot >= 8:
                return placed, len(held)
            continue
        u = queue[0]
        need = u['h'] + (queue[1]['h'] if u['keep'] and len(queue) > 1 else 0)
        if y + need <= BOTTOM + .01:
            placed.append((slot, y, u))
            y += u['h'] + u['gap']
            queue.pop(0)
        elif u.get('float') and len(held) < 2:
            held.append(queue.pop(0))
        else:
            slot, y = slot + 1, TOP
            if slot >= 8:
                return placed, len(queue) + len(held)
    return placed, 0


def make_tiles(placed):
    tiles = [Page(TILE_W, TILE_H) for _ in range(4)]       # face1-top, face1-bottom, face2-top, face2-bottom
    for slot, y, u in placed:
        side, col, half = slot // 4, (slot % 4) // 2, slot % 2
        tile = tiles[side * 2 + half]
        for p in shifted(u['paths'], COL_X[col], y):
            tile.strokes.append(Stroke(p, 'note:' + u['alt'][:40]))
    for t in tiles:
        t.validate()
    return tiles


def run(size, leading_k):
    units = build_units(size, leading_k)
    placed, over = flow(units)
    used = sum(u['h'] + u['gap'] for u in units)
    return units, placed, over, used


def a4_preview(tiles, out):
    import pymupdf
    pt = 72 / 25.4
    doc = pymupdf.open()
    for face in (0, 1):
        page = doc.new_page(width=A4_W * pt, height=A4_H * pt)
        shape = page.new_shape()
        shape.draw_rect(pymupdf.Rect(0, 0, A4_W * pt, A4_H * pt))
        shape.finish(color=(.75, .75, .75), width=.4)
        for half in (0, 1):
            ox, oy = PAPER_X0, WIN_Y[half]
            for s in tiles[face * 2 + half].strokes:
                shape.draw_polyline([((x + ox) * pt, (y + oy) * pt) for x, y in s.points])
            shape.finish(color=(0, 0, 0), width=.25 * pt, lineCap=1, lineJoin=1, closePath=False)
        shape.commit()
    doc.save(out)
    doc.close()


def pass_profile(half, air_note=''):
    """Machine profile for pass 1 (A4 top edge on the plate's back edge) or pass 2 (bottom edge on the front edge)."""
    from dataclasses import replace
    from plotnote.profile import Profile
    base = Profile.load(PROVEN_PROFILE)
    bed_y_of_window_bottom = BED_Y - (WIN_Y[0] + TILE_H) if half == 0 else A4_H - (WIN_Y[1] + TILE_H)
    return replace(base, paper_x=PAPER_X0 - (A4_W - BED_Y) / 2,
                   paper_y=bed_y_of_window_bottom, paper_width=TILE_W, paper_height=TILE_H,
                   nozzle_min_x=NOZZLE_MIN, nozzle_max_x=NOZZLE_MAX, nozzle_min_y=NOZZLE_MIN, nozzle_max_y=NOZZLE_MAX,
                   calibration_notes=base.calibration_notes + ' A4 two-pass window; nozzle range beyond the calibrated 40-150 is NOT verified.')


def export_gcode(tiles, out, air_mm=5):
    from plotnote.gcode import generate
    out.mkdir(parents=True, exist_ok=True)
    names = ['face1-pass1', 'face1-pass2', 'face2-pass1', 'face2-pass2']
    rows = []
    for i, (tile, name) in enumerate(zip(tiles, names)):
        prof = pass_profile(i % 2)
        prof.save(out / f'{name}-profile.json')
        for tag, air in (('', 0), ('-air', air_mm)):
            text, eff, report = generate(tile, prof, homed=True, air_mm=air)
            (out / f'{name}{tag}.gcode').write_text(text)
        draw = sum(math.dist(a, b) for st in tile.strokes for a, b in zip(st.points, st.points[1:]))
        travel = sum(math.dist(tile.strokes[k].points[-1], tile.strokes[k + 1].points[0]) for k in range(len(tile.strokes) - 1))
        minutes = draw / prof.draw_feed + travel / prof.travel_feed + len(tile.strokes) * 2 * (prof.lift_z - prof.draw_z) / prof.z_feed
        ys = [prof.machine_point(*pt)[1] for st in tile.strokes for pt in st.points]
        xs = [prof.machine_point(*pt)[0] for st in tile.strokes for pt in st.points]
        rows.append({'tile': name, 'strokes': len(tile.strokes), 'draw_mm': round(draw), 'minutes_est': round(minutes, 1),
                     'nozzle_x': [round(min(xs), 1), round(max(xs), 1)], 'nozzle_y': [round(min(ys), 1), round(max(ys), 1)],
                     'validate': str(report)[:120]})
    (out / 'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--personal-font', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--size', type=float, default=3.5)
    ap.add_argument('--leading', type=float, default=1.3)
    ap.add_argument('--allow-overflow', action='store_true', help='draw what fits and report where the content is cut off')
    ap.add_argument('--light', action='store_true', help='skip the heavy per-tile SVG/PNG/HTML export (preview PDF only)')
    ap.add_argument('--fit', action='store_true', help='shrink the size in 0.1 mm steps until everything fits')
    a = ap.parse_args()
    font = json.loads(a.personal_font.read_text())
    literals = ''.join(re.findall(r"'([^'\n]*)'", Path(__file__).read_text()))
    fallback = {c for c in set(literals) | set(''.join(it[1] for it in CONTENT if isinstance(it[1], str)))
                if not c.isspace() and c.isprintable() and c not in font['glyphs']}
    while True:                                                 # collect characters the personal font lacks
        try:
            with use_personal_font(font, ''.join(sorted(fallback))):
                size = a.size
                while True:
                    units, placed, over, used = run(size, a.leading)
                    print(f'size {size:.1f} mm: overflow {over} units, content {used:.0f} mm of {8 * (BOTTOM - TOP):.0f} mm', flush=True)
                    if over == 0 or not a.fit or size <= 2.2:
                        break
                    size = round(size - .1, 1)
                if over and not a.allow_overflow:
                    raise SystemExit(f'Does not fit at {size:.1f} mm ({over} units over)')
                if over:
                    cut = placed[-1][2]['alt']
                    print(f'CUT OFF after: {cut[:40]}  ({over} of {len(units)} units not drawn)')
                tiles = make_tiles(placed)
            break
        except PlotNoteError as e:
            m = re.search(r"Personal glyph missing: '(.)'", str(e))
            if not m:
                raise
            fallback.add(m.group(1))
    a.output.mkdir(parents=True, exist_ok=False)
    if not a.light:
        write_artifacts(tiles, a.output / 'tiles', bn.PEN)
    a4_preview(tiles, a.output / 'a4-both-sides.pdf')
    rows = export_gcode(tiles, a.output / 'gcode')
    for r in rows:
        print(r, flush=True)
    (a.output / 'layout.json').write_text(json.dumps({
        'a4_mm': [A4_W, A4_H], 'tile_mm': [TILE_W, TILE_H], 'window_a4_y_mm': list(WIN_Y), 'window_a4_x_mm': PAPER_X0,
        'font_size_mm': size, 'leading_k': a.leading, 'standard_font_fallback': ''.join(sorted(fallback)),
        'tiles': ['面1・上', '面1・下', '面2・上', '面2・下']}, ensure_ascii=False, indent=1))
    (a.output / 'note-content.md').write_text('\n'.join(u['alt'] for _, _, u in placed))
    print(json.dumps({'size_mm': size, 'fallback_chars': ''.join(sorted(fallback)),
                      'strokes': [len(t.strokes) for t in tiles]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
