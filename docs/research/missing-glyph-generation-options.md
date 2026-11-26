# 不足字を本人の筆跡から生成する方法の調査

確認日：2026-11-25。調査のみ。学習・推論・重みの実ダウンロード・外部への筆跡送信・課金処理は実行していない。対象は不足する「授掛断替険頻」と、将来の字庫拡張。これは実際に本人が書いた字の回収とは別で、生成した字には生成元と確認状態を付ける。

## 結論

**生成は可能な研究分野であり、ペン軌跡を直接生成する公開実装もある。** 今回に合う候補は SDT。画像だけを生成する FontDiffuser より、A1 mini の線の描画へ接続しやすいと考えられる。ただし、このユーザーの筆跡を再現できるかは未実験。まず既知文字を隠す試験で、字形と本人らしさを評価する必要がある。[SDT 公式実装](https://github.com/dailenson/SDT)

不足6字だけを早く補うなら、既存の本人筆画・部首を配置し直す方法も候補。モデル環境と重みが不要で、元の中心線を使える点から、初期試作は軽いという**工学的推測**。ただし独立字と偏では形が変わるため、切り貼りだけで本人らしい字が保証されるわけではない。文字構造の制約は日本語の字形に固定する。親側で調査している [KanjiVG](https://github.com/KanjiVG/kanjivg) の構造情報は、この用途の補助候補。

## 比較

| 候補 | 確認できた機能・公開物 | 今回の制約 |
|---|---|---|
| SDT / CVPR 2023 | 内容と参照筆跡を条件にオンライン軌跡を生成。公式 README は日本語・中国語・英語の生成を記載。コード、設定、重みへのリンクあり | 日本語チェックポイントのファイル実体は今回確認できなかった。CUDA 固定箇所があり、そのまま Mac CPU/MPS で動く保証はない |
| FontDiffuser / AAAI 2024 | 内容画像＋1枚のスタイル画像から字形画像を生成。学習済み重みへのリンクとデモあり | 出力はペン軌跡ではない。輪郭ベクトル化だけでは二重線になり、A1 mini 用には中心線・ペン上げ下げの復元が別途必要 |
| CF-Font / CVPR 2023 | 中国語の few-shot 字形画像生成。公開手順には GB2312 の6,763字、16字参照、複数字体での基礎学習を記載 | 6字だけのために基礎学習を始める経路は重い。日本語字形と中心線は別途対応。明示的なコードライセンスと即利用できる重みは今回未確認 |
| LF-Font / AAAI 2021 | 部品ごとのスタイル表現。原論文 README は8参照字の結果を記載。統合実装あり | 画像生成。中国語の部品情報を用いる手法で、日本語での即利用を実証したものではない |
| DiffInk / ICLR 2026 | テキスト行とスタイル参照から軌跡を直接生成。コードと重みリンクあり | 全行生成向け。今回の単字字庫への接続は別途必要。コード MIT と重みの利用条件は同一ではない |
| InkFormer-Char / TMLR 2026 | 単字の軌跡生成コード。1 GPU 推論の手順あり | 重みは Google Drive へのアクセス申請が必要と記載。即日の入手は未確認。コード MIT、重みは CASIA 条件に従う |

出典：[SDT README](https://github.com/dailenson/SDT/blob/master/README.md)、[FontDiffuser README](https://github.com/yeungchenwa/FontDiffuser/blob/main/README.md)、[CF-Font README](https://github.com/wangchi95/CF-Font/blob/main/README.md)、[LF-Font README](https://github.com/clovaai/lffont/blob/master/README.md)、[統合 FFG 実装](https://github.com/clovaai/fewshot-font-generation)、[DiffInk README](https://github.com/awei669/DiffInk)、[InkFormer README](https://github.com/awei669/InkFormer)。

## SDT を試す場合の具体的な確認点

- 日本語設定には `NUM_IMGS: 15` があり、訓練設定は20万ステップ。ただし、学習済みモデルでの参照入力による推論と、一からの訓練は別。既に回収した本人字から参照画像を作る余地がある。[日本語設定](https://github.com/dailenson/SDT/blob/master/configs/Japanese_TUATHANDS.yml)
- 著者の個人字体チュートリアルは15字以上を用意する手順。中国語重みで6千字程度を GPU で約3分生成したという**著者の報告**があるが、GPU型が明記されず、この Mac・今回の処理時間や費用の保証には使えない。[著者 Issue #43](https://github.com/dailenson/SDT/issues/43)
- 同じ Issue の著者回答は、タブレットの可変筆幅と学習時の均一筆幅との差が、平均的なスタイルになる一因だと説明している。Goodnotes の中心線を均一幅で画像化すれば分布差を一部減らせる可能性があるが、これは**今回の推測で、再現精度の保証ではない**。[著者回答を含む Issue](https://github.com/dailenson/SDT/issues/43)
- `user_generate.py` は現状 PNG を保存するが、描画前には相対座標とペン状態を持つ予測配列が存在する。`test.py` の online 出力は軌跡を保存する実装。画像を中心線化するより、予測座標を分離・累積して既存の PlotNote パスへ変換する方が自然という**設計判断**。[ユーザー推論](https://github.com/dailenson/SDT/blob/master/user_generate.py)、[online 保存](https://github.com/dailenson/SDT/blob/master/test.py)、[座標変換](https://github.com/dailenson/SDT/blob/master/utils/util.py)
- 日本語学習・生成のコードがあることと、必要な日本語の重み・辞書が今すぐ揃うことは区別する。公式 Google Drive の日本語ファイル一覧を今回は取得できなかった。`user_generate.py` の既定は中国語で、内容辞書も必要。[データローダー](https://github.com/dailenson/SDT/blob/master/data_loader/loader.py)、[既定設定](https://github.com/dailenson/SDT/blob/master/configs/CHINESE_USER.yml)
- 公式環境は Python 3.8・PyTorch 1.13・CUDA 11.7 系を記載し、推論コードに `.cuda()` / `.to('cuda')` がある。CPU/MPS 移植や別 GPU 環境整備の工数は、今回実行していないため未測定。[環境](https://github.com/dailenson/SDT/blob/master/environment.yml)

SDT のコードは [MIT License](https://github.com/dailenson/SDT/blob/master/LICENSE)。配布データ・重みの元データ由来の利用条件まで一括して MIT と決めつけない。DiffInk / InkFormer は重みが CASIA-OLHWDB の条件に従うと公式に明記している。[DiffInk 条件](https://github.com/awei669/DiffInk#license)、[InkFormer 条件](https://github.com/awei669/InkFormer#license)

## 日本語の字形と品質の確認

中国語モデルで出せる文字数が多くても、日本語の「掛・険・頻」などの形を保証しない。日本語の内容画像・文字コードを固定し、日本語としての部品と画数を目視する。地域ごとの字形に違いがあり、日本語用途には日本語の字形を使うべきことは Unicode の FAQ も説明している。[Unicode: Chinese and Japanese](https://www.unicode.org/faq/han_cjk.html)

最初の試験案：

1. 確認済みの本人字から、部品が異なる15〜30字程度の参照を選ぶ。量は試験設計上の提案であり、30字なら十分という実証値ではない。
2. 既に実物がある10〜20字を参照から外し、生成して本人の実字と比較する。全体の傾き、字幅、曲がり方、部品の配置、欠画・余画、ペン移動を確認する。
3. この比較が通ってから不足6字を生成する。既存の本人字はそのまま使い、不足分だけを生成字として保存する。
4. 元の実字・部品を使った合成・モデル生成を区別し、生成字は確認前に本番字庫へ入れない。G-code の座標検査と実機確認は従来どおり必要。

上記は研究結果からの次の試験提案で、まだ生成品質を検証した結果ではない。モデル料金・GPU時間・クラウド単価を測定していないため、特定の円額や所要時間は提示しない。
