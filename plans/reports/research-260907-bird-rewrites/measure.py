"""Merge the 22 replay runs and write verdicts.json, one row per audited id.

    MEASURE_WORK=<work-directory> python3 measure.py

The replay rule is the old gold's own: R-ORD when the 2024 statement has a top-level ORDER BY,
R-SET otherwise. A rewrite that adds or drops ORDER BY is therefore judged under the old rule;
this is deliberate and is restated in the report. The gold-only probe comparison is asserted
against the earlier gold-only-old.json, whose shuffle used the same seed.
"""

import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
HERE = Path(__file__).resolve().parent
OUT = WORK / "out"
DATABASES = [
    "california_schools",
    "card_games",
    "codebase_community",
    "debit_card_specializing",
    "european_football_2",
    "financial",
    "formula_1",
    "student_club",
    "superhero",
    "thrombosis_prediction",
    "toxicology",
]
GROUPS = ("rewrite-399", "text-only-172")
ANSWERED = re.compile(r"^q(\d+)\s+(\S+)\s+(\S+)\s+(EQUAL|NOT_EQUAL)\s+smells=(\S+)(?:\s+\S+)?$")
FAILED = re.compile(r"^q(\d+)\s+(\S+)\s+ERROR\s+smells=(\S+)")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def duplicate_rows(result: dict) -> int:
    rendered = [json.dumps(row, sort_keys=True) for row in result["rows"]]
    return len(rendered) - len(set(rendered))


def read_group(group: str) -> tuple[dict, dict]:
    rows: dict[int, dict] = {}
    summaries = {}
    for database in DATABASES:
        run = OUT / "tool" / group / database
        summary = load(run / "summary.json")
        summaries[database] = summary
        errors = {entry["question_id"]: entry for entry in summary["errors"]}
        for line in (run / "stdout.txt").read_text(encoding="utf-8").splitlines():
            found = ANSWERED.match(line)
            if found is not None:
                question_id = int(found.group(1))
                verdict = found.group(4)
                record = (
                    load(run / f"q{question_id}" / "counterexample.json")
                    if verdict == "NOT_EQUAL"
                    else None
                )
                rows[question_id] = {
                    "db": found.group(2),
                    "rule": found.group(3),
                    "verdict": verdict,
                    "mechanism": None if record is None else record["mechanism"]["class"],
                    "multiset_equal": (
                        None if record is None else record["mechanism"]["multiset_equal"]
                    ),
                    "bird_ex": 1 if record is None else record["bird_ex"]["value"],
                    "test_suite_ex": 1 if record is None else record["test_suite_ex"]["value"],
                    "gold_duplicate_rows": (
                        None if record is None else duplicate_rows(record["gold"]["result"])
                    ),
                    "error": None,
                    "smells": [] if found.group(5) == "none" else found.group(5).split(","),
                }
                continue
            failed = FAILED.match(line)
            if failed is None:
                continue
            question_id = int(failed.group(1))
            error = errors[question_id]
            timed_out = question_id in summary["timed_out"].get(error["side"], [])
            rows[question_id] = {
                "db": failed.group(2),
                "rule": None,
                "verdict": "ERROR",
                "mechanism": None,
                "multiset_equal": None,
                "bird_ex": None,
                "test_suite_ex": None,
                "gold_duplicate_rows": None,
                "error": {
                    "side": error["side"],
                    "step": error["step"],
                    "kind": "timeout" if timed_out else error["step"],
                    "message": error["message"],
                },
                "smells": [] if failed.group(3) == "none" else failed.group(3).split(","),
            }
    return rows, summaries


def counts(rows: dict[int, dict]) -> dict:
    same = sorted(
        question_id
        for question_id, row in rows.items()
        if row["verdict"] == "EQUAL" or row["multiset_equal"] is True
    )
    return {
        "audited": len(rows),
        "same_under_old_multiset_rule": len(same),
        "same_ids": same,
        "bird_set_equal": sum(row["bird_ex"] == 1 for row in rows.values()),
        "test_suite_equal": sum(row["test_suite_ex"] == 1 for row in rows.values()),
        "by_verdict": dict(Counter(row["verdict"] for row in rows.values())),
        "by_mechanism": dict(
            Counter(row["mechanism"] for row in rows.values() if row["verdict"] == "NOT_EQUAL")
        ),
        "errors_by_side_and_kind": dict(
            Counter(
                f"{row['error']['side']}:{row['error']['kind']}"
                for row in rows.values()
                if row["error"] is not None
            )
        ),
        "probe_fires": sum(bool(row["smells"]) for row in rows.values()),
    }


def main() -> None:
    groups = {group: read_group(group) for group in GROUPS}
    rewrite, harness = groups["rewrite-399"][0], groups["text-only-172"][0]
    expected_sizes = {"rewrite-399": 399, "text-only-172": 172}
    if {name: len(rows) for name, (rows, _) in groups.items()} != expected_sizes:
        raise SystemExit(f"run size moved: {len(rewrite)}, {len(harness)}")

    expected_smells = load(HERE.parent / "bird-dev-sqlite-260907" / "gold-only-old.json")
    drift = sorted(
        int(question_id)
        for question_id, row in expected_smells.items()
        if int(question_id) in rewrite and row["smells"] != rewrite[int(question_id)]["smells"]
    )
    measured_fires = {question_id for question_id, row in rewrite.items() if row["smells"]}
    if drift:
        raise SystemExit(f"gold-only probe drift on the 399: {drift}")

    harness_verdicts = Counter(row["verdict"] for row in harness.values())
    harness_errors = {
        question_id: row["error"]
        for question_id, row in harness.items()
        if row["error"] is not None
    }
    if harness_verdicts != {"EQUAL": 171, "ERROR": 1} or set(harness_errors) != {701}:
        raise SystemExit(
            f"harness check moved: {dict(harness_verdicts)}, errors {sorted(harness_errors)}"
        )

    document = {
        "reading": (
            "The 2025-11-06 SQL replayed as a prediction against the 2024-06-27 gold on "
            "dev.zip's own data. equal_or_multiset_equal is the old rule's multiset reading; "
            "bird_ex is BIRD's set reading. Text-only-172 repeats unchanged SQL as a harness "
            "check and is not part of the rewrite counts."
        ),
        "replay_rule": "the old gold's: R-ORD when it orders, R-SET otherwise",
        "groups": {
            "rewrite-399": {
                "counts": counts(rewrite),
                "questions": {str(key): rewrite[key] for key in sorted(rewrite)},
            },
            "text-only-172": {
                "counts": counts(harness),
                "questions": {str(key): harness[key] for key in sorted(harness)},
            },
        },
        "gold_only_probe_check": {
            "expected_fires": len(measured_fires),
            "drift": [],
            "source": "bird-dev-sqlite-260907/gold-only-old.json",
        },
        "runs": {
            group: {database: summary["run_id"] for database, summary in summaries.items()}
            for group, (_, summaries) in groups.items()
        },
    }
    (HERE / "verdicts.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")

    for group, (_, summaries) in groups.items():
        for database, _summary in summaries.items():
            target = HERE / "tool" / group / database
            target.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(
                OUT / "tool" / group / database / "summary.json", target / "summary.json"
            )
    print(json.dumps({group: counts(rows) for group, (rows, _) in groups.items()}, indent=2))


if __name__ == "__main__":
    main()
