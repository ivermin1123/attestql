"""Replay one gold set on dev's and Mini-Dev's copy of its differing database.

    MEASURE_WORK=<work> python3 replay_pairs.py <dev-20240627|dev-20251106|minidev-hf>
    MEASURE_WORK=<work> python3 replay_pairs.py <set> --retry-timeouts

Both copies use Python sqlite3's read-only URI, ``PRAGMA query_only`` and the same 30 second
progress-handler deadline as the tool. A run holds one SQLite connection at a time; callers run
three gold-set processes at most. ``--retry-timeouts`` keeps the under-load answer beside the
serial one and replaces every timed-out entry alone.

Readings, all over the values sqlite3 returns:

* BIRD: ``set(dev_rows) == set(minidev_rows)``.
* multiset: ``Counter(dev_rows) == Counter(minidev_rows)``.
* typed: each cell becomes ``(sqlite storage class, value)``. Python makes ``182 == 182.0``;
  this reading does not, which is the only reading that sees the Player heights.
"""

import base64
import json
import math
import os
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
DEV = WORK / "data/dev/dev_databases"
MINIDEV = WORK / "data/zip/minidev/MINIDEV/dev_databases"
DIFFERING = {
    "california_schools",
    "european_football_2",
    "formula_1",
    "thrombosis_prediction",
    "toxicology",
}
QUESTIONS = {
    "dev-20240627": WORK / "data/dev/dev_20240627/dev.json",
    "dev-20251106": WORK / "data/hf/dev_20251106-00000-of-00001.json",
    "minidev-hf": WORK / "data/hf/mini_dev_sqlite-00000-of-00001.json",
}
TIMEOUT_SECONDS = 30.0


def storage_class(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "real"
    if isinstance(value, str):
        return "text"
    if isinstance(value, bytes):
        return "blob"
    raise TypeError(f"sqlite3 returned {type(value)!r}")


def typed(rows: list[tuple[object, ...]]) -> list[tuple[tuple[str, object], ...]]:
    return [tuple((storage_class(value), value) for value in row) for row in rows]


def execute(path: Path, statement: str) -> dict:
    started = time.monotonic()
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    deadline = started + TIMEOUT_SECONDS

    def deadline_passed() -> int:
        return int(time.monotonic() >= deadline)

    connection.execute("pragma query_only = on")
    connection.set_progress_handler(deadline_passed, 1000)
    try:
        rows = connection.execute(statement).fetchall()
        return {
            "outcome": "scored",
            "row_count": len(rows),
            "rows": rows,
            "seconds": round(time.monotonic() - started, 3),
            "message": "",
        }
    except Exception as failed:
        elapsed = time.monotonic() - started
        interrupted = "interrupted" in str(failed).lower()
        return {
            "outcome": "timeout" if interrupted and elapsed >= TIMEOUT_SECONDS - 0.5 else "error",
            "row_count": None,
            "rows": [],
            "seconds": round(elapsed, 3),
            "message": " ".join(str(failed).split())[:300],
        }
    finally:
        connection.close()


def json_value(value: object) -> object:
    if isinstance(value, bytes):
        return {"base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, float) and not math.isfinite(value):
        return {"float": math.copysign(0.0, value)}
    return value


def row_json(row: tuple[object, ...]) -> list[object]:
    return [json_value(value) for value in row]


def typed_row_json(row: tuple[object, ...]) -> list[dict]:
    return [{"storage_class": storage_class(value), "value": json_value(value)} for value in row]


def first_set_difference(
    left: list[tuple[object, ...]], right: list[tuple[object, ...]]
) -> dict | None:
    right_set = set(right)
    for row in left:
        if row not in right_set:
            return {"side": "dev", "row": row_json(row)}
    left_set = set(left)
    for row in right:
        if row not in left_set:
            return {"side": "minidev", "row": row_json(row)}
    return None


def first_multiplicity_difference(
    left: Counter[tuple[object, ...]], right: Counter[tuple[object, ...]]
) -> dict | None:
    for row in sorted(set(left) | set(right), key=repr):
        if left[row] != right[row]:
            return {
                "row": row_json(row),
                "dev": left[row],
                "minidev": right[row],
            }
    return None


def classify(dev: dict, minidev: dict) -> dict:
    failed = dev["outcome"] != "scored" or minidev["outcome"] != "scored"
    dev_rows, minidev_rows = dev.pop("rows"), minidev.pop("rows")
    dev_counts, minidev_counts = Counter(dev_rows), Counter(minidev_rows)
    bird_set_equal = set(dev_rows) == set(minidev_rows)
    multiset_equal = dev_counts == minidev_counts
    typed_equal = Counter(typed(dev_rows)) == Counter(typed(minidev_rows))
    if failed:
        answer_class = "error-or-timeout"
    elif not bird_set_equal:
        answer_class = "different-rows"
    elif not multiset_equal:
        answer_class = "same-set-other-multiplicities"
    elif not typed_equal:
        answer_class = "typed-difference-only"
    else:
        answer_class = "identical-multiset"

    first_difference = None
    if answer_class == "different-rows":
        first_difference = first_set_difference(dev_rows, minidev_rows)
    elif answer_class == "same-set-other-multiplicities":
        first_difference = first_multiplicity_difference(dev_counts, minidev_counts)
    elif answer_class == "typed-difference-only":
        left, right = typed(dev_rows), typed(minidev_rows)
        found = first_set_difference(left, right)  # type: ignore[arg-type]
        if found is not None:
            first_difference = {
                "side": found["side"],
                "row": typed_row_json(found["row"]),
            }
    return {
        "bird_set_equal": bird_set_equal,
        "multiset_equal": multiset_equal,
        "typed_equal": typed_equal,
        "answer_class": answer_class,
        "first_difference": first_difference,
    }


def strip_internal(result: dict) -> dict:
    return {key: value for key, value in result.items() if key != "rows"}


def questions(name: str) -> list[dict]:
    return [
        entry for entry in json.loads(QUESTIONS[name].read_text()) if entry["db_id"] in DIFFERING
    ]


def output_path(name: str) -> Path:
    return WORK / "out" / "replay" / f"pairs-{name}.json"


def write(document: dict, path: Path) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(name: str) -> None:
    entries = questions(name)
    rows = []
    path = output_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    for position, entry in enumerate(entries):
        db = entry["db_id"]
        dev = execute(DEV / db / f"{db}.sqlite", entry["SQL"])
        minidev = execute(MINIDEV / db / f"{db}.sqlite", entry["SQL"])
        verdict = classify(dev, minidev)
        rows.append(
            {
                "position": position,
                "question_id": entry["question_id"],
                "db_id": db,
                "dev": strip_internal(dev),
                "minidev": strip_internal(minidev),
                **verdict,
            }
        )
        if position % 20 == 0 or position == len(entries) - 1:
            write({"gold_set": name, "retry": False, "questions": rows}, path)
    classes = Counter(row["answer_class"] for row in rows)
    write(
        {
            "gold_set": name,
            "retry": False,
            "readings": {
                "bird": "set(rows) equality",
                "multiset": "Counter(rows) equality",
                "typed": "Counter((sqlite storage class, value) per cell) equality",
            },
            "class_counts": dict(sorted(classes.items())),
            "questions": rows,
        },
        path,
    )
    print(f"{name}: {len(rows)} golds replayed, {dict(classes)}")


def retry_timeouts(name: str) -> None:
    path = output_path(name)
    document = json.loads(path.read_text())
    selected = [
        row
        for row in document["questions"]
        if row["dev"]["outcome"] == "timeout" or row["minidev"]["outcome"] == "timeout"
    ]
    if not selected:
        return
    path.with_suffix(".under-load.json").write_text(path.read_text(), encoding="utf-8")
    by_id = {entry["question_id"]: entry for entry in questions(name)}
    for old in selected:
        entry = by_id[old["question_id"]]
        db = entry["db_id"]
        dev = execute(DEV / db / f"{db}.sqlite", entry["SQL"])
        minidev = execute(MINIDEV / db / f"{db}.sqlite", entry["SQL"])
        new = {
            "position": old["position"],
            "question_id": entry["question_id"],
            "db_id": db,
            "dev": strip_internal(dev),
            "minidev": strip_internal(minidev),
            **classify(dev, minidev),
        }
        document["questions"][old["position"]] = new
    document["retry"] = True
    document["serial_retry_ids"] = [row["question_id"] for row in selected]
    document["class_counts"] = dict(
        sorted(Counter(row["answer_class"] for row in document["questions"]).items())
    )
    write(document, path)
    print(f"{name}: retried alone {[row['question_id'] for row in selected]}")


def main() -> None:
    if (
        len(sys.argv) not in (2, 3)
        or sys.argv[1] not in QUESTIONS
        or sys.argv[2:]
        not in (
            [],
            ["--retry-timeouts"],
        )
    ):
        raise SystemExit("usage: replay_pairs.py <set> [--retry-timeouts]")
    if len(sys.argv) == 3:
        retry_timeouts(sys.argv[1])
    else:
        run(sys.argv[1])


if __name__ == "__main__":
    main()
