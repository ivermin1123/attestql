"""Validate the hand readings against the fixed sample and add their counts."""

import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALLOWED = {"semantic", "structural", "cosmetic"}


def main() -> None:
    readings = json.loads((HERE / "readings.json").read_text(encoding="utf-8"))
    crosstab = json.loads((HERE / "crosstab.json").read_text(encoding="utf-8"))
    expected = {str(value) for values in crosstab["sample_ids"].values() for value in values}
    found = set(readings["questions"])
    if expected != found:
        raise SystemExit(
            f"reading ids differ from the sample: missing {sorted(expected - found)}, "
            f"extra {sorted(found - expected)}"
        )
    invalid = {
        question_id: row["class"]
        for question_id, row in readings["questions"].items()
        if row["class"] not in ALLOWED
    }
    if invalid:
        raise SystemExit(f"unknown reading classes: {invalid}")
    if set(readings["classes"]) != set(crosstab["sample_ids"]):
        raise SystemExit("a SQL class has readings but no estimate, or the reverse")

    by_reading = Counter(row["class"] for row in readings["questions"].values())
    by_class = defaultdict(Counter)
    for question_id, row in readings["questions"].items():
        sql_class = next(
            name for name, ids in crosstab["sample_ids"].items() if int(question_id) in ids
        )
        by_class[sql_class][row["class"]] += 1
    readings["summary"] = {
        "read": len(expected),
        "by_reading_class": dict(sorted(by_reading.items())),
        "by_sql_class": {
            name: dict(sorted(counts.items())) for name, counts in sorted(by_class.items())
        },
    }
    (HERE / "readings.json").write_text(json.dumps(readings, indent=1) + "\n", encoding="utf-8")
    print(readings["summary"])


if __name__ == "__main__":
    main()
