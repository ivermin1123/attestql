#!/usr/bin/env bash
#
# A summary's final "0 timed out" line also contains the word timeout, so the decision is the
# summary's own timed_out lists rather than grep over stdout.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MEASURE_WORK"
QUESTION=data/dev/dev_20240627/dev.json
QUESTION_ORIGIN="https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip (sha256 cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630, Last-Modified 2024-06-29, downloaded 2026-09-07), member dev_20240627/dev.json"
ATTESTQL="${ATTESTQL:-attestql}"
found=0

held_timeout() {  # one <summary.json>
  python3 - "$1" <<'PY'
import json, sys
timed_out = json.load(open(sys.argv[1]))["timed_out"]
raise SystemExit(0 if any(timed_out.values()) else 1)
PY
}

data_origin() {  # one <copy>
  case "$1" in
    dev) echo "dev.zip (sha256 cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630), member dev_20240627/dev_databases.zip, dev_databases" ;;
    minidev) echo "minidev.zip (sha256 cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f), member minidev/MINIDEV/dev_databases" ;;
  esac
}

for stdout in out/tool/*/*/stdout.txt; do
  [ -f "$stdout" ] || continue
  out="$(dirname "$stdout")"
  case "$out" in *.under-load) continue;; esac
  [ -d "$out.under-load" ] && continue
  held_timeout "$out/summary.json" || continue
  copy="$(basename "$(dirname "$out")")"; db="$(basename "$out")"
  case "$copy" in
    dev) root=data/dev/dev_databases ;;
    minidev) root=data/zip/minidev/MINIDEV/dev_databases ;;
    *) continue ;;
  esac
  found=$((found + 1))
  echo "timeout under load: $copy $db"
  ids="$(python3 "$here/question_ids.py" "$QUESTION" "$db")"
  rm -rf "$out.under-load"; mv "$out" "$out.under-load"; mkdir -p "$out"
  $ATTESTQL audit --engine sqlite --dsn "$root/$db/$db.sqlite" \
    --questions "$QUESTION" --questions-origin "$QUESTION_ORIGIN" --questions-date 2024-06-27 \
    --ids "$ids" --data-file "$root/$db/$db.sqlite" \
    --data-origin "$(data_origin "$copy"), $db/$db.sqlite" --data-date 2024-06-14 \
    --out "$out" > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "  rerun alone exit=$status: $(tail -1 "$out/stdout.txt")"
  if held_timeout "$out/summary.json"; then
    echo "  TIMEOUT SURVIVED THE SERIAL RERUN"
  fi
done
echo "runs holding a timeout: $found"
