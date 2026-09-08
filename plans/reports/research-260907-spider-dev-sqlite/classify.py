"""Write the hand reading of a stated sample of uncorrected gold fires.

usage: MEASURE_WORK=<work-directory> python3 classify.py

The sample is every second id among the fires on golds whose SQL Spider did not correct. The
class is a hand judgement against the question and shipped database, not a restatement of the
probe: wrong means the gold does not answer its question on this data; harmless means the move
is real but any answer it produces satisfies the question; rule means only this tool's replay
rule cares.
"""

import json
import os
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"]).resolve()
OUT = WORK / "out"

READING = {
    26: ("wrong", "2015 and 2014 tie for the most concerts, so the year returned is arbitrary."),
    95: (
        "wrong",
        "17 car-name rows share minimum horsepower across seven model names, and a shuffle moves the answer from amc to mazda.",
    ),
    133: (
        "wrong",
        "eight car-name rows share maximum mpg across seven model names, and a shuffle moves the answer from citroen to saab.",
    ),
    165: (
        "wrong",
        "five rows share the largest four-cylinder horsepower across three model names.",
    ),
    229: ("wrong", "12 airlines tie for the most flights, so the named airline is arbitrary."),
    231: (
        "wrong",
        "12 airlines tie for the fewest flights, so the abbreviation returned is arbitrary.",
    ),
    261: (
        "harmless",
        "two employees tied on age swap positions, but the names are still in ascending age order.",
    ),
    311: (
        "wrong",
        "templates 25/PP, 14/AD and 11/BK tie for the most documents.",
    ),
    331: ("wrong", "template types PP and BK tie for the most templates."),
    375: (
        "wrong",
        "six documents tie at the least paragraph count, so the returned document id is arbitrary.",
    ),
    395: (
        "wrong",
        "seven hometowns have one teacher each, so the most common hometown is not decided.",
    ),
    421: (
        "wrong",
        "museums 2 and 4 tie for the most visits and carry different names.",
    ),
    458: (
        "harmless",
        "left-handed players tied on birth date can swap, while the result remains ordered by birth date.",
    ),
    484: (
        "wrong",
        "all three rows name Madison Keys with different ranks, and the third rank moves between 16 and 12 under a shuffle.",
    ),
    541: (
        "wrong",
        "students 7 and 6 tie at three enrolments, so the row returned is arbitrary.",
    ),
    547: (
        "wrong",
        "five course codes tie for the most enrolments, so the course name is arbitrary.",
    ),
    573: (
        "wrong",
        "six transcripts tie at the least result count and carry six dates.",
    ),
    613: (
        "harmless",
        "episodes tied on rating swap positions, but the list is still ordered by rating.",
    ),
    641: (
        "wrong",
        "grouping tv_channel by country returns one arbitrary channel id per qualifying country, and a shuffle moves 700 to 714.",
    ),
    695: (
        "wrong",
        "contestants 2 and 5 tie for the fewest votes and have different names.",
    ),
    740: (
        "wrong",
        "five countries tie for the largest language count, so the country name is arbitrary.",
    ),
    788: (
        "wrong",
        "seven countries tie at population zero, so the smallest-population country is arbitrary.",
    ),
    804: (
        "wrong",
        "seven countries tie at population zero and the query cuts that tie to three.",
    ),
    816: (
        "wrong",
        "eight countries tie at a top percentage of 0.0 between two languages each, and the bare max picks one language arbitrarily.",
    ),
    824: (
        "harmless",
        "conductors tied on age swap positions, while the list remains ascending by age.",
    ),
    828: (
        "harmless",
        "orchestras tied on founding year reorder, and the query asks only for a descending year order.",
    ),
    836: (
        "harmless",
        "conductors tied on years of work reorder, while the list remains descending by that key.",
    ),
    844: (
        "wrong",
        "12 conductors tie at one orchestra each, so the most prolific conductor is arbitrary.",
    ),
    878: ("wrong", "grades 9 to 12 tie in highschooler count, so the returned grade is arbitrary."),
    906: (
        "wrong",
        "10 highschooler rows tie at the largest like count across nine names, and a shuffle moves John to Kyle.",
    ),
}


def main() -> None:
    gold_only = json.loads((OUT / "gold-only.json").read_text(encoding="utf-8"))
    corrections = json.loads((OUT / "corrections.json").read_text(encoding="utf-8"))
    corrected = {row["question_id"] for row in corrections["correction_set"]}
    population = [
        question_id
        for question_id in gold_only["passes"]["current"]["ids_with_a_smell"]
        if question_id not in corrected
    ]
    sample = population[::2]
    if sample != sorted(READING):
        raise SystemExit(f"the sampled fires moved: {sample} against {sorted(READING)}")
    questions = gold_only["passes"]["current"]["questions"]
    rows = []
    for question_id in sample:
        verdict, why = READING[question_id]
        row = questions[str(question_id)]
        rows.append(
            {
                "question_id": question_id,
                "db": row["db"],
                "probes": row["smells"],
                "class": verdict,
                "why": why,
            }
        )
    document = {
        "reading": (
            "A hand reading against the question and shipped data. wrong: the gold does not answer "
            "its question on this data. harmless: the detected move is real but every produced "
            "answer satisfies the question. rule: only this tool's replay rule cares."
        ),
        "population": "fires on golds whose SQL Spider did not correct",
        "population_size": len(population),
        "sample_rule": "every second id in ascending order",
        "sampled": True,
        "counts": dict(sorted(Counter(row["class"] for row in rows).items())),
        "rows": rows,
    }
    (OUT / "classification.json").write_text(
        json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(document["counts"])


if __name__ == "__main__":
    main()
