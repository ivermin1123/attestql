#!/usr/bin/env bash
# Regenerate the measurement from public inputs and prediction URLs.
set -euo pipefail
here="$(cd "$(dirname "$BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
: "${MEASURE_WORK:?set MEASURE_WORK outside the repository}"
: "${ATTESTQL_INPUTS:?set ATTESTQL_INPUTS to the read-only input cache}"
MEASURE_WORK="$(mkdir -p "$MEASURE_WORK" && cd "$MEASURE_WORK" && pwd)"
ATTESTQL_INPUTS="$(cd "$ATTESTQL_INPUTS" && pwd)"
export MEASURE_WORK
case "$MEASURE_WORK" in "$repo"|"$repo"/*) echo "work directory must be outside repo" >&2; exit 2;; esac
cd "$MEASURE_WORK"
mkdir -p data/dev data/hf data/preds bird_repo out

verify() { echo "$2  $1" | shasum -a 256 --check --status || { echo "digest mismatch: $1" >&2; exit 1; }; }

# Fill the input cache only where a file is absent, then link the fixed relative paths.
if [ ! -f "$ATTESTQL_INPUTS/dev/dev_20240627/dev.json" ]; then
  mkdir -p "$ATTESTQL_INPUTS/dev"
  curl -sSL 'https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip' -o "$ATTESTQL_INPUTS/dev.zip"
  unzip -o -q "$ATTESTQL_INPUTS/dev.zip" -d "$ATTESTQL_INPUTS/dev"
fi
if [ ! -f "$ATTESTQL_INPUTS/dev_20251106.json" ]; then
  curl -sSL 'https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/3c11fb193e5439b338e23677fa0aae11e8b85db9/data/dev_20251106-00000-of-00001.json' \
    -o "$ATTESTQL_INPUTS/dev_20251106.json"
fi
ln -sfn "$ATTESTQL_INPUTS/dev/dev_20240627" data/dev/dev_20240627
ln -sfn "$ATTESTQL_INPUTS/dev/dev_20240627/dev_databases" data/dev/dev_databases
ln -sfn "$ATTESTQL_INPUTS/dev_20251106.json" data/hf/dev_20251106-00000-of-00001.json
python3 "$here/check_inputs.py"

python3 "$here/fetch_predictions.py"
if [ ! -f bird_repo/evaluation.py ]; then
  curl -sSL 'https://raw.githubusercontent.com/AlibabaResearch/DAMO-ConvAI/dec31ae335d7a5168ee17d5cc40c105e0da66d4e/bird/llm/src/evaluation.py' \
    -o bird_repo/evaluation.py
fi
verify bird_repo/evaluation.py 2f591e559dc2d97e5b35d5b656e80b0c2edf968f0bb5a78ddfd1d88b4bbbc472

[ -d venv ] || { uv venv venv --python 3.13 -q && uv pip install --python venv/bin/python -q "$repo"; }
[ -d birdenv ] || { uv venv birdenv --python 3.13 -q && uv pip install --python birdenv/bin/python -q func_timeout; }
export ATTESTQL="$MEASURE_WORK/venv/bin/attestql"

python3 "$here/prepare_database.py"
python3 "$here/predictions_readable.py"
python3 "$here/check_predictions.py"
bash "$here/run_predictions.sh"
bash "$here/rerun_timeouts.sh"

bash "$here/run_official.sh"
python3 "$here/measure_predictions.py"
python3 "$here/credits_moved.py"
python3 "$here/sample_rows.py"
python3 "$here/classify.py"
python3 "$here/copy_results.py"
GIT_SHA="${GIT_SHA:-$(git -C "$repo" rev-parse HEAD)}" python3 "$here/build_report.py"
echo "done: $MEASURE_WORK/out/prediction-measurement.json"
