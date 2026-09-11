"""Merge the ten gold-only runs and name the fires that depend on the copy."""

import json
import os
import re
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
DATABASES = [
    "california_schools",
    "european_football_2",
    "formula_1",
    "thrombosis_prediction",
    "toxicology",
]
LINE = re.compile(
    r"^q(\d+)\s+(\S+)\s+(\S*)\s+(EQUAL|NOT_EQUAL|NOT_COMPARABLE|ERROR|GOLD-ONLY)\s+smells=(\S+)"
)


def read_copy(copy: str) -> dict:
    questions = {}
    summaries = {}
    timeouts = []
    for db in DATABASES:
        directory = WORK / "out" / "tool" / copy / db
        summary = json.loads((directory / "summary.json").read_text())
        summaries[db] = {
            "audited": summary["question_set"]["audited"],
            "smells": summary["smells"],
            "fixture_digest": summary["fixture"]["source"]["digest"],
            "run_id": summary["run_id"],
        }
        for line in (directory / "stdout.txt").read_text().splitlines():
            if re.search(r"timeout|timed out", line, re.IGNORECASE):
                timeouts.append({"db": db, "line": line})
            found = LINE.match(line)
            if not found:
                continue
            question_id, _db, rule, verdict, smells = found.groups()
            questions[int(question_id)] = {
                "db": db,
                "rule": rule,
                "verdict": verdict,
                "smells": [] if smells == "none" else smells.split(","),
            }
    return {
        "databases": summaries,
        "questions": questions,
        "by_probe": dict(
            sorted(Counter(smell for row in questions.values() for smell in row["smells"]).items())
        ),
        "questions_with_a_smell": sorted(
            question_id for question_id, row in questions.items() if row["smells"]
        ),
        "timeout_lines": timeouts,
    }


def main() -> None:
    copies = {copy: read_copy(copy) for copy in ("dev", "minidev")}
    different = []
    for question_id in sorted(
        set(copies["dev"]["questions"]) | set(copies["minidev"]["questions"])
    ):
        dev = copies["dev"]["questions"].get(question_id, {})
        minidev = copies["minidev"]["questions"].get(question_id, {})
        if dev.get("smells", []) != minidev.get("smells", []):
            different.append(
                {
                    "question_id": question_id,
                    "db": dev.get("db", minidev.get("db")),
                    "dev": dev.get("smells"),
                    "minidev": minidev.get("smells"),
                }
            )

    previous_path = Path(__file__).parent.parent / "bird-dev-sqlite-260907" / "gold-only-old.json"
    previous = json.loads(previous_path.read_text())
    crosscheck = []
    for question_id, row in copies["dev"]["questions"].items():
        expected = previous.get(str(question_id), {}).get("smells")
        if row["smells"] != expected:
            crosscheck.append(
                {
                    "question_id": question_id,
                    "current": row["smells"],
                    "at_6a43c01": expected,
                }
            )
    if crosscheck:
        raise SystemExit(f"the current dev runs differ from tree 6a43c01: {crosscheck}")
    document = {
        "copies": copies,
        "fired_on_one_copy_only": different,
        "crosscheck_against_6a43c01": {
            "source": "plans/reports/bird-dev-sqlite-260907/gold-only-old.json",
            "differences": crosscheck,
        },
    }
    target = WORK / "out" / "smells-by-copy.json"
    target.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(
        f"smells: dev {len(copies['dev']['questions_with_a_smell'])}, "
        f"minidev {len(copies['minidev']['questions_with_a_smell'])}, "
        f"one-copy-only {len(different)}, crosscheck differences {len(crosscheck)}"
    )


if __name__ == "__main__":
    main()
