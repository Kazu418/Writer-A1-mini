#!/bin/sh
set -eu
cd "$(dirname "$0")"
printf '%s\n' 'PlotNote を起動します。ブラウザで http://127.0.0.1:8765 を開いてください。終了: Ctrl+C'
./plotnote serve --workspace jobs
