"""Score BIRD dev SQLite predictions with BIRD's own dev evaluator code.

``execute_sql`` is imported verbatim from ``bird_repo/evaluation.py``
(AlibabaResearch/DAMO-ConvAI, commit dec31ae3, bird/llm/src/evaluation.py, sha256 2f591e55...),
the evaluator BIRD ships for the dev set. Nothing in it is replaced: its SQLite path is
``sqlite3.connect(db_path)`` and the path is this run's own copy of the database.

Pairing follows upstream exactly. ``package_sqls(mode='gpt')`` reads the prediction file in
entry order, takes the text before ``\\t----- bird -----\\t`` and the database after it, and
substitutes ``(" ", "financial")`` for an entry that is not a string; ``package_sqls(mode='gt')``
reads gold line ``i`` of ``<data_mode>_gold.sql``. ``run_sqls_parallel`` then runs pair ``i``
against ``db_places[i]``, the database the **prediction** named, which is what is reproduced
here. dev.zip ships that gold file as ``dev.sql`` rather than ``dev_gold.sql``; its 1,534 lines
match ``dev.json`` position for position, gold text and db_id alike, which reproduce.sh checks.
The 2025-11-06 pass publishes no ``.sql`` file, so its gold at position ``i`` is read from its
JSON entry ``i``; the two copies hold the same ids in the same order.

usage: bird_ex_official.py <copy: old|dev1106> <predictions.json> <out.json>
"""

import json
import os
import sys
import time
from pathlib import Path

from func_timeout import FunctionTimedOut, func_timeout

WORK = Path(os.environ["MEASURE_WORK"])  # the work directory reproduce.sh fills
sys.path.insert(0, str(WORK / "bird_repo"))
import evaluation  # noqa: E402  (upstream, verbatim)

META_TIME_OUT = 30.0  # upstream's default
OLD_QUESTIONS = WORK / "data/dev/dev_20240627/dev.json"
OLD_GOLD_SQL = WORK / "data/dev/dev_20240627/dev.sql"
NEW_QUESTIONS = WORK / "data/hf/dev_20251106-00000-of-00001.json"
DATABASES = WORK / "data/dev/dev_databases"
SUFFIX = "\t----- bird -----\t"


def database(db_id: str) -> str:
    """The file upstream's ``db_root_path + db_name + '/' + db_name + '.sqlite'`` names."""
    return str(DATABASES / db_id / f"{db_id}.sqlite")


def golds(copy: str) -> list[tuple[int, str, str]]:
    """(question_id, gold SQL, db_id) per position, in the question file's order."""
    entries = json.load(OLD_QUESTIONS.open())
    if copy == "old":
        lines = [line.rstrip("\n") for line in OLD_GOLD_SQL.open() if line.strip()]
        if len(lines) != len(entries):
            raise ValueError("the gold file and the question file differ in length")
        out = []
        for entry, line in zip(entries, lines, strict=True):
            sql, _, db_id = line.rpartition("\t")
            out.append((entry["question_id"], sql.strip(), db_id.strip()))
        return out
    new_by_id = {entry["question_id"]: entry for entry in json.load(NEW_QUESTIONS.open())}
    return [
        (
            entry["question_id"],
            new_by_id[entry["question_id"]]["SQL"],
            new_by_id[entry["question_id"]]["db_id"],
        )
        for entry in entries
    ]


def predictions(path: Path) -> list[tuple[str, str]]:
    """Upstream's ``package_sqls(mode='gpt')``: the statement and the database it named."""
    out = []
    for _, sql_str in json.load(path.open()).items():
        if isinstance(sql_str, str):
            sql, db_name = sql_str.split(SUFFIX) if SUFFIX in sql_str else (sql_str.strip(), "")
        else:
            sql, db_name = " ", "financial"
        out.append((sql, db_name))
    return out


def score_one(pred: str, gold: str, db_path: str) -> dict:
    started = time.perf_counter()
    try:
        res = func_timeout(META_TIME_OUT, evaluation.execute_sql, args=(pred, gold, db_path))
        outcome, message = "scored", ""
    except FunctionTimedOut:
        res, outcome, message = 0, "timeout", ""
    except Exception as failed:  # upstream's own catch-all
        res, outcome, message = 0, "error", " ".join(str(failed).split())[:300]
    return {
        "res": res,
        "outcome": outcome,
        "message": message,
        "seconds": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    copy, pred_path, out_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    pairs = golds(copy)
    preds = predictions(pred_path)
    if len(preds) != len(pairs):
        raise ValueError("the predictions and the golds differ in length")
    rows = []
    for position, ((question_id, gold, gold_db), (pred, pred_db)) in enumerate(
        zip(pairs, preds, strict=True)
    ):
        # Upstream runs the pair against the database the prediction named, not the gold's.
        scored = score_one(pred, gold, database(pred_db or gold_db))
        rows.append(
            {
                "position": position,
                "question_id": question_id,
                "db_id": gold_db,
                "prediction_db_id": pred_db,
                **scored,
            }
        )
    total = sum(row["res"] for row in rows)
    document = {
        "copy": copy,
        "predictions": pred_path.name,
        "evaluator": (
            "AlibabaResearch/DAMO-ConvAI bird/llm/src/evaluation.py execute_sql, commit "
            "dec31ae3, sha256 2f591e559dc2d97e5b35d5b656e80b0c2edf968f0bb5a78ddfd1d88b4bbbc472, "
            "unmodified"
        ),
        "databases": str(DATABASES),
        "positions": len(rows),
        "ex_sum": total,
        "ex_percent": round(100.0 * total / len(rows), 2),
        "errors": sum(1 for row in rows if row["outcome"] == "error"),
        "timeouts": sum(1 for row in rows if row["outcome"] == "timeout"),
        "rows": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=1))
    print(
        f"{copy} {pred_path.name}: EX {total}/{len(rows)} = {document['ex_percent']} %, "
        f"errors {document['errors']}, timeouts {document['timeouts']}"
    )


if __name__ == "__main__":
    main()
