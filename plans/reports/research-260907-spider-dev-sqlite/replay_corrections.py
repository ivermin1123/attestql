"""Replay each 2020 Spider correction before and after under the tool's SQLite envelope.

usage: MEASURE_WORK=<work-directory> python3 replay_corrections.py

The envelope is a read-only URI connection, ``PRAGMA query_only = ON``, and a 30 second wall
clock deadline installed as a progress handler. Rows and their order are compared as SQLite
returned them; no canonicalisation is applied. An execution error is an outcome, not a crash.
"""

import json
import os
import sqlite3
import time
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"]).resolve()
SPIDER = WORK / "data" / "spider" / "spider_data"
OUT = WORK / "out"


def run(db_id: str, sql: str) -> dict:
    path = SPIDER / "database" / db_id / f"{db_id}.sqlite"
    deadline = time.monotonic() + 30
    started = time.monotonic()
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.execute("PRAGMA query_only = ON")
    connection.set_progress_handler(lambda: time.monotonic() >= deadline, 1000)
    try:
        cursor = connection.execute(sql)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description or ()]
        return {
            "ok": True,
            "row_count": len(rows),
            "columns": columns,
            "rows": rows,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    except Exception as error:  # sqlite3 errors are measurements, including the 2020 typo
        return {
            "ok": False,
            "error": f"{type(error).__name__}: {error}",
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    finally:
        connection.close()


def main() -> None:
    corrections = json.loads((OUT / "corrections.json").read_text(encoding="utf-8"))
    rows = []
    for correction in corrections["correction_set"]:
        before = run(correction["db_id"], correction["before_sql"])
        after = run(correction["db_id"], correction["after_sql"])
        public = {
            "question_id": correction["question_id"],
            "db_id": correction["db_id"],
            "before": {key: value for key, value in before.items() if key != "rows"},
            "after": {key: value for key, value in after.items() if key != "rows"},
            "same_rows": before.get("ok", False)
            and after.get("ok", False)
            and before["rows"] == after["rows"],
        }
        rows.append(public)
    document = {
        "reading": (
            "Each before/after SQL pair replayed sequentially on its own database, in a fresh "
            "read-only query-only connection with a 30 s deadline. same_rows compares SQLite's "
            "ordered values exactly."
        ),
        "counts": {
            "pairs": len(rows),
            "both_executed": sum(row["before"]["ok"] and row["after"]["ok"] for row in rows),
            "before_only_executed": sum(
                row["before"]["ok"] and not row["after"]["ok"] for row in rows
            ),
            "after_only_executed": sum(
                not row["before"]["ok"] and row["after"]["ok"] for row in rows
            ),
            "neither_executed": sum(
                not row["before"]["ok"] and not row["after"]["ok"] for row in rows
            ),
            "same_rows": sum(row["same_rows"] for row in rows),
            "different_rows": sum(
                row["before"]["ok"] and row["after"]["ok"] and not row["same_rows"] for row in rows
            ),
        },
        "rows": rows,
    }
    (OUT / "corrections-replayed.json").write_text(
        json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(document["counts"])


if __name__ == "__main__":
    main()
