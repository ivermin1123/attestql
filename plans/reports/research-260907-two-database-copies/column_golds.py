"""Name the golds that touch CDS joins or Player.height, with their replay verdicts."""

import json
import os
import re
import sqlite3
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
SETS = {
    "dev-20240627": WORK / "data/dev/dev_20240627/dev.json",
    "dev-20251106": WORK / "data/hf/dev_20251106-00000-of-00001.json",
    "minidev-hf": WORK / "data/hf/mini_dev_sqlite-00000-of-00001.json",
}


def pairs(gold_set: str) -> dict[int, dict]:
    document = json.loads((WORK / "out" / "replay" / f"pairs-{gold_set}.json").read_text())
    return {row["question_id"]: row for row in document["questions"]}


def verdict(row: dict | None) -> dict:
    if row is None:
        return {"present": False}
    return {
        "present": True,
        "answer_class": row["answer_class"],
        "bird_set_equal": row["bird_set_equal"],
        "multiset_equal": row["multiset_equal"],
        "typed_equal": row["typed_equal"],
    }


def heights() -> dict:
    output = {}
    for database, name in (
        (WORK / "data/dev/dev_databases", "dev"),
        (WORK / "data/zip/minidev/MINIDEV/dev_databases", "minidev"),
    ):
        path = database / "european_football_2" / "european_football_2.sqlite"
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        connection.execute("pragma query_only = on")
        counts = dict(
            connection.execute(
                "select typeof(height), count(*) from Player group by typeof(height)"
            )
        )
        example = connection.execute(
            "select height from Player where height is not null order by rowid limit 1"
        ).fetchone()[0]
        connection.close()
        output[name] = {"storage_classes": counts, "example_first_row": example}
    return output


def main() -> None:
    cds = {}
    height = {}
    for gold_set, path in SETS.items():
        replay = pairs(gold_set)
        entries = [
            entry
            for entry in json.loads(path.read_text())
            if entry["db_id"]
            in {
                "california_schools",
                "european_football_2",
                "formula_1",
                "thrombosis_prediction",
                "toxicology",
            }
        ]
        cds_rows = []
        height_rows = []
        for entry in entries:
            sql = entry["SQL"]
            if re.search(r"\bsatscores\b", sql, re.IGNORECASE) and (
                re.search(r"\bschools\b", sql, re.IGNORECASE)
                or re.search(r"\bfrpm\b", sql, re.IGNORECASE)
            ):
                cds_rows.append(
                    {
                        "question_id": entry["question_id"],
                        **verdict(replay.get(entry["question_id"])),
                    }
                )
            if entry["db_id"] == "european_football_2" and re.search(
                r"\bheight\b", sql, re.IGNORECASE
            ):
                height_rows.append(
                    {
                        "question_id": entry["question_id"],
                        **verdict(replay.get(entry["question_id"])),
                    }
                )
        cds[gold_set] = cds_rows
        height[gold_set] = height_rows
    if len(height["dev-20240627"]) != 13:
        raise SystemExit(f"expected 13 height golds, found {len(height['dev-20240627'])}")
    document = {
        "cds_golds": cds,
        "height_golds": height,
        "player_height_storage": heights(),
        "height_source_check": {
            "run": False,
            "reason": "the European football dataset's Kaggle origin requires a login",
        },
    }
    target = WORK / "out" / "column-golds.json"
    target.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(
        f"CDS golds {[len(rows) for rows in cds.values()]}, height golds "
        f"{[len(rows) for rows in height.values()]}"
    )


if __name__ == "__main__":
    main()
