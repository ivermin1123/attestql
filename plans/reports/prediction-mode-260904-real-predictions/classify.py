"""Hand classification of every EX=1 & NOT_EQUAL row, applied per question.

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
  C  the tool's rule and not the question's: the same number under another declared
     numeric type (int8 against numeric, float8 against numeric), which the typed
     comparison refuses by design and which the question does not ask about.

A question's class holds for every model whose row shows the same mechanism; where a
model's prediction differs in kind, the (question, model) pair is judged on its own.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

import measure

WORK = Path(os.environ["MEASURE_WORK"])  # the work directory reproduce.sh fills

BY_QUESTION: dict[int, tuple[str, str]] = {
    45: ("C", "AvgScrWrite as int8 against AVG() as numeric, one row, same value 507"),
    149: (
        "B",
        "the prediction adds DISTINCT (1 row) where the gold repeats DISPONENT 461 times; the prediction is the cleaner answer",
    ),
    168: ("C", "float8 against numeric, one row, same value"),
    173: (
        "A",
        "the prediction reads trans instead of order and matches the gold's one row 13 times by coincidence of the data",
    ),
    206: ("B", "one distinct row (c) repeated"),
    207: ("A", "gold DISTINCT over 13 elements; the prediction returns 103,772 rows"),
    230: ("A", "gold DISTINCT over 5 (element, label) rows; the prediction returns 103"),
    240: ("A", "gold DISTINCT over 6 elements; the prediction lists every atom, 24 rows"),
    245: ("C", "float8 against numeric, one row, value 1"),
    249: (
        "A",
        "the prediction joins on atom_id OR atom_id2 and returns each of the 2 elements twice",
    ),
    253: ("A", "gold DISTINCT over 4 elements; the prediction returns 10 rows"),
    255: (
        "A",
        "a percentage computed by scalar subqueries, then selected once per row of molecule: 343 identical rows",
    ),
    268: (
        "A",
        "the prediction joins on atom_id OR atom_id2 and returns each of the 2 elements twice",
    ),
    281: ("A", "gold DISTINCT over 8 elements; the prediction joins bond and returns 621 rows"),
    345: ("A", "gold DISTINCT over 3 statuses; the prediction returns 523 to 3,810 rows"),
    358: ("B", "one distinct row (black) repeated, once per printing"),
    391: ("A", "gold DISTINCT over 8 names; the prediction returns 80"),
    414: ("A", "the prediction joins cards and multiplies 10 languages into 1,900 rows"),
    440: ("B", "one distinct row repeated"),
    459: (
        "B",
        "the gold's LIMIT 1 name; the prediction returns that one name 88 times, once per printing",
    ),
    462: ("B", "2 distinct translations, one of them twice: 3 rows"),
    477: ("B", "2 distinct artists, 5 rows, under three times the answer"),
    483: ("B", "149 distinct texts, 155 rows"),
    487: ("C", "float8 against numeric, one row, value 100"),
    522: ("A", "gold groups 2 (name, format) rows; the prediction returns 66"),
    528: ("B", "1,664 distinct rows, 1,890 rows"),
    565: (
        "A",
        "both results are empty on this data; the prediction projects (title, closeddate) or a bool, not the well-finished label the question asks for",
    ),
    790: ("C", "int8 against numeric, one row, value 351"),
    800: ("C", "float8 against numeric, one row, value 31.2"),
    850: ("A", "gold DISTINCT over 3 race names; the prediction returns 76"),
    854: ("B", "one distinct coordinate row repeated, once per race"),
    857: ("B", "one distinct coordinate row repeated, once per race"),
    868: ("B", "one distinct coordinate row repeated, once per race"),
    960: ("C", "numeric against float8, one row, same value"),
    978: ("B", "2 distinct rows, 3 rows"),
    1035: (
        "A",
        "gold DISTINCT over 161 ids; the prediction returns 356, so the count of teams is misstated",
    ),
    1057: ("C", "float8 against numeric, one row, same value"),
    1088: ("A", "gold DISTINCT over 1,105 names; the prediction returns 15,429"),
    1122: ("B", "one distinct row (Lionel Messi) repeated"),
    1124: ("A", "gold DISTINCT over 3,339 names; the prediction returns 42,823"),
    1130: ("B", "43 distinct names, 44 or 56 rows"),
    1134: ("C", "numeric against int8, one row, value 1"),
    1141: (
        "A",
        "gold DISTINCT over 2 classes; the prediction returns 6 rows, so the answer to a which-of-three question is a list of six",
    ),
    1147: ("B", "one distinct row (Lionel Messi) repeated"),
    1331: ("C", "int8 against numeric (SUM), one row, value 50"),
    1422: ("A", "gold DISTINCT over 4 categories; the prediction returns 45"),
    1432: ("C", "float8 against numeric or int8, one row, same value"),
    1435: ("B", "2 distinct names, 3 rows"),
    1457: ("A", "gold DISTINCT over 3 members; the prediction returns 11, one per expense"),
    1501: ("A", "gold DISTINCT over 2 countries; the prediction returns 978"),
    1506: ("A", "gold DISTINCT over 21 descriptions; the prediction returns 933"),
    1507: ("B", "2 distinct times, 3 rows"),
    1514: ("B", "one distinct row (CZK) repeated"),
    112: ("B", "one distinct row (Tachov) repeated 50 times through an extra join on account"),
    200: (
        "A",
        "gold DISTINCT over 2 molecule ids; the prediction joins atoms and bonds and returns 12 rows",
    ),
    371: ("C", "float8 against numeric, one row, same value"),
}

BY_PAIR: dict[tuple[int, str], tuple[str, str]] = {}


def classify(gold: str, models: list[str]) -> dict:
    out = {"classes": {}, "per_file": {}, "unjudged": []}
    for model in models:
        r = measure.measure(gold, model)
        counts = Counter()
        rows = []
        for i in r["ex1_not_equal_ids"]:
            judged = BY_PAIR.get((i, model)) or BY_QUESTION.get(i)
            if judged is None:
                out["unjudged"].append((model, i, r["questions"][str(i)]["mechanism"]))
                continue
            klass, reason = judged
            counts[klass] += 1
            rows.append(
                {
                    "question_id": i,
                    "class": klass,
                    "mechanism": r["questions"][str(i)]["mechanism"]["class"],
                    "reason": reason,
                }
            )
        total = sum(counts.values())
        out["per_file"][model] = {
            "ex1_not_equal": total,
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
    print("model | EX1&NE | A | B | C | A/all | (A+B)/all")
    tA = tB = tC = 0
    for m, r in result["per_file"].items():
        print(
            f"{m} | {r['ex1_not_equal']} | {r['A']} | {r['B']} | {r['C']} | {r['precision_A']} | {r['precision_A_or_B']}"
        )
        tA += r["A"]
        tB += r["B"]
        tC += r["C"]
    t = tA + tB + tC
    print(
        f"all | {t} | {tA} | {tB} | {tC} | {round(tA / t, 3) if t else None} | {round((tA + tB) / t, 3) if t else None}"
    )
    if result["unjudged"]:
        print("UNJUDGED:", result["unjudged"])
