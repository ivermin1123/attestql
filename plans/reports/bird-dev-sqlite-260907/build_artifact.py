"""Select, from a finished work directory, the outputs committed beside this script.

What is kept: every run's summary.json, BIRD's own scoring per file, the counts, the recall
split, the overlap with the published errata, the hand classification, the input checks, and the
per-question probe lines. What is not kept: the evidence records, the smells' own evidence and
every counterexample (they hold BIRD's question text, gold, predictions and rows), the
prediction files, the question files, the databases. An error message quotes a fragment of the
statement it rejected; the fragment is cut from the committed copies so that no BIRD statement
text is reproduced here, which is why this directory adds no entry to NOTICE.

usage: MEASURE_WORK=<work-directory> python3 build_artifact.py
"""

import json
import os
import re
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
HERE = Path(__file__).resolve().parent
OUT = WORK / "out"

CUT_AT = re.compile(r"(\s+LINE \d+:)|(Line \d+, Col: \d+\.)|(Error tokenizing )")
"""Where a message stops quoting itself and starts quoting the statement it rejected.

sqlglot writes ``Line n, Col: m.`` and then the fragment of the prediction it could not read,
which on these files often runs on into the model's prose. The PostgreSQL spelling is kept for
the same reason the sibling script keeps it: one rule, both engines.
"""

QUOTED = re.compile(r"[\"']")
"""The other way a message quotes the statement it rejected: sqlite3 writes ``near "X":`` and
``unrecognized token: "X"``, and a prediction that opens with a Markdown fence makes the whole
block one token. Everything from the first quote on is dropped."""


def cut(message: str) -> str:
    found = CUT_AT.search(message)
    if found is not None:
        message = message[: found.end()]
    quoted = QUOTED.search(message)
    if quoted is not None:
        message = message[: quoted.start()]
    return message.strip()


def sanitized(value: object) -> object:
    """Every message field cut, wherever it sits in the document."""
    if isinstance(value, dict):
        return {
            key: (
                cut(item)
                if key in ("message", "tool_message", "official_message", "error", "sqlite_error")
                and isinstance(item, str)
                else sanitized(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], str):
            return [value[0], cut(value[1])]  # an error_lines pair
        return [sanitized(item) for item in value]
    return value


def write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")


for run in sorted(OUT.glob("tool/*/*/summary.json")):
    db, copy = run.parent.name, run.parent.parent.name
    write(HERE / "tool" / copy / db / "summary.json", sanitized(json.loads(run.read_text())))
for run in sorted(OUT.glob("tool-predictions/*/*/*/summary.json")):
    db, file, copy = run.parent.name, run.parent.parent.name, run.parent.parent.parent.name
    write(
        HERE / "tool-predictions" / copy / file / db / "summary.json",
        sanitized(json.loads(run.read_text())),
    )
for scored in sorted(OUT.glob("official/*/*.json")):
    write(
        HERE / "official" / scored.parent.name / scored.name,
        sanitized(json.loads(scored.read_text())),
    )
for name in (
    "inputs.json",
    "measurement.json",
    "classification.json",
    "prediction-measurement.json",
    "predictions-turbo_output-changed.json",
    "predictions-turbo_output_kg-changed.json",
):
    write(HERE / name, sanitized(json.loads((OUT / name).read_text())))
# The per-question probe line of each copy, on its own, because that is what a reader checking a
# single question wants and measurement.json is large.
measurement = json.loads((OUT / "measurement.json").read_text())
for copy in ("old", "dev1106"):
    write(HERE / f"gold-only-{copy}.json", measurement["copies"][copy]["questions"])
print("artifact built under", HERE)
