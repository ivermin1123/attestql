"""Select, from a finished work directory, the outputs committed beside this script.

What is kept: every run's summary.json, BIRD's own scoring per file, the per-question
verdicts, the counts, the hand classification, and the counterexamples of the rows the
report discusses. What is not kept: the evidence records and counterexamples of every other
row (they hold BIRD's question text, gold and predictions), the prediction files, the golds.
Server error messages quote a fragment of the statement they rejected
the fragment (from
"LINE " on) is cut from the committed copies so that no prediction text is reproduced here.

usage: MEASURE_WORK=<work-directory> python3 build_artifact.py
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure  # noqa: E402  (beside this script, found once HERE is on the path)

OUT = WORK / "out"
EXAMPLES = [
    ("hf", "meta-llama-3-70b-instruct-2", 565),
    ("hf", "gpt-4", 1035),
    ("zip", "phi-3-medium-128k-instruct-1", 1473),
    ("hf", "gpt-35-turbo-instruct", 1057),
]


def cut(message: str) -> str:
    return re.split(r"\s+LINE \d+:", message, maxsplit=1)[0].strip()


def sanitized_summary(path: Path) -> dict:
    document = json.loads(path.read_text())
    for error in document.get("errors", []):
        error["message"] = cut(error["message"])
    return document


def write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")


for run in sorted(OUT.glob("tool/*/*/summary.json")):
    write(
        HERE / "tool" / run.parent.parent.name / run.parent.name / "summary.json",
        sanitized_summary(run),
    )
for scored in sorted(OUT.glob("official/*/*.json")):
    document = json.loads(scored.read_text())
    for row in document["rows"]:
        row["message"] = cut(row["message"])
    write(HERE / "official" / scored.parent.name / scored.name, document)


def sanitized(value: object) -> object:
    """Every message field cut, wherever it sits in the document."""
    if isinstance(value, dict):
        return {
            k: (
                cut(v)
                if k in ("message", "tool_message", "official_message") and isinstance(v, str)
                else sanitized(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        if (
            len(value) == 2 and isinstance(value[0], int) and isinstance(value[1], str)
        ):  # an error_lines pair
            return [value[0], cut(value[1])]
        return [sanitized(v) for v in value]
    return value


write(HERE / "measurement.json", sanitized(json.loads((OUT / "measurement.json").read_text())))
for name in ("classification.json", "aggregate.json"):
    write(HERE / name, json.loads((OUT / name).read_text()))
names = {}
for scored in sorted(OUT.glob("names/hf/*.json")):
    document = json.loads(scored.read_text())
    names[document["model"]] = {
        "equal": document["equal"],
        "names_differ": document["names_differ"],
        "differ_ids": [r["question_id"] for r in document["rows"] if r["differ"]],
    }
write(HERE / "names-hf.json", names)

for gold in ("zip", "hf"):
    verdicts = {}
    for model in measure.MODELS:
        qs = measure.read_run(gold, model)["questions"]
        verdicts[model] = {
            str(i): {
                "verdict": q["verdict"],
                "rule": q["rule"],
                "bird_ex": q["bird_ex"],
                **({"mechanism": q["mechanism"]["class"]} if "mechanism" in q else {}),
                **({"error": cut(q["message"])} if q["verdict"] == "ERROR" else {}),
            }
            for i, q in sorted(qs.items())
        }
    write(HERE / f"verdicts-{gold}.json", verdicts)
for gold, model, qid in EXAMPLES:
    target = HERE / "examples" / f"{gold}-{model}-q{qid}"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        OUT / "tool" / gold / model / f"q{qid}" / "counterexample.json",
        target / "counterexample.json",
    )
print("artifact built under", HERE)
