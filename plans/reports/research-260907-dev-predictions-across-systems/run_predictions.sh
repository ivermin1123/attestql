#!/usr/bin/env bash
# Run prediction mode over every selected file, one run per copy/file/database, three at a time.
set -uo pipefail
here="$(cd "$(dirname "$BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"

OLD_Q=data/dev/dev_20240627/dev.json
OLD_ORIGIN="https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip (sha256 cdd6f19faeb45a23970b98d3ef4c40a87987c95459c2cf12076897a60cf5a630, Last-Modified 2024-06-29), member dev_20240627/dev.json"
OLD_DATE=2024-06-27
NEW_Q=data/hf/dev_20251106-00000-of-00001.json
NEW_ORIGIN="https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/3c11fb193e5439b338e23677fa0aae11e8b85db9/data/dev_20251106-00000-of-00001.json (commit 3c11fb19)"
NEW_DATE=2026-01-18T08:51:02Z
DATA_ORIGIN="dev.zip (sha256 cdd6f19faeb45a23970b98d3ef4c40a87987c95459c2cf12076897a60cf5a630), member dev_20240627/dev_databases.zip, dev_databases"
DATA_DATE=2024-06-14
ATTESTQL="${ATTESTQL:-attestql}"

DATABASES=(
  european_football_2 formula_1 card_games codebase_community thrombosis_prediction
  toxicology student_club superhero financial california_schools debit_card_specializing
)
FILES=(
  alpha-sql-dev.json
  predict_dev-codes-1b-bird.json predict_dev-codes-1b-bird-with-evidence.json
  predict_dev-codes-3b-bird.json predict_dev-codes-3b-bird-with-evidence.json
  predict_dev-codes-7b-bird.json predict_dev-codes-7b-bird-with-evidence.json
  predict_dev-codes-15b-bird.json predict_dev-codes-15b-bird-with-evidence.json
  rsl-sql-deepseek.txt rsl-sql-gpt-4o.txt
  dail-sql-gpt-4-7shot-mask-thr-0.8.txt dail-sql-gpt-4-7shot-mask-thr-0.85.txt
  dail-sql-gpt-4-7shot-questionmask.txt dail-sql-gpt-4-9shot-mask-thr.txt
  dail-sql-gpt-4-9shot-questionmask.txt gsr-gpt-4o.sql
  csc-sql-7b.sql csc-sql-32b.sql
  atlas-core-20260301.sql atlas-core-20260324.sql
)

database_path() {
  if [ "$1" = card_games ]; then
    printf '%s\n' "data/dev/copies/card_games/card_games.sqlite"
  else
    printf '%s\n' "data/dev/dev_databases/$1/$1.sqlite"
  fi
}

one() {  # one <copy> <prediction file> <db_id>
  local copy="$1" file="$2" db="$3" q qo qd out ids status start db_path keying origin
  case "$copy" in
    old) q="$OLD_Q"; qo="$OLD_ORIGIN"; qd="$OLD_DATE" ;;
    dev1106) q="$NEW_Q"; qo="$NEW_ORIGIN"; qd="$NEW_DATE" ;;
  esac
  out="out/tool-predictions/$copy/$file/$db"
  if [ -f "$out/summary.json" ]; then echo "$copy $file $db already run"; return 0; fi
  ids="$(python3 "$here/question_ids.py" "$q" "$db")"
  db_path="$(database_path "$db")"
  case "$file" in
    alpha-sql-dev.json|dail-sql-*) keying=question-id ;;
    *) keying=position ;;
  esac
  provenance="$(python3 - "$here" "$file" <<'PY'
import json
import sys
from pathlib import Path
sources = json.loads((Path(sys.argv[1]) / "sources.json").read_text())
row = next(row for row in sources["accepted"] if row["name"] == sys.argv[2])
print(row["url"] + ", wrapped for JSON-only prediction files by predictions_readable.py")
print(row["commit_date"])
PY
)"
  origin="$(printf '%s\n' "$provenance" | sed -n 1p)"
  pdate="$(printf '%s\n' "$provenance" | sed -n 2p)"
  rm -rf "$out"; mkdir -p "$out"
  start=$SECONDS
  $ATTESTQL audit --engine sqlite --dsn "$db_path" \
    --questions "$q" --questions-origin "$qo" --questions-date "$qd" --ids "$ids" \
    --data-file "$db_path" --data-origin "$DATA_ORIGIN, $db/$db.sqlite" \
    --data-date "$DATA_DATE" --predictions "data/preds-run/$file.json" \
    --predictions-keyed-by "$keying" --predictions-origin "$origin" \
    --predictions-date "$pdate" --out "$out" \
    > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "$copy $file $db exit=$status in $((SECONDS - start))s: $(tail -1 "$out/stdout.txt")"
}

running=0
for copy in old dev1106; do
  for file in "${FILES[@]}"; do
    for db in "${DATABASES[@]}"; do
      one "$copy" "$file" "$db" &
      running=$((running + 1))
      [ "$running" -ge 3 ] && { wait -n; running=$((running - 1)); }
    done
  done
done
wait
echo ALL_DONE
