"""Read the tool's runs and BIRD's own scoring, and count what the report states.

Inputs, under the work directory:
  out/tool/<gold>/<model>/<db_id>/{stdout.txt,summary.json,q<id>/counterexample.json}
  out/official/<gold>/<model>.json      (bird_ex_official.py)
Outputs:
  out/measurement.json                  every count, every listed row
  out/manual-rows.md                    the EX=1 & NOT_EQUAL rows, for classification by hand

A Mini-Dev question file names eleven databases and ``--dsn`` takes one SQLite file, so one
(gold copy, prediction file) is eleven runs. The merge rule, stated once here and once in the
report: the counts of the eleven summaries are summed (questions audited, verdicts, smells,
errors, the credited-but-not-equal total and both of its breakdowns, elapsed seconds), the
per-question lines are concatenated, and the eleven run ids are listed. Nothing is averaged
and nothing is deduplicated: no question id appears in two of the eleven, because a question
names one database.

Unlike the PostgreSQL sibling of this script, the mechanism of a NOT_EQUAL is not recomputed
here: the tool records it in the counterexample, beside ``bird_ex`` and ``test_suite_ex``, and
a measurement that recomputed it would be measuring this script rather than the tool.
"""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])  # the work directory reproduce.sh fills
OUT = WORK / "out"
MODELS = [
    "gpt-35-turbo-instruct",
    "gpt-35-turbo",
    "gpt-4-32k",
    "gpt-4-turbo",
    "gpt-4",
    "meta-llama-3-70b-instruct-2",
    "meta-llama-3-8b-instruct-2",
    "mistralai-mixtral-8x7b-instru-4",
    "phi-3-medium-128k-instruct-1",
]
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
    r"^q(\d+)\s+(\S+)\s+(\S*)\s+(EQUAL|NOT_EQUAL|NOT_COMPARABLE|ERROR|GOLD-ONLY)\s+smells=(\S+)"
)
TIMEOUT = re.compile(r"timeout|timed out", re.IGNORECASE)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_run(gold: str, model: str, databases: list[str] | None = None) -> dict:
    """The eleven runs of one (gold copy, prediction file), merged into one."""
    questions: dict[int, dict] = {}
    merged = {
        "audited": 0,
        "entries": 0,
        "verdicts": Counter(),
        "smells": Counter(),
        "credited_total": 0,
        "by_mechanism": Counter(),
        "by_test_suite_ex": Counter(),
        "elapsed_seconds": Counter(),
        "run_ids": [],
        "errors": [],
        "timeout_lines": [],
    }
    for db in databases or DATABASES:
        directory = OUT / "tool" / gold / model / db
        summary = load(directory / "summary.json")
        merged["audited"] += summary["question_set"]["audited"]
        merged["entries"] = summary["question_set"]["entries"]
        merged["verdicts"].update(summary["verdicts"])
        merged["smells"].update(summary["smells"])
        credited = summary["credited_but_not_equal"]
        if credited is not None:
            merged["credited_total"] += credited["total"]
            merged["by_mechanism"].update(credited["by_mechanism"])
            merged["by_test_suite_ex"].update(credited["by_test_suite_ex"])
        merged["elapsed_seconds"].update(summary["elapsed_seconds"])
        merged["run_ids"].append(summary["run_id"])
        merged["errors"].extend(summary["errors"])
        merged["predictions"] = summary["predictions"]
        merged["question_set_digest"] = summary["question_set"]["digest"]
        text = (directory / "stdout.txt").read_text(encoding="utf-8")
        merged["timeout_lines"].extend(line for line in text.splitlines() if TIMEOUT.search(line))
        for line in text.splitlines():
            found = LINE.match(line)
            if not found:
                continue
            qid, db_id, rule, verdict, smells = found.groups()
            entry = {
                "db": db_id,
                "rule": rule,
                "verdict": verdict,
                "smells": [] if smells == "none" else smells.split(","),
                "bird_ex": None,
                "test_suite_ex": None,
                "directory": str(directory / f"q{qid}"),
            }
            if verdict == "EQUAL":
                entry["bird_ex"] = 1
                entry["test_suite_ex"] = None
            elif verdict in ("NOT_EQUAL", "NOT_COMPARABLE"):
                ce = load(directory / f"q{qid}" / "counterexample.json")
                entry["bird_ex"] = ce["bird_ex"]["value"]
                entry["test_suite_ex"] = ce["test_suite_ex"]["value"]
                entry["names_differ"] = "projection_names_differ" in ce
                entry["mechanism"] = ce["mechanism"]
            questions[int(qid)] = entry
    for error in merged["errors"]:
        entry = questions.get(error["question_id"])
        if entry is not None:
            entry["step"] = error["step"]
            entry["side"] = error["side"]
            entry["message"] = error["message"]
            entry["bird_ex"] = 0  # BIRD scores any exception 0
    return {"merged": merged, "questions": questions}


def read_official(gold: str, model: str) -> dict:
    document = load(OUT / "official" / gold / f"{model}.json")
    by_id: dict[int, dict] = {}
    for row in document["rows"]:
        by_id.setdefault(row["question_id"], row)  # the first position wins, as the tool does
    return {"document": document, "by_id": by_id}


def measure(gold: str, model: str) -> dict:
    run = read_run(gold, model)
    official = read_official(gold, model)
    qs = run["questions"]
    merged = run["merged"]
    compared = {i: q for i, q in qs.items() if q["verdict"] in ("EQUAL", "NOT_EQUAL")}
    tool_ex1 = sum(1 for q in compared.values() if q["bird_ex"] == 1)
    tool_ex0 = sum(1 for q in compared.values() if q["bird_ex"] == 0)
    errors = [(i, q.get("message", "")) for i, q in qs.items() if q["verdict"] == "ERROR"]
    agree = disagree = 0
    disagreements = []
    readable = {i: q for i, q in qs.items() if q["verdict"] in ("EQUAL", "NOT_EQUAL", "ERROR")}
    for i, q in readable.items():
        off = official["by_id"].get(i)
        if off is None:
            continue
        if off["res"] == q["bird_ex"]:
            agree += 1
        else:
            disagree += 1
            disagreements.append(
                {
                    "question_id": i,
                    "db": q["db"],
                    "tool_verdict": q["verdict"],
                    "tool_step": q.get("step", ""),
                    "tool_side": q.get("side", ""),
                    "tool_message": q.get("message", "")[:200],
                    "tool_bird_ex": q["bird_ex"],
                    "official": off["res"],
                    "official_outcome": off["outcome"],
                    "official_message": off["message"],
                }
            )
    loose = {i: q for i, q in compared.items() if q["verdict"] == "NOT_EQUAL" and q["bird_ex"] == 1}
    return {
        "gold": gold,
        "model": model,
        "audited": merged["audited"],
        "entries": merged["entries"],
        "verdicts": dict(merged["verdicts"]),
        "smells": dict(merged["smells"]),
        "compared": len(compared),
        "tool_ex1": tool_ex1,
        "tool_ex0": tool_ex0,
        "errors": len(errors),
        "error_lines": errors,
        "error_steps": dict(Counter(qs[i].get("step", "") for i, _ in errors)),
        "error_sides": dict(Counter(qs[i].get("side", "") for i, _ in errors)),
        "errors_official_res": dict(
            Counter(official["by_id"][i]["res"] for i, _ in errors if i in official["by_id"])
        ),
        "official_ex_sum": official["document"]["ex_sum"],
        "official_ex_percent": official["document"]["ex_percent"],
        "official_errors": official["document"]["errors"],
        "official_timeouts": official["document"]["timeouts"],
        "crosscheck": {"agree": agree, "disagree": disagree, "rows": disagreements},
        "ex1_not_equal": len(loose),
        "ex1_not_equal_by_class": dict(merged["by_mechanism"]),
        "ex1_not_equal_by_test_suite_ex": dict(merged["by_test_suite_ex"]),
        "ex1_not_equal_ids": sorted(loose),
        "credited_total_from_summaries": merged["credited_total"],
        "not_equal_names_differ": sum(
            1 for q in compared.values() if q["verdict"] == "NOT_EQUAL" and q.get("names_differ")
        ),
        "questions": {str(i): q for i, q in qs.items()},
        "positions_unused": (merged["predictions"] or {}).get("positions_unused"),
        "predictions_digest": (merged["predictions"] or {}).get("digest"),
        "question_set_digest": merged["question_set_digest"],
        "elapsed": dict(merged["elapsed_seconds"]),
        "run_ids": merged["run_ids"],
        "timeout_lines": merged["timeout_lines"],
    }


def gold_only(gold: str) -> dict:
    """The gold-only pass over one copy: which probe fired on which question."""
    run = read_run(gold, "gold-only")
    by_probe: dict[str, list[int]] = {}
    for i, q in sorted(run["questions"].items()):
        for smell in q["smells"]:
            by_probe.setdefault(smell, []).append(i)
    return {
        "audited": run["merged"]["audited"],
        "smells": dict(run["merged"]["smells"]),
        "by_probe": by_probe,
        "questions_with_a_smell": sorted(i for i, q in run["questions"].items() if q["smells"]),
        "run_ids": run["merged"]["run_ids"],
        "timeout_lines": run["merged"]["timeout_lines"],
    }


def zip_against_hf(z: dict, h: dict) -> list[dict]:
    changed = []
    for i in sorted(set(z["questions"]) | set(h["questions"])):
        a, b = z["questions"].get(str(i)), h["questions"].get(str(i))
        va = None if a is None else (a["verdict"], a["bird_ex"])
        vb = None if b is None else (b["verdict"], b["bird_ex"])
        if va != vb:
            changed.append({"question_id": i, "zip": va, "hf": vb})
    return changed


CORRECTED = {1029: "european_football_2", 207: "toxicology", 879: "formula_1"}


def unjust_zero(model: str, zip_m: dict, hf_m: dict) -> list[dict]:
    corrected = read_run("corrected", model, databases=sorted(set(CORRECTED.values())))["questions"]
    rows = []
    for i in CORRECTED:
        c = corrected.get(i, {})
        rows.append(
            {
                "question_id": i,
                "zip": (
                    zip_m["questions"][str(i)]["verdict"],
                    zip_m["questions"][str(i)]["bird_ex"],
                ),
                "hf": (hf_m["questions"][str(i)]["verdict"], hf_m["questions"][str(i)]["bird_ex"]),
                "corrected": (c.get("verdict"), c.get("bird_ex")),
            }
        )
    return rows


def manual_rows(measurements: dict) -> str:
    """Every EX=1 & NOT_EQUAL row on the Hugging Face gold, with what a hand needs."""
    hf = {e["question_id"]: e for e in load(WORK / "data/hf/mini_dev_sqlite-00000-of-00001.json")}
    lines = ["# EX=1 & NOT_EQUAL rows, Hugging Face gold, SQLite\n"]
    for model in MODELS:
        m = measurements["hf"][model]
        for i in m["ex1_not_equal_ids"]:
            q = m["questions"][str(i)]
            mech = q["mechanism"]
            ce = load(Path(q["directory"]) / "counterexample.json")
            lines.append(
                f"## {model} q{i} ({q['db']}, {q['rule']}) class={mech['class']} "
                f"test_suite_ex={q['test_suite_ex']}"
            )
            lines.append(f"Q: {hf[i]['question']}")
            if hf[i]["evidence"]:
                lines.append(f"E: {hf[i]['evidence']}")
            lines.append(f"GOLD: {ce['gold']['executed_sql']}")
            lines.append(f"PRED: {ce['second']['executed_sql']}")
            lines.append(
                f"types gold={mech['gold_types']} pred={mech['second_types']}; "
                f"rows gold={ce['bird_ex']['gold_rows']} (distinct {ce['bird_ex']['gold_distinct_rows']}) "
                f"pred={ce['bird_ex']['second_rows']} (distinct {ce['bird_ex']['second_distinct_rows']}); "
                f"multiset_equal={mech['multiset_equal']} order_equal={mech['order_equal']} "
                f"prefix={mech['shorter_result_is_a_prefix']}"
            )
            g = ce["gold"]["result"]["rows"][:6]
            s = ce["second"]["result"]["rows"][:6]
            lines.append(
                "gold rows: " + " | ".join(",".join(str(c["value"]) for c in r) for r in g)
            )
            lines.append(
                "pred rows: " + " | ".join(",".join(str(c["value"]) for c in r) for r in s)
            )
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) > 1:  # a subset of the models, while the others are still being run
        MODELS[:] = [m for m in MODELS if m in sys.argv[1:]]
    measurements = {"zip": {}, "hf": {}}
    for gold in ("zip", "hf"):
        for model in MODELS:
            measurements[gold][model] = measure(gold, model)
    document = {
        "per_file": {
            gold: {m: {k: v for k, v in r.items() if k != "questions"} for m, r in runs.items()}
            for gold, runs in measurements.items()
        },
        "gold_only": {gold: gold_only(gold) for gold in ("zip", "hf")},
        "zip_against_hf": {
            m: zip_against_hf(measurements["zip"][m], measurements["hf"][m]) for m in MODELS
        },
        "unjust_zero": {
            m: unjust_zero(m, measurements["zip"][m], measurements["hf"][m]) for m in MODELS
        },
    }
    (OUT / "measurement.json").write_text(json.dumps(document, indent=1))
    (OUT / "manual-rows.md").write_text(manual_rows(measurements))
    # The per-question tables the aggregation and the artifact read: one verdict per (file,
    # question) per copy, and the probes that fired on each gold of the Hugging Face copy.
    for gold in ("zip", "hf"):
        (OUT / f"verdicts-{gold}.json").write_text(
            json.dumps(
                {
                    model: {
                        str(i): {
                            "verdict": q["verdict"],
                            "rule": q["rule"],
                            "bird_ex": q["bird_ex"],
                            "test_suite_ex": q["test_suite_ex"],
                            "smells": q["smells"],
                            **({"mechanism": q["mechanism"]["class"]} if "mechanism" in q else {}),
                            **({"error": q.get("message", "")} if q["verdict"] == "ERROR" else {}),
                        }
                        for i, q in sorted(
                            measurements[gold][model]["questions"].items(), key=lambda p: int(p[0])
                        )
                    }
                    for model in MODELS
                },
                indent=1,
            )
        )
        (OUT / f"gold-only-{gold}.json").write_text(
            json.dumps(
                {
                    str(i): {"db": q["db"], "rule": q["rule"], "smells": q["smells"]}
                    for i, q in sorted(read_run(gold, "gold-only")["questions"].items())
                },
                indent=1,
            )
        )
    for gold in ("zip", "hf"):
        print(f"== {gold}")
        print(
            "model | audited | compared | EX=1 | EX=0 | ERROR | official EX | agree | disagree | "
            "EX1&NE | by class | by test suite"
        )
        for m in MODELS:
            r = document["per_file"][gold][m]
            print(
                f"{m} | {r['audited']} | {r['compared']} | {r['tool_ex1']} | {r['tool_ex0']} | "
                f"{r['errors']} | {r['official_ex_sum']} | {r['crosscheck']['agree']} | "
                f"{r['crosscheck']['disagree']} | {r['ex1_not_equal']} | "
                f"{r['ex1_not_equal_by_class']} | {r['ex1_not_equal_by_test_suite_ex']}"
            )
    for gold in ("zip", "hf"):
        print(f"gold-only {gold}:", document["gold_only"][gold]["smells"])
    for m in MODELS:
        print(
            "zip vs hf changed:",
            m,
            [(c["question_id"], c["zip"], c["hf"]) for c in document["zip_against_hf"][m]],
        )


if __name__ == "__main__":
    main()
