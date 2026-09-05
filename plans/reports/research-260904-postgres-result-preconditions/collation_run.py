import json

import psycopg

D = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data"
W = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rb"

with open(f"{D}/hf/mini_dev_pg-00000-of-00001.json") as f:
    golds = {row["question_id"]: row for row in json.load(f)}

text_order_ids = [1392, 1078, 1102, 846, 847, 931, 824, 220, 232, 115, 129]

DBS = {
    "bird": "host=127.0.0.1 port=5499 dbname=bird user=auditor",
    "bird_c": "host=127.0.0.1 port=5499 dbname=bird_c user=auditor",
    "bird_icu": "host=127.0.0.1 port=5499 dbname=bird_icu user=auditor",
}


def run(dsn, sql):
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("BEGIN READ ONLY")
        cur.execute("SET LOCAL statement_timeout = '15000'")
        cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
        cur.execute(sql)
        cols = [c.name for c in cur.description]
        rows = [tuple(r) for r in cur.fetchall()]
        cur.execute("ROLLBACK")
        return cols, rows


out = {}
for qid in text_order_ids:
    sql = golds[qid]["SQL"]
    per_db = {}
    for name, dsn in DBS.items():
        try:
            cols, rows = run(dsn, sql)
            per_db[name] = {"cols": cols, "rows": [[str(v) for v in r] for r in rows]}
        except Exception as e:
            per_db[name] = {"error": str(e)}
    order_bird_c = per_db["bird"]["rows"] == per_db["bird_c"].get("rows")
    order_bird_icu = per_db["bird"]["rows"] == per_db["bird_icu"].get("rows")
    set_bird_c = sorted(per_db["bird"]["rows"]) == sorted(per_db["bird_c"].get("rows", []))
    set_bird_icu = sorted(per_db["bird"]["rows"]) == sorted(per_db["bird_icu"].get("rows", []))
    out[qid] = {
        "db_id": golds[qid]["db_id"],
        "order_same_bird_vs_c": order_bird_c,
        "order_same_bird_vs_icu": order_bird_icu,
        "rowset_same_bird_vs_c": set_bird_c,
        "rowset_same_bird_vs_icu": set_bird_icu,
        "per_db": per_db,
    }
    print(
        qid,
        golds[qid]["db_id"],
        "order_c=",
        order_bird_c,
        "order_icu=",
        order_bird_icu,
        "set_c=",
        set_bird_c,
        "set_icu=",
        set_bird_icu,
    )

with open(f"{W}/collation_order_diff.json", "w") as f:
    json.dump(out, f, indent=1)
