#!/usr/bin/env bash
# Reproduce the two-database-copy measurement.
#
#   MEASURE_WORK=<work> ATTESTQL_INPUTS=<read-only-inputs> \
#     plans/reports/research-260907-two-database-copies/reproduce.sh
#
# Downloads only what is absent, verifies every digest, keeps all BIRD files outside the
# repository, and never opens more than three SQLite processes at once.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
: "${MEASURE_WORK:?set MEASURE_WORK}"
: "${ATTESTQL_INPUTS:=$HOME/.cache/attestql-measure/inputs}"
MEASURE_WORK="$(mkdir -p "$MEASURE_WORK" && cd "$MEASURE_WORK" && pwd)"
ATTESTQL_INPUTS="$(cd "$ATTESTQL_INPUTS" && pwd)"
export MEASURE_WORK ATTESTQL_INPUTS
case "$MEASURE_WORK" in "$repo"|"$repo"/*) echo "work directory must be outside the repository" >&2; exit 2;; esac
cd "$MEASURE_WORK"
mkdir -p data/dev data/hf data/zip data/preds minidev_repo out/replay out/tool out/official

verify() { echo "$2  $1" | shasum -a 256 --check --status || { echo "digest mismatch: $1" >&2; exit 1; }; }
download_if_absent() { [ -f "$2" ] || curl -sSL "$1" -o "$2"; }

download_if_absent "https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip" "$ATTESTQL_INPUTS/dev.zip"
verify "$ATTESTQL_INPUTS/dev.zip" cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630
[ -f "$ATTESTQL_INPUTS/dev/dev_20240627/dev.json" ] || \
  unzip -q "$ATTESTQL_INPUTS/dev.zip" "dev_20240627/dev.json" "dev_20240627/dev.sql" "dev_20240627/dev_databases/*" -d "$ATTESTQL_INPUTS/dev"
download_if_absent "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip" "$ATTESTQL_INPUTS/minidev.zip"
verify "$ATTESTQL_INPUTS/minidev.zip" cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f
[ -f "$ATTESTQL_INPUTS/minidev/minidev/MINIDEV/mini_dev_sqlite.json" ] || \
  unzip -q "$ATTESTQL_INPUTS/minidev.zip" "minidev/MINIDEV/mini_dev_sqlite.json" "minidev/MINIDEV/mini_dev_sqlite_gold.sql" "minidev/MINIDEV/dev_databases/*" -d "$ATTESTQL_INPUTS/minidev"
download_if_absent "https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/3c11fb193e5439b338e23677fa0aae11e8b85db9/data/dev_20251106-00000-of-00001.json" "$ATTESTQL_INPUTS/dev_20251106.json"
verify "$ATTESTQL_INPUTS/dev_20251106.json" ffd8018378ddb1a8794753e0a31cfc81862ff7318a5184c22f3dc4ce03a03feb
download_if_absent "https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/f65faf4ae3b638c1fa6df1d3370c8d92c8366301/data/mini_dev_sqlite-00000-of-00001.json" "$ATTESTQL_INPUTS/mini_dev_sqlite_hf.json"
verify "$ATTESTQL_INPUTS/mini_dev_sqlite_hf.json" 88ceb0710163cae46a256ecea8f0a8c98286599530b60587fda5c3cfe57d45d2
verify "$ATTESTQL_INPUTS/dev/dev_20240627/dev.json" 630272f2b1c44d8cef2c3b246f623355cf0bbc1e832c81061df895530dfc2f06
verify "$ATTESTQL_INPUTS/minidev/minidev/MINIDEV/mini_dev_sqlite.json" 4ba5fa8de55856222f484d380d2ba872b380bf79d825de70478e2120cb0fc43b

ln -sfn "$ATTESTQL_INPUTS/dev/dev_20240627" data/dev/dev_20240627
ln -sfn "$ATTESTQL_INPUTS/dev/dev_20240627/dev_databases" data/dev/dev_databases
ln -sfn "$ATTESTQL_INPUTS/dev_20251106.json" data/hf/dev_20251106-00000-of-00001.json
ln -sfn "$ATTESTQL_INPUTS/minidev/minidev" data/zip/minidev
ln -sfn "$ATTESTQL_INPUTS/mini_dev_sqlite_hf.json" data/hf/mini_dev_sqlite-00000-of-00001.json

commit=b3d4bcbbae9a96934ad812551eb400c7a3b23c12
while read -r model digest; do
  f="predict_mini_dev_${model}_sqlite.json"
  download_if_absent "https://raw.githubusercontent.com/bird-bench/mini_dev/$commit/llm/exp_result/sql_output_kg/$f" "data/preds/$f"
  verify "data/preds/$f" "$digest"
done < "$here/SHA256SUMS.predictions"
for f in evaluation_ex.py evaluation_utils.py; do
  download_if_absent "https://raw.githubusercontent.com/bird-bench/mini_dev/$commit/evaluation/$f" "minidev_repo/$f"
done
verify minidev_repo/evaluation_ex.py da1bbcd4530be83692d7c650c814ea9704bb710d0c953eb75d02ccb38233cf89
verify minidev_repo/evaluation_utils.py f6943d249caac5aeaef9bce21d43dbf29dcef85a0c965a76df032a9542f308bf

[ -x venv/bin/attestql ] || { uv venv venv --python 3.13 -q && uv pip install --python venv/bin/python -q "$repo"; }
[ -x birdenv/bin/python ] || { uv venv birdenv --python 3.13 -q && uv pip install --python birdenv/bin/python -q psycopg2-binary pymysql func_timeout; }
export ATTESTQL="$PWD/venv/bin/attestql"
PY="$PWD/venv/bin/python"
"$PY" "$here/verify_inputs.py"

for set in dev-20240627 dev-20251106 minidev-hf; do
  "$PY" "$here/replay_pairs.py" "$set" > "out/replay-$set.log" 2>&1 &
done
wait
for set in dev-20240627 dev-20251106 minidev-hf; do "$PY" "$here/replay_pairs.py" "$set" --retry-timeouts; done

bash "$here/run_tool.sh"
bash "$here/rerun_timeouts.sh"
"$PY" "$here/smells_by_copy.py"

# BIRD's evaluator opens card_games read-write even for its SELECTs; the input publication is
# deliberately read-only, so each run gets one byte-identical writable clone of that database.
for copy in dev minidev; do
  case "$copy" in
    dev) source_root=data/dev/dev_databases ;;
    minidev) source_root=data/zip/minidev/MINIDEV/dev_databases ;;
  esac
  target_root="writable-$copy"
  mkdir -p "$target_root/card_games"
  clone="$target_root/card_games/card_games.sqlite"
  if [ ! -f "$clone" ]; then
    cp "$source_root/card_games/card_games.sqlite" "$clone"
    chmod u+w "$clone"
  fi
  verify "$clone" c98bdb57fe7474da798b407785544b9af0daaad5d61fd21e2a73309493bc1227
  for db in california_schools codebase_community debit_card_specializing european_football_2 \
            financial formula_1 student_club superhero thrombosis_prediction toxicology; do
    ln -sfn "$source_root/$db" "$target_root/$db"
  done
done

running=0
for copy in dev minidev; do
  case "$copy" in
    dev) databases=writable-dev ;;
    minidev) databases=writable-minidev ;;
  esac
  while read -r model _digest; do
    f="predict_mini_dev_${model}_sqlite.json"
    birdenv/bin/python "$here/bird_ex_official.py" "data/preds/$f" "out/official/$copy/$model.json" "$databases" &
    running=$((running + 1)); [ "$running" -ge 3 ] && { wait -n; running=$((running - 1)); }
  done < "$here/SHA256SUMS.predictions"
done
wait
verify writable-dev/card_games/card_games.sqlite c98bdb57fe7474da798b407785544b9af0daaad5d61fd21e2a73309493bc1227
verify writable-minidev/card_games/card_games.sqlite c98bdb57fe7474da798b407785544b9af0daaad5d61fd21e2a73309493bc1227
"$PY" "$here/score_flips.py"

cde_url="https://www.cde.ca.gov/ds/si/ds/pubschls.asp"
if [ ! -s out/cde-public.tsv ]; then
  curl -sSL --max-time 60 "$cde_url" -o out/cde-public.tsv > out/cde-download.log 2>&1 || true
fi
if [ -s out/cde-public.tsv ] && head -1 out/cde-public.tsv | grep -qi "$(printf '\t')"; then
  "$PY" "$here/cds.py" out/cde-public.tsv "$cde_url"
else
  "$PY" "$here/cds.py"
fi
"$PY" "$here/column_golds.py"
MEASURE_WORK="$MEASURE_WORK" "$PY" "$here/build_artifact.py"
echo "done: $MEASURE_WORK"
