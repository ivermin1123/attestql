"""Select, from a finished work directory, the outputs committed beside this script.

What is kept: every run's summary.json, BIRD's own scoring per file, the per-question
verdicts and gold-only probes, the counts, the hand classification, and the counterexamples of
the rows the report discusses. What is not kept: the evidence records and counterexamples of
every other row (they hold BIRD's question text, gold and predictions), the prediction files,
the golds, the databases. An error message quotes a fragment of the statement it rejected; the
fragment (from "LINE " on) is cut from the committed copies so that no prediction text is
reproduced here.

usage: MEASURE_WORK=<work-directory> python3 build_artifact.py
"""

import json
import os
import re
import shutil
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
HERE = Path(__file__).resolve().parent
OUT = WORK / "out"
EXAMPLES: list[tuple[str, str, int]] = [
    ("hf", "gpt-4", 846),  # the only NOT_EQUAL by row order in the run
    ("hf", "gpt-35-turbo-instruct", 45),  # the storage-class rule: INTEGER 507 against REAL 507.0
    ("hf", "gpt-4", 1035),  # a wrong answer the benchmark credits: 161 distinct ids, 356 rows
]


CUT_AT = re.compile(r"(\s+LINE \d+:)|(Line \d+, Col: \d+\.)|(Error tokenizing )")
"""Where a message stops quoting itself and starts quoting the statement it rejected.

Two spellings, one per parser. PostgreSQL's ``LINE n:`` is followed by the fragment its
server echoed; sqlglot's ``Line n, Col: m.`` is followed by the fragment of the prediction
it could not read, which on these files often runs on into the model's prose. Neither
fragment may be committed here: it is BIRD's prediction text.
"""


QUOTED = re.compile(r"[\"']")
"""The other way a message quotes the statement it rejected: sqlite3 writes ``near "X":`` and
``unrecognized token: "X"``, and a prediction that opens with a Markdown fence makes the whole
block one token. Everything from the first double quote on is dropped for the same reason the
fragments above are."""


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
            k: (
                cut(v)
                if k
                in (
                    "message",
                    "tool_message",
                    "official_message",
                    "error",
                    "sqlite_error",
                    "postgresql_error",
                )
                and isinstance(v, str)
                else sanitized(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], str):
            return [value[0], cut(value[1])]  # an error_lines pair
        return [sanitized(v) for v in value]
    return value


def write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")


for run in sorted(OUT.glob("tool/*/*/*/summary.json")):
    db, model, gold = run.parent.name, run.parent.parent.name, run.parent.parent.parent.name
    write(
        HERE / "tool" / gold / model / db / "summary.json", sanitized(json.loads(run.read_text()))
    )
for scored in sorted(OUT.glob("official/*/*.json")):
    write(
        HERE / "official" / scored.parent.name / scored.name,
        sanitized(json.loads(scored.read_text())),
    )
for name in (
    "measurement.json",
    "classification.json",
    "aggregate.json",
    "verdicts-zip.json",
    "verdicts-hf.json",
    "gold-only-zip.json",
    "gold-only-hf.json",
):
    write(HERE / name, sanitized(json.loads((OUT / name).read_text())))
for gold, model, qid in EXAMPLES:
    target = HERE / "examples" / f"{gold}-{model}-q{qid}"
    target.mkdir(parents=True, exist_ok=True)
    source = OUT / "tool" / gold / model
    found = next(source.glob(f"*/q{qid}/counterexample.json"))
    shutil.copy(found, target / "counterexample.json")
print("artifact built under", HERE)
