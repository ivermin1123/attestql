#!/usr/bin/env bash
# Start the pinned PostgreSQL 16 sandbox for the audit, load the fixture that reproduces the
# three shipped-gold defects, hand a read-only login to one child command, and tear the server
# down again.
#
#   tools/audit-sandbox/run.sh <output-directory> -- <command> [args...]
#
# The whole lifecycle runs in the foreground: start, wait until the server answers on TCP, load
# fixture.sql, create the read-only auditor login, run the child, capture what it wrote, tear
# down. Teardown is on a trap and therefore runs on every exit path, including a signal and a
# failure, and the child's exit code is this script's exit code. There is no option to leave the
# sandbox running.
#
# Everything the run produces is written to <output-directory>, which must be outside the
# repository: the captures carry a container id and timestamps and are not repository artifacts.
#
# The image is pinned by the same OCI image index digest the Slice 1 harnesses used
# (tools/m5-sandbox/compose.yaml at the tag slice1-final), read from that file rather than
# resolved again. A tag moves; a digest does not. An index digest selects a different platform
# manifest per architecture, so the bytes that actually run are identical only on the same
# platform.
#
# Two passwords are generated per run. The superuser's reaches the server through the
# environment, is used over the container's own unix socket where the image trusts local
# connections, and is dropped before the child runs; the auditor's is written onto psql's stdin
# and handed to the child as PGPASSWORD. Neither is written to a tracked file, neither appears in
# any command line, and neither is echoed. The child receives the presence-only gate
# ATTESTQL_AUDIT_SANDBOX, which carries no secret, and ATTESTQL_AUDIT_DSN, which carries no
# password. A child therefore reaches this server as the read-only auditor and as nothing else.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/../.." && pwd)"
fixture="$here/fixture.sql"
container="attestql-audit-sandbox"
image="postgres@sha256:c1b3783309b6499c795eed7c20135a1a4d25cae1b575c3d52c6f536129a1b109"
port=5497
health_deadline_seconds=90

if [ $# -lt 3 ] || [ "$2" != "--" ]; then
  echo "usage: $0 <output-directory> -- <command> [args...]" >&2
  exit 2
fi
out="$1"
shift 2
mkdir -p "$out"
out="$(cd "$out" && pwd)"
case "$out" in
  "$repo_root" | "$repo_root"/*)
    echo "the output directory must be outside the repository: $out" >&2
    exit 2
    ;;
esac
if [ ! -f "$fixture" ]; then
  echo "the fixture this harness loads is missing: $fixture" >&2
  exit 2
fi

# A deterministic port means a second run must reuse or stop the first server, never drift onto
# another port and leave the first one orphaned. A container carrying this harness's own name is
# a leftover of a run that died before its trap and is removed; anything else holding the port is
# named and left alone, because this script has no business stopping it.
docker rm --force --volumes "$container" >/dev/null 2>&1 || true
if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "port $port is held by something this harness did not start:" >&2
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >&2
  echo "stop it and run again; the audit sandbox has no second port" >&2
  exit 1
fi

POSTGRES_PASSWORD="$(openssl rand -hex 24)"
auditor_credential="$(openssl rand -hex 24)"
export POSTGRES_PASSWORD

# Removes the container and the anonymous data volume the image declares, then drops the
# generated credentials out of this shell. Runs on success, on failure and on a signal: the two
# signal traps below exist so that the EXIT trap is reached rather than bypassed.
teardown() {
  local started=$SECONDS
  docker rm --force --volumes "$container" >/dev/null 2>&1 || true
  unset POSTGRES_PASSWORD auditor_credential PGPASSWORD
  echo "sandbox container and its data volume removed in $((SECONDS - started))s"
}
trap teardown EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# The healthcheck asks over TCP on the loopback address inside the container, which is the path
# the child will use. The temporary server the image runs while it initialises the cluster and
# creates the database listens on the unix socket only, so a TCP probe cannot report the server
# healthy before the database `audit` exists.
started_at=$SECONDS
docker run --detach --name "$container" \
  --publish "127.0.0.1:$port:5432" \
  --env POSTGRES_PASSWORD \
  --env POSTGRES_DB=audit \
  --health-cmd "pg_isready --host=127.0.0.1 --username=postgres --dbname=audit --quiet" \
  --health-interval=1s --health-timeout=5s --health-retries="$health_deadline_seconds" \
  "$image" >/dev/null

deadline=$((SECONDS + health_deadline_seconds))
until [ "$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null)" = "healthy" ]; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    docker logs "$container" > "$out/server.log" 2>&1 || true
    echo "the server did not answer within ${health_deadline_seconds}s; its log is $out/server.log" >&2
    exit 1
  fi
  sleep 1
done
healthy_seconds=$((SECONDS - started_at))
echo "server healthy on 127.0.0.1:$port after ${healthy_seconds}s"

# Every administrative statement goes over the container's unix socket as the superuser, where
# the image's own pg_hba trusts local connections, so no password is ever passed to psql.
psql_super() {
  docker exec --interactive "$container" psql --username=postgres --dbname=audit \
    --no-psqlrc --set=ON_ERROR_STOP=1 "$@"
}

started_at=$SECONDS
psql_super --file=- < "$fixture" > "$out/load.txt" 2>&1
load_seconds=$((SECONDS - started_at))
echo "fixture loaded in ${load_seconds}s; the load log is $out/load.txt"

# The read-only login the child audits with. printf is a shell builtin, so the credential reaches
# psql over the pipe and never exists as an argument vector or a temporary file. The role is
# read-only three times over: it holds SELECT and nothing else on the two schemas the fixture
# loads, it cannot create anything in either of them, and its sessions open read-only
# transactions by default.
# public.sealed is the one table it is not granted at all.
# The one place it may write is attestql_scratch, which the shuffled-copy smell needs and which
# holds no fixture table.
{
  printf "\\set auditor_password '%s'\n" "$auditor_credential"
  cat <<'SQL'
CREATE ROLE auditor LOGIN PASSWORD :'auditor_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM auditor;
GRANT USAGE ON SCHEMA public TO auditor;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO auditor;
-- The second schema the fixture loads, granted the same way and named the same way it was
-- created: a schema whose name is mixed case has to be quoted here too, and a gold that reads
-- one of its tables writes it out exactly like this.
GRANT USAGE ON SCHEMA "Quoted" TO auditor;
GRANT SELECT ON ALL TABLES IN SCHEMA "Quoted" TO auditor;
-- One table the grant above reached and this takes back: the audit needs a table that is
-- there and that its login may not read, which is not the same thing as a table nobody
-- loaded and is not repaired in the same place.
REVOKE SELECT ON public.sealed FROM auditor;
ALTER ROLE auditor SET default_transaction_read_only = on;
CREATE SCHEMA attestql_scratch AUTHORIZATION auditor;
SQL
} | psql_super --file=- >> "$out/load.txt" 2>&1
echo "read-only auditor login created; scratch schema attestql_scratch is its own"

{
  echo "image_reference=$image"
  echo "image_id=$(docker image inspect "$image" --format '{{.Id}}')"
  echo "image_platform=$(docker image inspect "$image" --format '{{.Os}}/{{.Architecture}}{{if .Variant}}/{{.Variant}}{{end}}')"
  echo "docker_server_version=$(docker version --format '{{.Server.Version}}')"
  echo "host_uname=$(uname -sm)"
  echo "server_version=$(psql_super --tuples-only --no-align --command='SELECT version()')"
  echo "database=audit"
  echo "port=$port"
  echo "child_role=auditor"
} > "$out/environment.txt"

# The superuser is done. Dropping its credential here is what makes the child, and everything it
# runs, reach this server as the auditor and as nothing else.
unset POSTGRES_PASSWORD

export ATTESTQL_AUDIT_SANDBOX=1
export ATTESTQL_AUDIT_DSN="host=127.0.0.1 port=$port dbname=audit user=auditor"
export PGPASSWORD="$auditor_credential"

echo "sandbox ready; running: $*"
started_at=$SECONDS
set +e
"$@" 2> "$out/child-stderr.txt" | tee "$out/child-stdout.txt"
child_status=${PIPESTATUS[0]}
set -e
child_seconds=$((SECONDS - started_at))
cat "$out/child-stderr.txt" >&2

{
  echo "child_command=$*"
  echo "child_exit_status=$child_status"
  echo "healthy_after_seconds=$healthy_seconds"
  echo "fixture_load_seconds=$load_seconds"
  echo "child_seconds=$child_seconds"
} > "$out/child.txt"
cat "$out/child.txt"

exit "$child_status"
