#!/usr/bin/env bash
# Run `attestql audit --engine sqlite` over every BIRD prediction file against both gold copies,
# and gold-only over each copy. Expects MEASURE_WORK filled by reproduce.sh.
#
# A Mini-Dev question file names eleven databases and `--dsn` takes one file, so a run is per
# database: eleven invocations per (gold copy, prediction file), each with `--ids` holding that
# database's question ids and `--dsn` its own `.sqlite`, each writing its own `summary.json`.
# measure.py merges the eleven into one row per file per copy. Nothing about the tool changes for
# a measurement.
#
# Three lanes at a time. A lane is one gold copy's whole pass; the databases inside it are read
# one after another, so at most three files are open. Three rather than more because the
# PostgreSQL measurement found six lanes starving the server; here every lane reads its own file
# and the risk is the page cache rather than a server, which is a reason to keep the bound and
# not a reason to raise it.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"

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
ATTESTQL="${ATTESTQL:-attestql}"

DATABASES=(california_schools card_games codebase_community debit_card_specializing european_football_2 financial formula_1 student_club superhero thrombosis_prediction toxicology)
MODELS=(gpt-35-turbo-instruct gpt-35-turbo gpt-4-32k gpt-4-turbo gpt-4 meta-llama-3-70b-instruct-2 meta-llama-3-8b-instruct-2 mistralai-mixtral-8x7b-instru-4 phi-3-medium-128k-instruct-1)

one() {  # one <gold copy> <model or gold-only>
  local gold="$1" model="$2" q qo qd predictions=() start status
  case "$gold" in
    zip) q="$ZIP_Q"; qo="$ZIP_ORIGIN"; qd="$ZIP_DATE" ;;
    hf)  q="$HF_Q";  qo="$HF_ORIGIN";  qd="$HF_DATE" ;;
  esac
  if [ "$model" != "gold-only" ]; then
    local file="predict_mini_dev_${model}_sqlite.json"
    case "$gold" in
      # The zip's own copy is what the positions were written against, so it is compared under
      # position keying; the Hugging Face copy holds two ids the positions do not name, so the
      # same file is re-keyed by id against the zip's entry order first.
      zip) predictions=(--predictions "data/preds/$file" --predictions-keyed-by position
                        --predictions-origin "$PRED_BASE/$file") ;;
      hf)  predictions=(--predictions "data/preds-by-id/$file" --predictions-keyed-by question-id
                        --predictions-origin "$PRED_BASE/$file, re-keyed by question id with predictions_by_question_id.py") ;;
    esac
    predictions+=(--predictions-date "$PRED_DATE")
  fi
  start=$SECONDS
  for db in "${DATABASES[@]}"; do
    local out="out/tool/$gold/$model/$db"
    local ids
    # A summary.json is written at the end of a run, so one that is there is a run that
    # finished and is not made again. That is what lets this script be re-entered after an
    # interruption; reproduce.sh starts it over an empty out/, where nothing is skipped.
    if [ -f "$out/summary.json" ]; then echo "$gold $model $db already run"; continue; fi
    ids="$(python3 "$here/question_ids.py" "$q" "$db")"
    rm -rf "$out"; mkdir -p "$out"
    $ATTESTQL audit --engine sqlite --dsn "data/zip/minidev/MINIDEV/dev_databases/$db/$db.sqlite" \
      --questions "$q" --questions-origin "$qo" --questions-date "$qd" --ids "$ids" \
      --data-file "data/zip/minidev/MINIDEV/dev_databases/$db/$db.sqlite" \
      --data-origin "$DATA_ORIGIN, $db/$db.sqlite" --data-date "$DATA_DATE" \
      "${predictions[@]}" --out "$out" > "$out.stdout.txt" 2> "$out.stderr.txt"
    status=$?
    # The console output lands in the run's directory only after the run: the tool takes over an
    # empty directory or one it marked, and refuses one that holds a file it did not write.
    mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
    echo "$gold $model $db exit=$status: $(tail -1 "$out/stdout.txt")"
  done
  echo "$gold $model done in $((SECONDS - start))s"
}

lane() { local gold="$1"; shift; for model in "$@"; do one "$gold" "$model"; done; }

for gold_copy in zip hf; do
  lane "$gold_copy" gold-only "${MODELS[@]:0:3}" &
  lane "$gold_copy" "${MODELS[@]:3:3}" &
  lane "$gold_copy" "${MODELS[@]:6:3}" &
  wait
done
echo ALL_DONE
