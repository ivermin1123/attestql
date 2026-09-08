"""Write the hand judgements for the sample selected by sample_rows.py."""

import json
import os
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
OUT = WORK / "out"

# A: wrong answer BIRD credited. B: harmless answer. C: AttestQL's typed rule alone.
JUDGEMENTS: dict[tuple[str, str, int], tuple[str, str]] = {
    ("alpha-sql-dev.json", "dev1106", 101): (
        "B",
        "Same distinct values.",
    ),
    ("alpha-sql-dev.json", "dev1106", 1212): (
        "B",
        "Same distinct values.",
    ),
    ("alpha-sql-dev.json", "old", 845): ("B", "Same distinct values."),
    ("atlas-core-20260301.sql", "dev1106", 473): (
        "B",
        "Same distinct values.",
    ),
    ("atlas-core-20260301.sql", "old", 483): (
        "B",
        "Same distinct values.",
    ),
    ("atlas-core-20260324.sql", "dev1106", 407): (
        "B",
        "Same distinct values.",
    ),
    ("atlas-core-20260324.sql", "old", 521): (
        "B",
        "Same distinct values.",
    ),
    ("csc-sql-32b.sql", "dev1106", 452): (
        "B",
        "Same distinct values.",
    ),
    ("csc-sql-32b.sql", "dev1106", 1447): (
        "B",
        "Same distinct values.",
    ),
    ("csc-sql-32b.sql", "old", 1088): (
        "B",
        "Same distinct values.",
    ),
    ("csc-sql-7b.sql", "dev1106", 481): ("B", "Same distinct values."),
    ("csc-sql-7b.sql", "dev1106", 1503): ("B", "Same distinct values."),
    ("csc-sql-7b.sql", "old", 1059): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-7shot-mask-thr-0.8.txt", "dev1106", 452): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-7shot-mask-thr-0.8.txt", "old", 275): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-7shot-mask-thr-0.8.txt", "old", 1514): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-7shot-mask-thr-0.85.txt", "dev1106", 1220): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-7shot-mask-thr-0.85.txt", "old", 1066): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-7shot-questionmask.txt", "dev1106", 854): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-7shot-questionmask.txt", "old", 681): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-9shot-mask-thr.txt", "dev1106", 407): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-9shot-mask-thr.txt", "old", 206): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-9shot-mask-thr.txt", "old", 1435): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-9shot-questionmask.txt", "dev1106", 1214): (
        "B",
        "Same distinct values.",
    ),
    ("dail-sql-gpt-4-9shot-questionmask.txt", "old", 1071): (
        "B",
        "Same distinct values.",
    ),
    ("gsr-gpt-4o.sql", "dev1106", 610): (
        "B",
        "Same distinct values.",
    ),
    ("gsr-gpt-4o.sql", "old", 229): ("B", "Same distinct values."),
    ("gsr-gpt-4o.sql", "old", 1071): ("B", "Same distinct values."),
    ("predict_dev-codes-15b-bird-with-evidence.json", "dev1106", 868): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-15b-bird-with-evidence.json", "old", 522): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-15b-bird.json", "dev1106", 355): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-15b-bird.json", "old", 321): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-1b-bird-with-evidence.json", "dev1106", 449): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-1b-bird-with-evidence.json", "old", 355): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-1b-bird.json", "dev1106", 316): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-1b-bird.json", "old", 635): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-3b-bird-with-evidence.json", "dev1106", 758): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-3b-bird-with-evidence.json", "old", 390): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-3b-bird.json", "dev1106", 257): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-3b-bird.json", "old", 44): (
        "C",
        "Storage class only.",
    ),
    ("predict_dev-codes-3b-bird.json", "old", 1449): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-7b-bird-with-evidence.json", "dev1106", 1209): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-7b-bird-with-evidence.json", "old", 1054): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-7b-bird.json", "dev1106", 622): (
        "B",
        "Same distinct values.",
    ),
    ("predict_dev-codes-7b-bird.json", "old", 521): (
        "B",
        "Same distinct values.",
    ),
    ("rsl-sql-deepseek.txt", "dev1106", 452): (
        "B",
        "Same distinct values.",
    ),
    ("rsl-sql-deepseek.txt", "old", 258): ("B", "Same distinct values."),
    ("rsl-sql-deepseek.txt", "old", 1244): ("B", "Same distinct values."),
    ("rsl-sql-gpt-4o.txt", "dev1106", 1051): (
        "B",
        "Same distinct values.",
    ),
    ("rsl-sql-gpt-4o.txt", "old", 470): ("B", "Same distinct values."),
}


def main() -> None:
    sample = json.loads((OUT / "classification-input.json").read_text(encoding="utf-8"))
    counts: Counter = Counter()
    rows = []
    for evidence in sample["rows"]:
        key = (evidence["file"], evidence["copy"], evidence["question_id"])
        judged = JUDGEMENTS.get(key)
        if judged is None:
            raise SystemExit(f"no hand judgement for {key}")
        classification, reason = judged
        counts[classification] += 1
        rows.append(
            {
                "file": evidence["file"],
                "copy": evidence["copy"],
                "question_id": evidence["question_id"],
                "db": evidence["db"],
                "mechanism": evidence["mechanism"],
                "test_suite_ex": evidence["test_suite_ex"],
                "class": classification,
                "reason": reason,
            }
        )
    total = sum(counts.values())
    document = {
        "rule": (
            "A is a wrong answer BIRD credited; B is harmless, most often duplicate rows for "
            "the same answer; C is the typed rule alone. Each reason is one sentence and reads "
            "the two shipped statements and the recorded result rows, not the question text "
            "beyond what decides the answer."
        ),
        "sample": {
            "population": sample["population"],
            "sampled": len(rows),
            "selection": sample["rule"],
            "classified": total,
            "A": counts["A"],
            "B": counts["B"],
            "C": counts["C"],
            "A_share": round(counts["A"] / total, 4),
            "A_or_B_share": round((counts["A"] + counts["B"]) / total, 4),
        },
        "rows": rows,
    }
    (OUT / "classification.json").write_text(
        json.dumps(document, indent=1) + "\n", encoding="utf-8"
    )
    print(json.dumps(document["sample"], indent=1))


if __name__ == "__main__":
    main()
