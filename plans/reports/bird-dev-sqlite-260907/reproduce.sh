#!/usr/bin/env bash
# Reproduce every number of measurement-260907-1435-bird-dev-sqlite.md.
#
#   MEASURE_WORK=<work-directory> plans/reports/bird-dev-sqlite-260907/reproduce.sh
#
# Needs: uv, curl, unzip. No container and no server: an audit of a SQLite file opens the file.
# The work directory must be outside the repository; it receives the 346 MB dev.zip, the eleven
# databases inside it, the 2025-11-06 question file, BIRD's two dev prediction files, a virtual
# environment holding this repository, and every output. Nothing BIRD publishes is copied into
# the repository: the report cites each file by URL and sha256, and the copies of the outputs
# committed beside this script are the ones build_artifact.py selects.
#
# Steps: download and verify the inputs; install the tool once from this repository at the commit
# the measurement runs at; run the gold-only pass over both copies (run_tool.sh, three processes
# at a time); rerun alone every run whose stdout holds a timeout line; count (measure.py) and
# classify (classify.py); then, because a public dev prediction file with a clear licence exists,
# run prediction mode over it and score it with BIRD's own dev evaluator.
#
# The cap of three processes is not a tuning knob. A SQLite statement's budget is wall-clock,
# kept by a progress handler against a deadline, so a starved process reports a timeout its
# statement did not earn: the Mini-Dev measurement before this one ran twenty processes at load
# average 61 and produced 19 gold timeouts that a serial rerun did not reproduce.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
: "${MEASURE_WORK:?set MEASURE_WORK to a directory outside the repository}"
MEASURE_WORK="$(mkdir -p "$MEASURE_WORK" && cd "$MEASURE_WORK" && pwd)"
export MEASURE_WORK
case "$MEASURE_WORK" in "$repo"|"$repo"/*) echo "the work directory must be outside the repository" >&2; exit 2;; esac
cd "$MEASURE_WORK"
mkdir -p data/dev data/hf data/preds data/preds-readable bird_repo out

verify() { echo "$2  $1" | shasum -a 256 --check --status || { echo "digest mismatch: $1" >&2; exit 1; }; }

# 1. Inputs, each verified against the digest the report states.
#
# The OSS endpoint stalls mid-transfer often enough that a single curl does not finish; each
# attempt gives up on a stalled transfer and the next resumes from the bytes already on disk.
want=346207293
for _ in $(seq 1 200); do
  have=$(wc -c < data/dev.zip 2>/dev/null || echo 0)
  [ "$have" -ge "$want" ] && break
  curl -sSL -C - --speed-time 20 --speed-limit 10240 --max-time 600 \
    "https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip" -o data/dev.zip || true
done
verify data/dev.zip cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630
unzip -o -q data/dev.zip -d data/dev
verify data/dev/dev_20240627/dev.json 630272f2b1c44d8cef2c3b246f623355cf0bbc1e832c81061df895530dfc2f06
unzip -o -q data/dev/dev_20240627/dev_databases.zip -d data/dev
# The 2025-11-06 pass, at the dataset commit the report pins rather than at main.
curl -sSL "https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/3c11fb193e5439b338e23677fa0aae11e8b85db9/data/dev_20251106-00000-of-00001.json" \
  -o data/hf/dev_20251106-00000-of-00001.json
verify data/hf/dev_20251106-00000-of-00001.json ffd8018378ddb1a8794753e0a31cfc81862ff7318a5184c22f3dc4ce03a03feb
# BIRD's own dev predictions and the evaluator it ships for the dev set.
commit=dec31ae335d7a5168ee17d5cc40c105e0da66d4e
base="https://raw.githubusercontent.com/AlibabaResearch/DAMO-ConvAI/$commit/bird/llm"
for f in turbo_output turbo_output_kg; do
  curl -sSL "$base/exp_result/$f/predict_dev.json" -o "data/preds/predict_dev_$f.json"
done
verify data/preds/predict_dev_turbo_output.json 4e74ed8a34192f60f65751beef7da7d6dd0b6ee71d894ecfe642bbf46786d181
verify data/preds/predict_dev_turbo_output_kg.json 1511489c56a7845ac281110a801fc8d21d8d332f7c230d411620878e9abda8c4
curl -sSL "$base/src/evaluation.py" -o bird_repo/evaluation.py
verify bird_repo/evaluation.py 2f591e559dc2d97e5b35d5b656e80b0c2edf968f0bb5a78ddfd1d88b4bbbc472
# The eleven databases are members of dev_databases.zip, itself a member of dev.zip, and are
# covered by its digest; the audit records each one's own digest in its summary.json under
# fixture.source. Five of the eleven are not the files Mini-Dev ships, which the report states;
# these are dev.zip's own, which is what BIRD dev is answered against.
python3 "$here/check_inputs.py"

# 2. The tool, installed once from this repository. Python 3.13 on purpose: the measured engine
# is the SQLite the library links, and 3.13 is what `just check` runs, so the run and the gate
# answer on the same library (3.53.4 here).
[ -d venv ] || { uv venv venv --python 3.13 -q && uv pip install --python venv/bin/python -q "$repo"; }
# func_timeout is what upstream's evaluator imports; it runs in its own environment so that
# nothing it needs can reach the environment the tool is measured in.
[ -d birdenv ] || { uv venv birdenv --python 3.13 -q && uv pip install --python birdenv/bin/python -q func_timeout; }
export ATTESTQL="$MEASURE_WORK/venv/bin/attestql"

# 3. The gold-only pass: 22 runs, three at a time; then every timeout rerun alone; then count.
bash "$here/run_tool.sh"
bash "$here/rerun_timeouts.sh"
python3 "$here/measure.py"
python3 "$here/classify.py"

# 4. Prediction mode over BIRD's own dev predictions, and BIRD's own scoring of the same files.
for f in turbo_output turbo_output_kg; do
  python3 "$here/predictions_readable.py" "data/preds/predict_dev_$f.json" \
    "data/preds-readable/predict_dev_$f.json" "out/predictions-$f-changed.json"
done
bash "$here/run_predictions.sh"
for copy in old dev1106; do
  for f in turbo_output turbo_output_kg; do
    birdenv/bin/python "$here/bird_ex_official.py" "$copy" \
      "data/preds/predict_dev_$f.json" "out/official/$copy/$f.json"
  done
done
python3 "$here/measure_predictions.py"
echo "done: $MEASURE_WORK/out/measurement.json and $MEASURE_WORK/out/prediction-measurement.json"
