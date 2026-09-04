#!/usr/bin/env bash
# Run `attestql audit` over every BIRD prediction file against both golds, over the three
# corrected golds, and once more with the id-keyed copy of one file. Two runs at a time, each
# with its own scratch schema. Expects MEASURE_WORK filled by reproduce.sh and PGPASSWORD set.
set -uo pipefail
cd "$MEASURE_WORK"
DSN="host=127.0.0.1 port=5498 dbname=bird user=auditor"
ZIP_Q=data/zip/minidev/MINIDEV/mini_dev_postgresql.json
ZIP_ORIGIN="https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip (sha256 cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f, downloaded 2026-09-04), member minidev/MINIDEV/mini_dev_postgresql.json"
ZIP_DATE=2024-06-19
HF_Q=data/hf/mini_dev_pg-00000-of-00001.json
HF_ORIGIN="https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/f65faf4ae3b638c1fa6df1d3370c8d92c8366301/data/mini_dev_pg-00000-of-00001.json (commit f65faf4a, downloaded 2026-09-04)"
HF_DATE=2026-01-18T08:44:25Z
COR_Q=data/corrected-gold.json
COR_ORIGIN="corrected golds for 1029, 879 and 207 from tools/audit-sandbox/predictions.json of ivermin1123/attestql"
COR_DATE=2026-09-04
PRED_BASE="https://raw.githubusercontent.com/bird-bench/mini_dev/b3d4bcbbae9a96934ad812551eb400c7a3b23c12/llm/exp_result/sql_output_kg"
PRED_DATE=2024-06-19
ATTESTQL="${ATTESTQL:-attestql}"

one() {  # one <gold> <model> <scratch-schema>
  local gold="$1" model="$2" schema="$3"
  local file="predict_mini_dev_${model}_postgresql.json"
  local out="out/tool/$gold/$model"
  mkdir -p "$out"
  case "$gold" in
    zip) q="$ZIP_Q"; qo="$ZIP_ORIGIN"; qd="$ZIP_DATE"; p="data/preds/$file"; keyed=position; extra=()
         po="$PRED_BASE/$file" ;;
    zip-by-id) q="$ZIP_Q"; qo="$ZIP_ORIGIN"; qd="$ZIP_DATE"; p="data/preds-by-id/$file"; keyed=question-id; extra=()
         po="$PRED_BASE/$file, re-keyed by question id with predictions_by_question_id.py" ;;
    hf)  q="$HF_Q"; qo="$HF_ORIGIN"; qd="$HF_DATE"; p="data/preds-by-id/$file"; keyed=question-id; extra=()
         po="$PRED_BASE/$file, re-keyed by question id with predictions_by_question_id.py" ;;
    corrected) q="$COR_Q"; qo="$COR_ORIGIN"; qd="$COR_DATE"; p="data/preds-by-id/$file"; keyed=question-id; extra=(--ids 1029,879,207)
         po="$PRED_BASE/$file, re-keyed by question id with predictions_by_question_id.py" ;;
  esac
  local start=$SECONDS
  $ATTESTQL audit --dsn "$DSN" --questions "$q" --questions-origin "$qo" --questions-date "$qd" \
    --predictions "$p" --predictions-keyed-by "$keyed" --predictions-origin "$po" --predictions-date "$PRED_DATE" \
    --scratch-schema "$schema" "${extra[@]}" --out "$out" > "$out.stdout.txt" 2> "$out.stderr.txt"
  local status=$?
  # The console output lands in the run's directory only after the run: the tool takes over
  # an empty directory or one it marked, and refuses one that holds a file it did not write.
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "$gold $model exit=$status in $((SECONDS - start))s: $(tail -1 "$out/stdout.txt")"
}

MODELS=(gpt-35-turbo-instruct gpt-35-turbo gpt-4-32k gpt-4-turbo gpt-4 meta-llama-3-70b-instruct-2 meta-llama-3-8b-instruct-2 mistralai-mixtral-8x7b-instru-4 phi-3-medium-128k-instruct-1)
( for m in "${MODELS[@]}"; do one zip "$m" attestql_scratch; done; one zip-by-id gpt-35-turbo-instruct attestql_scratch ) &
( for m in "${MODELS[@]}"; do one hf "$m" attestql_scratch2; done; for m in "${MODELS[@]}"; do one corrected "$m" attestql_scratch2; done ) &
wait
echo ALL_DONE
