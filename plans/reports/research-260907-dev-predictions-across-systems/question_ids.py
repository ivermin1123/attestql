"""The question ids one database holds in one question file, comma separated."""

import json
import sys
from pathlib import Path


def main() -> None:
    questions, db_id = Path(sys.argv[1]), sys.argv[2]
    entries = json.loads(questions.read_text(encoding="utf-8"))
    ids = [entry["question_id"] for entry in entries if entry["db_id"] == db_id]
    print(",".join(str(found) for found in dict.fromkeys(ids)))


if __name__ == "__main__":
    main()
