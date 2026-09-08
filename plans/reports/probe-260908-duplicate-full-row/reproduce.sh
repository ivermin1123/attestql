#!/usr/bin/env bash
# Regenerate this measurement from the public inputs.
#
#   MEASURE_WORK=<work directory outside the repository> \
#   ATTESTQL_INPUTS=<the read-only input cache> bash reproduce.sh
#
# The inputs are BIRD's minidev.zip and dev.zip, the Hugging Face Mini-Dev SQLite file,
# Spider 1.0's spider_data.zip, and one published prediction file; their digests are in
# proofs.json. Nothing here writes to a database and no input is committed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
: "${MEASURE_WORK:?set MEASURE_WORK outside the repository}"
: "${ATTESTQL_INPUTS:?set ATTESTQL_INPUTS to the read-only input cache}"
case "$MEASURE_WORK" in "$repo"|"$repo"/*) echo "work directory must be outside repo" >&2; exit 2;; esac
mkdir -p "$MEASURE_WORK"
cd "$repo"

minidev="$ATTESTQL_INPUTS/minidev/minidev/MINIDEV"
databases="$minidev/dev_databases"

# 1. Gold-only over both published copies of the Mini-Dev SQLite golds, one run per database.
for copy in zip hf; do
  case "$copy" in
    zip) questions="$minidev/mini_dev_sqlite.json" ;;
    hf)  questions="$ATTESTQL_INPUTS/mini_dev_sqlite_hf.json" ;;
  esac
  for db in "$databases"/*/; do
    name="$(basename "$db")"
    ids="$(python3 "$here/question_ids.py" "$questions" "$name")"
    [ -n "$ids" ] || continue
    uv run attestql audit --engine sqlite --dsn "$db$name.sqlite" \
      --questions "$questions" --ids "$ids" --out "$MEASURE_WORK/tool/$copy/$name" \
      >"$MEASURE_WORK/tool/$copy/$name.stdout.txt" 2>&1 || true
  done
done

# 2. The two Spider golds whose text does not decode, on wta_1.
unzip -o -q -j "$ATTESTQL_INPUTS/spider_data.zip" 'spider_data/dev.json' \
  'spider_data/database/wta_1/wta_1.sqlite' -d "$MEASURE_WORK/spider"
python3 "$here/spider_questions.py" "$MEASURE_WORK/spider"
uv run attestql audit --engine sqlite --dsn "$MEASURE_WORK/spider/wta_1.sqlite" \
  --questions "$MEASURE_WORK/spider/questions-wta_1.json" --ids 455,456 \
  --out "$MEASURE_WORK/spider/audit"

# 3. One published prediction file, one statement per line, read as it ships.
predictions="${PREDICTIONS:-$MEASURE_WORK/preds/rsl-sql-gpt-4o.txt}"
if [ -f "$predictions" ]; then
  dev="$ATTESTQL_INPUTS/dev/dev_20240627"
  ids="$(python3 "$here/question_ids.py" "$dev/dev.json" toxicology)"
  uv run attestql audit --engine sqlite \
    --dsn "$dev/dev_databases/toxicology/toxicology.sqlite" --questions "$dev/dev.json" \
    --predictions "$predictions" --predictions-format lines \
    --predictions-origin "RSL-SQL, GPT-4o, as shipped" --ids "$ids" \
    --out "$MEASURE_WORK/lines/toxicology"
else
  echo "no prediction file at $predictions; set PREDICTIONS to one of the 21 files of A44" >&2
fi

echo "done: $MEASURE_WORK"
