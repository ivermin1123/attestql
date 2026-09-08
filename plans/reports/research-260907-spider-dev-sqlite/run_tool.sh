#!/usr/bin/env bash
# Run gold-only audits over the three Spider passes, one SQLite run per database.
#
# The cap is three processes because SQLite's statement budget is wall clock in this process.
# A summary.json is written only when a run ends, so an existing one is reused after interruption.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"
ATTESTQL="${ATTESTQL:-attestql}"
ZIP_ORIGIN="https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view (spider_data.zip sha256 00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b, CC BY-SA 4.0)"
DATA_DATE=2018-09-24
CURRENT_Q=data/questions-current.json
BEFORE_Q=data/questions-before.json
TRANSFORMED_Q=data/questions-transformed.json
# Longest databases first, under the three-process cap.
DATABASES=(world_1 car_1 cre_Doc_Template_Mgt dog_kennels flight_2 student_transcripts_tracking wta_1 tvshow network_1 concert_singer pets_1 poker_player orchestra employee_hire_evaluation course_teach singer museum_visit battle_death voter_1 real_estate_properties)

one() {  # one <pass> <db_id>
  local pass="$1" db="$2" q qo qd out ids status start
  case "$pass" in
    current)
      q="$CURRENT_Q"
      qo="$ZIP_ORIGIN, member spider_data/dev.json"
      qd=2020-08-03
      ;;
    before)
      q="$BEFORE_Q"
      qo="$ZIP_ORIGIN member spider_data/dev.json with the 28 SQL lines of https://github.com/taoyds/spider/blob/e0b7bc91/evaluation_examples/dev.sql substituted"
      qd=2020-06-07
      ;;
    transformed)
      q="$TRANSFORMED_Q"
      qo="$ZIP_ORIGIN, member spider_data/dev.json, every double-quoted token resolving to no table or column changed to a single-quoted literal"
      qd=2020-08-03
      ;;
  esac
  ids="$(python3 "$here/question_ids.py" "$q" "$db")"
  [ -n "$ids" ] || { echo "$pass $db has no questions"; return 0; }
  out="out/tool/$pass/$db"
  if [ -f "$out/summary.json" ]; then echo "$pass $db already run"; return 0; fi
  rm -rf "$out"; mkdir -p "$out"
  start=$SECONDS
  $ATTESTQL audit --engine sqlite --dsn "data/spider/spider_data/database/$db/$db.sqlite" \
    --questions "$q" --questions-origin "$qo" --questions-date "$qd" --ids "$ids" \
    --data-file "data/spider/spider_data/database/$db/$db.sqlite" \
    --data-origin "$ZIP_ORIGIN, member spider_data/database/$db/$db.sqlite" \
    --data-date "$DATA_DATE" --statement-timeout 30 --out "$out" \
    > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "$pass $db exit=$status in $((SECONDS - start))s: $(tail -1 "$out/stdout.txt")"
}

running=0
for pass in current before transformed; do
  for db in "${DATABASES[@]}"; do
    one "$pass" "$db" &
    running=$((running + 1))
    [ "$running" -ge 3 ] && { wait -n; running=$((running - 1)); }
  done
done
wait
echo ALL_DONE
