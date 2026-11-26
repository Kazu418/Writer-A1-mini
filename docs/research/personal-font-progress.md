# Goodnotes本人筆跡字庫 — 作業記録

更新：2026-11-25。ゴールは未達成。最低条件は今回の4ページの全文字を本人の筆跡で揃え、既存のA1 mini用描画処理へ渡せること。拡張対象はGoodnotesに存在する文字と同字の別見本。

## 現在の実データ

- 元の `~/Downloads/GoodNote_BackUp_ALL.zip` を変更せず、102冊を処理。
- 検索データの認識候補、単語、文字位置、ストロークIDをローカルSQLiteへ保存。別形式のUTF-8文字範囲と矩形にも対応。
- 認識データには配布資料の印刷文字も混ざるため、認識字種数を「本人字庫の完成字数」とは扱わない。
- 元ページの現存オブジェクトIDを照合し、元のインクから2,735字種・5,780見本を回収。元の座標と各線内の点順序を保存。筆画の時間順は未検証。
- 4ページを実際に組み立てる `render_glyph` 呼び出しから必要字を再集計：**427字種**。Markdownを数えた430字種とは異なる。
- **416/427字種に元の筆跡候補あり**。候補は認識・切り分けの正しさを保証しない。
- 候補未回収：`²∑−・授頻（）＋：＝`。Unicode上の表記違いを含む。本人の別字を無断で割り当てたり、標準字体で補ったりしていない。
- 以前の手動5文字に加え、盲検の元インク見本をCodexが画像で確認し、合計413字種を登録。今回のノートでは411/427字種を実字として確認済み。さらに本人の確認済み筆跡から10種の明示的な表記変換を作り、合計421/427字種を出力可能。残りは `授掛断替険頻` の6字。OCR一致だけで承認していない。確認記録は `visual-reviews-001.json` 〜 `visual-reviews-007.json`。
- 単語の幾何分割は線を切断せずに提案し、未確認のまま保存。つながった字を強制的に切らない。

数値の正本は `output/personal-font/coverage.json` とSQLite。今後の回収・確認で変わる。

## 重要な発見

検索データには、文字・単語の候補に対応するストロークIDが含まれる。しかし検索用の点列は間引かれている。129本を照合した試料では、元インクと検索点列の始点・終点は一致し、点数は異なった。字庫には元インクを復号した点列を使用する。

検索データだけの矩形を採用せず、実際の手書きオブジェクトを領域へ割り当てる。元の `notes/<UUID>` がない検索メンバーや、領域をまたいで曖昧になる線は採用しない。削除ページも除外する。

## 検証済みの接続

1. 確認済み5文字の元の筆跡と、従来の手動5文字試作が同じ点列であることをスクリプトで照合。
2. 新形式の字庫 → 文字配置 → SVG → 既存G-code出力・独立検査をテスト。
3. 実データ「生活習慣病」44本・2,024点から `.gcode` と `.gcode.3mf` を生成し、同じ全筆跡との照合を通過。
4. 実際のPDF入力を `./plotnote convert --personal-font ...` で変換。
5. 本人字体スコープではキャッシュ済み標準字体を使わず、欠字はエラー。スコープ外では従来の字体へ戻る。
6. テスト211件通過。実際のオフラインHTMLをNodeで実行し、必要文字の絞り込み、見本SVGの作成、不正ラベルの拒否、承認、ローカル保存、JSONダウンロードの動作を確認。テストは実DBを変更しない。通信権限変更後はPlaywright CLI＋既存のChrome for Testingで実ブラウザを起動できた。今回ノートの絞り込み、文字検索、元インク見本の表示、2文字入力の拒否、登録とリロード後のローカル保存を実操作で確認。DBの確認状態はテストで変更しない。faviconの404以外の実行エラーなし。

新しいデータはプリンターへ送信していない。G-code生成と実機実行の既存機能を新規実装し直していない。

## 自動照合の現状

ローカルTesseractで1,176見本を独立に認識したが、元ラベルとの一致は10見本のみ。この方法では正誤を判定できない。一致・不一致だけで候補を自動承認していない。Apple Visionもこの実行環境では `nilError` となり、採用しなかった。

ユーザーはDatalab APIを指定。500は金額ではなく処理数であり、500処理以内ならFAST、約3000件を個別処理する場合は最安モデルという指定。24文字/ページで全7,561見本を316ページにまとめ、試験3ページを含む319ページを明示的にFASTで処理済み。API返却の `final_cost_cents` 合計は31.82025セント（$0.3182025）。キーは環境変数からcurlの標準入力へ渡し、保存・表示しない。画像以外の期待ラベルや元ノート名はアップロードしない。

Datalab照合結果は1,023一致、2,019別の1文字、1,758複数文字/読取困難、2,757読取なし、4重複ID。ラベル不一致には候補側の混入・誤認識とDatalab側の誤読の両方がある。一致のみで確定しない。元見本の状態とは独立した `independent_ocr` テーブルへ保存。見本の保管場所、全点列、ストロークIDを処理前のハッシュと照合し、7,561見本・3,780,527点が変更されていないことを確認。

通信権限変更後、Datalab認証確認はHTTP 200。Pythonの証明書設定では接続に失敗するため、証明書検証が通るシステムcurlを使用。検証を無効にしていない。再開時は保存されたジョブをポーリングし、受付不明のPOSTを自動で再送しない。

元のiCloud内PlotNoteへ戻し、ユーザーが「ダウンロード済みとして保持」を設定。作業はこの場所で継続。

## 主な成果物

- `output/personal-font/goodnotes.sqlite3`：認識グループ、原本への参照、元インク見本、確認状態、OCR監査。
- `output/personal-font/required-note.json`：実際のノート生成処理から得た必要文字。
- `output/personal-font/coverage.json`：候補・元インク・確認済みを区別した集計。
- `output/personal-font/review-note.html`：ネットワーク不要の確認画面。本人の元インクを描画。編集・承認結果をJSON保存できる。
- `output/personal-font/confirmed-font.json`：元の実字として確認済みの413文字。標準字体へのフォールバックなし。
- `output/personal-font/confirmed-proof/`：新字庫からのプレビュー。
- `output/personal-font/confirmed-gcode-proof/`：既存の中央試験プロファイルで生成・検査した5文字のG-code。未送信。
- `output/personal-font/confirmed-pdf-pipeline/`：PDF入力＋本人字庫の接続確認。

追加成果物：

- `output/personal-font/datalab/campaign/summary.json`：処理ページ数・照合結果・API返却金額。
- `output/personal-font/source-preservation-after-ocr.json`：全送信見本の元軌跡保存監査。
- `output/personal-font/review-all.html`：全3,288字種、OCR照合結果つき。
- `output/personal-font/confirmed-351-proof/`：登録済み全文字のプレビューと短文例。短文121本・6,157点から既存A1 mini経路でG-code生成・原本経路検査に合格。未送信。

## 最小ノート字庫の残り6字と追加採取

- 単独候補があっても未確認なら単語から再回収する `--unconfirmed` を追加。これで1,032見本を追加回収し、「条件」「平均」「誤解」などの全単語と照合して登録した。
- `--include-alternatives` で最後の7字の別認識候補も調べ、40見本を追加。完全な「尺」を確認できた。残り6字の候補は未回収、または数式・別字・不完全な内容。
- `personal-font-with-forms.json` は本人の実字413字と表記変換10字を収録。全角括弧・全角＋＝は同じ筆跡、²は2の一様縮小と上配置、∑はΣの数学表記。句点は本人のoを縮小、−は本人のーを中央に配置、・と：は元の文章で確認した本人の点の配置・繰り返し。各変換は `derivation` に記録し、実字の確認数には数えない。漢字を合成・標準字体で代用しない。
- `personal-forms-proof/` は新しい短文・数式記号のPNG/SVG/HTMLと検査済みG-code。実機には未送信。
- `capture/additional-six-characters.pdf` は1ページの追加用紙。`授・掛・断・替・険・頻` を各枠内に1字ずつ書き、新しい1ページのノートを `.goodnotes` で書き出して受領する。PDFラベルは背景なので筆跡には含めない。
- `capture/additional-six-characters.manifest.json` に用紙IDと記入枠を記録。`import_personal_capture_sheet.py` は背景の用紙IDと1ページであることを検証し、明示的なキャンバス寸法で元の線を枠へ対応付ける。寸法不明を推測しない。枠をまたぐ線は切らずにエラー。取り込むのは未承認候補であり、実際の記入データの確認は受領後。
- 原点タップも取り込みで保持。出力時だけ同じ端点を重ねて既存G-code形式へ対応させ、元の1点は `original_paths` に残す。位置も線形状も新しく作らない。
- 確認画面の保存を明示的な操作の差分へ変更。旧キャッシュの「未確認」スナップショットが新しい承認を上書きしない。旧データは別キーで保存。明示的に未確認へ戻した操作はJSONにも含める。実HTMLのJSで旧形式移行・差分保存・取り消しを検証。

取り込み例（ファイル名とキャンバス寸法は受領した実データを調べて指定）：

```sh
PYTHONPATH=src .venv/bin/python scripts/import_personal_capture_sheet.py completed.goodnotes --manifest output/personal-font/capture/additional-six-characters.manifest.json --db output/personal-font/goodnotes.sqlite3 --report output/personal-font/capture/import-report.json

# 実字のみと、明示的な表記変換付き字庫を分けて書き出す
PYTHONPATH=src .venv/bin/python -m plotnote.personal_font export-library --db output/personal-font/goodnotes.sqlite3 -o output/personal-font/confirmed-font.json
PYTHONPATH=src .venv/bin/python -m plotnote.personal_font export-library --db output/personal-font/goodnotes.sqlite3 -o output/personal-font/personal-font-with-forms.json --typographic-forms
```

全文字が揃っても全文4ページのサイズ・配置検証と、実機確認が残る。全Goodnotesの字種・別見本の確認も継続対象であり、ゴールは未達成。

## 続ける手順

すべてPlotNoteをカレントディレクトリにして実行する。

```sh
# 必要文字を実際の4ページから再集計（ファイルやプリンターを操作しない）
PYTHONPATH=src .venv/bin/python scripts/audit_note_characters.py -o output/personal-font/required-note.json

# 既存インポートは冊子のCRC・サイズで再開判定。--refresh を付けると再読込。
PYTHONPATH=src .venv/bin/python -m plotnote.goodnotes_index --archive ~/Downloads/GoodNote_BackUp_ALL.zip --db output/personal-font/goodnotes.sqlite3 --required output/personal-font/required-note.json --report output/personal-font/coverage.json
PYTHONPATH=src .venv/bin/python scripts/import_framed_search.py --archive ~/Downloads/GoodNote_BackUp_ALL.zip --db output/personal-font/goodnotes.sqlite3

# 別の候補を元インクへ戻す。全候補はDBに保存し、表示用には原則3見本を選ぶ。
PYTHONPATH=src .venv/bin/python scripts/materialize_personal_font.py --archive ~/Downloads/GoodNote_BackUp_ALL.zip --db output/personal-font/goodnotes.sqlite3 --per-character 3

# 必要文字の不足を単語・矩形から回収。既存の承認結果は上書きしない。
PYTHONPATH=src .venv/bin/python scripts/recover_missing_personal_glyphs.py --archive ~/Downloads/GoodNote_BackUp_ALL.zip --db output/personal-font/goodnotes.sqlite3 --required output/personal-font/required-note.json

# オフライン確認画面を書き出す
PYTHONPATH=src .venv/bin/python -m plotnote.personal_review --db output/personal-font/goodnotes.sqlite3 --required output/personal-font/required-note.json --standalone output/personal-font/review-note.html

# 確認画面から保存したJSONを取り込む。パスは実際の保存先に置き換える。
PYTHONPATH=src .venv/bin/python -m plotnote.personal_review --db output/personal-font/goodnotes.sqlite3 --required output/personal-font/required-note.json --import-reviews ~/Downloads/personal-font-reviews.json

# 確認済みの字だけを書き出す
PYTHONPATH=src .venv/bin/python -m plotnote.personal_font export-library --db output/personal-font/goodnotes.sqlite3 -o output/personal-font/confirmed-font.json

# すべて必要な字が揃った後、4ページを本人の筆跡で生成。新しい出力先を指定。
PYTHONPATH=src .venv/bin/python output/exam-note/build_note.py --personal-font output/personal-font/confirmed-font.json --output output/exam-note/personal-confirmed
```

## 未完了の要件

- 全ノート文字のラベル・分割の確認。実字411字＋表記変換10字で421/427字を出力可能。残り6字は記入用紙での追加採取待ち。
- 候補不足11字の探索・表記対応の検討。現存しない筆跡があれば本人から追加採取が必要。
- 全Goodnotes文字の回収範囲の拡大。元インク未対応・認識違い・未分割単語を残しており、網羅性は未証明。
- 新規見本の相対的な文字サイズ、ベースライン、句読点の配置の校正。登録済み413字のうち99字は行・単語から推定、5字は明示基準、309字は仮のバウンディングセル。元点列は保存済み。
- 全文4ページの本人字庫版生成、原稿との一致・可読性・用紙内配置の検証。
- 最終データの既存A1 mini経路への接続と、そのデータの実機確認。

## 2026-11-25 夜: iPhone手動確認の結果をDBへ反映

- 確認アプリ（`scripts/label_review_app.py`、Tailscale経由のiPhone操作）で、LT8とGoodnotesの仮ラベルを2,846件すべて目視確認。記録は `output/personal-font/lt8/applied/reviews-final.jsonl`。
- 区分ごとの○率: 2つが一致（自信あり）97%、同（自信低め）83%、AIだけの意見88%、top-5に入るだけ36%。
- 反映前に `goodnotes.sqlite3.before-label-review-20261125` を作成（同サイズ・quick_check ok）。取り込み2,670件（受理2,338・却下332）。保留165件は未確認のまま。
- 登録済み: 413字種 → **1,352字種**（見本2,751）。ラベルが書き換わった見本164件。
- 今回ノート427字種のうち実字は411字種のまま。実字なしは `²∑−。・授掛断替険頻（）＋：＝`。表記変換で補うのは10字、残る実字なしは `授掛断替険頻` の6字（本文中の出現11回）。
- 英数字は EMNIST（`output/datasets/`）で追加検証できる状態。詳細は `handwriting-datasets.md`。
