"""Score BIRD Mini-Dev PostgreSQL predictions with BIRD's own evaluator code.

``execute_sql`` and ``calculate_ex`` are imported verbatim from the upstream files in
``minidev_repo/`` (bird-bench/mini_dev, commit b3d4bcbb, evaluation/evaluation_utils.py sha256
f6943d24..., evaluation/evaluation_ex.py sha256 da1bbcd4...). Only ``connect_postgresql`` is
replaced, because upstream hard-codes a host, port and password
the connection here is the
read-only auditor login on the throwaway container. The try/except around one pair is what
upstream's ``execute_model`` does (timeout or any exception scores 0), reproduced so that the
reason is kept.

Pairing follows upstream: prediction key ``i`` is scored against gold line ``i`` of
``mini_dev_postgresql_gold.sql`` from the GitHub zip. For the Hugging Face gold, which has no
``.sql`` file, position ``i`` is mapped to the question id at entry ``i`` of the zip's question
file (the file the predictions answer) and that id's gold is read from the Hugging Face file.

usage: bird_ex_official.py <gold: zip|hf> <predictions.json> <out.json>
"""

import json
import os
import sys
import time
from pathlib import Path

import psycopg2
from func_timeout import FunctionTimedOut, func_timeout

WORK = Path(os.environ["MEASURE_WORK"])  # the work directory reproduce.sh fills
sys.path.insert(0, str(WORK / "minidev_repo"))
import evaluation_utils  # noqa: E402  (upstream, verbatim)
from evaluation_ex import calculate_ex  # noqa: E402  (upstream, verbatim)

DSN = "host=127.0.0.1 port=5498 dbname=bird user=auditor"
META_TIME_OUT = 30.0  # upstream's default


def connect_postgresql():
    return psycopg2.connect(DSN, password=os.environ["PGPASSWORD"])


evaluation_utils.connect_postgresql = connect_postgresql

ZIP_QUESTIONS = WORK / "data/zip/minidev/MINIDEV/mini_dev_postgresql.json"
ZIP_GOLD_SQL = WORK / "data/zip/minidev/MINIDEV/mini_dev_postgresql_gold.sql"
HF_QUESTIONS = WORK / "data/hf/mini_dev_pg-00000-of-00001.json"


def golds(which: str) -> list[tuple[int, str]]:
    """(question_id, gold SQL) per position, in the zip's order."""
    zip_entries = json.load(ZIP_QUESTIONS.open())
    if which == "zip":
        lines = [line.rstrip("\n") for line in ZIP_GOLD_SQL.open()]
        if len(lines) != len(zip_entries):
            raise ValueError("the gold file and the question file differ in length")
        return [
            (e["question_id"], line.split("\t")[0])
            for e, line in zip(zip_entries, lines, strict=True)
        ]
    hf_by_id = {e["question_id"]: e["SQL"] for e in json.load(HF_QUESTIONS.open())}
    return [(e["question_id"], hf_by_id[e["question_id"]]) for e in zip_entries]


def predictions(path: Path) -> list[str]:
    """Upstream's package_sqls(mode='pred'), without the db name it discards."""
    document = json.load(path.open())
    out = []
    for _, sql_str in document.items():
        if isinstance(sql_str, str):
            try:
                sql, _db = sql_str.split("\t----- bird -----\t")
            except ValueError:
                sql = sql_str.strip()
        else:
            sql = " "
        out.append(sql)
    return out


def score_one(pred: str, gold: str) -> dict:
    started = time.perf_counter()
    try:
        res = func_timeout(
            META_TIME_OUT,
            evaluation_utils.execute_sql,
            args=(pred, gold, None, "PostgreSQL", calculate_ex),
        )
        outcome = "scored"
        message = ""
    except FunctionTimedOut:
        res, outcome, message = 0, "timeout", ""
    except Exception as failed:
        res, outcome, message = 0, "error", " ".join(str(failed).split())[:300]
    return {
        "res": res,
        "outcome": outcome,
        "message": message,
        "seconds": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    which, pred_path, out_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    pairs = golds(which)
    preds = predictions(pred_path)
    if len(preds) != len(pairs):
        raise ValueError("the predictions and the golds differ in length")
    rows = []
    for position, ((question_id, gold), pred) in enumerate(zip(pairs, preds, strict=True)):
        scored = score_one(pred, gold)
        rows.append({"position": position, "question_id": question_id, **scored})
    total = sum(r["res"] for r in rows)
    document = {
        "gold": which,
        "predictions": str(pred_path.name),
        "evaluator": "bird-bench/mini_dev evaluation/evaluation_utils.py execute_sql + evaluation_ex.py calculate_ex, commit b3d4bcbb",
        "dsn_role": "auditor (read-only), PostgreSQL 16.15 in container attestql-minidev",
        "positions": len(rows),
        "ex_sum": total,
        "ex_percent": round(100.0 * total / len(rows), 2),
        "errors": sum(1 for r in rows if r["outcome"] == "error"),
        "timeouts": sum(1 for r in rows if r["outcome"] == "timeout"),
        "rows": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=1))
    print(
        f"{which} {pred_path.name}: EX {total}/500 = {document['ex_percent']} %, "
        f"errors {document['errors']}, timeouts {document['timeouts']}"
    )


if __name__ == "__main__":
    main()
