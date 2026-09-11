#!/usr/bin/env bash
# The five audits the site publishes, made again with the per-question directories the site
# needs. Nothing about the tool changes for them: these are the same invocations the four
# measurement reports in plans/reports/ document, with the same inputs, the same digests and
# the same caps, writing into a work directory outside the repository.
#
#   tools/site-select/audits.sh inputs     download and verify, copy the databases
#   tools/site-select/audits.sh sqlite     bird-dev-sqlite and minidev-sqlite
#   tools/site-select/audits.sh postgres   the container, the dump, and the eleven PG runs
#   tools/site-select/audits.sh teardown   remove the container
#
# RUNS_WORK is where everything goes; it must be outside the repository and its name reaches
# a published page, because the SQLite backend records the absolute path of the file it
# opened. /tmp/attestql-runs names no user, no repository and no build location, which is the
# same reason tools/site/build.py fixes its own sandbox path.
#
# Every audit is run from inside the work directory with relative paths, so that summary.json
# records `data/...` for the question file, the prediction file and the data file rather than
# this machine's own layout.
#
# Re-entrant on summary.json, as the measurement scripts are: a directory holding one is a run
# that finished and is not made again, so an interrupted pass is resumed by running it again.
#
# Three SQLite processes at a time and two PostgreSQL lanes, each lane with its own scratch
# schema. The cap is not a tuning knob: a statement's budget is wall clock, so a starved
# process reports a timeout its statement did not earn. rerun_timeouts below is the check that
# the cap held, and it is the rerun's directory that is published.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
RUNS_WORK="${RUNS_WORK:-/tmp/attestql-runs}"
mkdir -p "$RUNS_WORK"
RUNS_WORK="$(cd "$RUNS_WORK" && pwd)"
case "$RUNS_WORK" in "$repo"|"$repo"/*) echo "the work directory must be outside the repository" >&2; exit 2;; esac

CACHE="${ATTESTQL_INPUTS:-$HOME/.cache/attestql-measure/inputs}"
CONTAINER=attestql-minidev
IMAGE="postgres@sha256:c1b3783309b6499c795eed7c20135a1a4d25cae1b575c3d52c6f536129a1b109"
PORT=5498
# How long the server may take to answer, and how many tables of schema `public` a whole
# Mini-Dev dump leaves behind: 75, which is how many `fixture.row_counts` names in
# plans/reports/audit-260902-minidev-gold-only/summary.json. A partial load must not run audits.
HEALTH_DEADLINE=90
DUMP_TABLES=75
PRED_COMMIT=b3d4bcbbae9a96934ad812551eb400c7a3b23c12
PRED_BASE="https://raw.githubusercontent.com/bird-bench/mini_dev/$PRED_COMMIT/llm/exp_result/sql_output_kg"
TODAY="$(date +%F)"

DATABASES=(california_schools card_games codebase_community debit_card_specializing european_football_2 financial formula_1 student_club superhero thrombosis_prediction toxicology)
# Longest first, as the BIRD dev measurement orders them: the two that dominate start first.
DEV_ORDER=(european_football_2 formula_1 card_games codebase_community thrombosis_prediction toxicology student_club superhero financial california_schools debit_card_specializing)
MODELS=(gpt-35-turbo-instruct gpt-35-turbo gpt-4-32k gpt-4-turbo gpt-4 meta-llama-3-70b-instruct-2 meta-llama-3-8b-instruct-2 mistralai-mixtral-8x7b-instru-4 phi-3-medium-128k-instruct-1)

# Where every origin string comes from: the four measurement scripts, verbatim, with the
# download date of a file fetched today set to today's.
ZIP_DIGEST=cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f
DEV_DIGEST=cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630
MINIDEV_SQLITE_ORIGIN="https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip (sha256 $ZIP_DIGEST, downloaded 2026-09-07), member minidev/MINIDEV/mini_dev_sqlite.json"
MINIDEV_SQLITE_DATE=2024-06-19
MINIDEV_PG_ORIGIN="https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip (sha256 $ZIP_DIGEST, downloaded 2026-09-07), member minidev/MINIDEV/mini_dev_postgresql.json"
MINIDEV_PG_DATE=2024-06-19
HF_PG_ORIGIN="https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/f65faf4ae3b638c1fa6df1d3370c8d92c8366301/data/mini_dev_pg-00000-of-00001.json (commit f65faf4a, downloaded $TODAY)"
HF_PG_DATE=2026-01-18T08:44:25Z
DEV1106_ORIGIN="https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/3c11fb193e5439b338e23677fa0aae11e8b85db9/data/dev_20251106-00000-of-00001.json (commit 3c11fb19, downloaded 2026-09-07)"
DEV1106_DATE=2026-01-18T08:51:02Z
MINIDEV_DATA_ORIGIN="minidev.zip (sha256 $ZIP_DIGEST), member minidev/MINIDEV/dev_databases"
MINIDEV_DATA_DATE=2024-06-13
DEV_DATA_ORIGIN="dev.zip (sha256 $DEV_DIGEST), member dev_20240627/dev_databases.zip, dev_databases"
DEV_DATA_DATE=2024-06-14
DUMP_ORIGIN="minidev.zip (sha256 $ZIP_DIGEST), member minidev/MINIDEV_postgresql/BIRD_dev.sql"
DUMP_DATE=2024-06-13
PRED_DATE=2024-06-19

verify() { echo "$2  $1" | shasum -a 256 --check --status || { echo "digest mismatch: $1" >&2; exit 1; }; }

# One file fetched, with the retries the OSS and GitHub endpoints have needed before: a
# stalled transfer is given up on and the next attempt resumes from the bytes on disk.
fetch() {  # fetch <url> <path> <digest>
  local url="$1" path="$2" digest="$3" attempt
  if [ -f "$path" ] && echo "$digest  $path" | shasum -a 256 --check --status; then return 0; fi
  mkdir -p "$(dirname "$path")"
  for attempt in 1 2 3 4 5 6; do
    curl -sSL -C - --speed-time 20 --speed-limit 10240 --max-time 900 "$url" -o "$path" && \
      echo "$digest  $path" | shasum -a 256 --check --status && return 0
    echo "  attempt $attempt failed for $(basename "$path"), retrying" >&2
    sleep 3
  done
  echo "could not fetch $url to the stated digest" >&2
  exit 1
}

inputs() {
  cd "$RUNS_WORK"
  mkdir -p data/preds-sqlite data/preds-pg data/questions out
  echo "== verifying the cached inputs against $CACHE/SHA256SUMS"
  ( cd "$CACHE" && shasum -a 256 --check --status SHA256SUMS ) || {
    echo "the cached inputs do not match their own SHA256SUMS" >&2; exit 1; }

  # The question files, copied so that a run states a relative path of its own rather than
  # this machine's home directory.
  cp -f "$CACHE/minidev/minidev/MINIDEV/mini_dev_sqlite.json" data/questions/mini_dev_sqlite.json
  cp -f "$CACHE/minidev/minidev/MINIDEV/mini_dev_postgresql.json" data/questions/mini_dev_postgresql.json
  cp -f "$CACHE/dev_20251106.json" data/questions/dev_20251106-00000-of-00001.json
  verify data/questions/mini_dev_sqlite.json 4ba5fa8de55856222f484d380d2ba872b380bf79d825de70478e2120cb0fc43b
  verify data/questions/mini_dev_postgresql.json d2731292f20b8d8569cd956dd747ffe1df13cd625076263e38ae9ebcef50b1ab
  verify data/questions/dev_20251106-00000-of-00001.json ffd8018378ddb1a8794753e0a31cfc81862ff7318a5184c22f3dc4ce03a03feb
  fetch "https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/f65faf4ae3b638c1fa6df1d3370c8d92c8366301/data/mini_dev_pg-00000-of-00001.json" \
    data/questions/mini_dev_pg-00000-of-00001.json 7fa740ef9225389cff6c34432120e8325d0ca3008d73db1ae38731234bc10da7

  echo "== the eighteen prediction files"
  while read -r model digest; do
    [ -n "$model" ] || continue
    fetch "$PRED_BASE/predict_mini_dev_${model}_sqlite.json" \
      "data/preds-sqlite/predict_mini_dev_${model}_sqlite.json" "$digest"
  done < "$repo/plans/reports/minidev-sqlite-260907/SHA256SUMS.predictions"
  while read -r model digest; do
    [ -n "$model" ] || continue
    fetch "$PRED_BASE/predict_mini_dev_${model}_postgresql.json" \
      "data/preds-pg/predict_mini_dev_${model}_postgresql.json" "$digest"
  done <<'DIGESTS'
gpt-35-turbo-instruct df1edf6aac3c01cf93041bcd7b60378efe6f7359f19add6d2af2345bef092bf9
gpt-35-turbo fa363fe3c3fc45d97cb47e6ec15133b291acccd750e5136b6e7b4d1c8d13a4be
gpt-4-32k 0fba1bfbeb487d641c8ae1e8bb01f762b2d29ddfb7c14dbd94e832f53cc10270
gpt-4-turbo 428fd115a67a76d6312ea205aab64764b5a09444587588eda442a94cfee65211
gpt-4 cd39466740516d2d4672e8421010edab4816ff9875781f44df100840b41eaa49
meta-llama-3-70b-instruct-2 32d005d4529798c3be39a5af000454728404e840ce2205506bb9514232ad6330
meta-llama-3-8b-instruct-2 aa8d2ecc9d70a14d315648a939eb0e9104a2b1e4bd09047391ed9539865f8876
mistralai-mixtral-8x7b-instru-4 862dffc4cdca4875650841a456b698e515e978125f5b28f798022e88176562cb
phi-3-medium-128k-instruct-1 8defb4399ab3393200cfba510024df7d9cf2cff8c9c7df647e3309cf751ac82d
DIGESTS

  echo "== the two sets of eleven databases, copied and not linked"
  # Copied because a link resolves, and a resolved link names the home directory this work
  # directory exists to keep off a published page.
  for db in "${DATABASES[@]}"; do
    for pair in "minidev:$CACHE/minidev/minidev/MINIDEV/dev_databases" "dev:$CACHE/dev/dev_20240627/dev_databases"; do
      local_name="${pair%%:*}"; source="${pair#*:}"
      target="data/$local_name/dev_databases/$db/$db.sqlite"
      [ -f "$target" ] && continue
      mkdir -p "$(dirname "$target")"
      cp "$source/$db/$db.sqlite" "$target"
    done
  done
  target=data/minidev/BIRD_dev.sql
  [ -f "$target" ] || cp "$CACHE/minidev/minidev/MINIDEV_postgresql/BIRD_dev.sql" "$target"

  echo "== the tool, installed once into the work directory"
  # Installed once rather than through `uv run` per invocation: an earlier measurement found
  # resolving the environment per run too slow to finish in a day. Python 3.13 on purpose, so
  # that the measured SQLite is the library `just check` runs against.
  [ -d venv ] || { uv venv venv --python 3.13 -q && uv pip install --python venv/bin/python -q "$repo"; }
  uv pip install --python venv/bin/python -q "$repo"
  echo "inputs ready in $RUNS_WORK"
}

# Run the jobs of one batch and collect every status. `wait -n` would need bash 4.3 while the
# note above says bash 3.2, and a bare `wait` throws every status away, which is how a run of
# eleven databases could fail eleven times and still report itself done.
FAILED=0
BATCH=()

batch_add() {  # batch_add <pid>
  BATCH+=("$1")
  [ "${#BATCH[@]}" -ge 3 ] && batch_drain
  return 0
}

batch_drain() {
  local pid
  for pid in ${BATCH[@]+"${BATCH[@]}"}; do
    wait "$pid" || FAILED=$((FAILED + 1))
  done
  BATCH=()
}

# One SQLite audit of one database. Skipped when its summary.json is already there.
sqlite_one() {  # sqlite_one <out> <questions> <origin> <date> <databases-dir> <data-origin> <data-date> <db> [predictions args...]
  local out="$1" questions="$2" origin="$3" qdate="$4" dbdir="$5" dorigin="$6" ddate="$7" db="$8"; shift 8
  local ids status start
  if [ -f "$out/summary.json" ]; then echo "already run: $out"; return 0; fi
  ids="$(python3 "$here/question_ids.py" "$questions" "$db")"
  [ -n "$ids" ] || { echo "no question names $db in $questions" >&2; return 1; }
  rm -rf "$out"; mkdir -p "$out"
  start=$SECONDS
  "$ATTESTQL" audit --engine sqlite --dsn "$dbdir/$db/$db.sqlite" \
    --questions "$questions" --questions-origin "$origin" --questions-date "$qdate" --ids "$ids" \
    --data-file "$dbdir/$db/$db.sqlite" --data-origin "$dorigin, $db/$db.sqlite" --data-date "$ddate" \
    "$@" --out "$out" > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  # The console output lands in the run's directory only after the run: the tool takes over an
  # empty directory or one it marked, and refuses one holding a file it did not write.
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "$out exit=$status in $((SECONDS - start))s: $(tail -1 "$out/stdout.txt")"
  # 0 is no disagreement and 1 is at least one, both of them runs that happened; 2 and above is
  # a tool error, and so is a run that wrote no summary. Returning it is what lets the caller
  # refuse to print its DONE marker over a failure.
  [ "$status" -le 1 ] && [ -f "$out/summary.json" ] && return 0
  return 1
}

# The arguments one SQLite run of one prediction file takes, as a global array: bash 3.2 on
# macOS returns no array from a function.
sqlite_prediction_args() {  # sqlite_prediction_args <model>
  local file="predict_mini_dev_${1}_sqlite.json"
  PREDICTION_ARGS=(--predictions "data/preds-sqlite/$file" --predictions-keyed-by position
                   --predictions-origin "$PRED_BASE/$file" --predictions-date "$PRED_DATE")
}

sqlite_runs() {
  cd "$RUNS_WORK"
  export ATTESTQL="${ATTESTQL:-$RUNS_WORK/venv/bin/attestql}"
  local db model

  echo "== bird-dev-sqlite: the 2025-11-06 copy, gold-only, eleven databases"
  for db in "${DEV_ORDER[@]}"; do
    sqlite_one "runs/bird-dev-sqlite/dev-20251106/$db" data/questions/dev_20251106-00000-of-00001.json \
      "$DEV1106_ORIGIN" "$DEV1106_DATE" data/dev/dev_databases "$DEV_DATA_ORIGIN" "$DEV_DATA_DATE" "$db" &
    batch_add $!
  done
  batch_drain

  echo "== minidev-sqlite: the nine prediction files against the zip's questions, keyed by position"
  for model in "${MODELS[@]}"; do
    sqlite_prediction_args "$model"
    for db in "${DATABASES[@]}"; do
      sqlite_one "runs/minidev-sqlite/$model/$db" data/questions/mini_dev_sqlite.json \
        "$MINIDEV_SQLITE_ORIGIN" "$MINIDEV_SQLITE_DATE" data/minidev/dev_databases \
        "$MINIDEV_DATA_ORIGIN" "$MINIDEV_DATA_DATE" "$db" "${PREDICTION_ARGS[@]}" &
      batch_add $!
    done
  done
  batch_drain
  [ "$FAILED" -eq 0 ] || { echo "$FAILED SQLite run(s) failed" >&2; return 1; }
  echo "SQLITE_DONE"
}

# Every run whose summary names a question the statement bound stopped, made again alone into a
# fresh directory, the crowded answer kept beside it as `<name>.under-load`. What is published
# is the rerun; the report states how many were made again.
#
# Read off `timed_out` in the summary and not off a grep of stdout, which is what the two
# measurement scripts did: the run's closing line now states "0 timed out (0 gold, 0
# prediction)" whether anything did or not, so a grep for the words matches every run and would
# rerun all hundred and ten of them alone. The summary names the questions.
rerun_timeouts() {  # rerun_timeouts [path prefix]
  cd "$RUNS_WORK"
  export ATTESTQL="${ATTESTQL:-$RUNS_WORK/venv/bin/attestql}"
  local only="${1:-runs/}" summary out found=0 name group benchmark stopped
  # The prefix is what keeps the two stages out of each other: each reruns its own engine's
  # runs, so the SQLite pass and the PostgreSQL pass can overlap without one moving a
  # directory the other is writing into.
  for summary in runs/*/*/*/summary.json runs/*/*/summary.json; do
    [ -f "$summary" ] || continue
    out="$(dirname "$summary")"
    case "$out" in *.under-load) continue;; esac
    case "$out" in "$only"*) ;; *) continue;; esac
    stopped="$(python3 -c "
import json, sys
stated = json.load(open(sys.argv[1])).get('timed_out') or {}
print(', '.join(f'{side}: {\",\".join(str(q) for q in ids)}' for side, ids in stated.items() if ids))
" "$summary")"
    [ -n "$stopped" ] || continue
    found=$((found + 1))
    echo "timed out under load: $out ($stopped)"
    name="$(basename "$out")"; group="$(basename "$(dirname "$out")")"
    benchmark="$(basename "$(dirname "$(dirname "$out")")")"
    case "$benchmark" in
      runs) benchmark="$group"; group="";;
    esac
    rm -rf "$out.under-load"; mv "$out" "$out.under-load"
    case "$benchmark/$group" in
      bird-dev-sqlite/*)
        sqlite_one "$out" data/questions/dev_20251106-00000-of-00001.json "$DEV1106_ORIGIN" \
          "$DEV1106_DATE" data/dev/dev_databases "$DEV_DATA_ORIGIN" "$DEV_DATA_DATE" "$name" ;;
      minidev-sqlite/*)
        sqlite_prediction_args "$group"
        sqlite_one "$out" data/questions/mini_dev_sqlite.json "$MINIDEV_SQLITE_ORIGIN" \
          "$MINIDEV_SQLITE_DATE" data/minidev/dev_databases "$MINIDEV_DATA_ORIGIN" \
          "$MINIDEV_DATA_DATE" "$name" "${PREDICTION_ARGS[@]}" ;;
      minidev-pg-gold-only/*) pg_gold_only "$name" attestql_scratch ;;
      minidev-pg/*) pg_prediction "$name" attestql_scratch ;;
      *) echo "  no rule for $out" >&2; mv "$out.under-load" "$out"; continue ;;
    esac
    stopped="$(python3 -c "
import json, sys
stated = json.load(open(sys.argv[1])).get('timed_out') or {}
print(', '.join(f'{side}: {\",\".join(str(q) for q in ids)}' for side, ids in stated.items() if ids))
" "$out/summary.json" 2>/dev/null || echo unreadable)"
    if [ -n "$stopped" ]; then
      echo "  the bound stopped the same questions alone: $stopped"
    else
      echo "  nothing reached the bound when it ran alone"
    fi
  done
  echo "runs the bound stopped something in: $found"
}

# The server the two PostgreSQL benchmarks are audited on: the image digest the merge gate's
# own sandbox pins, a password from openssl that never reaches a command line or a file, the
# read-only auditor role and the two scratch schemas the two lanes write their shuffles in.
postgres_up() {
  cd "$RUNS_WORK"
  local password auditor_password deadline loaded
  docker rm --force --volumes "$CONTAINER" >/dev/null 2>&1 || true
  # Registered before the container exists rather than after this function returns: from
  # `docker run` onward there is something to remove, and a Ctrl-C during the start, the load
  # or the role setup used to leave `attestql-minidev` holding port 5498.
  trap postgres_down EXIT
  password="$(openssl rand -hex 24)"; POSTGRES_PASSWORD="$password"; export POSTGRES_PASSWORD
  docker run --detach --name "$CONTAINER" --publish "127.0.0.1:$PORT:5432" \
    --env POSTGRES_PASSWORD --env POSTGRES_DB=bird \
    --health-cmd "pg_isready --host=127.0.0.1 --username=postgres --dbname=bird --quiet" \
    --health-interval=1s --health-timeout=5s --health-retries=$HEALTH_DEADLINE "$IMAGE" >/dev/null || return 1
  # With a deadline, as tools/audit-sandbox/run.sh has one: a server that never answers used to
  # be a loop with nothing to say.
  deadline=$((SECONDS + HEALTH_DEADLINE))
  until [ "$(docker inspect --format '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null)" = "healthy" ]; do
    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "the server did not answer within ${HEALTH_DEADLINE}s" >&2
      docker logs --tail 20 "$CONTAINER" >&2 || true
      return 1
    fi
    sleep 1
  done
  echo "== loading the dump; psql's output goes to out/load.txt"
  # psql's own status is not the check: the dump names a role this server does not have, so it
  # reports an error per ALTER OWNER and exits non-zero on a load that is otherwise whole. What
  # is checked is the result, which is the tables.
  docker exec --interactive "$CONTAINER" psql --username=postgres --dbname=bird --no-psqlrc \
    --quiet --file=- < data/minidev/BIRD_dev.sql > out/load.txt 2>&1 || true
  loaded="$(docker exec "$CONTAINER" psql --username=postgres --dbname=bird --no-psqlrc \
    --tuples-only --no-align --command \
    "select count(*) from information_schema.tables where table_schema = 'public'" 2>/dev/null)"
  if [ "$loaded" != "$DUMP_TABLES" ]; then
    echo "the dump loaded $loaded tables of the $DUMP_TABLES the Mini-Dev fixture holds; the log is out/load.txt" >&2
    return 1
  fi
  echo "the dump loaded $loaded tables"
  auditor_password="$(openssl rand -hex 24)"
  # Checked, because this script runs without `set -e`: a role that was not made leaves every
  # audit below failing to authenticate, and this function used to print "server up" anyway.
  if ! { printf "\\set auditor_password '%s'\n" "$auditor_password"; cat <<'SQL'
CREATE ROLE auditor LOGIN PASSWORD :'auditor_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
REVOKE CREATE ON SCHEMA public FROM PUBLIC; REVOKE CREATE ON SCHEMA public FROM auditor;
GRANT USAGE ON SCHEMA public TO auditor; GRANT SELECT ON ALL TABLES IN SCHEMA public TO auditor;
ALTER ROLE auditor SET default_transaction_read_only = on;
CREATE SCHEMA attestql_scratch AUTHORIZATION auditor; CREATE SCHEMA attestql_scratch2 AUTHORIZATION auditor;
SQL
  } | docker exec --interactive "$CONTAINER" psql --username=postgres --dbname=bird --no-psqlrc \
      --set=ON_ERROR_STOP=1 --file=- >> out/load.txt 2>&1; then
    echo "the read-only auditor role was not created; the log is out/load.txt" >&2
    return 1
  fi
  unset POSTGRES_PASSWORD
  PGPASSWORD="$auditor_password"; export PGPASSWORD
  echo "server up on 127.0.0.1:$PORT"
}

postgres_down() { docker rm --force --volumes "$CONTAINER" >/dev/null 2>&1 || true; echo "container removed"; }

DSN="host=127.0.0.1 port=$PORT dbname=bird user=auditor"

# The gold-only runs, at the 30 second budget the two committed summaries record.
pg_gold_only() {  # pg_gold_only <zip|hf> <scratch schema>
  local copy="$1" schema="$2" out="runs/minidev-pg-gold-only/$1" questions origin qdate status start
  case "$copy" in
    zip) questions=data/questions/mini_dev_postgresql.json; origin="$MINIDEV_PG_ORIGIN"; qdate="$MINIDEV_PG_DATE" ;;
    hf) questions=data/questions/mini_dev_pg-00000-of-00001.json; origin="$HF_PG_ORIGIN"; qdate="$HF_PG_DATE" ;;
    *) echo "unknown gold copy $copy" >&2; return 1 ;;
  esac
  if [ -f "$out/summary.json" ]; then echo "already run: $out"; return 0; fi
  rm -rf "$out"; mkdir -p "$out"
  start=$SECONDS
  "$ATTESTQL" audit --dsn "$DSN" --questions "$questions" --questions-origin "$origin" \
    --questions-date "$qdate" --data-file data/minidev/BIRD_dev.sql --data-origin "$DUMP_ORIGIN" \
    --data-date "$DUMP_DATE" --scratch-schema "$schema" --statement-timeout 30 --out "$out" \
    > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "$out exit=$status in $((SECONDS - start))s: $(tail -1 "$out/stdout.txt")"
  [ "$status" -le 1 ] && [ -f "$out/summary.json" ] && return 0
  return 1
}

# The nine prediction runs, against the zip's own question file under position keying, which
# is the pairing BIRD's own evaluator credits with. 120 seconds, so that q707 of
# meta-llama-3-70b is compared rather than left as a timeout.
pg_prediction() {  # pg_prediction <model> <scratch schema>
  local model="$1" schema="$2" out="runs/minidev-pg/$1" file status start
  file="predict_mini_dev_${model}_postgresql.json"
  if [ -f "$out/summary.json" ]; then echo "already run: $out"; return 0; fi
  rm -rf "$out"; mkdir -p "$out"
  start=$SECONDS
  "$ATTESTQL" audit --dsn "$DSN" --questions data/questions/mini_dev_postgresql.json \
    --questions-origin "$MINIDEV_PG_ORIGIN" --questions-date "$MINIDEV_PG_DATE" \
    --predictions "data/preds-pg/$file" --predictions-keyed-by position \
    --predictions-origin "$PRED_BASE/$file" --predictions-date "$PRED_DATE" \
    --data-file data/minidev/BIRD_dev.sql --data-origin "$DUMP_ORIGIN" --data-date "$DUMP_DATE" \
    --scratch-schema "$schema" --statement-timeout 120 --out "$out" \
    > "$out.stdout.txt" 2> "$out.stderr.txt"
  status=$?
  mv "$out.stdout.txt" "$out/stdout.txt"; mv "$out.stderr.txt" "$out/stderr.txt"
  echo "$out exit=$status in $((SECONDS - start))s: $(tail -1 "$out/stdout.txt")"
  [ "$status" -le 1 ] && [ -f "$out/summary.json" ] && return 0
  return 1
}

postgres_runs() {
  cd "$RUNS_WORK"
  export ATTESTQL="${ATTESTQL:-$RUNS_WORK/venv/bin/attestql}"
  local model index=0
  pg_gold_only zip attestql_scratch &
  batch_add $!
  pg_gold_only hf attestql_scratch2 &
  batch_add $!
  batch_drain
  # Two lanes, each with a scratch schema of its own, as the prediction-mode measurement ran.
  # A lane fails when any run in it does, which is what the `||` carries out of the subshell.
  ( status=0
    for model in "${MODELS[@]:0:5}"; do pg_prediction "$model" attestql_scratch || status=1; done
    exit "$status" ) &
  batch_add $!
  ( status=0
    for model in "${MODELS[@]:5:4}"; do pg_prediction "$model" attestql_scratch2 || status=1; done
    exit "$status" ) &
  batch_add $!
  batch_drain
  [ "$FAILED" -eq 0 ] || { echo "$FAILED PostgreSQL run(s) failed" >&2; return 1; }
  echo "POSTGRES_DONE"
}

case "${1:-}" in
  inputs) inputs ;;
  sqlite) sqlite_runs || exit 1
          rerun_timeouts runs/bird-dev-sqlite/; rerun_timeouts runs/minidev-sqlite/ ;;
  postgres) postgres_up || { echo "the server did not start" >&2; exit 1; }
            postgres_runs || exit 1
            rerun_timeouts runs/minidev-pg-gold-only/; rerun_timeouts runs/minidev-pg/ ;;
  rerun) rerun_timeouts "${2:-runs/}" ;;
  teardown) postgres_down ;;
  *) sed -n '2,30p' "$0"; exit 2 ;;
esac
