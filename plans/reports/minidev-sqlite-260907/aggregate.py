"""The totals the report states, and the comparison against the PostgreSQL measurement.

Reads out/measurement.json and out/classification.json from the work directory, and the
committed PostgreSQL run from this repository: `plans/reports/prediction-mode-260904-real-predictions/`
(the verdicts of every file on both golds, measured at `cf0b033` and `0963374`) and
`plans/reports/audit-260902-minidev-gold-only/` and `audit-260903-minidev-hf-gold-only/` (the
gold-only probes on the zip copy and on the Hugging Face copy). The two engines audited the same 500 questions from the same benchmark, so a question
whose smell or verdict differs between them is a difference the two backends made, and that
is what the last two tables of the report are.
"""

import json
import os
import re
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])  # the work directory reproduce.sh fills
REPO = Path(__file__).resolve().parents[3]
POSTGRES = REPO / "plans/reports/prediction-mode-260904-real-predictions"
POSTGRES_GOLD_ONLY = {
    "hf": REPO / "plans/reports/audit-260903-minidev-hf-gold-only/stdout.txt",
    "zip": REPO / "plans/reports/audit-260902-minidev-gold-only/stdout.txt",
}
LINE = re.compile(r"^q(\d+)\s+(\S+)\s+(\S*)\s+GOLD-ONLY\s+smells=(\S+)")

m = json.loads((WORK / "out/measurement.json").read_text())
c = json.loads((WORK / "out/classification.json").read_text())
out: dict = {}

# 1. Per copy, the totals of the nine files.
for gold in ("zip", "hf"):
    t: Counter = Counter()
    for r in m["per_file"][gold].values():
        t["audited"] += r["audited"]
        t["compared"] += r["compared"]
        t["ex1"] += r["tool_ex1"]
        t["ex0"] += r["tool_ex0"]
        t["errors"] += r["errors"]
        t["official_ex"] += r["official_ex_sum"]
        t["agree"] += r["crosscheck"]["agree"]
        t["disagree"] += r["crosscheck"]["disagree"]
        t["ex1_not_equal"] += r["ex1_not_equal"]
        for key, value in r["ex1_not_equal_by_class"].items():
            t["class_" + key] += value
        for key, value in r["ex1_not_equal_by_test_suite_ex"].items():
            t["test_suite_ex_" + key] += value
        for key, value in r["error_steps"].items():
            t["errstep_" + key] += value
        for key, value in r["error_sides"].items():
            t["errside_" + key] += value
        t["not_equal_names_differ"] += r["not_equal_names_differ"]
    out[gold] = dict(t)
out["disagreements"] = {
    gold: [row for r in m["per_file"][gold].values() for row in r["crosscheck"]["rows"]]
    for gold in ("zip", "hf")
}

# 2. The hand classification.
tc: Counter = Counter()
for r in c["per_file"].values():
    for klass in "ABC":
        tc[klass] += r[klass]
total = sum(tc.values())
out["classes"] = {
    **tc,
    "total": total,
    "A_over_all": round(tc["A"] / total, 3) if total else None,
    "AB_over_all": round((tc["A"] + tc["B"]) / total, 3) if total else None,
    "A_over_AB": round(tc["A"] / (tc["A"] + tc["B"]), 3) if (tc["A"] + tc["B"]) else None,
}
by_question: dict[int, str] = {}
seen: Counter = Counter()
for r in c["per_file"].values():
    for row in r["rows"]:
        seen[row["question_id"]] += 1
        by_question[row["question_id"]] = row["class"]
out["distinct_questions"] = len(seen)
out["distinct_questions_by_class"] = dict(Counter(by_question.values()))
out["sampled"] = c.get("sampled")

# 3. Gold-only, both copies, and the delta between them.
out["gold_only"] = {
    gold: {
        "audited": m["gold_only"][gold]["audited"],
        "smells": m["gold_only"][gold]["smells"],
        "by_probe": m["gold_only"][gold]["by_probe"],
        "questions_with_a_smell": m["gold_only"][gold]["questions_with_a_smell"],
    }
    for gold in ("zip", "hf")
}
zip_probes = m["gold_only"]["zip"]["by_probe"]
hf_probes = m["gold_only"]["hf"]["by_probe"]
out["gold_only"]["delta_zip_to_hf"] = {
    probe: {
        "only_on_zip": sorted(set(zip_probes.get(probe, [])) - set(hf_probes.get(probe, []))),
        "only_on_hf": sorted(set(hf_probes.get(probe, [])) - set(zip_probes.get(probe, []))),
    }
    for probe in sorted(set(zip_probes) | set(hf_probes))
}

# 4. Against PostgreSQL: the gold-only probes over the same copy of the question set.
out["smells_against_postgresql"] = {}
for gold in ("zip", "hf"):
    postgres_probes: dict[int, list[str]] = {}
    for line in POSTGRES_GOLD_ONLY[gold].read_text(encoding="utf-8").splitlines():
        found = LINE.match(line)
        if not found:
            continue
        qid, _db, _rule, smells = found.groups()
        postgres_probes[int(qid)] = [] if smells == "none" else smells.split(",")
    sqlite_probes = {
        int(i): q["smells"]
        for i, q in json.loads((WORK / f"out/gold-only-{gold}.json").read_text()).items()
    }
    smell_moves = []
    for qid in sorted(set(postgres_probes) | set(sqlite_probes)):
        on_postgres = sorted(postgres_probes.get(qid, []))
        on_sqlite = sorted(sqlite_probes.get(qid, []))
        if on_postgres != on_sqlite:
            smell_moves.append({"question_id": qid, "postgresql": on_postgres, "sqlite": on_sqlite})
    out["smells_against_postgresql"][gold] = {
        "moves": smell_moves,
        "postgresql_fired_on": sum(1 for v in postgres_probes.values() if v),
        "sqlite_fired_on": sum(1 for v in sqlite_probes.values() if v),
        "postgresql_by_probe": dict(
            Counter(probe for probes in postgres_probes.values() for probe in probes)
        ),
        "sqlite_by_probe": dict(
            Counter(probe for probes in sqlite_probes.values() for probe in probes)
        ),
    }

# 5. Against PostgreSQL: the verdict of every (file, question) on the same gold copy.
verdict_moves = {}
for gold in ("zip", "hf"):
    postgres_verdicts = json.loads((POSTGRES / f"verdicts-{gold}.json").read_text())
    sqlite_verdicts = json.loads((WORK / f"out/verdicts-{gold}.json").read_text())
    moves = []
    for model, questions in sqlite_verdicts.items():
        for qid, on_sqlite in questions.items():
            on_postgres = postgres_verdicts.get(model, {}).get(qid)
            if on_postgres is None:
                continue

            # An ERROR is scored 0 by BIRD on both engines; the committed PostgreSQL file
            # records its bird_ex as null and this run's as 0, so the two are read the same
            # way here rather than counted as 702 moves that are only a spelling.
            def reading(row: dict) -> tuple[str, int | None]:
                return (row["verdict"], 0 if row["verdict"] == "ERROR" else row["bird_ex"])

            if reading(on_postgres) != reading(on_sqlite):
                moves.append(
                    {
                        "model": model,
                        "question_id": int(qid),
                        "postgresql": (on_postgres["verdict"], on_postgres["bird_ex"]),
                        "sqlite": (on_sqlite["verdict"], on_sqlite["bird_ex"]),
                        "postgresql_error": on_postgres.get("error", ""),
                        "sqlite_error": on_sqlite.get("error", ""),
                    }
                )
    verdict_moves[gold] = {
        "total": len(moves),
        "by_pair": dict(Counter(f"{row['postgresql'][0]}->{row['sqlite'][0]}" for row in moves)),
        "distinct_questions": len({row["question_id"] for row in moves}),
        "rows": moves,
    }
out["verdicts_against_postgresql"] = verdict_moves

# 6. Unjust zeros and unjust ones, against the three corrections.
unjust_zero = []
unjust_one = []
for model, rows in m["unjust_zero"].items():
    for row in rows:
        qid = row["question_id"]
        for gold in ("zip", "hf"):
            _verdict, ex = row[gold]
            corrected_verdict, corrected_ex = row["corrected"]
            if ex == 0 and corrected_ex == 1:
                unjust_zero.append((model, qid, gold, corrected_verdict))
            if ex == 1 and corrected_verdict == "NOT_EQUAL" and corrected_ex == 0:
                unjust_one.append((model, qid, gold))
out["unjust_zero"] = unjust_zero
out["unjust_one"] = unjust_one
out["unjust_table"] = m["unjust_zero"]

# 7. The zip copy against the Hugging Face copy, same predictions.
out["zip_against_hf"] = {
    model: [
        (r["question_id"], r["zip"], r["hf"]) for r in rows if r["question_id"] not in (119, 120)
    ]
    for model, rows in m["zip_against_hf"].items()
}
out["timeout_lines"] = {
    gold: {
        model: r["timeout_lines"] for model, r in m["per_file"][gold].items() if r["timeout_lines"]
    }
    for gold in ("zip", "hf")
}

(WORK / "out/aggregate.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "disagreements"}, indent=1)[:12000])
