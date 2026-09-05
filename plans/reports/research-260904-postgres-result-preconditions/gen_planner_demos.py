"""Planner-switch and work_mem/hashagg demonstrations, task R-B item 1 and item 3.

Builds one small scratch table as postgres (superuser, in bird's public schema,
dropped at the end), then compares an ORDER BY with duplicate keys (tie order)
and a float SUM under different plan choices.
"""

import json
from pathlib import Path

import psycopg

W = Path(__file__).resolve().parent
SUPERUSER = "host=127.0.0.1 port=5499 dbname=bird user=postgres"
AUDITOR = "host=127.0.0.1 port=5499 dbname=bird user=auditor"

DDL = """
DROP TABLE IF EXISTS attestql_scratch.rb_tiebreak;
CREATE TABLE attestql_scratch.rb_tiebreak (k int, v float8);
INSERT INTO attestql_scratch.rb_tiebreak (k, v)
SELECT 1, i FROM generate_series(1, 20000) AS i;
"""

with psycopg.connect(SUPERUSER, autocommit=True) as conn, conn.cursor() as cur:
    cur.execute(DDL)
    cur.execute("GRANT SELECT ON attestql_scratch.rb_tiebreak TO auditor")

TIE_SQL = "SELECT k, v FROM attestql_scratch.rb_tiebreak ORDER BY k LIMIT 3"
SUM_SQL = "SELECT sum(v) FROM attestql_scratch.rb_tiebreak"


def run(sql, before):
    with psycopg.connect(AUDITOR, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("BEGIN READ ONLY")
        for stmt in before:
            cur.execute(stmt)
        cur.execute(sql)
        rows = [tuple(r) for r in cur.fetchall()]
        cur.execute("ROLLBACK")
        return rows


tie_seq = run(TIE_SQL, ["SET LOCAL enable_seqscan = on", "SET LOCAL enable_sort = on"])
tie_noseq = run(TIE_SQL, ["SET LOCAL enable_seqscan = off", "SET LOCAL enable_sort = off"])
sum_parallel_off = run(SUM_SQL, ["SET LOCAL max_parallel_workers_per_gather = 0"])
sum_parallel_on_hashagg_off = run(
    SUM_SQL, ["SET LOCAL max_parallel_workers_per_gather = 4", "SET LOCAL enable_hashagg = off"]
)

payload = {
    "note": "20000-row scratch table, k constant (a total tie under ORDER BY k)",
    "tie_seqscan_sort_on": [[str(v) for v in r] for r in tie_seq],
    "tie_seqscan_sort_off": [[str(v) for v in r] for r in tie_noseq],
    "tie_same": tie_seq == tie_noseq,
    "sum_parallel_off": str(sum_parallel_off[0][0]),
    "sum_parallel_on_hashagg_off": str(sum_parallel_on_hashagg_off[0][0]),
    "sum_same": sum_parallel_off == sum_parallel_on_hashagg_off,
}
(W / "planner_switch_demo.json").write_text(json.dumps(payload, indent=1))
print(json.dumps(payload, indent=1))

with psycopg.connect(SUPERUSER, autocommit=True) as conn, conn.cursor() as cur:
    cur.execute("DROP TABLE IF EXISTS attestql_scratch.rb_tiebreak")
