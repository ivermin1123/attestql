"""Execute the 170 gold/prediction pairs on the research server and apply every reading.

One psycopg2 connection per pair, a fresh read-only transaction each time, so one pair's
error or timeout cannot affect another. Session settings follow the task's instructions:
SET LOCAL max_parallel_workers_per_gather = 0, SET LOCAL statement_timeout = '30s'.

Writes, per pair, the fetched rows (typed) to $W/pairs_data/<model>__q<id>.json (scratch,
not the repository) and accumulates the reading verdicts into results.json here.
"""

import json
import os
import sys
import traceback
from datetime import date, datetime
from datetime import time as dtime
from decimal import Decimal
from pathlib import Path

import psycopg2

sys.path.insert(0, os.path.dirname(__file__))
import readings as R

DSN = "host=127.0.0.1 port=5499 dbname=bird user=auditor"
HERE = os.path.dirname(__file__)
W = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-ra"
SQL_DIR = f"{W}/sql"
DATA_DIR = f"{W}/pairs_data"
os.makedirs(DATA_DIR, exist_ok=True)


def tag(value):
    if value is None:
        return {"t": "null", "v": None}
    if isinstance(value, bool):
        return {"t": "bool", "v": value}
    if isinstance(value, Decimal):
        return {"t": "dec", "v": str(value)}
    if isinstance(value, (date, datetime, dtime)):
        return {"t": type(value).__name__, "v": value.isoformat()}
    if isinstance(value, (int, float, str)):
        return {"t": type(value).__name__, "v": value}
    return {"t": type(value).__name__, "v": str(value)}


def run_one(conn, sql):
    with conn.cursor() as cur:
        cur.execute("SET LOCAL max_parallel_workers_per_gather = 0")
        cur.execute("SET LOCAL statement_timeout = '30s'")
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return cols, rows


def execute_pair(pair):
    model, qid = pair["model"], pair["question_id"]
    with open(f"{SQL_DIR}/{model}__q{qid}.json") as f:
        payload = json.load(f)
    gold_sql, pred_sql, question = payload["gold_sql"], payload["pred_sql"], payload["question"]

    gold_sql_nd = R._strip_distinct(gold_sql)
    pred_sql_nd = R._strip_distinct(pred_sql)

    conn = psycopg2.connect(DSN)
    conn.set_session(readonly=True, autocommit=False)
    try:
        gold_cols, gold_rows = run_one(conn, gold_sql)
        pred_cols, pred_rows = run_one(conn, pred_sql)
        # test-suite-sql-eval's CLI default (keep_distinct=False) strips DISTINCT from the
        # SQL text before executing, so the raw multiplicity (join fanout) is what its
        # multiset comparison sees. Re-run only when stripping actually changed the text.
        if gold_sql_nd != gold_sql:
            gold_cols_nd, gold_rows_nd = run_one(conn, gold_sql_nd)
        else:
            gold_cols_nd, gold_rows_nd = gold_cols, gold_rows
        if pred_sql_nd != pred_sql:
            pred_cols_nd, pred_rows_nd = run_one(conn, pred_sql_nd)
        else:
            pred_cols_nd, pred_rows_nd = pred_cols, pred_rows
        conn.rollback()
    except Exception as e:
        conn.rollback()
        conn.close()
        return {"model": model, "question_id": qid, "error": f"{type(e).__name__}: {e}"}
    conn.close()

    with open(f"{DATA_DIR}/{model}__q{qid}.json", "w") as f:
        json.dump(
            {
                "gold_cols": gold_cols,
                "gold_rows": [[tag(v) for v in row] for row in gold_rows],
                "pred_cols": pred_cols,
                "pred_rows": [[tag(v) for v in row] for row in pred_rows],
            },
            f,
        )

    out = {"model": model, "question_id": qid}
    for name, fn in R.READINGS.items():
        if name == "test_suite":
            continue
        try:
            out[name] = bool(fn(gold_cols, gold_rows, pred_cols, pred_rows, gold_sql, question))
        except Exception as e:
            out[name] = None
            out[f"{name}_error"] = f"{type(e).__name__}: {e}"
    try:
        out["test_suite"] = bool(
            R.test_suite_result_eq(
                gold_cols_nd, gold_rows_nd, pred_cols_nd, pred_rows_nd, gold_sql, question
            )
        )
    except Exception as e:
        out["test_suite"] = None
        out["test_suite_error"] = f"{type(e).__name__}: {e}"
    return out


def main():
    pairs = json.loads(Path(f"{HERE}/pairs.json").read_text())
    results = []
    errors = []
    for i, pair in enumerate(pairs):
        try:
            r = execute_pair(pair)
        except Exception as e:
            r = {
                "model": pair["model"],
                "question_id": pair["question_id"],
                "error": f"{type(e).__name__}: {e}",
                "trace": traceback.format_exc(),
            }
        if "error" in r:
            errors.append(r)
        r["class"] = pair["class"]
        r["mechanism"] = pair["mechanism"]
        r["rule"] = pair["rule"]
        results.append(r)
        if (i + 1) % 20 == 0:
            print(f"{i + 1}/{len(pairs)} done", flush=True)

    with open(f"{HERE}/results.json", "w") as f:
        json.dump(results, f, indent=1)
    print(f"wrote {len(results)} results, {len(errors)} errors")
    if errors:
        print("ERRORS:", json.dumps(errors, indent=1)[:4000])


if __name__ == "__main__":
    main()
