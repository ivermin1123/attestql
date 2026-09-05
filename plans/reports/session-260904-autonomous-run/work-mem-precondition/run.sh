#!/usr/bin/env bash
# Audit the nine golds twice on the research server: once with the auditor role at the
# server's own work_mem, once with `ALTER ROLE auditor SET work_mem = '64kB'`. Each role
# state gets two invocations, because gold-only mode writes a question's directory only
# where a smell fired and two of the nine fire none here: the gold-only run is the one a
# maintainer makes, and the run with a deliberate non-answer beside each gold is what makes
# the tool write all nine gold records. The raw statements without the envelope are run
# beside both, as the control. Needs PGPASSWORD for the auditor login and Docker for the two
# role statements, which go in over the container's local socket as the superuser. WORK is
# where the runs write; nothing under it is committed but the comparison this ends with.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK:?set WORK to a scratch directory}"
ATTESTQL="${ATTESTQL:-attestql}"
IFS=' ' read -r -a PYTHON <<< "${PYTHON_COMMAND:-uv run python}"
CONTAINER=attestql-research-pg
DSN="host=127.0.0.1 port=5499 dbname=bird user=auditor"
ORIGIN="https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/f65faf4ae3b638c1fa6df1d3370c8d92c8366301/data/mini_dev_pg-00000-of-00001.json (commit f65faf4a), the nine summation-order-sensitive golds"

role() {  # role <SQL>
  docker exec --interactive "$CONTAINER" \
    psql --username=postgres --dbname=bird --no-psqlrc --quiet --set=ON_ERROR_STOP=1 \
    --command "$1" > /dev/null
}

audit() {  # audit <output directory> [extra flags]
  local out="$1" status=0
  shift
  $ATTESTQL audit --dsn "$DSN" --questions "$HERE/nine-golds.json" \
    --questions-origin "$ORIGIN" --questions-date 2026-01-18T08:44:25Z \
    --scratch-schema attestql_scratch --statement-timeout 120 --out "$out" "$@" \
    > "$out.stdout.txt" || status=$?
  tail -1 "$out.stdout.txt"
  # 1 is at least one NOT_EQUAL, which is what the run with a non-answer beside each gold
  # is for; 2 would be the tool failing and stops this.
  [ "$status" -le 1 ]
}

both() {  # both <role state>
  audit "$WORK/gold-only-$1"
  audit "$WORK/$1" --predictions "$HERE/force-a-record.json" \
    --predictions-keyed-by question-id \
    --predictions-origin "a deliberate non-answer per question, so that the tool writes every gold's record" \
    --predictions-date 2026-09-05
  "${PYTHON[@]}" "$HERE/control_raw_statements.py" "$WORK/raw-$1.json"
}

mkdir -p "$WORK"
trap 'role "ALTER ROLE auditor RESET work_mem"' EXIT

role "ALTER ROLE auditor RESET work_mem"
both default-work-mem

role "ALTER ROLE auditor SET work_mem = '64kB'"
both role-at-64kb

role "ALTER ROLE auditor RESET work_mem"
"${PYTHON[@]}" "$HERE/compare_two_runs.py" "$WORK"
