"""Score one Mini-Dev prediction file with BIRD's own unmodified SQLite evaluator.

    MEASURE_WORK=<work> python bird_ex_official.py <predictions.json> <out.json> <db-directory>

The gold is always the Hugging Face copy. Position ``i`` follows the zip question file, as
upstream's positional prediction files do; the database argument chooses dev.zip's or
minidev.zip's copy. The only change from the sibling script is that argument.
"""

import json
import os
import sys
import time
from pathlib import Path

from func_timeout import FunctionTimedOut, func_timeout

WORK = Path(os.environ["MEASURE_WORK"])
sys.path.insert(0, str(WORK / "minidev_repo"))
import evaluation_utils  # noqa: E402  (upstream, verbatim)
from evaluation_ex import calculate_ex  # noqa: E402  (upstream, verbatim)

META_TIME_OUT = 30.0
ZIP_QUESTIONS = WORK / "data/zip/minidev/MINIDEV/mini_dev_sqlite.json"
HF_QUESTIONS = WORK / "data/hf/mini_dev_sqlite-00000-of-00001.json"


def golds() -> list[tuple[int, str, str]]:
    zip_entries = json.loads(ZIP_QUESTIONS.read_text())
    by_id = {entry["question_id"]: entry for entry in json.loads(HF_QUESTIONS.read_text())}
    return [
        (
            entry["question_id"],
            by_id[entry["question_id"]]["SQL"],
            by_id[entry["question_id"]]["db_id"],
        )
        for entry in zip_entries
    ]


def predictions(path: Path) -> list[str]:
    out = []
    for _, value in json.loads(path.read_text()).items():
        if not isinstance(value, str):
            out.append(" ")
            continue
        try:
            statement, _database = value.split("\t----- bird -----\t")
        except ValueError:
            statement = value.strip()
        out.append(statement)
    return out


def score_one(pred: str, gold: str, database: Path) -> dict:
    started = time.perf_counter()
    try:
        result = func_timeout(
            META_TIME_OUT,
            evaluation_utils.execute_sql,
            args=(pred, gold, str(database), "SQLite", calculate_ex),
        )
        outcome, message = "scored", ""
    except FunctionTimedOut:
        result, outcome, message = 0, "timeout", ""
    except Exception as failed:
        result, outcome, message = 0, "error", " ".join(str(failed).split())[:300]
    return {
        "res": result,
        "outcome": outcome,
        "message": message,
        "seconds": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: bird_ex_official.py <predictions> <out> <database-directory>")
    source, target, databases = (Path(argument) for argument in sys.argv[1:])
    pairs = golds()
    preds = predictions(source)
    if len(preds) != len(pairs):
        raise ValueError("the predictions and the golds differ in length")
    rows = []
    for position, ((question_id, gold, db_id), pred) in enumerate(zip(pairs, preds, strict=True)):
        rows.append(
            {
                "position": position,
                "question_id": question_id,
                "db_id": db_id,
                **score_one(pred, gold, databases / db_id / f"{db_id}.sqlite"),
            }
        )
    total = sum(row["res"] for row in rows)
    document = {
        "gold": "hugging-face",
        "predictions": source.name,
        "evaluator": (
            "bird-bench/mini_dev evaluation/evaluation_utils.py execute_sql + "
            "evaluation_ex.py calculate_ex, commit b3d4bcbb, SQLite path unmodified"
        ),
        "databases": str(databases),
        "positions": len(rows),
        "ex_sum": total,
        "ex_percent": round(100.0 * total / len(rows), 2),
        "errors": sum(row["outcome"] == "error" for row in rows),
        "timeouts": sum(row["outcome"] == "timeout" for row in rows),
        "rows": rows,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(
        f"{databases.name} {source.name}: EX {total}/500 = {document['ex_percent']} %, "
        f"errors {document['errors']}, timeouts {document['timeouts']}"
    )


if __name__ == "__main__":
    main()
