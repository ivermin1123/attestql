"""Do work_mem / enable_hashagg change the 9 float-summation-sensitive golds
once max_parallel_workers_per_gather is forced to 0 (task R-B item 3)?"""

import json
from pathlib import Path

import psycopg

D = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data"
W = Path(__file__).resolve().parent
DSN = "host=127.0.0.1 port=5499 dbname=bird user=auditor"
IDS = [1473, 1476, 1482, 1529, 1531, 1380, 1390, 1410, 955]

with open(f"{D}/hf/mini_dev_pg-00000-of-00001.json") as f:
    golds = {row["question_id"]: row["SQL"] for row in json.load(f)}


def run(sql, before):
    with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("BEGIN READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '20000'")
        cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
        for stmt in before:
            cur.execute(stmt)
        cur.execute(sql)
        rows = [tuple(str(v) for v in r) for r in cur.fetchall()]
        cur.execute("ROLLBACK")
        return rows


out = {}
for qid in IDS:
    sql = golds[qid]
    baseline = run(sql, [])
    hashagg_off = run(sql, ["SET LOCAL enable_hashagg = off"])
    small_work_mem = run(sql, ["SET LOCAL work_mem = '64kB'", "SET LOCAL hash_mem_multiplier = 1"])
    out[qid] = {
        "baseline": baseline,
        "enable_hashagg_off": hashagg_off,
        "work_mem_64kB": small_work_mem,
        "enable_hashagg_off_same": baseline == hashagg_off,
        "work_mem_64kB_same": baseline == small_work_mem,
    }
    print(qid, out[qid]["enable_hashagg_off_same"], out[qid]["work_mem_64kB_same"])

(W / "hashagg_workmem_demo.json").write_text(json.dumps(out, indent=1))
