"""The question ids one database holds in a question file, comma separated.

question_ids.py <questions.json> <db_id>
"""

import json
import sys
from pathlib import Path

entries = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
ids = [entry["question_id"] for entry in entries if entry["db_id"] == sys.argv[2]]
print(",".join(str(found) for found in dict.fromkeys(ids)))
