"""Hand classification of the EX=1 & NOT_EQUAL rows, applied per question.

Every judgment below was made by reading the question, both statements and both results
(out/manual-rows.md). Three classes, by what a person deciding the row would say:

  A  a wrong answer the benchmark credited: the prediction answers a different question
     (another table, another projection), repeats a scalar once per row of an unrelated
     table, or returns a list whose duplicates misstate what the question asks to enumerate
     or count (every distinct row is there, but the list is at least twice as long as the
     answer and the question asks for the things, not the rows);
  B  a harmless difference: one distinct row repeated (the answer is unambiguous), a
     prediction stricter than the gold (DISTINCT added), or a list under twice the answer's
     length with every row present;
  C  the tool's rule and not the question's: the same value under another declared type,
     which on SQLite is the storage class the column's cells came back at, and which the
     question does not ask about.

A question's class holds for every model whose row shows the same mechanism; where a model's
prediction differs in kind, the (question, model) pair is judged on its own.

The report classifies every row when there are fewer than 100 and a stated sample of 50
otherwise. ``SAMPLE`` holds the sample when one was drawn: the rows are ordered by (model,
question id) and every ``len(rows) // 50``-th is taken, so the sample is a fixed function of
the run and not a choice made after seeing the answers.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

import measure

WORK = Path(os.environ["MEASURE_WORK"])  # the work directory reproduce.sh fills
SAMPLE_SIZE = 50

BY_QUESTION: dict[int, tuple[str, str]] = {
    45: ("C", "AvgScrWrite as INTEGER 507 against AVG() as REAL 507.0, one row, same value"),
    206: ("B", "one distinct row (c) repeated, 2 or 4 rows"),
    227: (
        "A",
        "a percentage computed by two scalar subqueries and then selected once per row of molecule: 343 identical rows where the question asks for one number",
    ),
    230: ("A", "gold DISTINCT over 5 (element, label) rows; the prediction returns 636"),
    240: ("A", "gold DISTINCT over 6 elements; the prediction lists every atom, 24 rows"),
    345: ("A", "gold DISTINCT over 3 statuses; the prediction returns 3,810 rows"),
    358: ("B", "one distinct row (black) repeated, once per printing"),
    391: ("A", "gold DISTINCT over 8 names; the prediction returns 80"),
    440: ("B", "one distinct row repeated, 6 rows"),
    459: (
        "B",
        "the gold's LIMIT 1 name; the prediction returns that one name 88 times, once per printing",
    ),
    462: ("B", "2 distinct translations, one of them twice: 3 rows"),
    522: ("A", "gold groups 2 (name, format) rows; the prediction returns 66"),
    528: ("B", "1,664 distinct rows, 1,890 rows"),
    854: ("B", "one distinct coordinate row repeated, once per race"),
    1035: (
        "A",
        "gold DISTINCT over 161 ids; the prediction returns 356, so the count of teams is misstated",
    ),
    1036: ("B", "128 distinct names, 129 rows"),
    1088: ("A", "gold DISTINCT over 1,105 names; the prediction returns 15,429"),
    1124: ("A", "gold DISTINCT over 3,339 names; the prediction returns 42,823"),
    1130: ("B", "43 distinct names, 56 rows"),
    1141: (
        "A",
        "gold DISTINCT over 2 classes; the prediction returns 6 rows, so the answer to a which-of-three question is a list of six",
    ),
    1147: ("B", "one distinct row (Lionel Messi) repeated"),
    1155: ("A", "gold DISTINCT over 103 patients; the prediction returns 1,281 rows"),
    1187: (
        "A",
        "gold DISTINCT over 63 ids; the prediction returns 465, so the count the question asks for is misstated",
    ),
    1209: ("A", "gold DISTINCT over 38 diagnoses; the prediction returns 871"),
    1220: ("A", "gold DISTINCT over 20 patients; the prediction returns 44"),
    1232: ("A", "gold DISTINCT over 13 patients; the prediction returns 74"),
    1435: ("B", "2 distinct names, 3 rows"),
    1500: (
        "B",
        "the prediction adds DISTINCT (27 rows) where the gold repeats the 27 descriptions over 976 rows; the prediction is the cleaner answer",
    ),
    1506: ("A", "gold DISTINCT over 21 descriptions; the prediction returns 933"),
    1507: ("B", "2 distinct times, 3 rows"),
    1514: ("B", "one distinct row (CZK) repeated, 3 rows"),
}

BY_PAIR: dict[tuple[int, str], tuple[str, str]] = {}


def rows_of(gold: str, models: list[str]) -> list[tuple[str, int]]:
    """Every EX=1 & NOT_EQUAL row, ordered by (model, question id)."""
    found = []
    for model in models:
        for question_id in measure.measure(gold, model)["ex1_not_equal_ids"]:
            found.append((model, question_id))
    return found


def classify(gold: str, models: list[str]) -> dict:
    every = rows_of(gold, models)
    if len(every) < 100:
        chosen, sampled = every, None
    else:
        step = len(every) // SAMPLE_SIZE
        chosen = every[::step][:SAMPLE_SIZE]
        sampled = {
            "size": len(chosen),
            "of": len(every),
            "rule": f"ordered by (model, question id), every {step}th row, first {SAMPLE_SIZE}",
        }
    out: dict = {"per_file": {}, "unjudged": [], "sampled": sampled}
    by_model: dict[str, list[int]] = {}
    for model, question_id in chosen:
        by_model.setdefault(model, []).append(question_id)
    for model in models:
        measured = measure.measure(gold, model)
        counts: Counter = Counter()
        rows = []
        for question_id in by_model.get(model, []):
            judged = BY_PAIR.get((question_id, model)) or BY_QUESTION.get(question_id)
            if judged is None:
                out["unjudged"].append(
                    (model, question_id, measured["questions"][str(question_id)]["mechanism"])
                )
                continue
            klass, reason = judged
            counts[klass] += 1
            rows.append(
                {
                    "question_id": question_id,
                    "class": klass,
                    "mechanism": measured["questions"][str(question_id)]["mechanism"]["class"],
                    "test_suite_ex": measured["questions"][str(question_id)]["test_suite_ex"],
                    "reason": reason,
                }
            )
        total = sum(counts.values())
        out["per_file"][model] = {
            "ex1_not_equal": measured["ex1_not_equal"],
            "classified": total,
            "A": counts["A"],
            "B": counts["B"],
            "C": counts["C"],
            "precision_A": round(counts["A"] / total, 3) if total else None,
            "precision_A_or_B": round((counts["A"] + counts["B"]) / total, 3) if total else None,
            "rows": rows,
        }
    return out


if __name__ == "__main__":
    models = sys.argv[1:] or measure.MODELS
    result = classify("hf", models)
    (WORK / "out/classification.json").write_text(json.dumps(result, indent=1))
    print("model | EX1&NE | classified | A | B | C | A/all | (A+B)/all")
    totals: Counter = Counter()
    for model, row in result["per_file"].items():
        print(
            f"{model} | {row['ex1_not_equal']} | {row['classified']} | {row['A']} | {row['B']} | "
            f"{row['C']} | {row['precision_A']} | {row['precision_A_or_B']}"
        )
        for klass in "ABC":
            totals[klass] += row[klass]
    total = sum(totals.values())
    print(
        f"all | | {total} | {totals['A']} | {totals['B']} | {totals['C']} | "
        f"{round(totals['A'] / total, 3) if total else None} | "
        f"{round((totals['A'] + totals['B']) / total, 3) if total else None}"
    )
    if result["sampled"]:
        print("sample:", result["sampled"])
    if result["unjudged"]:
        print("UNJUDGED:", len(result["unjudged"]), result["unjudged"][:20])
