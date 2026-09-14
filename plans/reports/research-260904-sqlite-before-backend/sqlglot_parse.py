"""Parse every gold of the three sets with sqlglot's sqlite dialect.

Run with the sqlglot venv:
  $W/env/bin/python scripts/sqlglot_parse.py
"""

import json
import os
import re
import sys

sys.path.insert(
    0,
    os.environ.get("MEASURE_WORK", ".") + "/work-rd/scripts",
)
import sqlglot
from load_golds import SETS, load
from sqlglot import ErrorLevel

SCRATCH = os.environ.get("MEASURE_WORK", ".")
"""The directory this run worked in, which held `data/` and `work-r*/`.

Read from the environment and not written here: the run of 2026-09-04 used a scratch
directory belonging to the session that made it, and one machine's layout is not something
this repository publishes. The default is what a rerun from that directory reads."""

OUT = f"{SCRATCH}/work-rd"


def shape(msg):
    """Bucket an error message by removing the variable parts."""
    m = re.sub(r"Line \d+, Col: \d+\.", "", msg)
    m = re.sub(r"'[^']*'", "'X'", m)
    m = re.sub(r"\s+", " ", m).strip()
    # Keep only first line / first clause as the shape key.
    return m.split(".")[0][:80]


def main():
    summary = {}
    for set_name in SETS:
        rows = load(set_name)
        parsed = 0
        failures = []
        for r in rows:
            try:
                sqlglot.parse_one(r["SQL"], read="sqlite", error_level=ErrorLevel.RAISE)
                parsed += 1
            except Exception as e:
                failures.append(
                    {
                        "question_id": r["question_id"],
                        "db_id": r["db_id"],
                        "error": str(e),
                        "shape": shape(str(e)),
                    }
                )
        summary[set_name] = {
            "total": len(rows),
            "parsed": parsed,
            "failed": len(failures),
        }
        with open(f"{OUT}/sqlglot_failures_{set_name}.json", "w") as f:
            json.dump(failures, f, indent=1)
        print(set_name, parsed, "/", len(rows), "failed", len(failures))

    with open(f"{OUT}/sqlglot_summary.json", "w") as f:
        json.dump(summary, f, indent=1)


if __name__ == "__main__":
    main()
