"""Read the tool's runs and BIRD's own scoring, and count what the report states.

Inputs, under the directory this script sits in:
  out/tool/<gold>/<model>/stdout.txt, summary.json, q<id>/{counterexample,evidence-gold,evidence-second}.json
  out/official/<gold>/<model>.json      (bird_ex_official.py)
Outputs:
  out/measurement.json                  every count, every listed row
  out/manual-rows.md                    the EX=1 & NOT_EQUAL rows, for classification by hand
"""

import json
import os
import re
from collections import Counter
from decimal import Decimal
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
LINE = re.compile(
    r"^q(\d+)\s+(\S+)\s+(\S*)\s+(EQUAL|NOT_EQUAL|NOT_COMPARABLE|ERROR|GOLD-ONLY)\s+smells=(\S+)(?:\s+(.*))?$"
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def typed_rows(record: dict) -> list[tuple]:
    rows = []
    for row in record["result"]["rows"]:
        cells = []
        for cell in row:
            value = cell["value"]
            if cell["type"] == "dec":
                value = Decimal(value)
            cells.append((cell["type"], value))
        rows.append(tuple(cells))
    return rows


def mechanism(directory: Path, rule: str) -> dict:
    """Why the typed comparison said NOT_EQUAL, read off the two full records."""
    gold = load(directory / "evidence-gold.json")
    second = load(directory / "evidence-second.json")
    gold_types = [c["pg_type"] for c in gold["result"]["columns"]]
    second_types = [c["pg_type"] for c in second["result"]["columns"]]
    rows_g, rows_s = typed_rows(gold), typed_rows(second)
    multiset_equal = Counter(rows_g) == Counter(rows_s)
    set_equal = set(rows_g) == set(rows_s)
    untyped_multiset_equal = Counter(tuple(v for _, v in r) for r in rows_g) == Counter(
        tuple(v for _, v in r) for r in rows_s
    )
    if gold_types != second_types:
        klass = "type"
    elif not multiset_equal:
        klass = "multiplicity" if set_equal else "value"
    else:
        klass = "order" if rule == "R-ORD" else "unexplained"
    return {
        "class": klass,
        "gold_types": gold_types,
        "second_types": second_types,
        "multiset_equal": multiset_equal,
        "set_equal": set_equal,
        "untyped_multiset_equal": untyped_multiset_equal,
        "order_equal": rows_g == rows_s,
        "gold_rows": len(rows_g),
        "second_rows": len(rows_s),
        "gold_distinct": len(set(rows_g)),
        "second_distinct": len(set(rows_s)),
    }


def read_run(gold: str, model: str) -> dict:
    directory = OUT / "tool" / gold / model
    summary = load(directory / "summary.json")
    questions = {}
    for line in (directory / "stdout.txt").read_text(encoding="utf-8").splitlines():
        found = LINE.match(line)
        if not found:
            continue
        qid, db, rule, verdict, smells, rest = found.groups()
        entry = {
            "db": db,
            "rule": rule,
            "verdict": verdict,
            "smells": smells,
            "bird_ex": None,
            "message": rest if verdict == "ERROR" else "",
        }
        if verdict == "EQUAL":
            entry["bird_ex"] = 1
        elif verdict in ("NOT_EQUAL", "NOT_COMPARABLE"):
            ce = load(directory / f"q{qid}" / "counterexample.json")
            entry["bird_ex"] = ce["bird_ex"]["value"]
            entry["names_differ"] = "projection_names_differ" in ce
            entry["mechanism"] = mechanism(directory / f"q{qid}", rule)
        questions[int(qid)] = entry
    return {"summary": summary, "questions": questions}


def read_official(gold: str, model: str) -> dict:
    document = load(OUT / "official" / gold / f"{model}.json")
    by_id: dict[int, dict] = {}
    both: dict[int, list] = {}
    for row in document["rows"]:
        both.setdefault(row["question_id"], []).append(row)
        by_id.setdefault(row["question_id"], row)  # the first position wins, as the tool does
    return {"document": document, "by_id": by_id, "positions": both}


def measure(gold: str, model: str) -> dict:
    run = read_run(gold, model)
    official = read_official(gold, model)
    qs = run["questions"]
    verdicts = Counter(q["verdict"] for q in qs.values())
    compared = {i: q for i, q in qs.items() if q["verdict"] in ("EQUAL", "NOT_EQUAL")}
    error_steps = {e["question_id"]: e["step"] for e in run["summary"]["errors"]}
    for i, q in qs.items():
        if q["verdict"] == "ERROR":
            q["step"] = error_steps.get(i, "")
            # BIRD scores any exception 0; the tool's ERROR is compared with that reading
            q["bird_ex"] = 0
    tool_ex1 = sum(1 for q in compared.values() if q["bird_ex"] == 1)
    tool_ex0 = sum(1 for q in compared.values() if q["bird_ex"] == 0)
    errors = [(i, q["message"]) for i, q in qs.items() if q["verdict"] == "ERROR"]
    # cross-check per question id, over the questions the tool read
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
                    "tool_verdict": q["verdict"],
                    "tool_step": q.get("step", ""),
                    "tool_message": q.get("message", "")[:160],
                    "tool_bird_ex": q["bird_ex"],
                    "official": off["res"],
                    "official_outcome": off["outcome"],
                    "official_message": off["message"],
                }
            )
    # the tool's errors against the official reading
    error_official = Counter(
        official["by_id"][i]["res"] for i, _ in errors if i in official["by_id"]
    )
    error_steps_count = Counter(qs[i].get("step", "") for i, _ in errors)
    # EX=1 & NOT_EQUAL by mechanism
    loose = {i: q for i, q in compared.items() if q["verdict"] == "NOT_EQUAL" and q["bird_ex"] == 1}
    by_class = Counter(q["mechanism"]["class"] for q in loose.values())
    names_only = sum(
        1 for q in compared.values() if q["verdict"] == "NOT_EQUAL" and q.get("names_differ")
    )
    return {
        "gold": gold,
        "model": model,
        "audited": run["summary"]["question_set"]["audited"],
        "entries": run["summary"]["question_set"]["entries"],
        "verdicts": dict(verdicts),
        "compared": len(compared),
        "tool_ex1": tool_ex1,
        "tool_ex0": tool_ex0,
        "errors": len(errors),
        "error_lines": errors,
        "errors_official_res": dict(error_official),
        "error_steps": dict(error_steps_count),
        "official_ex_sum": official["document"]["ex_sum"],
        "official_ex_percent": official["document"]["ex_percent"],
        "official_errors": official["document"]["errors"],
        "official_timeouts": official["document"]["timeouts"],
        "crosscheck": {"agree": agree, "disagree": disagree, "rows": disagreements},
        "ex1_not_equal": len(loose),
        "ex1_not_equal_by_class": dict(by_class),
        "ex1_not_equal_ids": sorted(loose),
        "not_equal_names_differ": names_only,
        "questions": {str(i): q for i, q in qs.items()},
        "positions_unused": run["summary"]["predictions"].get("positions_unused"),
        "predictions_digest": run["summary"]["predictions"].get("digest"),
        "question_set_digest": run["summary"]["question_set"]["digest"],
        "elapsed": run["summary"]["elapsed_seconds"],
        "run_id": run["summary"]["run_id"],
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


def unjust_zero(model: str, zip_m: dict, hf_m: dict) -> list[dict]:
    corrected = read_run("corrected", model)["questions"]
    rows = []
    for i in (1029, 207, 879):
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
    hf = {e["question_id"]: e for e in load(WORK / "data/hf/mini_dev_pg-00000-of-00001.json")}
    lines = ["# EX=1 & NOT_EQUAL rows, Hugging Face gold\n"]
    for model in MODELS:
        m = measurements["hf"][model]
        for i in m["ex1_not_equal_ids"]:
            q = m["questions"][str(i)]
            mech = q["mechanism"]
            ce = load(OUT / "tool" / "hf" / model / f"q{i}" / "counterexample.json")
            lines.append(f"## {model} q{i} ({q['db']}, {q['rule']}) class={mech['class']}")
            lines.append(f"Q: {hf[i]['question']}")
            if hf[i]["evidence"]:
                lines.append(f"E: {hf[i]['evidence']}")
            lines.append(f"GOLD: {ce['gold']['executed_sql']}")
            lines.append(f"PRED: {ce['second']['executed_sql']}")
            lines.append(
                f"types gold={mech['gold_types']} pred={mech['second_types']}; rows gold={mech['gold_rows']} (distinct {mech['gold_distinct']}) pred={mech['second_rows']} (distinct {mech['second_distinct']}); multiset_equal={mech['multiset_equal']} order_equal={mech['order_equal']}"
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
    import sys

    if len(sys.argv) > 1:  # a subset of the models, while the others are still being run
        MODELS[:] = [m for m in MODELS if m in sys.argv[1:]]
    measurements = {"zip": {}, "hf": {}}
    for gold in ("zip", "hf"):
        for model in MODELS:
            measurements[gold][model] = measure(gold, model)
    zip_by_id = read_run("zip-by-id", "gpt-35-turbo-instruct")["questions"]
    zip_pos = measurements["zip"]["gpt-35-turbo-instruct"]["questions"]
    keying_same = all(
        (zip_pos[str(i)]["verdict"], zip_pos[str(i)]["bird_ex"] or 0)
        == (q["verdict"], q["bird_ex"] or 0)
        for i, q in zip_by_id.items()
    ) and len(zip_by_id) == len(zip_pos)
    document = {
        "per_file": {
            gold: {m: {k: v for k, v in r.items() if k != "questions"} for m, r in runs.items()}
            for gold, runs in measurements.items()
        },
        "zip_against_hf": {
            m: zip_against_hf(measurements["zip"][m], measurements["hf"][m]) for m in MODELS
        },
        "unjust_zero": {
            m: unjust_zero(m, measurements["zip"][m], measurements["hf"][m]) for m in MODELS
        },
        "position_keying_equals_id_keying_on_zip": keying_same,
    }
    (OUT / "measurement.json").write_text(json.dumps(document, indent=1))
    (OUT / "manual-rows.md").write_text(manual_rows(measurements))
    for gold in ("zip", "hf"):
        print(f"== {gold}")
        print(
            "model | audited | compared | EX=1 | EX=0 | ERROR | official EX | agree | disagree | EX1&NE | by class"
        )
        for m in MODELS:
            r = document["per_file"][gold][m]
            print(
                f"{m} | {r['audited']} | {r['compared']} | {r['tool_ex1']} | {r['tool_ex0']} | {r['errors']} | "
                f"{r['official_ex_sum']} | {r['crosscheck']['agree']} | {r['crosscheck']['disagree']} | "
                f"{r['ex1_not_equal']} | {r['ex1_not_equal_by_class']}"
            )
    print("position keying == id keying on zip:", keying_same)
    for m in MODELS:
        print(
            "zip vs hf changed:",
            m,
            [(c["question_id"], c["zip"], c["hf"]) for c in document["zip_against_hf"][m]],
        )
    for m in MODELS:
        print("unjust zero:", m, document["unjust_zero"][m])


if __name__ == "__main__":
    main()
