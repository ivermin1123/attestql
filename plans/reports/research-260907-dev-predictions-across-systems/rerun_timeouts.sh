#!/usr/bin/env bash
# Rerun alone every prediction run whose stdout says timeout, keeping the loaded answer.
set -uo pipefail
here="$(cd "$(dirname "$BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"
ATTESTQL="${ATTESTQL:-attestql}"

OLD_Q=data/dev/dev_20240627/dev.json
OLD_ORIGIN="https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip (sha256 cdd6f19faeb45a23970b98d3ef4c40a87987c95459c2cf12076897a60cf5a630, Last-Modified 2024-06-29), member dev_20240627/dev.json"
OLD_DATE=2024-06-27
NEW_Q=data/hf/dev_20251106-00000-of-00001.json
NEW_ORIGIN="https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/3c11fb193e5439b338e23677fa0aae11e8b85db9/data/dev_20251106-00000-of-00001.json (commit 3c11fb19)"
NEW_DATE=2026-01-18T08:51:02Z
DATA_ORIGIN="dev.zip (sha256 cdd6f19faeb45a23970b98d3ef4c40a87987c95459c2cf12076897a60cf5a630), member dev_20240627/dev_databases.zip, dev_databases"

for summary in out/tool-predictions/*/*/*/summary.json; do
  [ -f "$summary" ] || continue
  out="$(dirname "$summary")"
  case "$out" in *.under-load|*.timeout-rerun) continue;; esac
  [ -d "$out.under-load" ] && continue
  python3 - "$summary" <<'PY' || continue
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(not any(summary.get("timed_out", {}).values()))
PY
  db="$(basename "$out")"; file="$(basename "$(dirname "$out")")"
  copy="$(basename "$(dirname "$(dirname "$out")")")"
  echo "timeout under load: $copy $file $db"
  timeout_ids="$(python3 - "$summary" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
ids = sorted({qid for ids in summary["timed_out"].values() for qid in ids})
print(",".join(str(qid) for qid in ids))
PY
)"
  case "$copy" in
    old) q="$OLD_Q"; qo="$OLD_ORIGIN"; qd="$OLD_DATE" ;;
    dev1106) q="$NEW_Q"; qo="$NEW_ORIGIN"; qd="$NEW_DATE" ;;
  esac
  case "$file" in alpha-sql-dev.json|dail-sql-*) keying=question-id;; *) keying=position;; esac
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
  if [ "$db" = card_games ]; then db_path=data/dev/copies/card_games/card_games.sqlite
  else db_path="data/dev/dev_databases/$db/$db.sqlite"; fi
  rm -rf "$out.under-load"; mv "$out" "$out.under-load"; mkdir -p "$out"
  rm -rf "$out.timeout-rerun"
  $ATTESTQL audit --engine sqlite --dsn "$db_path" --questions "$q" \
    --questions-origin "$qo" --questions-date "$qd" --ids "$timeout_ids" \
    --data-file "$db_path" --data-origin "$DATA_ORIGIN, $db/$db.sqlite" \
    --data-date 2024-06-14 --predictions "data/preds-run/$file.json" \
    --predictions-keyed-by "$keying" --predictions-origin "$origin" \
    --predictions-date "$pdate" --out "$out.timeout-rerun" \
    > "$out.timeout-rerun.stdout.txt" 2> "$out.timeout-rerun.stderr.txt"
  status=$?
  mv "$out.timeout-rerun.stdout.txt" "$out.timeout-rerun/stdout.txt"
  mv "$out.timeout-rerun.stderr.txt" "$out.timeout-rerun/stderr.txt"
  python3 "$here/merge_timeout_rerun.py" "$out.under-load/summary.json" \
    "$out.timeout-rerun/summary.json" "$out"
  echo "rerun alone: exit=$status ids=$timeout_ids $(tail -1 "$out/stdout.txt")"
done
