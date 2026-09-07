"""Read the prediction-mode runs over BIRD's own two dev prediction files, and BIRD's scoring.

Inputs, under the work directory:
  out/tool-predictions/<copy>/<file>/<db_id>/{stdout.txt,summary.json,q<id>/counterexample.json}
  out/official/<copy>/<file>.json      (bird_ex_official.py)
Output:
  out/prediction-measurement.json

The merge rule is run_tool.sh's: the eleven summaries' counts are summed, the per-question lines
concatenated, the eleven run ids listed; no id appears in two of the eleven. The mechanism of a
NOT_EQUAL is not recomputed here: the tool records it in the counterexample beside ``bird_ex``
and ``test_suite_ex``, and a measurement that recomputed it would be measuring this script.
"""

import json
import os
import re
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
OUT = WORK / "out"
COPIES = ("old", "dev1106")
FILES = ("turbo_output", "turbo_output_kg")
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


def read_run(copy: str, file: str) -> dict:
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
    }
    for db in DATABASES:
        directory = OUT / "tool-predictions" / copy / file / db
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
        for text in directory.joinpath("stdout.txt").read_text().splitlines():
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
                entry["mechanism"] = counterexample["mechanism"]
            questions[int(question_id)] = entry
    for error in merged["errors"]:
        entry = questions.get(error["question_id"])
        if entry is not None:
            entry["step"] = error["step"]
            entry["side"] = error["side"]
            entry["message"] = error["message"]
            entry["bird_ex"] = 0  # BIRD scores any exception 0
    return {"merged": merged, "questions": questions}


def measure(copy: str, file: str) -> dict:
    run = read_run(copy, file)
    questions, merged = run["questions"], run["merged"]
    official = load(OUT / "official" / copy / f"{file}.json")
    by_id: dict[int, dict] = {}
    for row in official["rows"]:
        by_id.setdefault(row["question_id"], row)
    compared = {i: q for i, q in questions.items() if q["verdict"] in ("EQUAL", "NOT_EQUAL")}
    errors = [i for i, q in questions.items() if q["verdict"] == "ERROR"]
    agree, disagreements = 0, []
    readable = {i: q for i, q in questions.items() if q["verdict"] != "NOT_COMPARABLE"}
    for question_id, question in readable.items():
        scored = by_id.get(question_id)
        if scored is None:
            continue
        if scored["res"] == question["bird_ex"]:
            agree += 1
        else:
            disagreements.append(
                {
                    "question_id": question_id,
                    "db": question["db"],
                    "tool_verdict": question["verdict"],
                    "tool_step": question.get("step", ""),
                    "tool_side": question.get("side", ""),
                    "tool_message": question.get("message", "")[:200],
                    "tool_bird_ex": question["bird_ex"],
                    "official": scored["res"],
                    "official_outcome": scored["outcome"],
                    "official_message": scored["message"],
                }
            )
    loose = sorted(
        i for i, q in compared.items() if q["verdict"] == "NOT_EQUAL" and q["bird_ex"] == 1
    )
    return {
        "copy": copy,
        "file": file,
        "audited": merged["audited"],
        "verdicts": dict(merged["verdicts"]),
        "smells": dict(merged["smells"]),
        "compared": len(compared),
        "tool_ex1": sum(1 for q in compared.values() if q["bird_ex"] == 1),
        "tool_ex0": sum(1 for q in compared.values() if q["bird_ex"] == 0),
        "errors": len(errors),
        "error_steps": dict(Counter(questions[i].get("step", "") for i in errors)),
        "error_sides": dict(Counter(questions[i].get("side", "") for i in errors)),
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
        "ex1_not_equal": len(loose),
        "ex1_not_equal_by_mechanism": dict(merged["by_mechanism"]),
        "ex1_not_equal_by_test_suite_ex": dict(merged["by_test_suite_ex"]),
        "ex1_not_equal_ids": loose,
        "credited_total_from_summaries": merged["credited_total"],
        "not_equal_names_differ": sum(
            1 for q in compared.values() if q["verdict"] == "NOT_EQUAL" and q.get("names_differ")
        ),
        "elapsed": dict(merged["elapsed_seconds"]),
        "run_ids": merged["run_ids"],
    }


def main() -> None:
    rows = {f"{copy}/{file}": measure(copy, file) for copy in COPIES for file in FILES}
    document = {
        "reading": (
            "Prediction mode over BIRD's own two dev prediction files "
            "(AlibabaResearch/DAMO-ConvAI, bird/llm/exp_result/{turbo_output,turbo_output_kg}/"
            "predict_dev.json, MIT), against both copies of the question set, on SQLite. One row "
            "per (copy, file); crosscheck is the tool's reading of BIRD's EX against BIRD's own "
            "evaluator run here unmodified."
        ),
        "files": rows,
    }
    OUT.joinpath("prediction-measurement.json").write_text(json.dumps(document, indent=1) + "\n")
    for name, row in rows.items():
        print(
            f"{name}: compared {row['compared']}, EX=1 {row['tool_ex1']}, errors {row['errors']}, "
            f"BIRD {row['official_ex_sum']}, agree {row['crosscheck']['agree']}/"
            f"{row['crosscheck']['readable']}, loose {row['ex1_not_equal']}"
        )


if __name__ == "__main__":
    main()
