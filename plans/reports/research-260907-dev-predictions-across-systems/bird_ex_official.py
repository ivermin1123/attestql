"""Run BIRD's own dev evaluator, unmodified, over one selected prediction file.

bird_ex_official.py <copy:old|dev1106> <prediction.json> <out.json>
"""

import json
import os
import sys
import time
from pathlib import Path

from func_timeout import FunctionTimedOut, func_timeout

WORK = Path(os.environ["MEASURE_WORK"])
sys.path.insert(0, str(WORK / "bird_repo"))
import evaluation  # noqa: E402  (upstream, verbatim)

META_TIME_OUT = 30.0
OLD_QUESTIONS = WORK / "data/dev/dev_20240627/dev.json"
OLD_GOLD_SQL = WORK / "data/dev/dev_20240627/dev.sql"
NEW_QUESTIONS = WORK / "data/hf/dev_20251106-00000-of-00001.json"
DATABASES = WORK / "data/dev/dev_databases"
SUFFIX = "\t----- bird -----\t"


def database(db_id: str) -> str:
    """The file upstream names, except the byte-identical WAL work copy of card_games."""
    root = WORK / "data/dev/copies" if db_id == "card_games" else DATABASES
    return str(root / db_id / f"{db_id}.sqlite")


def golds(copy: str) -> list[tuple[int, str, str]]:
    entries = json.loads(OLD_QUESTIONS.read_text(encoding="utf-8"))
    if copy == "old":
        lines = [line.rstrip("\n") for line in OLD_GOLD_SQL.open(encoding="utf-8") if line.strip()]
        if len(lines) != len(entries):
            raise ValueError("the gold file and the question file differ in length")
        return [
            (
                entry["question_id"],
                line.rpartition("\t")[0].strip(),
                line.rpartition("\t")[2].strip(),
            )
            for entry, line in zip(entries, lines, strict=True)
        ]
    new_by_id = {entry["question_id"]: entry for entry in json.loads(NEW_QUESTIONS.read_text())}
    return [
        (
            entry["question_id"],
            new_by_id[entry["question_id"]]["SQL"],
            new_by_id[entry["question_id"]]["db_id"],
        )
        for entry in entries
    ]


def predictions(path: Path, pairs: list[tuple[int, str, str]]) -> list[tuple[str, str]]:
    """Statements in question order, with the prediction's named database when it has one."""
    shipped = json.loads(path.read_text(encoding="utf-8"))
    positional = set(shipped) == {str(position) for position in range(len(pairs))}
    out = []
    for position, (question_id, _, _) in enumerate(pairs):
        key = str(position) if positional else str(question_id)
        value = shipped[key]
        if not isinstance(value, str):
            sql, db_id = " ", "financial"
        elif SUFFIX in value:
            sql, db_id = value.split(SUFFIX)
        else:
            sql, db_id = value.strip(), ""
        out.append((sql, db_id))
    return out


def score_one(pred: str, gold: str, db_path: str) -> dict:
    started = time.perf_counter()
    try:
        result = func_timeout(META_TIME_OUT, evaluation.execute_sql, args=(pred, gold, db_path))
        outcome, message = "scored", ""
    except FunctionTimedOut:
        result, outcome, message = 0, "timeout", ""
    except Exception as failed:  # upstream's own catch-all
        result, outcome, message = 0, "error", " ".join(str(failed).split())[:300]
    return {
        "res": result,
        "outcome": outcome,
        "message": message,
        "seconds": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    copy, pred_path, out_path = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    pairs = golds(copy)
    preds = predictions(pred_path, pairs)
    rows = []
    for (question_id, gold, gold_db), (pred, pred_db) in zip(pairs, preds, strict=True):
        scored = score_one(pred, gold, database(pred_db or gold_db))
        rows.append(
            {
                "position": len(rows),
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
        "card_games": "byte-identical work copy, WAL sidecars need a writable directory",
        "positions": len(rows),
        "ex_sum": total,
        "ex_percent": round(100.0 * total / len(rows), 2),
        "errors": sum(row["outcome"] == "error" for row in rows),
        "timeouts": sum(row["outcome"] == "timeout" for row in rows),
        "rows": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(
        f"{copy} {pred_path.name}: EX {total}/{len(rows)} = "
        f"{document['ex_percent']} %, errors {document['errors']}, "
        f"timeouts {document['timeouts']}"
    )


if __name__ == "__main__":
    main()
