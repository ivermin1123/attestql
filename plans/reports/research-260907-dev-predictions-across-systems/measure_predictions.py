"""Merge the per-database prediction runs and compare them with BIRD's evaluator."""

import json
import os
import re
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
OUT = WORK / "out"
COPIES = ("old", "dev1106")
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
LINE = re.compile(
    r"^q(\d+)\s+(\S+)\s+(\S*)\s+(EQUAL|NOT_EQUAL|NOT_COMPARABLE|ERROR)\s+smells=(\S+)"
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def selected_files() -> list[str]:
    sources = load(Path(__file__).resolve().parent / "sources.json")
    return [row["name"] for row in sources["accepted"]]


FILES = selected_files()


def read_run(copy: str, prediction_file: str) -> dict:
    questions: dict[int, dict] = {}
    merged = {
        "audited": 0,
        "verdicts": Counter(),
        "smells": Counter(),
        "credited_total": 0,
        "by_mechanism": Counter(),
        "by_test_suite_ex": Counter(),
        "elapsed_seconds": Counter(),
        "run_ids": [],
        "errors": [],
        "timeouts": Counter(),
        "timeout_ids": [],
    }
    for db in DATABASES:
        directory = OUT / "tool-predictions" / copy / prediction_file / db
        summary = load(directory / "summary.json")
        merged["audited"] += sum(summary["verdicts"].values())
        merged["verdicts"].update(summary["verdicts"])
        merged["smells"].update(summary["smells"])
        credited = summary["credited_but_not_equal"]
        merged["credited_total"] += credited["total"]
        merged["by_mechanism"].update(credited["by_mechanism"])
        merged["by_test_suite_ex"].update(credited["by_test_suite_ex"])
        merged["elapsed_seconds"].update(summary["elapsed_seconds"])
        merged["run_ids"].append(summary["run_id"])
        merged["errors"].extend(summary["errors"])
        for side, ids in summary["timed_out"].items():
            merged["timeouts"][side] += len(ids)
            merged["timeout_ids"].extend(
                {"side": side, "question_id": question_id} for question_id in ids
            )
        for text in directory.joinpath("stdout.txt").read_text(encoding="utf-8").splitlines():
            found = LINE.match(text)
            if found is None:
                continue
            question_id, db_id, _rule, verdict, smells = found.groups()
            entry = {
                "db": db_id,
                "verdict": verdict,
                "smells": [] if smells == "none" else smells.split(","),
                "bird_ex": None,
                "test_suite_ex": None,
            }
            if verdict == "EQUAL":
                entry["bird_ex"] = 1
            elif verdict in ("NOT_EQUAL", "NOT_COMPARABLE"):
                counterexample = load(directory / f"q{question_id}" / "counterexample.json")
                entry["bird_ex"] = counterexample["bird_ex"]["value"]
                entry["test_suite_ex"] = counterexample["test_suite_ex"]["value"]
                entry["names_differ"] = "projection_names_differ" in counterexample
                entry["mechanism"] = counterexample["mechanism"]["class"]
            questions[int(question_id)] = entry
    for error in merged["errors"]:
        entry = questions.get(error["question_id"])
        if entry is not None:
            entry.update(
                {
                    "step": error["step"],
                    "side": error["side"],
                    "message": error["message"],
                    "bird_ex": 0,
                }
            )
    return {"merged": merged, "questions": questions}


def measure(copy: str, prediction_file: str) -> dict:
    run = read_run(copy, prediction_file)
    questions, merged = run["questions"], run["merged"]
    official = load(OUT / "official" / copy / f"{prediction_file}.json")
    by_id = {row["question_id"]: row for row in official["rows"]}
    compared = {
        question_id: question
        for question_id, question in questions.items()
        if question["verdict"] in ("EQUAL", "NOT_EQUAL")
    }
    errors = [
        question_id for question_id, question in questions.items() if question["verdict"] == "ERROR"
    ]
    readable = {
        question_id: question
        for question_id, question in questions.items()
        if question["verdict"] != "NOT_COMPARABLE"
    }
    agree = 0
    disagreements = []
    for question_id, question in readable.items():
        scored = by_id[question_id]
        if scored["res"] == question["bird_ex"]:
            agree += 1
        else:
            disagreements.append(
                {
                    "question_id": question_id,
                    "tool_verdict": question["verdict"],
                    "tool_step": question.get("step", ""),
                    "tool_side": question.get("side", ""),
                    "tool_bird_ex": question["bird_ex"],
                    "official": scored["res"],
                    "official_outcome": scored["outcome"],
                    "official_message": scored["message"],
                }
            )
    credited = sorted(
        question_id for question_id, question in questions.items() if question["bird_ex"] == 1
    )
    loose = sorted(
        question_id
        for question_id in compared
        if compared[question_id]["verdict"] == "NOT_EQUAL" and compared[question_id]["bird_ex"] == 1
    )
    return {
        "copy": copy,
        "file": prediction_file,
        "audited": merged["audited"],
        "verdicts": dict(merged["verdicts"]),
        "smells": dict(merged["smells"]),
        "compared": len(compared),
        "tool_ex1": sum(question["bird_ex"] == 1 for question in questions.values()),
        "tool_ex0": sum(question["bird_ex"] == 0 for question in questions.values()),
        "errors": len(errors),
        "error_steps": dict(Counter(questions[i].get("step", "") for i in errors)),
        "error_sides": dict(Counter(questions[i].get("side", "") for i in errors)),
        "timeouts_by_side": dict(merged["timeouts"]),
        "timeout_ids": merged["timeout_ids"],
        "official_ex_sum": official["ex_sum"],
        "official_ex_percent": official["ex_percent"],
        "official_errors": official["errors"],
        "official_timeouts": official["timeouts"],
        "crosscheck": {
            "readable": len(readable),
            "agree": agree,
            "disagree": len(disagreements),
            "rows": disagreements,
        },
        "credited_ids": credited,
        "ex1_not_equal": len(loose),
        "ex1_not_equal_share": round(len(loose) / len(credited), 4) if credited else 0.0,
        "ex1_not_equal_by_mechanism": dict(merged["by_mechanism"]),
        "ex1_not_equal_by_test_suite_ex": dict(merged["by_test_suite_ex"]),
        "ex1_not_equal_ids": loose,
        "credited_total_from_summaries": merged["credited_total"],
        "not_equal_names_differ": sum(
            question.get("names_differ", False) for question in compared.values()
        ),
        "elapsed": dict(merged["elapsed_seconds"]),
        "run_ids": merged["run_ids"],
        "questions": questions,
    }


def baseline_a37() -> dict:
    prior = load(
        Path(__file__).resolve().parent.parent
        / "bird-dev-sqlite-260907"
        / "prediction-measurement.json"
    )
    rows = [
        row
        for row in prior["files"].values()
        if row["copy"] == "old" and row["file"] in {"turbo_output", "turbo_output_kg"}
    ]
    credited = sum(row["tool_ex1"] for row in rows)
    loose = sum(row["ex1_not_equal"] for row in rows)
    return {
        "files": len(rows),
        "credited": credited,
        "credited_but_not_equal": loose,
        "share": round(loose / credited, 4),
    }


def main() -> None:
    rows = {
        f"{copy}/{prediction_file}": measure(copy, prediction_file)
        for copy in COPIES
        for prediction_file in FILES
    }
    old = [row for row in rows.values() if row["copy"] == "old"]
    pooled_credited = sum(row["tool_ex1"] for row in old)
    pooled_loose = sum(row["ex1_not_equal"] for row in old)
    document = {
        "reading": (
            "Prediction mode over every licensed full-dev prediction file found, against both "
            "copies of the gold, on SQLite. Crosscheck is the tool's BIRD EX reading against "
            "BIRD's own unmodified evaluator. The questions field carries every per-question "
            "reading used by the sample and moved-credits scripts."
        ),
        "files": rows,
        "baseline_a37": baseline_a37(),
        "execution": {
            "loaded_run_stall": {
                "stopped_at": "2026-09-07 22:22 +07",
                "resumed_at": "2026-09-08 09:27 +07",
                "cause": "background jobs were suspended in the first PTY launch",
                "safety": (
                    "a run either finished with a summary before the stall or had every "
                    "timeout rerun alone afterward"
                ),
            }
        },
        "pooled_old": {
            "files": len(old),
            "credited": pooled_credited,
            "credited_but_not_equal": pooled_loose,
            "share": round(pooled_loose / pooled_credited, 4),
            "by_mechanism": dict(
                sum(
                    (Counter(row["ex1_not_equal_by_mechanism"]) for row in old),
                    Counter(),
                )
            ),
        },
    }
    OUT.joinpath("prediction-measurement.json").write_text(
        json.dumps(document, indent=1) + "\n", encoding="utf-8"
    )
    for name, row in rows.items():
        print(
            f"{name}: compared {row['compared']}, EX=1 {row['tool_ex1']}, "
            f"errors {row['errors']}, BIRD {row['official_ex_sum']}, agree "
            f"{row['crosscheck']['agree']}/{row['crosscheck']['readable']}, "
            f"credited NOT_EQUAL {row['ex1_not_equal']}"
        )
    print(f"pooled old: {pooled_loose}/{pooled_credited} = {document['pooled_old']['share']:.1%}")


if __name__ == "__main__":
    main()
