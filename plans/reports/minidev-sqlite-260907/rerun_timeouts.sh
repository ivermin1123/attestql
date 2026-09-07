#!/usr/bin/env bash
# Rerun alone, into a fresh directory, every run whose stdout holds a timeout line.
#
# A SQLite statement's budget is wall-clock: `src/attestql/audit/sqlite.py` installs a
# progress handler and stops the statement when a deadline passes. A process that is not
# being scheduled therefore reports a timeout its statement did not earn, and the runs above
# are three at a time for that reason. This is the check that the cap held: the rerun is one
# process on an idle machine, and what it says is what the measurement uses. A timeout that
# survives it is a real one and is named in the report with its serial time.
#
# The old directory is kept beside the new one as `<db>.under-load`, so that a reader can see
# both answers. measure.py reads `<db>`, which after this script is the serial run.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"
ATTESTQL="${ATTESTQL:-attestql}"

ZIP_Q=data/zip/minidev/MINIDEV/mini_dev_sqlite.json
ZIP_ORIGIN="https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip (sha256 cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f, downloaded 2026-09-07), member minidev/MINIDEV/mini_dev_sqlite.json"
ZIP_DATE=2024-06-19
HF_Q=data/hf/mini_dev_sqlite-00000-of-00001.json
HF_ORIGIN="https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/f65faf4ae3b638c1fa6df1d3370c8d92c8366301/data/mini_dev_sqlite-00000-of-00001.json (commit f65faf4a, downloaded 2026-09-07)"
HF_DATE=2026-01-18T08:44:25Z
DATA_ORIGIN="minidev.zip (sha256 cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f), member minidev/MINIDEV/dev_databases"
DATA_DATE=2024-06-13
PRED_BASE="https://raw.githubusercontent.com/bird-bench/mini_dev/b3d4bcbbae9a96934ad812551eb400c7a3b23c12/llm/exp_result/sql_output_kg"
PRED_DATE=2024-06-19

found=0
for stdout in out/tool/zip/*/*/stdout.txt out/tool/hf/*/*/stdout.txt; do
  [ -f "$stdout" ] || continue
  out="$(dirname "$stdout")"
  # A directory this script already moved aside is the under-load answer it kept, not a run to
  # redo; without this a second pass would rerun the reruns and lose the serial ones.
  case "$out" in *.under-load) continue;; esac
  grep -qiE 'timeout|timed out' "$stdout" || continue
  db="$(basename "$out")"; model="$(basename "$(dirname "$out")")"; gold="$(basename "$(dirname "$(dirname "$out")")")"
  found=$((found + 1))
  echo "timeout under load: $gold $model $db"
  grep -inE 'timeout|timed out' "$stdout" | sed 's/^/    /'
  case "$gold" in
    zip) q="$ZIP_Q"; qo="$ZIP_ORIGIN"; qd="$ZIP_DATE" ;;
    hf)  q="$HF_Q";  qo="$HF_ORIGIN";  qd="$HF_DATE" ;;
  esac
  predictions=()
  if [ "$model" != "gold-only" ]; then
    file="predict_mini_dev_${model}_sqlite.json"
    case "$gold" in
      zip) predictions=(--predictions "data/preds/$file" --predictions-keyed-by position
                        --predictions-origin "$PRED_BASE/$file") ;;
      hf)  predictions=(--predictions "data/preds-by-id/$file" --predictions-keyed-by question-id
                        --predictions-origin "$PRED_BASE/$file, re-keyed by question id with predictions_by_question_id.py") ;;
    esac
    predictions+=(--predictions-date "$PRED_DATE")
  fi
  ids="$(python3 "$here/question_ids.py" "$q" "$db")"
  rm -rf "$out.under-load"; mv "$out" "$out.under-load"
  mkdir -p "$out"
  start=$SECONDS
  $ATTESTQL audit --engine sqlite --dsn "data/zip/minidev/MINIDEV/dev_databases/$db/$db.sqlite" \
    --questions "$q" --questions-origin "$qo" --questions-date "$qd" --ids "$ids" \
    --data-file "data/zip/minidev/MINIDEV/dev_databases/$db/$db.sqlite" \
    --data-origin "$DATA_ORIGIN, $db/$db.sqlite" --data-date "$DATA_DATE" \
    "${predictions[@]}" --out "$out" > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "  rerun alone in $((SECONDS - start))s, exit=$status: $(tail -1 "$out/stdout.txt")"
  if grep -qiE 'timeout|timed out' "$out/stdout.txt"; then
    echo "  TIMEOUT SURVIVED THE SERIAL RERUN"
    grep -inE 'timeout|timed out' "$out/stdout.txt" | sed 's/^/    /'
  fi
done
echo "runs holding a timeout line: $found"
