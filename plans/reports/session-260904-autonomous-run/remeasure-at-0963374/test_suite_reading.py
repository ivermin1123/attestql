"""The test-suite reading over the 170 rows the research report R-A applied six readings to.

R-A (`plans/reports/research-260904-result-readings/`) re-executed the 170 EX=1 and NOT_EQUAL
pairs of the run at `41621c0` and found test-suite's `result_eq` refusing 37 of them, with the
DISTINCT strip the evaluator performs. The tool now records `test_suite_ex` on the rows it
fetched, without that strip. This reads, from a finished `reproduce.sh` work directory, the
counterexample of each of the same 170 pairs on the Hugging Face gold and counts what the
recorded reading says, by hand class and against `bird_ex` of the same file.

usage: test_suite_reading.py <pairs.json> <results.json> <work-dir> <out.json>
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> None:
    pairs_path, results_path, work, out = (Path(argument) for argument in sys.argv[1:5])
    pairs = json.loads(pairs_path.read_text(encoding="utf-8"))
    stripped = {
        (row["model"], row["question_id"]): row["test_suite"]
        for row in json.loads(results_path.read_text(encoding="utf-8"))
    }
    rows: list[dict[str, object]] = []
    for pair in pairs:
        model, question_id = pair["model"], pair["question_id"]
        path = work / "out" / "tool" / "hf" / model / f"q{question_id}" / "counterexample.json"
        if not path.exists():
            rows.append({"model": model, "question_id": question_id, "missing": True})
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "model": model,
                "question_id": question_id,
                "class": pair["class"],
                "verdict": document["verdict"]["result"],
                "bird_ex": document["bird_ex"]["value"],
                "test_suite_ex": document["test_suite_ex"]["value"],
                "order_matters": document["test_suite_ex"]["order_matters"],
                "test_suite_stripped_r_a": stripped.get((model, question_id)),
            }
        )
    found = [row for row in rows if "missing" not in row]
    refused = [row for row in found if row["test_suite_ex"] == 0]
    refused_and_credited = [row for row in refused if row["bird_ex"] == 1]
    summary = {
        "pairs": len(pairs),
        "found": len(found),
        "missing": len(rows) - len(found),
        "bird_ex_1": sum(1 for row in found if row["bird_ex"] == 1),
        "test_suite_ex_0": len(refused),
        "test_suite_ex_0_by_class": dict(Counter(str(row["class"]) for row in refused)),
        "bird_ex_1_and_test_suite_ex_0": len(refused_and_credited),
        "bird_ex_1_and_test_suite_ex_0_by_class": dict(
            Counter(str(row["class"]) for row in refused_and_credited)
        ),
        "r_a_stripped_test_suite_false": sum(1 for value in stripped.values() if value is False),
        "agree_with_r_a_stripped": sum(
            1
            for row in found
            if (row["test_suite_ex"] == 1) == bool(row["test_suite_stripped_r_a"])
        ),
        "verdicts": dict(Counter(str(row["verdict"]) for row in found)),
    }
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
