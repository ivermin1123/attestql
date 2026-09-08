"""Spider 1.0 dev as a BIRD-shaped question file, for the one database wta_1.

spider_questions.py <directory holding dev.json>

The id of a question is its position in Spider's own dev.json, which is what the lane of
2026-09-07 numbered them by (register A43), so q455 and q456 name the same two golds here.
Evidence is empty: Spider states none, and an empty hint is a hint the set did not give.
"""

import json
import sys
from pathlib import Path

directory = Path(sys.argv[1])
dev = json.loads((directory / "dev.json").read_text(encoding="utf-8"))
questions = [
    {
        "question_id": position,
        "db_id": entry["db_id"],
        "question": entry["question"],
        "evidence": "",
        "SQL": " ".join(entry["query"].split()),
        "difficulty": "simple",
    }
    for position, entry in enumerate(dev)
    if entry["db_id"] == "wta_1"
]
target = directory / "questions-wta_1.json"
target.write_text(json.dumps(questions, indent=1) + "\n", encoding="utf-8")
print(f"{target}: {len(questions)} questions")
