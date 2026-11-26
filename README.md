# Writer A1 mini

友人のノートを、所有者の **Bambu Lab A1 mini + ペンホルダー** で書けるファイルへ変換し、プレビュー承認後に渡すための公開プロジェクトです。変換器の内部名とCLI名は **PlotNote** です。

友人はノートをAgentへ渡し、A4の枚数・片面/両面・文字サイズなどを答えます。Agentが原稿を組み、**実際の筆記軌跡のPDF** を見せます。友人がOKした同じ版のPDFと印刷用ファイルをZIPへまとめ、所有者へ渡します。友人側ではプリンターへ接続しません。

## 入口

| したいこと | 読むもの |
|---|---|
| Agentにノートを作らせる | [AGENTS.md](AGENTS.md) → [友人側の手順](docs/FRIEND_WORKFLOW.md) |
| 固定の機械条件を確認する | [A1 miniの制約](docs/MACHINE_CONSTRAINTS.md) |
| ファイルを受け取り実機で書く | [所有者側の操作](docs/OWNER_OPERATIONS.md) |
| 以前つまずいた点を知る | [実機・データ作成の教訓](docs/PRINTING_LESSONS.md) |
| ソース・字庫・原稿・履歴を探す | [ファイル案内](docs/FILE_MAP.md) |

## 最初に動かす

Python 3.11以降を用意し、リポジトリのルートで実行します。

```sh
sh scripts/bootstrap.sh
.venv/bin/python scripts/prepare_handoff.py prepare \
  --request examples/handoff/request.json \
  --output jobs/example-note
.venv/bin/python scripts/prepare_handoff.py verify jobs/example-note
```

これは小さな同梱サンプルから、A4片面・2タイルの生成と検証を試す例です。`jobs/example-note/preview.pdf` を開いてください。サンプルは全文ノートや筆跡の品質見本ではありません。

納品用の生成・確認・承認・ZIP作成は [FRIEND_WORKFLOW.md](docs/FRIEND_WORKFLOW.md) の順序で行います。本人によるプレビュー承認前に、`approve` を実行しないでください。

```sh
# 本人がプレビューを確認した後だけ実行
.venv/bin/python scripts/prepare_handoff.py approve jobs/example-note \
  --reviewer '本人の名前' \
  --preview-sha256 <確認したPDFのSHA-256>
.venv/bin/python scripts/prepare_handoff.py bundle jobs/example-note \
  --output deliveries/example-note.zip
```

## 変換器について

日本語はKanjiVG、英数字・ギリシャ文字はHersheyの中心線を使い、文字の輪郭を二重になぞらず描きます。文字を抽出できるPDF、線で構成されたSVGに対応します。本人のGoodnotes軌跡から作った字庫を使う経路もあります。文字・図表・数式を正しく構造化する作業はAgentが行います。

```sh
./plotnote doctor
./plotnote fonts --check '三角関数 αβ ∫ √ x²'
./plotnote inspect examples/japanese-note.pdf
./plotnote convert examples/japanese-note.pdf -o jobs/input-preview
./plotnote serve
```

`PlotNote.command` はローカル画面を起動します。汎用画面と `plotnote export` は別寸法/別プロファイルも扱う開発用機能を含みます。**この所有者への新しい納品物は、固定プロファイルを強制する `scripts/prepare_handoff.py` を使います。** 初期の148mm角テンプレートを、現在のA4二回印刷の正本と混同しないでください。

## 実機の制約と確認状況

A4の各面を2回、両面なら計4回に分け、毎回紙を所定の端へ合わせます。ペンがノズルより手前にあるため、A4上部には届かない余白があります。描画窓、オフセット、Z、速度、紙の置き方をまとめた [MACHINE_CONSTRAINTS.md](docs/MACHINE_CONSTRAINTS.md) が固定設定の正本です。

所有者がタイル1の筆記完了と良好な結果を確認しました。その後、訂正後のタイル2を開始した記録があります。すべての面の完成や、許可矩形全体の干渉なしまで検証済みという意味ではありません。

本番G-codeは加熱OFFの指定のみですが、本体側で開始時に約75℃、一時停止時に約90℃の目標が設定された実例があります。キャンセル後にホーム状態を失ったこともあります。ペンを外してホームし、最新の全軸ホーム状態を検査してから開始します。取り付け基準、筆圧、停止/再開の注意は [OWNER_OPERATIONS.md](docs/OWNER_OPERATIONS.md) を参照してください。

## ファイルと検証

納品には実寸プレビュー、タイルSVG、G-code、同じG-codeの `.gcode.3mf`、有効プロファイル、マニフェスト、承認記録を含めます。コンテナは再スライス用の3Dモデルではありません。

固定装置用の検証器は、紙予算、各面の2タイル、機械プロファイル、筆記G-code、収容G-code、実際の量子化座標から作ったPDF、チェックサム、承認した版との一致を検査します。ノートの意味、文字の可読性、公式を空白にする対象が適切かは、Agentの原本照合と本人の確認が必要です。

```sh
.venv/bin/python -m pytest -q
```

多くの原稿・字庫・実験履歴も共有用に保管しています。容量の大きい資料の復元と、履歴/現行データの区別は [FILE_MAP.md](docs/FILE_MAP.md) を読んでください。実機接続用の認証情報は含めません。

## ライセンス

コードは既存の **AGPL-3.0-or-later** を維持します。リポジトリの公開に伴うライセンスの変更はありません。KanjiVG由来の軌跡はCC BY-SA 3.0、Hershey関連データなどの条件は [THIRD_PARTY.md](docs/THIRD_PARTY.md) を参照してください。PyMuPDFはAGPL/商用デュアルライセンスです。個人のノート・筆跡や収録データセットはコードと別の権利を持つため、所有者の許可なく再配布しないでください。
