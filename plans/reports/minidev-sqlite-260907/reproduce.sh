#!/usr/bin/env bash
# Reproduce every number of measurement-260907-1106-minidev-sqlite.md.
#
#   MEASURE_WORK=<work-directory> plans/reports/minidev-sqlite-260907/reproduce.sh
#
# Needs: uv, curl, unzip. No container and no server: an audit of a SQLite file opens the
# file. The work directory must be outside the repository; it receives the 800 MB zip, the
# eleven databases it holds, the prediction files, a virtual environment holding this
# repository, and every output. It is reusable: the next phase reads BIRD dev, whose
# databases are the same eleven files, and it may be deleted once that phase is done.
# Nothing BIRD publishes is copied into the repository: the report cites each file by URL
# and sha256, and the copies of the outputs committed beside this script are the ones
# build_artifact.py selects.
#
# Steps: download and verify the inputs; install the tool once from this repository at the
# commit the measurement runs at; run the tool over both gold copies (run_tool.sh, three
# processes at a time); rerun alone every run whose stdout holds a timeout line; run the
# three corrected golds; score every file with BIRD's own evaluator (bird_ex_official.py,
# three at a time); count (measure.py, classify.py, aggregate.py).
#
# The cap of three processes is not a tuning knob. A SQLite statement's budget is
# wall-clock, kept by a progress handler against a deadline, so a starved process reports a
# timeout its statement did not earn: an earlier attempt at this measurement ran twenty
# processes at load average 61 and produced 19 gold timeouts that a serial rerun did not
# reproduce.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
: "${MEASURE_WORK:?set MEASURE_WORK to a directory outside the repository}"
MEASURE_WORK="$(mkdir -p "$MEASURE_WORK" && cd "$MEASURE_WORK" && pwd)"
export MEASURE_WORK
case "$MEASURE_WORK" in "$repo"|"$repo"/*) echo "the work directory must be outside the repository" >&2; exit 2;; esac
cd "$MEASURE_WORK"
mkdir -p data/preds data/preds-by-id data/hf data/zip minidev_repo out

verify() { echo "$2  $1" | shasum -a 256 --check --status || { echo "digest mismatch: $1" >&2; exit 1; }; }

# 1. Inputs, each verified against the digest the report states.
[ -f data/minidev.zip ] || curl -sSL "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip" -o data/minidev.zip
verify data/minidev.zip cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f
unzip -o -q data/minidev.zip "minidev/MINIDEV/mini_dev_sqlite.json" "minidev/MINIDEV/mini_dev_sqlite_gold.sql" "minidev/MINIDEV/dev_databases/*" -d data/zip
verify data/zip/minidev/MINIDEV/mini_dev_sqlite.json 4ba5fa8de55856222f484d380d2ba872b380bf79d825de70478e2120cb0fc43b
verify data/zip/minidev/MINIDEV/mini_dev_sqlite_gold.sql 6fb891aa8e1d948499de3295a24dd18d783d7ac04971908cbe2533436901af81
curl -sSL "https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/f65faf4ae3b638c1fa6df1d3370c8d92c8366301/data/mini_dev_sqlite-00000-of-00001.json" -o data/hf/mini_dev_sqlite-00000-of-00001.json
verify data/hf/mini_dev_sqlite-00000-of-00001.json 88ceb0710163cae46a256ecea8f0a8c98286599530b60587fda5c3cfe57d45d2
commit=b3d4bcbbae9a96934ad812551eb400c7a3b23c12
while read -r model digest; do
  f="predict_mini_dev_${model}_sqlite.json"
  [ -f "data/preds/$f" ] || curl -sSL "https://raw.githubusercontent.com/bird-bench/mini_dev/$commit/llm/exp_result/sql_output_kg/$f" -o "data/preds/$f"
  verify "data/preds/$f" "$digest"
done < "$here/SHA256SUMS.predictions"
for f in evaluation_ex.py evaluation_utils.py; do
  [ -f "minidev_repo/$f" ] || curl -sSL "https://raw.githubusercontent.com/bird-bench/mini_dev/$commit/evaluation/$f" -o "minidev_repo/$f"
done
verify minidev_repo/evaluation_ex.py da1bbcd4530be83692d7c650c814ea9704bb710d0c953eb75d02ccb38233cf89
verify minidev_repo/evaluation_utils.py f6943d249caac5aeaef9bce21d43dbf29dcef85a0c965a76df032a9542f308bf
# The eleven databases are members of the zip and are covered by its digest; the audit
# records each one's own digest in the run's summary.json under fixture.source.

# The predictions, re-keyed by question id for the Hugging Face copy, whose two extra ids the
# positions do not name.
for f in data/preds/*.json; do
  python3 "$here/predictions_by_question_id.py" data/zip/minidev/MINIDEV/mini_dev_sqlite.json \
    "$f" "data/preds-by-id/$(basename "$f")"
done
# The corrected golds: the three statements the SQLite sandbox fixture carries as its
# predictions, against the Hugging Face copy's own question, evidence and difficulty.
python3 - "$repo" <<'PY'
import json, sys
from pathlib import Path
repo = Path(sys.argv[1])
fix = json.load(open(repo / "tools/audit-sandbox-sqlite/predictions.json"))
hf = {e["question_id"]: e for e in json.load(open("data/hf/mini_dev_sqlite-00000-of-00001.json"))}
out = [{**{k: hf[int(i)][k] for k in ("question_id", "db_id", "question", "evidence")},
        "SQL": sql, "difficulty": hf[int(i)]["difficulty"]}
       for i, sql in fix.items() if int(i) in hf]
json.dump(out, open("data/corrected-gold.json", "w"), indent=1, ensure_ascii=False)
PY

# 2. The tool, installed once from this repository. `uv run` per invocation resolves the
# environment 247 times and is what an earlier attempt found too slow to finish in a day.
# Python 3.13 on purpose: the measured engine is the SQLite the library links, and 3.13 is what
# `just check` runs, so the run and the gate answer on the same library (3.53.4 here).
[ -d venv ] || { uv venv venv --python 3.13 -q && uv pip install --python venv/bin/python -q "$repo"; }
# psycopg2 and pymysql are imported at the top of upstream's evaluation_utils.py, for the two
# dialects this measurement does not use; the module does not import without them.
[ -d birdenv ] || { uv venv birdenv --python 3.13 -q && uv pip install --python birdenv/bin/python -q psycopg2-binary pymysql func_timeout; }
export ATTESTQL="$MEASURE_WORK/venv/bin/attestql"

# 3. The runs: 220 of them, three at a time; then every timeout rerun alone; then the
# corrected golds.
bash "$here/run_tool.sh"
bash "$here/rerun_timeouts.sh"
DBS=(european_football_2 formula_1 toxicology)
IDS=(1029 879 207)
for model in $(sed 's/ .*//' "$here/SHA256SUMS.predictions"); do
  for index in 0 1 2; do
    out="out/tool/corrected/$model/${DBS[$index]}"
    [ -f "$out/summary.json" ] && continue
    rm -rf "$out"; mkdir -p "$out"
    "$ATTESTQL" audit --engine sqlite \
      --dsn "data/zip/minidev/MINIDEV/dev_databases/${DBS[$index]}/${DBS[$index]}.sqlite" \
      --questions data/corrected-gold.json \
      --questions-origin "the three golds of tools/audit-sandbox-sqlite/predictions.json, against the Hugging Face copy's own question text" \
      --ids "${IDS[$index]}" \
      --predictions "data/preds-by-id/predict_mini_dev_${model}_sqlite.json" \
      --predictions-keyed-by question-id --out "$out" \
      > "$out.stdout.txt" 2> "$out.stderr.txt" || true
    mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  done
done

# 4. BIRD's own evaluator, three at a time, and the counts.
for gold in zip hf; do
  running=0
  for f in data/preds/*.json; do
    m="$(basename "$f" .json)"; m="${m#predict_mini_dev_}"; m="${m%_sqlite}"
    birdenv/bin/python "$here/bird_ex_official.py" "$gold" "$f" "out/official/$gold/$m.json" &
    running=$((running + 1)); [ "$running" -ge 3 ] && { wait -n; running=$((running - 1)); }
  done
  wait
done
python3 "$here/measure.py"
python3 "$here/classify.py"
python3 "$here/aggregate.py"
echo "done: $MEASURE_WORK/out/aggregate.json"
