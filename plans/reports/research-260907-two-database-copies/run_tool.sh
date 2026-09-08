#!/usr/bin/env bash
# Gold-only AttestQL runs over both copies of the five differing databases.
#
# Expects MEASURE_WORK filled by reproduce.sh and ATTESTQL pointing at the tool installed from
# this worktree. Three runs at a time; rerun_timeouts.sh gives every timeout one serial retry.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"

QUESTION=data/dev/dev_20240627/dev.json
QUESTION_ORIGIN="https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip (sha256 cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630, Last-Modified 2024-06-29, downloaded 2026-09-07), member dev_20240627/dev.json"
QUESTION_DATE=2024-06-27
ATTESTQL="${ATTESTQL:-attestql}"
DATABASES=(formula_1 european_football_2 toxicology thrombosis_prediction california_schools)

one() {  # one <copy> <db_id>
  local copy="$1" db="$2" root origin date out ids status start
  case "$copy" in
    dev)
      root=data/dev/dev_databases
      origin="dev.zip (sha256 cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630), member dev_20240627/dev_databases.zip, dev_databases"
      date=2024-06-14 ;;
    minidev)
      root=data/zip/minidev/MINIDEV/dev_databases
      origin="minidev.zip (sha256 cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f), member minidev/MINIDEV/dev_databases"
      date=2024-06-14 ;;
    *) return 2 ;;
  esac
  out="out/tool/$copy/$db"
  if [ -f "$out/summary.json" ]; then echo "$copy $db already run"; return 0; fi
  ids="$(python3 "$here/question_ids.py" "$QUESTION" "$db")"
  rm -rf "$out"; mkdir -p "$out"
  start=$SECONDS
  $ATTESTQL audit --engine sqlite --dsn "$root/$db/$db.sqlite" \
    --questions "$QUESTION" --questions-origin "$QUESTION_ORIGIN" --questions-date "$QUESTION_DATE" \
    --ids "$ids" --data-file "$root/$db/$db.sqlite" --data-origin "$origin, $db/$db.sqlite" \
    --data-date "$date" --out "$out" > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "$copy $db exit=$status in $((SECONDS - start))s: $(tail -1 "$out/stdout.txt")"
}

running=0
for copy in dev minidev; do
  for db in "${DATABASES[@]}"; do
    one "$copy" "$db" &
    running=$((running + 1))
    [ "$running" -ge 3 ] && { wait -n; running=$((running - 1)); }
  done
done
wait
echo ALL_DONE
