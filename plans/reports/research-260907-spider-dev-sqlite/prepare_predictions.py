"""Verify and convert the CodeS Spider dev prediction file.

usage: MEASURE_WORK=<work-directory> python3 prepare_predictions.py

CodeS ships one SQL per line in dev order. Spider question ids here are the zero-based dev
positions, so the converted map keyed by those ids needs no positional reading; the same file
serves the full current pass and the 213-question transformed pass.
"""

import hashlib
import json
import os
import re
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"]).resolve()
OUT = WORK / "out"
SOURCE = WORK / "data" / "predict_sources" / "pred_sqls-codes-1b-spider.txt"
SHA256 = "913576f655c6ca9a00762c83acf05234006fae164826e9577cbd1373d07274d2"
COMMIT = "e203386173eecf6fbe8b14cf233611a2fb7c994e"
URL = f"https://github.com/RUCKBReasoning/codes/blob/{COMMIT}/results/pred_sqls-codes-1b-spider.txt"


def normalise(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip().rstrip(";")).casefold().replace('"', "'")


def main() -> None:
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != SHA256:
        raise SystemExit(f"prediction digest mismatch: {digest}")
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1034 or any(not line.strip() for line in lines):
        raise SystemExit(f"expected 1,034 non-empty prediction lines, got {len(lines)}")
    questions = json.loads((WORK / "data" / "questions-current.json").read_text())
    matched = sum(
        normalise(row["SQL"]) == normalise(lines[index]) for index, row in enumerate(questions)
    )
    converted = {str(index): sql for index, sql in enumerate(lines)}
    (WORK / "data" / "predictions-codes.json").write_text(
        json.dumps(converted, indent=1) + "\n", encoding="utf-8"
    )
    inputs_path = OUT / "inputs.json"
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    inputs["prediction"] = {
        "model": "CodeS-1B",
        "repository": "https://github.com/RUCKBReasoning/codes",
        "licence": "Apache-2.0",
        "commit": COMMIT,
        "commit_date": "2024-08-21T02:48:14Z",
        "url": URL,
        "path": "results/pred_sqls-codes-1b-spider.txt",
        "sha256": SHA256,
        "lines": len(lines),
        "normalised_gold_matches": matched,
        "keying": "question_id, whose value is the zero-based dev position",
    }
    inputs_path.write_text(json.dumps(inputs, indent=1) + "\n", encoding="utf-8")
    print(f"prepared 1,034 predictions; {matched} normalise to their gold")


if __name__ == "__main__":
    main()
