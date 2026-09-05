import json
import re

import psycopg

D = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data"
W = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rb"

with open(f"{D}/hf/mini_dev_pg-00000-of-00001.json") as f:
    golds = json.load(f)

DSN = "host=127.0.0.1 port=5499 dbname=bird user=auditor"

DATE_LITERAL_RE = re.compile(r"'\d{1,4}[/-]\d{1,2}[/-]\d{1,4}'")
BACKSLASH_RE = re.compile(r"'[^']*\\\\[^']*'")
TOCHAR_RE = re.compile(r"\bto_char\s*\(", re.I)
TODATE_RE = re.compile(r"\bto_date\s*\(", re.I)
TOTS_RE = re.compile(r"\bto_timestamp\s*\(", re.I)
SUM_AVG_RE = re.compile(r"\b(SUM|AVG)\s*\(", re.I)

out = []
for row in golds:
    qid = row["question_id"]
    sql = row["SQL"]
    entry = {"question_id": qid, "db_id": row["db_id"]}
    entry["date_literal"] = bool(DATE_LITERAL_RE.search(sql))
    entry["backslash_literal"] = bool(BACKSLASH_RE.search(sql))
    entry["to_char"] = bool(TOCHAR_RE.search(sql))
    entry["to_date"] = bool(TODATE_RE.search(sql))
    entry["to_timestamp"] = bool(TOTS_RE.search(sql))
    entry["sum_avg"] = bool(SUM_AVG_RE.search(sql))
    # One connection per gold: a failed statement need not be unwound by hand.
    with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
        try:
            cur.execute("BEGIN READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '10000'")
            cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
            cur.execute(sql)
            types = []
            for col in cur.description or ():
                t = conn.adapters.types.get(col.type_code)
                types.append(t.name if t else str(col.type_code))
            entry["result_types"] = types
            entry["row_count"] = len(cur.fetchall())
            cur.execute("ROLLBACK")
        except psycopg.Error as e:
            entry["error"] = str(e)[:200]
    out.append(entry)
with open(f"{W}/gold_run_all.json", "w") as f:
    json.dump(out, f, indent=1)
print("done", len(out))
