"""The hand classification of the golds BIRD left alone that a probe fired on.

    MEASURE_WORK=<work-directory> python3 classify.py

measure.py splits the 1,534 questions into the 399 golds BIRD rewrote in its 2025-11-06 pass,
the 172 that differ only in text and the 963 it left alone, and writes the ids of the third
group a probe fired on to ``out/manual-rows.md``. There are 25 of them, under the 100 the phase
sets as the point where a sample replaces a full reading, so every one is read here rather than
sampled: no seed, no sample, the whole group.

The reading, applied to each in turn against the shipped data and the question as asked:

wrong     the gold does not answer its question on this data. Either it returns one row out of
          several the data does not choose between (so a different, equally correct statement
          scores 0), or it plainly answers a different question.
harmless  the probe fired on something real, and the answer is the same either way: the rows
          come back in another order, and BIRD compares them as a set.
rule      the probe's own rule, not the question's. The gold does what the question asks and the
          fire is a property of how this tool reads it.

``why`` states what was read, in this repository's own words: no gold text, question text or row
from BIRD is reproduced here (NOTICE). The evidence each verdict rests on is the run's own
``smells.json`` under the work directory, which stays there.
"""

import json
import os
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
OUT = WORK / "out"

CLASSIFICATION: dict[int, tuple[str, str]] = {
    30: (
        "wrong",
        "three cities tie at positions 3 to 5 of 1,022 with three different names; a LIMIT 5 returns two of the three and the data does not say which",
    ),
    57: (
        "wrong",
        "seven rows tie across positions 329 to 335 with seven different phone numbers; the 333rd is not a row the data picks out",
    ),
    81: (
        "wrong",
        "the ordering key is NULL in nine rows and SQLite sorts NULL first ascending, so the gold returns a school with no latitude rather than the lowest one, and nine different schools could come back",
    ),
    82: (
        "wrong",
        "two schools share the largest absolute longitude and offer different grade spans",
    ),
    392: (
        "wrong",
        "418 cards share the earliest ruling date; the gold's three are three of 418 and any other three answer the question as well",
    ),
    423: (
        "rule",
        "the ordering key is a text column holding only numbers, which the probe reads as a numeric column sorted as text, but the question asks for alphabetical order, which is what a text sort is",
    ),
    484: (
        "wrong",
        "the gold orders by converted mana cost and never cuts, returning all 155 Italian cards of the set where 12 carry the highest cost the question asks for",
    ),
    523: (
        "wrong",
        "the gold groups by release date and cuts at the largest language count, and several dates share that count; the projected average is a sum of ids divided by a count of ids divided by four, which is not an annual number of sets either",
    ),
    766: ("wrong", "63 rows tie on the largest strength value, 36 of them naming a different hero"),
    802: ("wrong", "two superheroes share the largest height"),
    847: (
        "wrong",
        "the qualifying time is NULL in six of the 22 rows and sorts first ascending, so the gold returns a driver who set no time in that period rather than the best one",
    ),
    879: (
        "wrong",
        "the ordering key is a text column of numbers, so 9.5 sorts above 10 and the fastest speed is not the one returned; reported upstream as mini_dev issue 24 and corrected in Mini-Dev's Hugging Face copy, still open in both copies of dev",
    ),
    893: (
        "harmless",
        "the top two drivers hold the same points, so a shuffled copy returns the same three drivers in another order and BIRD compares them as a set",
    ),
    906: (
        "wrong",
        "the gold orders by year and cuts at one, and 17 races share the first year, so which of that season's races comes back is arbitrary",
    ),
    927: (
        "wrong",
        "the same text-typed speed column as q879, with a NOT NULL filter added and the same wrong order",
    ),
    1002: (
        "wrong",
        "the join to the standings repeats each driver once per race, so 14 rows share the largest date of birth and name 14 different races",
    ),
    1004: (
        "wrong",
        "a bare SUM with no GROUP BY beside two ungrouped columns: the total is every driver's wins added together (7,890) and the name beside it is one arbitrary row's",
    ),
    1034: (
        "wrong",
        "three rows tie on the largest overall rating in that year and name two different players",
    ),
    1090: (
        "wrong",
        "the oldest player has four attribute rows, two of which carry a different long-passing score",
    ),
    1117: (
        "wrong",
        "three players tie at positions 8 to 10 of the weight order, so two of the ten ids are arbitrary",
    ),
    1144: (
        "wrong",
        "two players share the largest weight, and the one the subquery picks has 14 attribute rows carrying three different (finishing, curve) pairs, which the outer LIMIT 1 cuts without an ordering",
    ),
    1290: (
        "wrong",
        "four laboratory rows share the largest albumin value inside the stated range and carry four different dates",
    ),
    1365: (
        "wrong",
        "two budgets share the lowest remaining amount and carry different expense descriptions; the question asks for expenses and the gold returns one",
    ),
    1389: ("wrong", "three expenses share the lowest cost and belong to three different events"),
    1517: (
        "wrong",
        "ten transactions share the earliest date and belong to customers in three different segments",
    ),
}


def main() -> None:
    measurement = json.loads((OUT / "measurement.json").read_text())
    unchanged = set(measurement["split"]["unchanged"]["ids"])
    fired = set(measurement["copies"]["old"]["questions_with_a_smell"])
    expected = sorted(unchanged & fired)
    if expected != sorted(CLASSIFICATION):
        raise SystemExit(
            f"the group moved: {expected} against the classified {sorted(CLASSIFICATION)}"
        )
    questions = measurement["copies"]["old"]["questions"]
    rows = [
        {
            "question_id": question_id,
            "db": questions[str(question_id)]["db"],
            "probes": questions[str(question_id)]["smells"],
            "class": verdict,
            "why": why,
        }
        for question_id, (verdict, why) in sorted(CLASSIFICATION.items())
    ]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["class"]] = counts.get(row["class"], 0) + 1
    document = {
        "reading": (
            "Every gold BIRD left unchanged in its 2025-11-06 pass that a gold-only probe fired "
            "on, read by hand against the shipped data. 25 of them, under the 100 at which a "
            "sample would replace a full reading, so this is the whole group and not a sample. "
            "wrong: the gold does not answer its question on this data. harmless: the probe "
            "fired on something real and the answer is the same either way. rule: the tool's own "
            "rule, not the question's."
        ),
        "group": "the 963 golds unchanged between the 2024-06-27 copy and the 2025-11-06 pass",
        "sampled": False,
        "counts": counts,
        "rows": rows,
    }
    (OUT / "classification.json").write_text(json.dumps(document, indent=1) + "\n")
    print("classified:", counts)


if __name__ == "__main__":
    main()
