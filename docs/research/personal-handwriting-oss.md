# Goodnotes個人筆跡をPlotNoteへ取り込むためのOSS調査

調査日：2026-11-25。公開一次資料・ソース・LICENSEを確認。個人バックアップの解析結果は親エージェント側の別調査。本書の候補について、学習・推論・アーカイブ変換は実行していない。公開サイトに個人データを送信していない。

## 判断

今回の目的では、まず**本人の実際のペン軌跡を文字・短語ごとに集める、複数見本付きのストローク字庫**を作ることを推奨する。TTF/OTFはデジタル文書向けの派生出力にできる。プロッターはJSON/SVGの中心線を直接使う構成が適する。Goodnotes解析器は既に存在するが、任意のノートから日本語全文字の正しい字庫を無人で完成させる既製OSSは、今回確認した範囲では見つからない。

これは下記資料を踏まえた技術判断であり、個人のバックアップで全字の抽出・認識が成功するという保証ではない。

## 比較

| 候補 | 確認した入出力 | 日本語への適用と今回の位置付け | ライセンスの確認 |
|---|---|---|---|
| [parser-for-goodnotes](https://github.com/Kaih1825/parser-for-goodnotes) | Goodnotes 5/6 `.goodnotes` → JSON、SVG等。Protobuf、Apple LZ4、TPLから座標・筆圧等を読む。 | 筆跡形状は言語に依存しない抽出元。文字認識・文字切り分けを自動完成するものではない。まず少数ページで元画面との比較が必要。 | [LICENSE](https://github.com/Kaih1825/parser-for-goodnotes/blob/main/LICENSE)はMIT。 |
| [goodparse](https://github.com/franzthiemann/goodparse) | `.goodnotes` → Xournal++、Excalidraw、PDF。Python APIに `stroke.points = [(x,y,width),…]`。 | 生の中心線座標を取り出す試作に合う。抽出成功率とストローク順序は実データで検証する。 | [LICENSE](https://github.com/franzthiemann/goodparse/blob/main/LICENSE)はGPLv3。一方、調査時の`pyproject.toml`はMIT表記で矛盾する。MITとは断定せず、統合・配布前に確認する。 |
| [FontForge](https://github.com/fontforge/fontforge) | SVG/EPSの字形輪郭を取り込み、TTF/OTF等を作成・編集。 | 収集済み文字をインストール用フォントへまとめる段階に有効。未知文字の本人風生成や筆順の推定は別工程。 | [LICENSE](https://github.com/fontforge/fontforge/blob/master/LICENSE)による全体はGPLv3以降。多くの部品はBSD等。 |
| [DM-Font](https://github.com/clovaai/dmfont) | 少数の参照字形画像＋内容 → 字形画像。実験・公開チェックポイントは韓国語手書きとタイ語印刷。 | 「少数見本で全文字」の研究例。ただし完全な部品合成文字向けで、漢字向けには修正が必要と統合リポジトリも説明。日本語へそのまま導入する候補にはしにくい。 | READMEはMIT。ただしFUNIT由来`modules.py`を例外として明記。モデル・訓練フォントの条件も別途確認。 |
| [LF-Font](https://github.com/clovaai/lffont) / [MX-Font](https://github.com/clovaai/mxfont) | 少数の参照字形から未収集字の見た目を合成。MXの公式`eval.py`は各字をPNG保存。 | 漢字の欠字を本人風に補う研究候補。中国語中心の字形・部品データ、日本語かな・新字体への適応と評価が要る。プロッター用軌跡は別途必要。 | 両方のLICENSEはMIT型許諾。元フォント・学習データの利用条件とは分けて確認。 |
| [DeepVecFont-v2](https://github.com/yizhiwang96/deepvecfont-v2) | TTF→FontForge SFD等で作ったデータからSVGを生成。英語・中国語のチェックポイントあり。 | ベクター出力だが、フォント輪郭を学習したもの。人が運筆した中心線・筆順とは区別する必要がある。日本語個人筆跡を直接プロットする第一候補ではない。 | コードはMIT。READMEは使用中国語フォントにFounderの商用許諾が別途必要と記載。 |
| [DeepWriting](https://github.com/emreaksan/deepwriting) | 座標差・ペン上げ等の系列を生成し、文字内容と筆跡スタイルを分離するC-VRNN。 | 方式は目的に近い。ただし公式設定は70文字アルファベット、英語/IAM由来。日本語用の文字ラベル・文字境界・多数の軌跡対を整備して再学習する研究開発になる。 | コードはMIT。公式データセットは[CC BY-NC-SA 4.0＋追加条件](https://files.ait.ethz.ch/projects/deepwriting/license.pdf)。コード許諾とデータ許諾を混同しない。 |
| [sjvasquez/handwriting-synthesis](https://github.com/sjvasquez/handwriting-synthesis) | RNNによるペン位置差・ペン上げの生成、SVG書き出し。スタイルのprimingあり。 | 英語筆記体の参考実装。`drawing.py`の文字一覧に漢字・かなはなく、現状の重みで日本語は書けない。 | 調査時のルートに明示的LICENSEを確認できず、MIT等とは扱わない。 |
| [Handwriting Stroke Transfer](https://github.com/ZhrZhr2022/handwriting-stroke-transfer) | 標準漢字筆順を本人風TTFのシルエットへ合わせ、逐画JSON・medianを持つ字庫へ変換。 | 欠字を画像/輪郭で生成した後、筆順付き中心線へ戻す方法として有望。ただし本人の実際の運筆ではなく標準筆順の変形。既定は中国語3500字で、かな・日本語字形への対応が要る。実機品質は未確認。 | [LICENSE](https://github.com/ZhrZhr2022/handwriting-stroke-transfer/blob/main/LICENSE)はMIT。筆順データと入力TTFの条件は別。 |

各入出力の根拠：[Goodnotes解析README](https://github.com/Kaih1825/parser-for-goodnotes#readme)、[goodparse API例](https://github.com/franzthiemann/goodparse#library)、[FontForge SVG取込](https://fontforge.org/docs/tutorial/importexample.html)、[FFG公式比較・データ形式](https://github.com/clovaai/fewshot-font-generation#readme)、[MX画像保存実装](https://github.com/clovaai/mxfont/blob/main/eval.py)、[DeepVecFont-v2の前処理と出力](https://github.com/yizhiwang96/deepvecfont-v2#readme)、[DeepWriting設定](https://github.com/emreaksan/deepwriting/blob/master/config.py)、[sjvasquez文字一覧](https://github.com/sjvasquez/handwriting-synthesis/blob/master/drawing.py)、[Stroke Transfer説明](https://github.com/ZhrZhr2022/handwriting-stroke-transfer#readme)。

## 抽出で注意する点

`parser-for-goodnotes`のSVG表示は、筆圧から太さを付けた閉じたリボン輪郭を生成する。これを通常の線としてプロットすると袋文字になる。今回必要なのはJSON/内部モデルの点列であり、表示用SVGの輪郭ではない。[作者による復号・SVGリボンの説明](https://github.com/Kaih1825/parser-for-goodnotes#motivation--under-the-hood)

`goodparse`はPython APIで点列を公開するので、Xournal++/PDFへ変換してから戻す必要がない。書き写し再生と、任意文章を本人の字体で生成することは別で、後者では「どのストロークが何の文字か」の対応付けが必要になる。[API例](https://github.com/franzthiemann/goodparse#library)

元データに座標・筆圧があっても、描画レイヤー順が実時間の筆順と一致するとは未検証。消しゴム・移動/複製・変形・蛍光ペンの扱いを確認する。タイムスタンプや認識結果が全ページに残っているとも仮定しない。[parser-for-goodnotesの観測済み対応範囲](https://github.com/Kaih1825/parser-for-goodnotes#features)

## 推奨する段階

以下はOSSの入出力を踏まえた実装案。

1. 少数の読みやすいGoodnotesページで、背景を除いた点列を抽出。元ページの筆跡と重ね、欠け・余計な線・順序・移動後座標を検証する。
2. 文字列と軌跡を対応付ける確認画面を作る。Goodnotes内の検索/認識結果が使える場合は候補として利用し、位置対応の精度を測る。かなの濁点、後から足した点、部首、数式を安易に別文字と判定しない。
3. 同じ文字を複数例収集。平均化して癖を消すより、実際の見本を複数保存して使い分ける。連結が強いかなは短語単位も残す。
4. 選んだ軌跡を極端に正規化せず、文字ごとの幅・高さ・字間・行の傾きを測る。本人のばらつきの分布を使い、無関係なランダム変形を減らす。
5. まず次のノートで必要な文字について、既存見本によるカバー率を出す。未収集字だけ追加採取する。かな・数字・頻出漢字から着手し、日本語全文字の完成を最初の条件にしない。
6. それでも不足する文字は、既存KanjiVG等のフォールバックを明示する。本人風欠字の自動生成は、画像生成＋標準中心線フィット、または部品/軌跡モデル学習の別実験に分ける。
7. 正規化した中心線字庫をPlotNoteの描画データとする。デジタル閲覧用の個人TTF/OTFが欲しい場合は、同じ見本から輪郭を作ってFontForge等へ渡す。元の点列を保持し、TTFから運筆を復元する往復を避ける。

## どこまでが現実的か

- **最も確度が高い**：バックアップから実際に書いた字を抽出し、その文字を別の文章で再利用する。本人の字形を保つため、単なるフォントの回転より根本的に改善できる。
- **実装上の主要課題**：日本語の文字境界とUnicodeラベルの対応、同じ字の複数例の選別、元ノートにない字の網羅。
- **研究開発**：数枚の自由記述ノートだけから、本人が一度も書いていない日本語文字をすべて自然な運筆で生成すること。既存OSSの「少数見本」デモを、そのままこの条件の実証と解釈しない。
- **物理的な限界**：Goodnotesの可変筆圧・太さが取れても、現在のボールペン＋ばねホルダーではデジタルインクと同じ濃淡の再現を前提にしない。まず形・つながり・字間・運筆の個性を移す。

## 実施範囲

この調査では個人データを公開サービスへアップロードせず、モデル学習・大規模フォント生成・プリンター実行も開始していない。Goodnotes解析器の動作確認は親エージェントのローカル調査結果を併記して最終判断する。

## このバックアップでの実測結果

ローカル検証日：2026-11-25。元の`~/Downloads/GoodNote_BackUp_ALL.zip`は変更していない。外部サービスにバックアップや抽出物を送信していない。公開パーサーのソースを読み、インストールせずに調査用のパスから実行した。

- 外側ZIPは約2.4GiB、102個の`.goodnotes`原本を含む。PDFだけの書き出しではない。
- `Math Self`：5ページ、2,271ストローク、173,882座標点を復号。
- `Health`：保存されたページメンバー33個のうち、削除マーカー10個を除く23ページ、10,173ストローク、700,661座標点を復号。
- 2冊合計28ページ、12,444ストローク、874,543座標点。これは全102冊の総数ではない。
- 背景・貼付画像を外し、元の中心線と色からPNG/SVGを再描画した。数学の式、漢字・かな・英数字の本人の崩れた字形を視覚確認できた。全ページの完全一致を検証したものではない。
- タイトル「生活習慣病」を目視で転記し、5文字を手動の範囲指定で切り出した。文字ごとの縦横比と連結した画を保った最小字庫・比較画像を作成。各1見本のみで、任意文を網羅する完成フォントではない。
- `search/`内には日本語らしいUTF-8文字列が多数あるが、誤認識らしきものも含む。文字ボックス／ストロークIDとの正確な対応は未検証。学習用の正解ラベルとはまだ扱えない。
- 抽出パーサーの`Page.strokes`は描画レイヤー順。試作の5文字も保存順を保っただけで、人間の実時間の筆順を復元したとは主張しない。各線内の点列は維持。今後、元オブジェクトの順序情報等を検証する必要がある。

検証の再実行：`PlotNote/.venv/bin/python PlotNote/output/handwriting-research/probe_archive.py`。手動5文字試作：`PlotNote/.venv/bin/python PlotNote/output/handwriting-research/make_glyph_proof.py`。どちらもプリンター操作を行わない。

ローカル出力：

- `../../output/handwriting-research/archive-probe.json`：件数、ソーススナップショットのSHA256、サンプル内訳。
- `../../output/handwriting-research/japanese-strokes.svg` / `.png`：本人の日本語筆跡だけを再描画したページ。
- `../../output/handwriting-research/personal-stroke-proof.json`：5文字の中心線見本。ラベルは手動、筆順未検証の注記付き。
- `../../output/handwriting-research/personal-vs-standard.svg` / `.png`：従来字形と本人の字形の比較。上下で同じ「生活習慣病」。

**この実測を踏まえた結論**：本人が実際に書いた字形をPlotNoteで再利用する道筋は確認できた。次に必要なのは大きなモデルの学習より先に、文字・短語の切り分けとラベル確認、複数見本の収集、必要な文章に対する文字カバー率の測定である。TTF/OTF作成は別の出力工程として可能だが、プロッターには元の中心線見本を使う。未出現の漢字を本人風の自然な運筆で補う部分は別途検証する。
