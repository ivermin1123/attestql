"""Equality-family operators (GROUP BY, =, LIKE) are collation-independent under
deterministic collations; ordering operators (<,>,<=,>=) are not. Task R-B item 2/3."""

import json
from pathlib import Path

import psycopg

D = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data"
W = Path(__file__).resolve().parent

with open(f"{D}/hf/mini_dev_pg-00000-of-00001.json") as f:
    golds = {row["question_id"]: row["SQL"] for row in json.load(f)}

DBS = {
    "bird": "host=127.0.0.1 port=5499 dbname=bird user=auditor",
    "bird_c": "host=127.0.0.1 port=5499 dbname=bird_c user=auditor",
    "bird_icu": "host=127.0.0.1 port=5499 dbname=bird_icu user=auditor",
}

SAMPLE = {
    "groupby_text": [1531, 1322, 1381, 1404, 1405],
    "eq_text": [1471, 1472, 1473, 1476, 1479],
    "like_text": [1482, 1338, 1105, 1110, 1113],
    "ord_cmp_text": [1133],
}


def run(dsn, sql):
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("BEGIN READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '15000'")
        cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
        cur.execute(sql)
        rows = [tuple(str(v) for v in r) for r in cur.fetchall()]
        cur.execute("ROLLBACK")
        return rows


out = {}
for kind, ids in SAMPLE.items():
    for qid in ids:
        sql = golds[qid]
        per_db = {name: run(dsn, sql) for name, dsn in DBS.items()}
        out[f"{kind}:{qid}"] = {
            "rowset_same_bird_vs_c": sorted(per_db["bird"]) == sorted(per_db["bird_c"]),
            "rowset_same_bird_vs_icu": sorted(per_db["bird"]) == sorted(per_db["bird_icu"]),
            "order_same_bird_vs_c": per_db["bird"] == per_db["bird_c"],
            "order_same_bird_vs_icu": per_db["bird"] == per_db["bird_icu"],
        }
        print(kind, qid, out[f"{kind}:{qid}"])

(W / "deterministic_collation_demo.json").write_text(json.dumps(out, indent=1))
