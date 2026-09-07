#!/usr/bin/env bash
# Run `attestql audit --engine sqlite` gold-only over both copies of the BIRD dev question set.
# Expects MEASURE_WORK filled by reproduce.sh.
#
# A dev question file names eleven databases and `--dsn` takes one file, so a run is per
# database: eleven invocations per copy, each with `--ids` holding that database's question ids
# and `--dsn` its own `.sqlite`, each writing its own `summary.json`. measure.py merges the
# eleven into one row per copy. Nothing about the tool changes for a measurement.
#
# Three processes at a time. A SQLite statement's budget is wall clock, kept by a progress
# handler against a deadline, so a starved process reports a timeout its statement did not earn;
# the cap is what keeps a reported timeout meaningful, and rerun_timeouts.sh is the check that it
# held. The 22 runs are ordered longest-database-first so the two that dominate start first.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"

OLD_Q=data/dev/dev_20240627/dev.json
OLD_ORIGIN="https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip (sha256 cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630, Last-Modified 2024-06-29, downloaded 2026-09-07), member dev_20240627/dev.json"
OLD_DATE=2024-06-27
NEW_Q=data/hf/dev_20251106-00000-of-00001.json
NEW_ORIGIN="https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/3c11fb193e5439b338e23677fa0aae11e8b85db9/data/dev_20251106-00000-of-00001.json (commit 3c11fb19, downloaded 2026-09-07)"
NEW_DATE=2026-01-18T08:51:02Z
DATA_ORIGIN="dev.zip (sha256 cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630), member dev_20240627/dev_databases.zip, dev_databases"
DATA_DATE=2024-06-14
ATTESTQL="${ATTESTQL:-attestql}"

# Longest first: european_football_2 and formula_1 carry the rows the shuffle probe rereads.
DATABASES=(european_football_2 formula_1 card_games codebase_community thrombosis_prediction toxicology student_club superhero financial california_schools debit_card_specializing)

one() {  # one <copy> <db_id>
  local copy="$1" db="$2" q qo qd out ids status start
  case "$copy" in
    old) q="$OLD_Q"; qo="$OLD_ORIGIN"; qd="$OLD_DATE" ;;
    dev1106) q="$NEW_Q"; qo="$NEW_ORIGIN"; qd="$NEW_DATE" ;;
  esac
  out="out/tool/$copy/$db"
  # A summary.json is written at the end of a run, so one that is there is a run that finished
  # and is not made again: that is what lets this script be re-entered after an interruption.
  if [ -f "$out/summary.json" ]; then echo "$copy $db already run"; return 0; fi
  ids="$(python3 "$here/question_ids.py" "$q" "$db")"
  rm -rf "$out"; mkdir -p "$out"
  start=$SECONDS
  $ATTESTQL audit --engine sqlite --dsn "data/dev/dev_databases/$db/$db.sqlite" \
    --questions "$q" --questions-origin "$qo" --questions-date "$qd" --ids "$ids" \
    --data-file "data/dev/dev_databases/$db/$db.sqlite" \
    --data-origin "$DATA_ORIGIN, $db/$db.sqlite" --data-date "$DATA_DATE" \
    --out "$out" > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  # The console output lands in the run's directory only after the run: the tool takes over an
  # empty directory or one it marked, and refuses one that holds a file it did not write.
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "$copy $db exit=$status in $((SECONDS - start))s: $(tail -1 "$out/stdout.txt")"
}

running=0
for copy in old dev1106; do
  for db in "${DATABASES[@]}"; do
    one "$copy" "$db" &
    running=$((running + 1))
    [ "$running" -ge 3 ] && { wait -n; running=$((running - 1)); }
  done
done
wait
echo ALL_DONE
