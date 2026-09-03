"""Rewrite a BIRD positional prediction file as one keyed by question id.

BIRD's ``predict_mini_dev_*_postgresql.json`` files are keyed ``"0"``..``"499"``: the position
of the entry in the question file the model answered, which is the GitHub zip's
``mini_dev_postgresql.json`` (500 entries; ids 137 and 138 appear twice, at positions 484/487 and
485/488). The Hugging Face file holds the same 498 entries in the same order with the two
repeats removed and ids 119 and 120 appended, so a position past 486 names a different question
in each file. Keying by id removes that ambiguity: the id is read off the zip entry the position
names, the lowest position wins when an id repeats, and the later positions are listed beside the
output so that nothing is silently dropped.

usage: predictions_by_question_id.py <bird-predictions.json> <out-by-id.json>
"""

import json
import os
import sys
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])  # the work directory reproduce.sh fills
ZIP_QUESTIONS = WORK / "data/zip/minidev/MINIDEV/mini_dev_postgresql.json"


def main() -> None:
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    entry_ids = [e["question_id"] for e in json.load(ZIP_QUESTIONS.open())]
    document = json.load(source.open())
    by_id: dict[str, str] = {}
    unused: list[int] = []
    for key in sorted(document, key=int):
        question_id = str(entry_ids[int(key)])
        if question_id in by_id:
            unused.append(int(key))
            continue
        by_id[question_id] = document[key]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(by_id, indent=1, ensure_ascii=False))
    print(f"{source.name}: {len(by_id)} ids, positions not used {unused}")


if __name__ == "__main__":
    main()
