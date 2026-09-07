#!/usr/bin/env bash
# Run `attestql audit --engine sqlite` over BIRD's own two dev prediction files against both
# copies of the question set. Expects MEASURE_WORK filled by reproduce.sh.
#
# Same shape as run_tool.sh: one run per (copy, prediction file, database), three at a time,
# longest database first. The prediction files are keyed "0" to "1533", the positions of the
# question file's entries, which is what `--predictions-keyed-by position` reads; both copies
# hold the same 1,534 ids in the same order, so one keying answers for both.
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
PRED_BASE="https://raw.githubusercontent.com/AlibabaResearch/DAMO-ConvAI/dec31ae335d7a5168ee17d5cc40c105e0da66d4e/bird/llm/exp_result"
PRED_DATE=2023-06-11
ATTESTQL="${ATTESTQL:-attestql}"

DATABASES=(european_football_2 formula_1 card_games codebase_community thrombosis_prediction toxicology student_club superhero financial california_schools debit_card_specializing)
FILES=(turbo_output turbo_output_kg)

one() {  # one <copy> <prediction file> <db_id>
  local copy="$1" file="$2" db="$3" q qo qd out ids status start
  case "$copy" in
    old) q="$OLD_Q"; qo="$OLD_ORIGIN"; qd="$OLD_DATE" ;;
    dev1106) q="$NEW_Q"; qo="$NEW_ORIGIN"; qd="$NEW_DATE" ;;
  esac
  out="out/tool-predictions/$copy/$file/$db"
  if [ -f "$out/summary.json" ]; then echo "$copy $file $db already run"; return 0; fi
  ids="$(python3 "$here/question_ids.py" "$q" "$db")"
  rm -rf "$out"; mkdir -p "$out"
  start=$SECONDS
  $ATTESTQL audit --engine sqlite --dsn "data/dev/dev_databases/$db/$db.sqlite" \
    --questions "$q" --questions-origin "$qo" --questions-date "$qd" --ids "$ids" \
    --data-file "data/dev/dev_databases/$db/$db.sqlite" \
    --data-origin "$DATA_ORIGIN, $db/$db.sqlite" --data-date "$DATA_DATE" \
    --predictions "data/preds-readable/predict_dev_$file.json" \
    --predictions-keyed-by position \
    --predictions-origin "$PRED_BASE/$file/predict_dev.json, every non-string entry replaced by the single space upstream's package_sqls substitutes (predictions_readable.py)" \
    --predictions-date "$PRED_DATE" \
    --out "$out" > "$out.stdout.txt" 2> "$out.stderr.txt"
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
