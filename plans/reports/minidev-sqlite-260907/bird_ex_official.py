"""Score BIRD Mini-Dev SQLite predictions with BIRD's own evaluator code.

``execute_sql`` and ``calculate_ex`` are imported verbatim from the upstream files in
``minidev_repo/`` (bird-bench/mini_dev, commit b3d4bcbb, evaluation/evaluation_utils.py sha256
f6943d24..., evaluation/evaluation_ex.py sha256 da1bbcd4...). Nothing is replaced here, unlike
the PostgreSQL sibling of this script: upstream's SQLite path is ``sqlite3.connect(db_path)``
and the path is this run's own copy of the database, so what scores the predictions is the
evaluator as it ships.

Pairing follows upstream: prediction key ``i`` is scored against gold line ``i`` of
``mini_dev_sqlite_gold.sql`` from the GitHub zip, on the database named at the end of that
line. For the Hugging Face gold, which has no ``.sql`` file, position ``i`` is mapped to the
question id at entry ``i`` of the zip's question file (the file the predictions answer) and
that id's gold and database are read from the Hugging Face file.

usage: bird_ex_official.py <gold: zip|hf> <predictions.json> <out.json>
"""

import json
import os
import sys
import time
from pathlib import Path

from func_timeout import FunctionTimedOut, func_timeout

WORK = Path(os.environ["MEASURE_WORK"])  # the work directory reproduce.sh fills
sys.path.insert(0, str(WORK / "minidev_repo"))
import evaluation_utils  # noqa: E402  (upstream, verbatim)
from evaluation_ex import calculate_ex  # noqa: E402  (upstream, verbatim)

META_TIME_OUT = 30.0  # upstream's default

ZIP_QUESTIONS = WORK / "data/zip/minidev/MINIDEV/mini_dev_sqlite.json"
ZIP_GOLD_SQL = WORK / "data/zip/minidev/MINIDEV/mini_dev_sqlite_gold.sql"
HF_QUESTIONS = WORK / "data/hf/mini_dev_sqlite-00000-of-00001.json"
DATABASES = WORK / "data/zip/minidev/MINIDEV/dev_databases"


def database(db_id: str) -> str:
    """The file upstream's ``connect_db`` opens for that database, as upstream lays it out."""
    return str(DATABASES / db_id / f"{db_id}.sqlite")


def golds(which: str) -> list[tuple[int, str, str]]:
    """(question_id, gold SQL, db_id) per position, in the zip's order."""
    zip_entries = json.load(ZIP_QUESTIONS.open())
    if which == "zip":
        lines = [line.rstrip("\n") for line in ZIP_GOLD_SQL.open() if line.strip()]
        if len(lines) != len(zip_entries):
            raise ValueError("the gold file and the question file differ in length")
        pairs = []
        for entry, line in zip(zip_entries, lines, strict=True):
            sql, _, db_id = line.rpartition("\t")
            pairs.append((entry["question_id"], sql.strip(), db_id.strip()))
        return pairs
    hf_by_id = {entry["question_id"]: entry for entry in json.load(HF_QUESTIONS.open())}
    return [
        (
            entry["question_id"],
            hf_by_id[entry["question_id"]]["SQL"],
            hf_by_id[entry["question_id"]]["db_id"],
        )
        for entry in zip_entries
    ]


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


def score_one(pred: str, gold: str, db_id: str) -> dict:
    started = time.perf_counter()
    try:
        res = func_timeout(
            META_TIME_OUT,
            evaluation_utils.execute_sql,
            args=(pred, gold, database(db_id), "SQLite", calculate_ex),
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
    for position, ((question_id, gold, db_id), pred) in enumerate(zip(pairs, preds, strict=True)):
        scored = score_one(pred, gold, db_id)
        rows.append({"position": position, "question_id": question_id, "db_id": db_id, **scored})
    total = sum(r["res"] for r in rows)
    document = {
        "gold": which,
        "predictions": str(pred_path.name),
        "evaluator": (
            "bird-bench/mini_dev evaluation/evaluation_utils.py execute_sql + "
            "evaluation_ex.py calculate_ex, commit b3d4bcbb, SQLite path unmodified"
        ),
        "databases": str(DATABASES),
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
