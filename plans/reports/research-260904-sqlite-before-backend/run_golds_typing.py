"""Task 4b: execute every gold against its database (read-only), 30 s cap per
gold via a worker process (SIGALRM is not available across the pool boundary
cleanly on all platforms, so a subprocess-per-batch with a hard wall-clock
budget is used instead: a query that has not returned after 30 s is killed and
counted as a skip). Per result column, the set of Python types seen (a
faithful proxy for SQLite's storage class here: sqlite3 with no adapters
registered returns int for 'integer', float for 'real', str for 'text', bytes
for 'blob', None for 'null', by https://docs.python.org/3/library/sqlite3.html
#sqlite-and-python-types). Also computes, per gold, whether a bare Python
set() of its result rows is smaller than a set keyed on (type, value) per
cell, which is exactly where 1 == 1.0 == True would merge two SQLite-typed
values BIRD's evaluator would otherwise tell apart.
"""

import json
import multiprocessing as mp
import sqlite3
import sys
import time

sys.path.insert(
    0,
    "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rd/scripts",
)
from load_golds import load

D = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data/zip/minidev/MINIDEV/dev_databases"
W = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rd"


def _run_one(db_id, sql, q):
    try:
        con = sqlite3.connect(f"file:{D}/{db_id}/{db_id}.sqlite?mode=ro", uri=True)
        cur = con.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        con.close()
        q.put(("ok", rows))
    except Exception as e:
        q.put(("error", f"{type(e).__name__}: {e}"))


def run_with_timeout(db_id, sql, timeout=30):
    q = mp.Queue()
    p = mp.Process(target=_run_one, args=(db_id, sql, q))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        return "timeout", None
    if not q.empty():
        return q.get()
    return "error", "no result (process died)"


def analyze(rows):
    """Per-column type sets, and the Python-vs-typed set-size gap."""
    if not rows:
        return {"n_rows": 0, "n_cols": 0, "col_type_sets": [], "python_set_smaller": False}
    n_cols = len(rows[0])
    col_types = [set() for _ in range(n_cols)]
    for row in rows:
        for i, v in enumerate(row):
            col_types[i].add(type(v).__name__)
    python_set_size = len(set(rows))
    typed_rows = [tuple((type(v).__name__, v) for v in row) for row in rows]
    typed_set_size = len(set(typed_rows))
    return {
        "n_rows": len(rows),
        "n_cols": n_cols,
        "col_type_sets": [sorted(s) for s in col_types],
        "python_set_size": python_set_size,
        "typed_set_size": typed_set_size,
        "python_set_smaller": python_set_size < typed_set_size,
    }


def main(set_name):
    rows = load(set_name)
    out_path = f"{W}/typing_{set_name}.json"
    out = []
    done_ids = set()
    try:
        with open(out_path) as f:
            out = json.load(f)
        done_ids = {r["question_id"] for r in out}
        print(f"resuming {set_name}: {len(done_ids)} already done", flush=True)
    except FileNotFoundError:
        pass
    t0 = time.time()
    for i, r in enumerate(rows):
        if r["question_id"] in done_ids:
            continue
        status, payload = run_with_timeout(r["db_id"], r["SQL"])
        if status == "ok":
            info = analyze(payload)
            info.update({"question_id": r["question_id"], "db_id": r["db_id"], "status": "ok"})
        else:
            info = {
                "question_id": r["question_id"],
                "db_id": r["db_id"],
                "status": status,
                "detail": str(payload)[:200],
            }
        out.append(info)
        if (i + 1) % 25 == 0:
            with open(out_path, "w") as f:
                json.dump(out, f, indent=1)
            print(set_name, i + 1, "/", len(rows), f"{time.time() - t0:.0f}s", flush=True)
    with open(out_path, "w") as f:
        json.dump(out, f, indent=1)
    print(set_name, "done", f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
