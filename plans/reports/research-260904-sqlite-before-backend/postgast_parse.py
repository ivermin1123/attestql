"""Run the tool's own parser (postgast, via attestql.audit.statements.parse_statement)
over the same three gold sets. Run with the worktree's uv env:

  cd <the checkout this file is in>
  UV_PROJECT_ENVIRONMENT=/tmp/attestql-research-venv uv run python \
      /private/tmp/.../scripts/postgast_parse.py
"""

import json
import os
import re
import sys

sys.path.insert(
    0,
    os.environ.get("MEASURE_WORK", ".") + "/work-rd/scripts",
)
from load_golds import SETS, load

from attestql.audit.statements import StatementRefused, parse_statement

SCRATCH = os.environ.get("MEASURE_WORK", ".")
"""The directory this run worked in, which held `data/` and `work-r*/`.

Read from the environment and not written here: the run of 2026-09-04 used a scratch
directory belonging to the session that made it, and one machine's layout is not something
this repository publishes. The default is what a rerun from that directory reads."""

OUT = f"{SCRATCH}/work-rd"


def shape(msg):
    m = re.sub(r"'[^']*'", "'X'", msg)
    m = re.sub(r"\s+", " ", m).strip()
    return m[:100]


def main():
    summary = {}
    for set_name in SETS:
        rows = load(set_name)
        parsed = 0
        failures = []
        for r in rows:
            try:
                parse_statement(r["SQL"])
                parsed += 1
            except StatementRefused as e:
                failures.append(
                    {
                        "question_id": r["question_id"],
                        "db_id": r["db_id"],
                        "reason": str(e.reason),
                        "shape": shape(str(e.reason)),
                    }
                )
            except Exception as e:
                failures.append(
                    {
                        "question_id": r["question_id"],
                        "db_id": r["db_id"],
                        "reason": f"{type(e).__name__}: {e}",
                        "shape": f"OTHER:{type(e).__name__}",
                    }
                )
        summary[set_name] = {
            "total": len(rows),
            "parsed": parsed,
            "failed": len(failures),
        }
        with open(f"{OUT}/postgast_failures_{set_name}.json", "w") as f:
            json.dump(failures, f, indent=1)
        print(set_name, parsed, "/", len(rows), "failed", len(failures))

    with open(f"{OUT}/postgast_summary.json", "w") as f:
        json.dump(summary, f, indent=1)


if __name__ == "__main__":
    main()
