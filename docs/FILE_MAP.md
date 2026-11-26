# ファイル案内と資料の復元

## 普段の入口

| パス | 役割 |
|---|---|
| `AGENTS.md` | Agentが毎回最初に読む短い入口と必須条件 |
| `docs/FRIEND_WORKFLOW.md` | ノート受領、枚数確認、生成、本人承認、所有者への納品 |
| `docs/MACHINE_CONSTRAINTS.md` | 今回の所有者の装置条件、紙の置き方、座標、Z、速度、確認の限界 |
| `docs/OWNER_OPERATIONS.md` | 実機の受取/準備/開始/中断/再開 |
| `docs/PRINTING_LESSONS.md` | 中央から始まる問題、ペン高さ、ホーム消失、数式削除の訂正など |
| `profiles/a1-mini-owner-v1.json` | 固定機械契約の機械可読表現 |
| `scripts/prepare_handoff.py` | 固定装置用のオフライン生成・検証・承認・ZIP作成CLI |
| `examples/handoff/request.json` | CLIを試す最小のリクエスト |
| `examples/handoff/pass1.svg`, `pass2.svg` | 小さな合成線画。字体の品質見本や位置合わせ用印ではない |

新しいノートの正規の入口は `scripts/prepare_handoff.py`。過去の試行ディレクトリを複製し、送信用スクリプトを実行することから始めない。

## 容量の大きい資料

共有リポジトリは、大きな資料をGitHubの通常ファイルとして扱える分割アーカイブに保管する。Git LFSは不要。復元ツールは標準Pythonだけで動く。

```sh
# リポジトリのルートで実行
python3 scripts/archive_project_materials.py restore \
  --archive-dir archives/project-materials \
  --destination .
```

`archives/project-materials/manifest.json` が収録ファイルとハッシュの正本。`materials-0001.zip` などのパーツをすべて取得する。復元すると元の相対パス、例えば `output/personal-font/...`、`output/exam-note/...` が戻る。

既存の同一ファイルはハッシュで確認してスキップする。内容の異なるファイルを無断で上書きしない。作業済み環境と衝突する場合は別の空ディレクトリへ復元する。

```sh
python3 scripts/archive_project_materials.py restore \
  --archive-dir archives/project-materials \
  --destination restored-materials
```

この場合、資料は `restored-materials/output/...` にある。歴史的スクリプトがリポジトリ相対の `output/` を前提とする場合があるため、別ディレクトリへ復元したことを踏まえてパスを指定する。

収録はフォント、Goodnotesデータベースと保全コピー、データセット、研究資料、旧版出力を含む。環境キャッシュ、`.pyc`、`.DS_Store`、一時的な `.pkl` などは復元対象ではない。実際の収録範囲や除外理由はマニフェストを確認する。アーカイブは、全ての外部参照先や元のiCloudバックアップまで新たに取得したという意味ではない。

## 変換器のソース

| モジュール | 責務 |
|---|---|
| `src/plotnote/handoff.py` | 固定機械契約、依頼形式、A4実軌跡プレビュー、承認・納品の一致検証 |
| `src/plotnote/profile.py` | 校正値と紙/機械/ペンの描画可能範囲 |
| `src/plotnote/gcode.py` | ストロークを順序を保った絶対座標G-codeに変換 |
| `src/plotnote/validate.py` | 生成結果を別パーサーで再読込し、命令/範囲/元軌跡を検査 |
| `src/plotnote/package.py` | `.gcode.3mf` と収容G-codeの照合 |
| `src/plotnote/printer_state.py` | 所有者側で全軸ホーム状態などを検査する純粋関数 |
| `src/plotnote/fonts.py` | 標準中心線字体・本人字庫・明示的な欠字フォールバック |
| `src/plotnote/pdf_input.py`, `svg_input.py` | 文字を保持したPDF、ベクターSVGの読込 |
| `src/plotnote/artifacts.py` | 汎用のSVG/PDF/PNG/筆順プレビュー |
| `src/plotnote/cli.py`, `server.py` | 汎用CLIとローカル画面 |
| `src/plotnote/contact_test.py` | 初期の接触/空描きテスト。現在の納品用経路とは別 |

手元の版の仕様を調べるときは、実際の `--help` とコードを確認する。古い文書のコマンドを、別の更新版へ検証せずコピーしない。

## ノートと実機試行の履歴

| パス | 内容・位置付け |
|---|---|
| `output/exam-note/source.md` | 元ノートのテキスト化資料 |
| `output/exam-note/build_note.py` | 初期の148mm角ノート用の図式/文字組み部品 |
| `output/exam-note/build_a4_note.py` | A4縦、各面2回、2.8mm版を作った組版。サンプル原稿固有の内容を含む |
| `output/exam-note/a4-v4/` | 元の公式を含むA4版、比較用PDFとG-code |
| `output/exam-note/a4-v4-pressure/` | 元配置を保ち、描画Zだけ0.1mm下げた版 |
| `output/exam-note/prepare_formula_blanks.py` | 元配置を再現し、G-code一致と公式ストローク対応を得る作業用処理 |
| `output/exam-note/export_formula_blanks.py` | インライン文字式まで消した旧処理。訂正前の比較資料 |
| `output/exam-note/export_display_formula_blanks.py` | 別枠の数学の公式だけ消す訂正後の処理 |
| `output/exam-note/a4-v4-formula-blanks/` | 誤った消去範囲の旧版。新しい印刷には使わない |
| `output/exam-note/a4-v4-display-formula-blanks/` | 文章中の文字式を残した訂正後のG-code/PDF/検証結果 |
| `output/contact-test/` | 中央での高さ、速度、文字サイズ、本人字庫の試行と当時の記録 |
| `output/contact-test-instructions.md` | 初期接触テスト向けの歴史的手順 |
| `docs/CALIBRATION.md` | 別装置の初回実測にも使う汎用校正説明。現在の固定装置の正本はMACHINE_CONSTRAINTS |
| `docs/PDF_CONTRACT.md` | 汎用PDF入力の文字/線/寸法条件。148mmの初期テンプレートを含む |

`a4-v4-display-formula-blanks/` は今回のサンプルの正しい訂正版であって、将来のあらゆるノートの完成品ではない。新しい依頼は新しいjob_id/出力先で作る。

履歴の `live-*.json` は当時の命令、状態、結果を残す資料。「RUNNING」や受信ACKだけで筆跡の完成とみなさない。元ノートの図中のラベル重なりなど、未解決の品質指摘も [PRINTING_LESSONS.md](PRINTING_LESSONS.md) に残している。

### 所有者専用の実機操作資料

`output/contact-test/` と各実験ディレクトリに残る `send_*once.py`、`position_*once.py`、`home_*once.py`、`prepare_face1_pass2_once.py` などは、実機を動かした当時の所有者用プログラム。共有版では所有者操作の明示的な環境変数 `WRITER_A1_MINI_OWNER_CONTROL=1` を要求するガードが付く。

友人側でそのガードを解除しない。これらは生成/納品に必要ない。コピーされたjournal、固定IP、機器識別子、証明書ピン、所有者Macの認証設定の読込を持つことがある。ローカルの秘密値は共有しないが、資料中の接続情報が自分の装置用だと仮定して実行しない。

## 本人の筆跡・フォント研究

| パス | 内容 |
|---|---|
| `output/personal-font/goodnotes.sqlite3` | 元インク、見本、確認状態、OCR監査などを保管するデータベース |
| `output/personal-font/goodnotes.sqlite3.before-label-review-20261125` | 手動確認結果反映前の保全コピー |
| `output/personal-font/confirmed-font.json` | 確認済み実字の字庫 |
| `output/personal-font/personal-font-with-forms.json` | 実字に明示的な句読点/数式記号等の表記変換を加えた字庫 |
| `output/personal-font/coverage.json`, `required-note.json` | 必要字種、収集範囲、確認済み/不足の監査 |
| `output/personal-font/review-*.html` | 字の元見本を確認する画面 |
| `output/personal-font/lt8/` | 別字庫との候補比較、手動レビュー、結果の適用記録 |
| `output/handwriting-research/` | Goodnotesインクの回収、数式/文字の軌跡、比較用資料 |
| `output/datasets/` | 追加検証用データセット。独自の権利・由来を確認する |
| `docs/research/` | OCR、既存ツール、フォント回収、字体品質の研究と当時の進捗 |

この作業では2026-11-25夜に、実字の登録が1352字種となった記録がある。表記変換付き版には追加の10種がある。時点を明示して扱い、件数を固定仕様にはしない。字庫の違いは欠字、句読点、組版幅へ影響する。

本人字庫の再生成・OCR・レビューは、通常のノート依頼で必須ではない。本人の筆跡そのものを変えたり、OCR一致だけで確認済みにしたりしない。外部OCRの再実行は通信/費用を伴う別作業なので、保存結果の再利用を先に確認する。

## テスト・設計の背景

- `tests/`: 入力拒否、字体、数式位置、幾何、プロファイル、G-code、コンテナ、プレビュー、承認・納品など。
- `.mini-spec-kit/`: 最初の仕様・計画・制約・検証チェックリスト。
- `examples/japanese-note*`: 初期変換器のPDF/SVG/プレビュー例。
- `docs/THIRD_PARTY.md`、`src/plotnote/data/*LICENSE*`、`LICENSE`: 依存素材とコードの権利。

プライベート共有であっても、コード、標準フォント、元ノート、本人の筆跡、データセットの権利をひとつにまとめて変更しない。

## 下線付きキーワードの書体を変えた版

`output/exam-note/a4-v5-standard-keywords/`は、印刷済みの表面を保ち、これから印刷する裏面の下線付き本文キーワードだけを標準手書き風ストロークへ変えた版。`build_standard_keywords.py`が生成元で、共有ライブラリは`src/plotnote/keyword_style.py`。字庫を変えたキーワードの一覧、その他の筆記命令が同一である検証、SVG、G-code、実G-codeからのA4プレビューを含む。原点合わせ用の旧版始点と、書体変更後の最初の線の始点を混同しない。
