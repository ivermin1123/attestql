"""Run the tool's own parser (postgast, via attestql.audit.statements.parse_statement)
over the same three gold sets. Run with the worktree's uv env:

  cd /Users/hoangle/Desktop/code/attestql-research
  UV_PROJECT_ENVIRONMENT=/tmp/attestql-research-venv uv run python \
      /private/tmp/.../scripts/postgast_parse.py
"""

import json
import re
import sys

sys.path.insert(
    0,
    "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rd/scripts",
)
from load_golds import SETS, load

from attestql.audit.statements import StatementRefused, parse_statement

OUT = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rd"


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
