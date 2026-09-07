#!/usr/bin/env bash
# Rerun alone, into a fresh directory, every run whose stdout holds a timeout line.
#
# A SQLite statement's budget is wall-clock: `src/attestql/audit/sqlite.py` installs a progress
# handler and stops the statement when a deadline passes. A process that is not being scheduled
# therefore reports a timeout its statement did not earn, and the runs are three at a time for
# that reason. This is the check that the cap held: the rerun is one process on an idle machine,
# and what it says is what the measurement uses. A timeout that survives it is a real one and is
# named in the report with its serial time.
#
# Both layouts are covered: the gold-only runs at `out/tool/<copy>/<db>` and the prediction runs
# at `out/tool-predictions/<copy>/<file>/<db>`. The old directory is kept beside the new one as
# `<db>.under-load`, so that a reader can see both answers; measure.py and
# measure_predictions.py read `<db>`, which after this script is the serial run.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"
ATTESTQL="${ATTESTQL:-attestql}"

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

found=0
for stdout in out/tool/*/*/stdout.txt out/tool-predictions/*/*/*/stdout.txt; do
  [ -f "$stdout" ] || continue
  out="$(dirname "$stdout")"
  # A directory this script already moved aside is the under-load answer it kept, not a run to
  # redo; without this a second pass would rerun the reruns and lose the serial ones. A run
  # whose `.under-load` sibling exists has already been rerun alone and its timeout already
  # judged, so a second pass leaves both directories as they are.
  case "$out" in *.under-load) continue;; esac
  [ -d "$out.under-load" ] && { echo "$out already rerun alone"; continue; }
  grep -qiE 'timeout|timed out' "$stdout" || continue
  db="$(basename "$out")"
  case "$out" in
    out/tool/*) copy="$(basename "$(dirname "$out")")"; file="" ;;
    *) file="$(basename "$(dirname "$out")")"; copy="$(basename "$(dirname "$(dirname "$out")")")" ;;
  esac
  found=$((found + 1))
  echo "timeout under load: $copy ${file:-gold-only} $db"
  grep -inE 'timeout|timed out' "$stdout" | sed 's/^/    /'
  case "$copy" in
    old) q="$OLD_Q"; qo="$OLD_ORIGIN"; qd="$OLD_DATE" ;;
    dev1106) q="$NEW_Q"; qo="$NEW_ORIGIN"; qd="$NEW_DATE" ;;
  esac
  predictions=()
  if [ -n "$file" ]; then
    predictions=(--predictions "data/preds-readable/predict_dev_$file.json"
                 --predictions-keyed-by position
                 --predictions-origin "$PRED_BASE/$file/predict_dev.json, every non-string entry replaced by the single space upstream's package_sqls substitutes (predictions_readable.py)"
                 --predictions-date "$PRED_DATE")
  fi
  ids="$(python3 "$here/question_ids.py" "$q" "$db")"
  rm -rf "$out.under-load"; mv "$out" "$out.under-load"
  mkdir -p "$out"
  start=$SECONDS
  $ATTESTQL audit --engine sqlite --dsn "data/dev/dev_databases/$db/$db.sqlite" \
    --questions "$q" --questions-origin "$qo" --questions-date "$qd" --ids "$ids" \
    --data-file "data/dev/dev_databases/$db/$db.sqlite" \
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
