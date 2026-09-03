#!/usr/bin/env bash
# Reproduce every number of measurement-260904-prediction-mode-on-real-predictions.md.
#
#   plans/reports/prediction-mode-260904-real-predictions/reproduce.sh <work-directory>
#
# Needs: Docker (port 5498 free), uv, curl, unzip, and this repository installed so that
# `attestql` is on PATH (`uv tool install .`, or set ATTESTQL="uv run attestql"). The work
# directory must be outside the repository; it receives the 800 MB zip, the 1 GB dump, the
# prediction files and every output. Nothing BIRD publishes is copied into the repository:
# the report cites each file by URL and sha256, and the copies of the outputs committed
# beside this script are the ones `build_artifact.py` selects.
#
# Steps: download and verify the inputs; start a throwaway PostgreSQL 16 container pinned by
# digest; load the Mini-Dev dump; create the read-only auditor; run the tool (run_tool.sh);
# score every file with BIRD's own evaluator (bird_ex_official.py); count (measure.py,
# classify.py, column_names.py, aggregate.py); remove the container. Teardown is on a trap.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
export MEASURE_WORK="$(mkdir -p "$1" && cd "$1" && pwd)"
case "$MEASURE_WORK" in "$repo"|"$repo"/*) echo "the work directory must be outside the repository" >&2; exit 2;; esac
cd "$MEASURE_WORK"
mkdir -p data/preds data/hf data/zip minidev_repo out

verify() { echo "$2  $1" | shasum -a 256 --check --status || { echo "digest mismatch: $1" >&2; exit 1; }; }

# 1. Inputs, each verified against the digest the report states.
[ -f data/minidev.zip ] || curl -sSL "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip" -o data/minidev.zip
verify data/minidev.zip cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f
unzip -o -q data/minidev.zip "minidev/MINIDEV/mini_dev_postgresql.json" "minidev/MINIDEV/mini_dev_postgresql_gold.sql" "minidev/MINIDEV_postgresql/BIRD_dev.sql" -d data/zip
verify data/zip/minidev/MINIDEV/mini_dev_postgresql.json d2731292f20b8d8569cd956dd747ffe1df13cd625076263e38ae9ebcef50b1ab
verify data/zip/minidev/MINIDEV/mini_dev_postgresql_gold.sql 8922d94a9ffcd0c4602f0e74290305bb5fced19a2208daef825d8e43c6f0d759
curl -sSL "https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/f65faf4ae3b638c1fa6df1d3370c8d92c8366301/data/mini_dev_pg-00000-of-00001.json" -o data/hf/mini_dev_pg-00000-of-00001.json
verify data/hf/mini_dev_pg-00000-of-00001.json 7fa740ef9225389cff6c34432120e8325d0ca3008d73db1ae38731234bc10da7
commit=b3d4bcbbae9a96934ad812551eb400c7a3b23c12
while read -r model digest; do
  f="predict_mini_dev_${model}_postgresql.json"
  curl -sSL "https://raw.githubusercontent.com/bird-bench/mini_dev/$commit/llm/exp_result/sql_output_kg/$f" -o "data/preds/$f"
  verify "data/preds/$f" "$digest"
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
for f in evaluation_ex.py evaluation_utils.py; do
  curl -sSL "https://raw.githubusercontent.com/bird-bench/mini_dev/$commit/evaluation/$f" -o "minidev_repo/$f"
done
verify minidev_repo/evaluation_ex.py da1bbcd4530be83692d7c650c814ea9704bb710d0c953eb75d02ccb38233cf89
verify minidev_repo/evaluation_utils.py f6943d249caac5aeaef9bce21d43dbf29dcef85a0c965a76df032a9542f308bf
# The corrected golds: the three statements the sandbox fixture carries as its predictions.
python3 - "$repo" <<'PY'
import json, sys
from pathlib import Path
repo = Path(sys.argv[1])
fix = json.load(open(repo / "tools/audit-sandbox/predictions.json"))
hf = {e["question_id"]: e for e in json.load(open("data/hf/mini_dev_pg-00000-of-00001.json"))}
out = [{**{k: hf[int(i)][k] for k in ("question_id", "db_id", "question", "evidence")}, "SQL": sql, "difficulty": hf[int(i)]["difficulty"]}
       for i, sql in fix.items()]
json.dump(out, open("data/corrected-gold.json", "w"), indent=1, ensure_ascii=False)
PY
mkdir -p data/preds-by-id
for f in data/preds/*.json; do python3 "$here/predictions_by_question_id.py" "$f" "data/preds-by-id/$(basename "$f")"; done
[ -d birdenv ] || { uv venv birdenv -q && uv pip install --python birdenv/bin/python -q psycopg2-binary pymysql func_timeout; }

# 2. The server: the same image digest the merge gate's sandbox pins.
container=attestql-minidev
image="postgres@sha256:c1b3783309b6499c795eed7c20135a1a4d25cae1b575c3d52c6f536129a1b109"
docker rm --force --volumes "$container" >/dev/null 2>&1 || true
teardown() { docker rm --force --volumes "$container" >/dev/null 2>&1 || true; echo "container removed"; }
trap teardown EXIT
POSTGRES_PASSWORD="$(openssl rand -hex 24)"; export POSTGRES_PASSWORD
docker run --detach --name "$container" --publish "127.0.0.1:5498:5432" --env POSTGRES_PASSWORD --env POSTGRES_DB=bird \
  --health-cmd "pg_isready --host=127.0.0.1 --username=postgres --dbname=bird --quiet" --health-interval=1s --health-timeout=5s --health-retries=90 "$image" >/dev/null
until [ "$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null)" = "healthy" ]; do sleep 1; done
docker exec --interactive "$container" psql --username=postgres --dbname=bird --no-psqlrc --quiet --file=- < data/zip/minidev/MINIDEV_postgresql/BIRD_dev.sql > out/load.txt 2>&1 || true
auditor_password="$(openssl rand -hex 24)"
{ printf "\\set auditor_password '%s'\n" "$auditor_password"; cat <<'SQL'
CREATE ROLE auditor LOGIN PASSWORD :'auditor_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
REVOKE CREATE ON SCHEMA public FROM PUBLIC; REVOKE CREATE ON SCHEMA public FROM auditor;
GRANT USAGE ON SCHEMA public TO auditor; GRANT SELECT ON ALL TABLES IN SCHEMA public TO auditor;
ALTER ROLE auditor SET default_transaction_read_only = on;
CREATE SCHEMA attestql_scratch AUTHORIZATION auditor; CREATE SCHEMA attestql_scratch2 AUTHORIZATION auditor;
SQL
} | docker exec --interactive "$container" psql --username=postgres --dbname=bird --no-psqlrc --set=ON_ERROR_STOP=1 --file=- >> out/load.txt 2>&1
unset POSTGRES_PASSWORD
export PGPASSWORD="$auditor_password"

# 3. The tool, BIRD's evaluator, the counts.
bash "$here/run_tool.sh"
for gold in zip hf; do for f in data/preds/*.json; do
  m="$(basename "$f" .json)"; m="${m#predict_mini_dev_}"; m="${m%_postgresql}"
  birdenv/bin/python "$here/bird_ex_official.py" "$gold" "$f" "out/official/$gold/$m.json"
done; done
for m in gpt-35-turbo-instruct gpt-35-turbo gpt-4-32k gpt-4-turbo gpt-4 meta-llama-3-70b-instruct-2 meta-llama-3-8b-instruct-2 mistralai-mixtral-8x7b-instru-4 phi-3-medium-128k-instruct-1; do
  birdenv/bin/python "$here/column_names.py" hf "$m" "out/names/hf/$m.json"
done
(cd "$here" && python3 measure.py && python3 classify.py && python3 aggregate.py)
echo "done: $MEASURE_WORK/out/aggregate.json"
