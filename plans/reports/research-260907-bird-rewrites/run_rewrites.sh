#!/usr/bin/env bash
# Replay BIRD's rewritten SQL as predictions against the old golds, one run per database.
#
# Two groups: rewrite-399 is the measurement; text-only-172 repeats unchanged SQL and is the
# harness check. Three SQLite processes at a time, longest databases first.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${MEASURE_WORK:?set MEASURE_WORK}"
: "${ATTESTQL:?set ATTESTQL to the venv attestql}"
cd "$MEASURE_WORK"

OLD_ORIGIN="https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip (sha256 cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630, Last-Modified 2024-06-29, downloaded 2026-09-07), member dev_20240627/dev.json"
REWRITE_ORIGIN="https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/3c11fb193e5439b338e23677fa0aae11e8b85db9/data/dev_20251106-00000-of-00001.json (commit 3c11fb19, downloaded 2026-09-07), SQL for the audited ids selected by split.py"
HARNESS_ORIGIN="dev.zip member dev_20240627/dev.json (sha256 630272f2b1c44d8cef2c3b246f623355cf0bbc1e832c81061df895530dfc2f06), unchanged SQL for the audited ids selected by split.py"
DATA_ORIGIN="dev.zip (sha256 cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630), member dev_20240627/dev_databases.zip, dev_databases"
DATABASES=(european_football_2 formula_1 card_games codebase_community thrombosis_prediction toxicology student_club superhero financial california_schools debit_card_specializing)

one() { # one <group> <db>
  local group="$1" db="$2" out origin date status start database
  out="out/tool/$group/$db"
  origin="$REWRITE_ORIGIN"; date=2026-01-18T08:51:02Z
  [ "$group" = text-only-172 ] && { origin="$HARNESS_ORIGIN"; date=2024-06-27; }
  database="data/dev/dev_databases/$db/$db.sqlite"
  [ -f "data/dev/copies/$db/$db.sqlite" ] && database="data/dev/copies/$db/$db.sqlite"
  if [ -f "$out/summary.json" ]; then echo "$group $db already run"; return 0; fi
  rm -rf "$out"; mkdir -p "$out"
  start=$SECONDS
  "$ATTESTQL" audit --engine sqlite --dsn "$database" \
    --questions data/dev/dev_20240627/dev.json --questions-origin "$OLD_ORIGIN" \
    --questions-date 2024-06-27 --ids "$(cat "out/ids/$group/$db.txt")" \
    --predictions "data/predictions/$group.json" --predictions-origin "$origin" \
    --predictions-date "$date" --data-file "$database" \
    --data-origin "$DATA_ORIGIN, $db/$db.sqlite" --data-date 2024-06-14 --out "$out" \
    > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "$group $db exit=$status in $((SECONDS - start))s: $(tail -1 "$out/stdout.txt")"
}

running=0
for group in rewrite-399 text-only-172; do
  for db in "${DATABASES[@]}"; do
    one "$group" "$db" &
    running=$((running + 1))
    [ "$running" -ge 3 ] && { wait -n; running=$((running - 1)); }
  done
done
wait
echo ALL_DONE
