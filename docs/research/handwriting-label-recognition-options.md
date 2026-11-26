# Goodnotes 実筆跡の単字ラベル認識候補

調査日: 2026-11-25。調査のみ。モデル実行・インストール・画像送信・学習・課金処理はしていない。文字生成は対象外。

## 結論

最初の候補は **LT8/japanese-handwriting-onnx による孤立単字分類**。文章の意味や筆順を入力しないため、無意味に並べた漢字と、筆画間の時系列が未証明な Goodnotes データに適する可能性がある。ただし「正しく一文字を切り出せたか」は別問題であり、今回の本人筆跡での精度は未検証。既存の目視承認済み文字で先に盲検評価し、その後で未確認見本へ広げる。

## 1. 画像型: LT8 Japanese Handwriting ONNX

- ResNet 単字分類器。3,082 クラス（JIS 第1水準漢字2,965字＋かな）。ETL9G/ETL6 学習、ETL8G は評価用。書き順不要。小書きかな・第2水準漢字・英数字・句読点は対象外で、二/ニ等は文脈なしで決められない。
- 作者申告: 筆者分離テスト top-1 99.79%、未学習 ETL8G 98.98%。CPU 3.2 ms/字も作者測定であり、Goodnotes やこの Mac での実証ではない。
- 入力は128×128のグレースケール。縦横比を変えず正方形へ余白追加。出力 logits から top-k と softmax を得られる。作者の棄却閾値0.7は、そのまま本データの保証には使わない。[モデルカード](https://huggingface.co/LT8/japanese-handwriting-onnx)

実際の配布一覧に fp16 ONNX **15.2 MB**、int8 **11.4 MB**、fp32 **30.2 MB**、`labels.json`、`confusable.json`、`predict.py`、ブラウザ例を確認。重み・推論例は入手可能だが、この配布一覧には完全な学習ソースや独立した LICENSE ファイルは見当たらない。[配布ファイル](https://huggingface.co/LT8/japanese-handwriting-onnx/tree/main)

ONNX Runtime は macOS/Arm に CPU パッケージを案内しているため、Mac でのローカル推論経路がある。実行は未確認。クラウドAPIの従量料金は不要で、電力・セットアップ時間は別。[ONNX Runtime 公式](https://onnxruntime.ai/docs/get-started/with-python.html)

カードのライセンス表示は独自の `etl-character-database`。AIST 原データは無料使用可だが、データ自体の無断再配布は禁止。これを MIT と読み替えたり、重み・推論コードまで自由再配布可と断定したりしない。原データの取得・再学習は初回推論に不要。[ETL 公式使用条件](https://etlcdb.db.aist.go.jp/download2/)

**運用上の推論:** 対象外の記号や複数字画像も必ず3,082クラスのどれかへ寄せる構造なので、高い softmax だけで正解と断定しない。小書きかな、同形異字は元ページの位置・周囲の文字を併用する。中国語の分類器へ置き換えて日本語字形差を増やすより、日本語 ETL モデルから始める方が本用途に直接合う。

## 2. 軌跡型: ML Kit Digital Ink

公式の日本語対応モデルを使い、端末へモデルを取得後はオフライン。入力は時刻付き点列を含むストローク列。公式SDKは Android/iOS 向けで、Mac の Python バッチとして直接使える製品ではない。[概要](https://developers.google.com/ml-kit/vision/digital-ink-recognition/)・[言語一覧](https://developers.google.com/ml-kit/vision/digital-ink-recognition/base-models)

複数の文字列候補を順位付きで返すが、公式 Android ガイドの数値スコア提供は shape 分類器のみ。日本語の文字候補の確率が得られる前提は置かない。さらに公式は自然な筆順から外れると精度が落ちると明記。今回のレイヤー順をそのまま真の筆順と見なせないため、第一候補にはしにくい。[ストローク順序とスコア](https://developers.google.com/ml-kit/vision/digital-ink-recognition/android)

SDK/API は無料。モデル重みはSDK経由取得で、汎用ONNXとして公開されているわけではない。iOS/Android実装と端末での検証が必要で、開発作業量やこのデータでの精度は未測定。[ML Kit 公式の価格説明](https://developers.google.com/ml-kit/guides)

## 3. 軌跡型: Zinnia / Tegaki

Zinnia は C++/STL の SVM 認識器で、座標のストローク列から N-best と SVM スコアを返す。スコアは校正済み確率ではない。エンジンは new BSD、モデルは別途必要。[Zinnia 公式・API例](https://taku910.github.io/zinnia/index.html)

**筆順非依存ではない。** ソースではストローク番号 `sid` ごとの特徴と、前ストローク終点から次ストローク始点への移動特徴を使う。順序を変えると入力特徴が変わることがコードから確認できる。[特徴抽出ソース](https://raw.githubusercontent.com/taku910/zinnia/master/zinnia/feature.cpp)

日本語モデルは Tegaki/Tomoe 系。Debian は `tegaki-zinnia-japanese` 0.3-3 のモデル・ソースを配布し、モデルのライセンスは LGPL-2.1+ と記載。正確な収録文字集合は使用するモデル実体で確認が必要で、JIS 全字対応や現代筆跡での高精度は保証しない。[モデル入手先](https://packages.debian.org/sid/tegaki-zinnia-japanese)・[モデルの著作権情報](https://metadata.ftp-master.debian.org/changelogs/main/t/tegaki-zinnia-japanese/tegaki-zinnia-japanese_0.3-3_copyright)

ローカル実行にAPI従量料金は不要。C++ライブラリは移植可能だが、この Mac でのビルドは未確認。Tegaki の Mac GUI 案内は X11 前提の旧環境で、現行 macOS/Apple Silicon ですぐ動く根拠にはならない。[Tegaki 公式手順](https://tegaki.github.io/userdoc/)

## 次に行うなら: 小さい盲検試験の提案（未実行）

1. 既存413実字の目視承認から、切り分けも正しい見本を選び、正解ラベルを認識入力へ渡さず評価。かな・単純漢字・複雑漢字・崩した字を含める。既存OCRの推測ラベルを正解にしない。
2. 対象モデルのラベル一覧と正解を照合し、対象内 top-1 / top-5、対象外字数、棄却後の採用精度と採用率を別々に集計。閾値調整用と最終評価用を分ける。
3. 数式・記号・複数字・筆画欠落を混ぜた負例で誤採用率を測る。文字認識失敗と切り分け失敗を分けて記録する。作者の99%や閾値0.7を転用しない。
4. 元の実筆画を保持したまま、画像化の線幅・余白だけ少数条件で確認。分類器はラベルを付ける役割に限定し、A1 mini 用に使う本人の座標を生成・改変しない。
5. 単字で決まらない同形字や対象外文字は元ページの文脈・検索文字・目視で補う。軌跡認識は筆順の信頼性を確認できる場合の追加比較とする。

判断: Datalab に文脈のない文字シートを繰り返し送る前に、単字用モデルと切り分け品質を独立評価する価値が高い。改善幅は現時点では仮説であり、モデルの追加学習や大量処理に進む根拠はまだない。


## 補助: 元の文章で読み、文字座標から原筆跡へ対応させる

単字シートに組み替える前の行・単語には、同形異字や小書きかなを区別する情報が残る。Google Cloud Vision の DOCUMENT_TEXT_DETECTION は手書きに対応し、Symbol ごとの文字・boundingBox・confidence を返す。元ページまたは元の行を認識し、位置を既存の原筆画IDに対応させる経路が考えられる。これは設計上の提案であり、Datalab より本人筆跡で高精度という実測はない。印刷背景や図の文字を本人筆跡と誤採用しない照合も必要。

- [Google Vision 手書き認識](https://docs.cloud.google.com/vision/docs/handwriting)
- [Symbol の公式仕様](https://docs.cloud.google.com/vision/docs/reference/rest/v1/AnnotateImageResponse#Symbol)

単字モデルの対象外字や候補不一致に限定すれば、全件をAPIへ送る回数を抑えられる。両者の一致だけで正解と断定せず、切り出しが一文字であることを別に確認する。
