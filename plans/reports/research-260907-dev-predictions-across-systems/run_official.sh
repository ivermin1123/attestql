#!/usr/bin/env bash
# Run BIRD's evaluator once per file and gold copy, three evaluator processes at a time.
set -uo pipefail
here="$(cd "$(dirname "$BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"
PY="${PY:-birdenv/bin/python}"

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
  csc-sql-7b.sql csc-sql-32b.sql atlas-core-20260301.sql atlas-core-20260324.sql
)

one() {
  local copy="$1" file="$2" out="out/official/$copy/$file.json"
  if [ -f "$out" ]; then echo "$copy $file already scored"; return 0; fi
  mkdir -p "$(dirname "$out")"
  "$PY" "$here/bird_ex_official.py" "$copy" "data/preds-run/$file.json" "$out"
}

running=0
for copy in old dev1106; do
  for file in "${FILES[@]}"; do
    one "$copy" "$file" &
    running=$((running + 1))
    [ "$running" -ge 3 ] && { wait -n; running=$((running - 1)); }
  done
done
wait
echo OFFICIAL_DONE
