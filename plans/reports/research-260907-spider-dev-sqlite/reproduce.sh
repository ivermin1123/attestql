#!/usr/bin/env bash
# Verify the pinned Spider inputs, install this tree once, and regenerate every measurement.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
: "${MEASURE_WORK:?set MEASURE_WORK to a directory outside the repository}"
: "${ATTESTQL_INPUTS:?set ATTESTQL_INPUTS to the shared read-only inputs directory}"
MEASURE_WORK="$(mkdir -p "$MEASURE_WORK" && cd "$MEASURE_WORK" && pwd)"
ATTESTQL_INPUTS="$(cd "$ATTESTQL_INPUTS" && pwd)"
export MEASURE_WORK ATTESTQL_INPUTS
case "$MEASURE_WORK" in "$repo"|"$repo"/*) echo "the work directory must be outside the repository" >&2; exit 2;; esac
cd "$MEASURE_WORK"

ZIP_SHA=00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b
BEFORE_SHA=6d3ac4f5e2657e30ff9418353be9f1360fe6517075809b8c13bc7a9c3f82a02a
AFTER_SHA=36e8c72ec576cc78a225b1f039d5269239d9c80ded027b748fe28aba6797cccf
PRED_SHA=913576f655c6ca9a00762c83acf05234006fae164826e9577cbd1373d07274d2
verify() { echo "$2  $1" | shasum -a 256 --check --status || { echo "digest mismatch: $1" >&2; exit 1; }; }

mkdir -p data/spider data/spider-2020 data/predict_sources out
if [ -f "$ATTESTQL_INPUTS/spider_data.zip" ]; then
  cp "$ATTESTQL_INPUTS/spider_data.zip" data/spider_data.zip
else
  uvx gdown 1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J -O data/spider_data.zip
fi
verify data/spider_data.zip "$ZIP_SHA"
unzip -o -q data/spider_data.zip 'spider_data/dev.json' 'spider_data/dev_gold.sql' 'spider_data/tables.json' -d data/spider
python3 - > data/dev-dbs.txt <<'PY'
import json
from pathlib import Path
entries = json.loads(Path("data/spider/spider_data/dev.json").read_text())
for db in sorted({entry["db_id"] for entry in entries}):
    print(db)
PY
while IFS= read -r db; do
  unzip -o -q data/spider_data.zip "spider_data/database/$db/*" -d data/spider
done < data/dev-dbs.txt

# The two 2020 sides are always refetched from the pinned commits, even when a shared copy exists.
gh api 'repos/taoyds/spider/contents/evaluation_examples/dev.sql?ref=e0b7bc91' \
  --header 'Accept: application/vnd.github.raw+json' > data/spider-2020/dev.sql.before
gh api 'repos/taoyds/spider/contents/evaluation_examples/dev.sql?ref=25fcd85d' \
  --header 'Accept: application/vnd.github.raw+json' > data/spider-2020/dev.sql.after
verify data/spider-2020/dev.sql.before "$BEFORE_SHA"
verify data/spider-2020/dev.sql.after "$AFTER_SHA"
gh api 'repos/RUCKBReasoning/codes/contents/results/pred_sqls-codes-1b-spider.txt?ref=e203386173eecf6fbe8b14cf233611a2fb7c994e' \
  --header 'Accept: application/vnd.github.raw+json' > data/predict_sources/pred_sqls-codes-1b-spider.txt
verify data/predict_sources/pred_sqls-codes-1b-spider.txt "$PRED_SHA"

[ -d venv ] || { uv venv venv --python 3.13 -q && uv pip install --python venv/bin/python -q "$repo"; }
PY=venv/bin/python
export ATTESTQL="$MEASURE_WORK/venv/bin/attestql"
rm -rf out data/questions-*.json data/predictions-codes.json
mkdir out

"$PY" "$here/prepare.py"
bash "$here/run_tool.sh"
MEASURE_WORK="$MEASURE_WORK" ATTESTQL="$ATTESTQL" "$PY" "$here/rerun_timeouts.py"
"$PY" "$here/measure.py"
"$PY" "$here/replay_corrections.py"
"$PY" "$here/prepare_predictions.py"
bash "$here/run_predictions.sh"
MEASURE_WORK="$MEASURE_WORK" ATTESTQL="$ATTESTQL" "$PY" "$here/rerun_timeouts.py"
"$PY" "$here/measure_predictions.py"
"$PY" "$here/classify.py"
"$PY" "$here/build_artifact.py"
echo "done: $MEASURE_WORK/out and $here"
