"""Select, from a finished work directory, the outputs committed beside this script.

No Spider question file, gold file, prediction file or database is committed. The 28 correction
pairs remain in corrections.json as measured short SQL under CC BY-SA 4.0. Error messages in
summary copies are cut before any quoted SQL fragment.
"""

import json
import os
import re
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"]).resolve()
HERE = Path(__file__).resolve().parent
OUT = WORK / "out"
CUT_AT = re.compile(r"(\s+LINE \d+:)|(Line \d+, Col: \d+\.)|(Error tokenizing )|( near )")
QUOTED = re.compile(r"[\"']")
DOCUMENTS = (
    "inputs.json",
    "corrections.json",
    "gold-only.json",
    "recall.json",
    "classification.json",
    "corrections-replayed.json",
    "prediction-measurement.json",
    "timeout-reruns.json",
)


def cut(message: str) -> str:
    found = CUT_AT.search(message)
    if found is not None:
        message = message[: found.end()]
    quoted = QUOTED.search(message)
    if quoted is not None:
        message = message[: quoted.start()]
    return message.strip()


def sanitized(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: cut(item)
            if key in ("message", "error") and isinstance(item, str)
            else sanitized(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], str):
            return [value[0], cut(value[1])]
        return [sanitized(item) for item in value]
    return value


def write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    for name in DOCUMENTS:
        write(HERE / name, sanitized(json.loads((OUT / name).read_text(encoding="utf-8"))))
    for run in sorted(OUT.glob("tool/*/*/summary.json")):
        write(
            HERE / "tool" / run.parent.parent.name / run.parent.name / "summary.json",
            sanitized(json.loads(run.read_text(encoding="utf-8"))),
        )
    for run in sorted(OUT.glob("tool-predictions/*/*/summary.json")):
        write(
            HERE / "tool-predictions" / run.parent.parent.name / run.parent.name / "summary.json",
            sanitized(json.loads(run.read_text(encoding="utf-8"))),
        )
    print("artifact built under", HERE)


if __name__ == "__main__":
    main()
