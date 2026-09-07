"""Merge the CodeS prediction runs and count verdicts, mechanisms and result readings.

usage: MEASURE_WORK=<work-directory> python3 measure_predictions.py
"""

import json
import os
import re
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"]).resolve()
OUT = WORK / "out"
PASSES = ("current", "transformed")
LINE = re.compile(
    r"^q(\d+)\s+(\S+)\s+(\S*)\s+(EQUAL|NOT_EQUAL|NOT_COMPARABLE|ERROR)\s+smells=(\S+)"
)
PROBES = (
    "ordering-over-numeric-text",
    "arbitrary-cut",
    "not-a-function-of-the-data",
    "float-aggregate-order",
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def error_reason(message: str) -> str:
    if message.startswith("execute: Could not decode to UTF-8"):
        return "sqlite-text-is-not-utf-8"
    if "no such column" in message:
        return "no-such-column"
    if "ambiguous column name" in message:
        return "ambiguous-column-name"
    return "other"


def read_pass(name: str, databases: list[str]) -> dict:
    questions: dict[int, dict] = {}
    verdicts: Counter = Counter()
    smells: Counter = Counter()
    mechanisms: Counter = Counter()
    credited: Counter = Counter()
    test_suite: Counter = Counter()
    errors: list[dict] = []
    run_ids: list[str] = []
    for db in databases:
        directory = OUT / "tool-predictions" / name / db
        if not directory.joinpath("summary.json").is_file():
            continue
        summary = load(directory / "summary.json")
        verdicts.update(summary["verdicts"])
        smells.update(summary["smells"])
        credited.update(summary["credited_but_not_equal"]["by_mechanism"])
        run_ids.append(summary["run_id"])
        errors.extend(
            {
                "question_id": row["question_id"],
                "db": db,
                "side": row["side"],
                "step": row["step"],
                "reason": error_reason(row["message"]),
            }
            for row in summary["errors"]
        )
        for text in directory.joinpath("stdout.txt").read_text(encoding="utf-8").splitlines():
            found = LINE.match(text)
            if found is None:
                continue
            question_id, db_id, rule, verdict, fired = found.groups()
            row = {
                "db": db_id,
                "verdict": verdict,
                "rule": rule,
                "probes": [] if fired == "none" else fired.split(","),
                "bird_ex": None,
                "test_suite_ex": None,
                "mechanism": None,
            }
            if verdict == "EQUAL":
                row["bird_ex"] = 1
                row["test_suite_ex"] = 1
            elif verdict == "NOT_EQUAL":
                counterexample = load(directory / f"q{question_id}" / "counterexample.json")
                row["bird_ex"] = counterexample["bird_ex"]["value"]
                row["test_suite_ex"] = counterexample["test_suite_ex"]["value"]
                row["mechanism"] = counterexample["mechanism"]["class"]
                mechanisms[row["mechanism"]] += 1
            questions[int(question_id)] = row
    compared = {
        question_id: row
        for question_id, row in questions.items()
        if row["verdict"] in ("EQUAL", "NOT_EQUAL")
    }
    for row in compared.values():
        credited[row["bird_ex"], row["verdict"]] += 1
        test_suite[row["test_suite_ex"]] += 1
    return {
        "selected": sum(1 for _ in questions),
        "audited": sum(verdicts.values()),
        "verdicts": dict(sorted(verdicts.items())),
        "compared": len(compared),
        "smells": {probe: smells[probe] for probe in PROBES},
        "questions_with_a_smell": sum(bool(row["probes"]) for row in questions.values()),
        "not_equal_by_mechanism": dict(sorted(mechanisms.items())),
        "errors": errors,
        "errors_by_side": dict(sorted(Counter(row["side"] for row in errors).items())),
        "errors_by_step": dict(sorted(Counter(row["step"] for row in errors).items())),
        "errors_by_reason": dict(sorted(Counter(row["reason"] for row in errors).items())),
        "bird_ex_on_compared": dict(
            sorted(Counter(row["bird_ex"] for row in compared.values()).items())
        ),
        "test_suite_ex_on_compared": dict(sorted(test_suite.items())),
        "bird_ex1_and_not_equal": credited[1, "NOT_EQUAL"],
        "run_ids": run_ids,
        "questions": questions,
    }


def main() -> None:
    inputs = load(OUT / "inputs.json")
    databases = sorted(inputs["dev_databases"])
    passes = {name: read_pass(name, databases) for name in PASSES}
    ambiguous = inputs["double_quoted_literals"]["ids"]
    delta = []
    for question_id in ambiguous:
        current = passes["current"]["questions"][question_id]
        transformed = passes["transformed"]["questions"][question_id]
        delta.append(
            {
                "question_id": question_id,
                "verdict_changed": current["verdict"] != transformed["verdict"],
                "rule_changed": current["rule"] != transformed["rule"],
                "bird_ex_changed": current["bird_ex"] != transformed["bird_ex"],
                "test_suite_ex_changed": current["test_suite_ex"] != transformed["test_suite_ex"],
            }
        )
    document = {
        "prediction": inputs["prediction"],
        "passes": passes,
        "current_to_transformed_on_the_213_ambiguous_literals": {
            "golds": len(delta),
            "verdicts_changed": sum(row["verdict_changed"] for row in delta),
            "replay_rules_changed": sum(row["rule_changed"] for row in delta),
            "bird_ex_changed": sum(row["bird_ex_changed"] for row in delta),
            "test_suite_ex_changed": sum(row["test_suite_ex_changed"] for row in delta),
        },
    }
    write_path = OUT / "prediction-measurement.json"
    write_path.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    for name, row in passes.items():
        print(
            f"{name}: compared {row['compared']}, EQUAL {row['verdicts'].get('EQUAL', 0)}, "
            f"NOT_EQUAL {row['verdicts'].get('NOT_EQUAL', 0)}, errors {len(row['errors'])}, "
            f"bird_ex1 {row['bird_ex_on_compared'].get('1', 0)}"
        )


if __name__ == "__main__":
    main()
