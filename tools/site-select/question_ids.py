"""The question ids one database holds in one BIRD question file, comma separated.

    question_ids.py <questions.json> <db_id>

What ``audits.sh`` gives ``--ids``, so that a run over one ``.sqlite`` file audits exactly the
questions that name it. Ids are printed once and in file order; a file that names an id twice is
the zip's own shape and the tool deduplicates it, so printing it twice would change nothing.

The same helper the two SQLite measurements used, copied here rather than imported across
``plans/``: those directories are the record of a measurement that has already been made, and a
script that a later run depends on is a script that cannot be left alone.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast


def main() -> None:
    questions, db_id = Path(sys.argv[1]), sys.argv[2]
    entries = cast("list[dict[str, object]]", json.loads(questions.read_text(encoding="utf-8")))
    ids = [entry["question_id"] for entry in entries if entry["db_id"] == db_id]
    print(",".join(str(found) for found in dict.fromkeys(ids)))


if __name__ == "__main__":
    main()
