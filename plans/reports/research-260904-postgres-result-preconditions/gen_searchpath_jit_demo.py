"""search_path (statement meaning) and jit (result bytes), task R-B item 1."""

import json
from pathlib import Path

import psycopg

W = Path(__file__).resolve().parent
SUPERUSER = "host=127.0.0.1 port=5499 dbname=bird user=postgres"
AUDITOR = "host=127.0.0.1 port=5499 dbname=bird user=auditor"

with psycopg.connect(SUPERUSER, autocommit=True) as conn, conn.cursor() as cur:
    cur.execute("DROP TABLE IF EXISTS attestql_scratch.rb_sp")
    cur.execute("DROP TABLE IF EXISTS attestql_scratch2.rb_sp")
    cur.execute("CREATE TABLE attestql_scratch.rb_sp (v text)")
    cur.execute("CREATE TABLE attestql_scratch2.rb_sp (v text)")
    cur.execute("INSERT INTO attestql_scratch.rb_sp VALUES ('from scratch1')")
    cur.execute("INSERT INTO attestql_scratch2.rb_sp VALUES ('from scratch2')")
    cur.execute("GRANT SELECT ON attestql_scratch.rb_sp TO auditor")
    cur.execute("GRANT SELECT ON attestql_scratch2.rb_sp TO auditor")

out = {}
for path in ("attestql_scratch, public", "attestql_scratch2, public"):
    with psycopg.connect(AUDITOR, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("BEGIN READ ONLY")
        cur.execute(f"SET LOCAL search_path = {path}")
        cur.execute("SELECT v FROM rb_sp")
        out[f"search_path={path}"] = [r[0] for r in cur.fetchall()]
        cur.execute("ROLLBACK")

with psycopg.connect(SUPERUSER, autocommit=True) as conn, conn.cursor() as cur:
    cur.execute("DROP TABLE IF EXISTS attestql_scratch.rb_sp")
    cur.execute("DROP TABLE IF EXISTS attestql_scratch2.rb_sp")

jit = {}
sql = (
    "SELECT sum(v) FROM (SELECT (i % 97)::float8 / 3.0 AS v FROM generate_series(1, 300000) AS i) s"
)
for value in ("off", "on"):
    with psycopg.connect(AUDITOR, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("BEGIN READ ONLY")
        cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
        cur.execute(f"SET LOCAL jit = {value}")
        cur.execute("SET LOCAL jit_above_cost = 0")
        cur.execute(sql)
        jit[f"jit={value}"] = str(cur.fetchone()[0])
        cur.execute("ROLLBACK")

(W / "search_path_demo.json").write_text(json.dumps(out, indent=1))
(W / "jit_demo.json").write_text(json.dumps(jit, indent=1))
print("search_path", out)
print("jit", jit)
