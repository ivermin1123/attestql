#!/usr/bin/env bash
# Run CodeS-1B prediction mode over the current and transformed Spider passes.
#
# The converted prediction map is keyed by Spider's zero-based question id, so no positional
# keying is needed and the same map serves the transformed subset. Three processes at a time.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"
ATTESTQL="${ATTESTQL:-attestql}"
ZIP_ORIGIN="https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view (spider_data.zip sha256 00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b, CC BY-SA 4.0)"
PRED_ORIGIN="https://github.com/RUCKBReasoning/codes/blob/e203386173eecf6fbe8b14cf233611a2fb7c994e/results/pred_sqls-codes-1b-spider.txt (Apache-2.0, sha256 913576f655c6ca9a00762c83acf05234006fae164826e9577cbd1373d07274d2)"
PRED_DATE=2024-08-21
DATA_DATE=2018-09-24
DATABASES=(world_1 car_1 cre_Doc_Template_Mgt dog_kennels flight_2 student_transcripts_tracking wta_1 tvshow network_1 concert_singer pets_1 poker_player orchestra employee_hire_evaluation course_teach singer museum_visit battle_death voter_1 real_estate_properties)

one() {  # one <pass> <db_id>
  local pass="$1" db="$2" q qo qd out ids status start
  case "$pass" in
    current)
      q=data/questions-current.json
      qo="$ZIP_ORIGIN, member spider_data/dev.json"
      qd=2020-08-03
      ;;
    transformed)
      q=data/questions-transformed.json
      qo="$ZIP_ORIGIN, member spider_data/dev.json, every double-quoted token resolving to no table or column changed to a single-quoted literal"
      qd=2020-08-03
      ;;
  esac
  ids="$(python3 "$here/question_ids.py" "$q" "$db")"
  [ -n "$ids" ] || { echo "$pass $db has no questions"; return 0; }
  out="out/tool-predictions/$pass/$db"
  if [ -f "$out/summary.json" ]; then echo "$pass $db already run"; return 0; fi
  rm -rf "$out"; mkdir -p "$out"
  start=$SECONDS
  $ATTESTQL audit --engine sqlite --dsn "data/spider/spider_data/database/$db/$db.sqlite" \
    --questions "$q" --questions-origin "$qo" --questions-date "$qd" --ids "$ids" \
    --data-file "data/spider/spider_data/database/$db/$db.sqlite" \
    --data-origin "$ZIP_ORIGIN, member spider_data/database/$db/$db.sqlite" \
    --data-date "$DATA_DATE" --predictions data/predictions-codes.json \
    --predictions-origin "$PRED_ORIGIN" --predictions-date "$PRED_DATE" \
    --statement-timeout 30 --out "$out" > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "$pass $db exit=$status in $((SECONDS - start))s: $(tail -1 "$out/stdout.txt")"
}

running=0
for pass in current transformed; do
  for db in "${DATABASES[@]}"; do
    one "$pass" "$db" &
    running=$((running + 1))
    [ "$running" -ge 3 ] && { wait -n; running=$((running - 1)); }
  done
done
wait
echo ALL_DONE
