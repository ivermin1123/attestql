"""Draw the blind sample for the second reading of the class A hand classification.

Run from the repository root with the output directory as its argument (or in
``SECOND_READER_OUT``). It reads the published Mini-Dev PostgreSQL runs under
``tools/site/data/minidev-pg/``, takes every row the first reader classed A that has a question
directory on the site (66 of the 69; the other three are whole only in the release assets), draws
30 of them with a fixed seed, and writes two files into the directory given as the first
argument: ``packet.json``, what the second reader sees (question, evidence, both statements, both
results with up to 25 rows a side, BIRD's own score, the typed verdict, its mechanism and the
differing rows, and no label), and ``key.json``, the first reader's class and reason for the same
30 items, which the second reader must not open.
"""

import json
import os
import random
import sys
from pathlib import Path

SEED = 20260913
SAMPLE = 30
DATA = Path("tools/site/data/minidev-pg")


def _result(record: dict[str, object]) -> dict[str, object]:
    result = record["result"]
    if not isinstance(result, dict):
        raise TypeError("a record's result is an object")
    rows = result.get("rows") or []
    if not isinstance(rows, list):
        raise TypeError("a result's rows are a list")
    return {
        "columns": result.get("columns"),
        "row_count": record.get("row_count"),
        "rows_shown": rows[:25],
    }


def main(out: Path) -> None:
    classification = json.loads((DATA / "classification.json").read_text())
    rows: list[tuple[str, int, str, str, str]] = []
    for file, per_file in classification["per_file"].items():
        for row in per_file["rows"]:
            if row["class"] == "A" and (DATA / file / f"q{row['question_id']}").is_dir():
                rows.append(
                    (file, row["question_id"], row["class"], row["mechanism"], row["reason"])
                )
    rows.sort()
    sample = sorted(random.Random(SEED).sample(rows, SAMPLE))  # noqa: S311 - a fixed seed, not a secret
    packet: list[dict[str, object]] = []
    key: list[dict[str, object]] = []
    for item, (file, question_id, cls, mechanism, reason) in enumerate(sample, 1):
        qdir = DATA / file / f"q{question_id}"
        counterexample = json.loads((qdir / "counterexample.json").read_text())
        gold = json.loads((qdir / "evidence-gold.json").read_text())
        second = json.loads((qdir / "evidence-second.json").read_text())
        questions = {
            str(q["question_id"]): q
            for q in json.loads((DATA / file / "questions.json").read_text())
        }
        question = questions.get(str(question_id), {})
        differing = counterexample["differing_rows"]
        packet.append(
            {
                "item": item,
                "db_id": question.get("db_id"),
                "question": question.get("question"),
                "evidence": question.get("evidence"),
                "gold_sql": gold["executed_sql"],
                "prediction_sql": second["executed_sql"],
                "gold_result": _result(gold),
                "prediction_result": _result(second),
                "bird_ex": counterexample["bird_ex"],
                "verdict": counterexample["verdict"],
                "mechanism": counterexample["mechanism"],
                "differing_rows": {
                    k: (v[:25] if isinstance(v, list) else v) for k, v in differing.items()
                },
            }
        )
        key.append(
            {
                "item": item,
                "file": file,
                "question_id": question_id,
                "class": cls,
                "mechanism": mechanism,
                "reason": reason,
            }
        )
    out.mkdir(parents=True, exist_ok=True)
    (out / "packet.json").write_text(json.dumps(packet, indent=1, default=str))
    (out / "key.json").write_text(json.dumps(key, indent=1))
    print(f"class A rows with a question directory: {len(rows)}; sampled: {len(sample)}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else os.environ["SECOND_READER_OUT"]))
