"""The question ids one database holds in one Mini-Dev question file, comma separated.

    question_ids.py <questions.json> <db_id>

What ``run_tool.sh`` gives ``--ids``, so that a run over one ``.sqlite`` file audits exactly the
questions that name it. Ids are printed once and in file order; a file that names an id twice is
the zip's own shape and the tool deduplicates it, so printing it twice would change nothing.
"""

import json
import sys
from pathlib import Path


def main() -> None:
    questions, db_id = Path(sys.argv[1]), sys.argv[2]
    entries = json.load(questions.open())
    ids = [entry["question_id"] for entry in entries if entry["db_id"] == db_id]
    print(",".join(str(found) for found in dict.fromkeys(ids)))


if __name__ == "__main__":
    main()
