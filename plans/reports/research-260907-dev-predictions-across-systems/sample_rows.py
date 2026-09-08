"""Select the stated 50-row hand-classification sample and carry its evidence."""

import json
import os
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
OUT = WORK / "out"
SAMPLE_SIZE = 50


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def counterexample(copy: str, prediction_file: str, db: str, question_id: int) -> dict:
    return load(
        OUT
        / "tool-predictions"
        / copy
        / prediction_file
        / db
        / f"q{question_id}"
        / "counterexample.json"
    )


def main() -> None:
    measured = load(OUT / "prediction-measurement.json")
    old = load(WORK / "data/dev/dev_20240627/dev.json")
    new = {
        entry["question_id"]: entry
        for entry in load(WORK / "data/hf/dev_20251106-00000-of-00001.json")
    }
    universe = []
    for prediction_file in sorted(measured["files"]):
        row = measured["files"][prediction_file]
        for question_id in row["ex1_not_equal_ids"]:
            universe.append((row["file"], row["copy"], question_id))
    universe.sort(key=lambda row: (row[0], row[1], row[2]))
    step = max(1, len(universe) // SAMPLE_SIZE)
    chosen = universe[::step][:SAMPLE_SIZE]
    rows = []
    for prediction_file, copy, question_id in chosen:
        question_row = measured["files"][f"{copy}/{prediction_file}"]["questions"][str(question_id)]
        evidence = counterexample(copy, prediction_file, question_row["db"], question_id)
        question = old[question_id] if copy == "old" else new[question_id]
        rows.append(
            {
                "file": prediction_file,
                "copy": copy,
                "question_id": question_id,
                "db": question_row["db"],
                "mechanism": question_row["mechanism"],
                "mechanism_detail": evidence["mechanism"],
                "test_suite_ex": question_row["test_suite_ex"],
                "bird_ex_detail": evidence["bird_ex"],
                "question": question["question"],
                "gold_sql": evidence["gold"]["executed_sql"],
                "prediction_sql": evidence["second"]["executed_sql"],
                "gold_result": evidence["gold"]["result"],
                "prediction_result": evidence["second"]["result"],
                "differing_rows": evidence["differing_rows"],
            }
        )
    document = {
        "rule": (
            f"all EX=1 and NOT_EQUAL rows ordered by (file, copy, id), every {step}th row, "
            f"first {SAMPLE_SIZE}"
        ),
        "population": len(universe),
        "sampled": len(rows),
        "step": step,
        "rows": rows,
    }
    (OUT / "classification-input.json").write_text(
        json.dumps(document, indent=1) + "\n", encoding="utf-8"
    )
    print(document["rule"])
    for row in rows:
        print(row["file"], row["copy"], row["question_id"], row["mechanism"])


if __name__ == "__main__":
    main()
