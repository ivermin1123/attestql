"""Rewrite a BIRD positional prediction file as one keyed by question id.

BIRD's ``predict_mini_dev_*_sqlite.json`` files are keyed ``"0"``..``"499"``: the position of
the entry in the question file the model answered, which is the GitHub zip's
``mini_dev_sqlite.json`` (500 entries; ids 137 and 138 appear twice). The Hugging Face file
holds the same 498 entries in the same order with the two repeats removed and ids 119 and 120
appended, so a position past 486 names a different question in each file. Keying by id removes
that ambiguity: the id is read off the zip entry the position names, the lowest position wins
when an id repeats, and the later positions are listed beside the output so that nothing is
silently dropped.

The sibling of the same script in ``plans/reports/prediction-mode-260904-real-predictions/``,
which reads the PostgreSQL question file. The file to read the ids off is an argument here,
because a copy that differed only in a constant would be two things to keep in step.

    predictions_by_question_id.py <questions.json> <bird-predictions.json> <out-by-id.json>
"""

import json
import sys
from pathlib import Path


def main() -> None:
    questions, source, target = (Path(argument) for argument in sys.argv[1:4])
    entry_ids = [entry["question_id"] for entry in json.load(questions.open())]
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
