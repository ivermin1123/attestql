"""Write the hand judgements for the sample selected by sample_rows.py.

The gold and prediction row counts are taken from the recorded results; the class, the
distinct prediction row count and the one-sentence reason are hand-written.
"""

import json
import os
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
OUT = WORK / "out"

RULE = (
    "Each row was read by hand from the question, both statements, both results and the "
    "tool's differing-row summary; q635 and q44 were also checked in the database. A is a "
    "wrong answer the benchmark credited: a different question answered, a scalar "
    "repeated per row of an unrelated table, or the things asked for (names, ids, "
    "patients, events) listed at least twice over. B is harmless: one distinct row "
    "repeated, DISTINCT added to the gold's answer, or a list under twice the answer's "
    "length with every row present. C is the tool's rule alone: the same value under "
    "another declared type or storage class. The twice line is applied as written, so "
    "2.2x and 2.35x rows (q1220, q758, q1447) are A."
)
REPLACED_NOTE = (
    "A first pass classed 49 rows B by template; this row-by-row reading replaced it on 2026-09-08."
)

# A: wrong answer BIRD credited. B: harmless answer. C: AttestQL's typed rule alone.
# The third element is the number of distinct prediction rows, read over the full result;
# where the recorded result holds every row it is checked against a recount.
JUDGEMENTS: dict[tuple[str, str, int], tuple[str, str, int]] = {
    ("alpha-sql-dev.json", "dev1106", 101): (
        "B",
        "Earliest 1995 accounts: 315 distinct ids, prediction 359 rows (44 repeats), under twice, all present.",
        315,
    ),
    ("alpha-sql-dev.json", "dev1106", 1212): (
        "B",
        "Inpatient or outpatient: gold 10,778 rows over 3 values, prediction adds DISTINCT and returns the 3.",
        3,
    ),
    ("alpha-sql-dev.json", "old", 845): (
        "B",
        "Powers of heroes above 80% of mean height: gold 472 rows over 104 names, prediction DISTINCT returns 104.",
        104,
    ),
    ("atlas-core-20260301.sql", "dev1106", 473): (
        "B",
        "Yes or no for one card set: gold 5 rows of NO (one per printing), prediction DISTINCT returns one NO.",
        1,
    ),
    ("atlas-core-20260301.sql", "old", 483): (
        "B",
        "Italian rulings of Coldsnap: 149 distinct texts, prediction 155 rows (empty text 5 more), under twice.",
        149,
    ),
    ("atlas-core-20260324.sql", "dev1106", 407): (
        "B",
        "Types of German cards: gold 1,693 rows over 408 (subtypes, supertypes), prediction DISTINCT returns 408.",
        408,
    ),
    ("atlas-core-20260324.sql", "old", 521): (
        "B",
        "Status of one card in legacy: gold one row Banned, prediction Banned twice (two legality rows).",
        1,
    ),
    ("csc-sql-32b.sql", "dev1106", 452): (
        "A",
        "Cards with a text box: 21,738 distinct names, prediction 56,707 rows (Forest 691x); 2.6x, asks for names.",
        21738,
    ),
    ("csc-sql-32b.sql", "dev1106", 1447): (
        "A",
        "Events that underspend: 20 distinct (name, location), prediction 47 rows, one per budget line; 2.35x.",
        20,
    ),
    ("csc-sql-32b.sql", "old", 1088): (
        "A",
        "Players with volleys and dribbling over 70: 1,105 distinct names, prediction 15,429 rows per snapshot; 14x.",
        1105,
    ),
    ("csc-sql-7b.sql", "dev1106", 481): (
        "B",
        "Languages with flavor text for one card: gold 15 rows over 8 languages, prediction DISTINCT returns 8.",
        8,
    ),
    ("csc-sql-7b.sql", "dev1106", 1503): (
        "A",
        "Products bought in EUR: 7 distinct descriptions, prediction 66 rows (Diesel 41x), one per transaction; 9x.",
        7,
    ),
    ("csc-sql-7b.sql", "old", 1059): (
        "A",
        "Players taller than 180: gold 7,258 names (7,165 distinct), prediction joins attributes, 120,895 rows; 17x.",
        7165,
    ),
    ("dail-sql-gpt-4-7shot-mask-thr-0.8.txt", "dev1106", 452): (
        "A",
        "Cards with a text box: 21,738 distinct names, prediction 56,707 rows (Forest 691x); 2.6x, asks for names.",
        21738,
    ),
    ("dail-sql-gpt-4-7shot-mask-thr-0.8.txt", "old", 275): (
        "A",
        "Molecules with a double bond: 370 distinct ids, prediction 1,844 rows, one per bond (TR397 26x); 5x.",
        370,
    ),
    ("dail-sql-gpt-4-7shot-mask-thr-0.8.txt", "old", 1514): (
        "B",
        "Currency at one timestamp: gold one row CZK, prediction CZK three times (three transactions).",
        1,
    ),
    ("dail-sql-gpt-4-7shot-mask-thr-0.85.txt", "dev1106", 1220): (
        "A",
        "Patients with UN = 29: 20 distinct (ID, sex, birthday), prediction 44 rows, one per lab test; 2.2x.",
        20,
    ),
    ("dail-sql-gpt-4-7shot-mask-thr-0.85.txt", "old", 1066): (
        "B",
        "Passing class of CLB: gold one row Mixed, prediction Mixed six times (six attribute snapshots).",
        1,
    ),
    ("dail-sql-gpt-4-7shot-questionmask.txt", "dev1106", 854): (
        "B",
        "Australian GP circuit coordinates: gold one (lat, lng), prediction the same pair 11 times, once per race.",
        1,
    ),
    ("dail-sql-gpt-4-7shot-questionmask.txt", "old", 681): (
        "B",
        "Names with 20,000-view posts in 2011: gold 24 rows over 23 names (PhD twice), prediction DISTINCT, 23.",
        23,
    ),
    ("dail-sql-gpt-4-9shot-mask-thr.txt", "dev1106", 407): (
        "B",
        "Types of German cards: gold 1,693 rows over 408 (subtypes, supertypes), prediction DISTINCT returns 408.",
        408,
    ),
    ("dail-sql-gpt-4-9shot-mask-thr.txt", "old", 206): (
        "B",
        "Elements of bond TR004_8_9: gold one row c, prediction c twice (both atoms are carbon).",
        1,
    ),
    ("dail-sql-gpt-4-9shot-mask-thr.txt", "old", 1435): (
        "B",
        "Closed game events in the window: 2 distinct names, prediction 3 rows (Football game twice), under twice.",
        2,
    ),
    ("dail-sql-gpt-4-9shot-questionmask.txt", "dev1106", 1214): (
        "A",
        "Patients with TP below 6: 68 distinct (ID, sex, birthday), prediction 544 rows, one per lab test; 8x.",
        68,
    ),
    ("dail-sql-gpt-4-9shot-questionmask.txt", "old", 1071): (
        "B",
        "Team short name for one attribute triple: gold one row GLA, prediction GLA twice (two snapshots).",
        1,
    ),
    ("gsr-gpt-4o.sql", "dev1106", 610): (
        "A",
        "Badges of the top-reputation user: 80 distinct names, prediction 456 rows (Nice Answer 205x); 5.7x.",
        80,
    ),
    ("gsr-gpt-4o.sql", "old", 229): (
        "B",
        "Bond type of molecule TR000: gold one row '-', prediction '-' four times (four bonds).",
        1,
    ),
    ("gsr-gpt-4o.sql", "old", 1071): (
        "B",
        "Team short name for one attribute triple: gold one row GLA, prediction GLA twice (two snapshots).",
        1,
    ),
    ("predict_dev-codes-15b-bird-with-evidence.json", "dev1106", 868): (
        "B",
        "Malaysian GP circuit coordinates: gold one (lat, lng), prediction the same pair 19 times, once per race.",
        1,
    ),
    ("predict_dev-codes-15b-bird-with-evidence.json", "old", 522): (
        "A",
        "EDHRec rank-1 cards and banned formats: gold 2 grouped (Sol Ring, format) rows, prediction 66, each 33x.",
        2,
    ),
    ("predict_dev-codes-15b-bird.json", "dev1106", 355): (
        "B",
        "Keyword on Angel of Mercy: gold one row Flying, prediction Flying 15 times (15 printings).",
        1,
    ),
    ("predict_dev-codes-15b-bird.json", "old", 321): (
        "B",
        "Molecule of atoms TR000_2 and TR000_4: gold one row TR000 via the bond, prediction TR000 twice via atom.",
        1,
    ),
    ("predict_dev-codes-1b-bird-with-evidence.json", "dev1106", 449): (
        "A",
        "Language and type of azorius cards: 250 distinct pairs, prediction 1,035 rows, one per translation; 4x.",
        250,
    ),
    ("predict_dev-codes-1b-bird-with-evidence.json", "old", 355): (
        "B",
        "Keyword on Angel of Mercy: gold one row Flying, prediction Flying 15 times (15 printings).",
        1,
    ),
    ("predict_dev-codes-1b-bird.json", "dev1106", 316): (
        "A",
        "Non-carcinogenic molecules with c: 189 distinct ids, prediction 2,000 rows, one per carbon atom; 10x.",
        189,
    ),
    ("predict_dev-codes-1b-bird.json", "old", 635): (
        "A",
        "Posts by Matt Parker with over 4 votes: prediction counts his 5 bounty votes with BountyAmount > 4 instead.",
        1,
    ),
    ("predict_dev-codes-3b-bird-with-evidence.json", "dev1106", 758): (
        "A",
        "Hair colour of 185 cm human heroes: 5 distinct colours, prediction 11 rows, one per hero; 2.2x, at threshold.",
        5,
    ),
    ("predict_dev-codes-3b-bird-with-evidence.json", "old", 390): (
        "B",
        "Colors and formats of cards 1 to 20: gold 157 rows over 24 pairs, prediction DISTINCT returns the 24.",
        24,
    ),
    ("predict_dev-codes-3b-bird.json", "dev1106", 257): (
        "B",
        "atom_id2 for sulfur atoms: 268 distinct ids, prediction 287 rows (19 repeats), under twice, all present.",
        268,
    ),
    ("predict_dev-codes-3b-bird.json", "old", 44): (
        "C",
        "One row (435, Los Angeles) both sides; INTEGER 435 vs AVG() REAL 435.0; NumTstTakr picks the same record.",
        1,
    ),
    ("predict_dev-codes-3b-bird.json", "old", 1449): (
        "A",
        "Members with an expense over 100: 2 distinct (name, major) rows, prediction 6, each member 3 times; 3x.",
        2,
    ),
    ("predict_dev-codes-7b-bird-with-evidence.json", "dev1106", 1209): (
        "A",
        "Diagnoses with GPT > 60: 38 distinct, prediction 871 rows (SLE 281x) per lab test, ordered DESC not ASC; 23x.",
        38,
    ),
    ("predict_dev-codes-7b-bird-with-evidence.json", "old", 1054): (
        "B",
        "Defensive work rate of David Wilson: gold one row medium, prediction medium 13 times (13 snapshots).",
        1,
    ),
    ("predict_dev-codes-7b-bird.json", "dev1106", 622): (
        "B",
        "Badges Sharpie obtained: 21 distinct names, prediction 32 rows (Yearling 4x), under twice, all present.",
        21,
    ),
    ("predict_dev-codes-7b-bird.json", "old", 521): (
        "B",
        "Status of one card in legacy: gold one row Banned, prediction Banned twice (two legality rows).",
        1,
    ),
    ("rsl-sql-deepseek.txt", "dev1106", 452): (
        "A",
        "Cards with a text box: 21,738 distinct names, prediction 56,707 rows (Forest 691x); 2.6x, asks for names.",
        21738,
    ),
    ("rsl-sql-deepseek.txt", "old", 258): (
        "B",
        "Bond types for tin atoms: gold one row '-', prediction '-' eight times (eight bonds).",
        1,
    ),
    ("rsl-sql-deepseek.txt", "old", 1244): (
        "B",
        "Patients after 1992 with PT < 14: gold 219 rows over 48 ids, prediction adds DISTINCT and returns the 48.",
        48,
    ),
    ("rsl-sql-gpt-4o.txt", "dev1106", 1051): (
        "B",
        "Player with the highest potential: gold one row Lionel Messi, prediction Messi six times (six snapshots).",
        1,
    ),
    ("rsl-sql-gpt-4o.txt", "old", 470): (
        "B",
        "Release dates of sets with Ancestor's Chosen: 3 distinct dates, prediction 4 rows (one twice), under twice.",
        3,
    ),
}


def distinct_rows(result: dict, recorded: int, key: tuple[str, str, int]) -> int:
    if not result["truncated"] and result["row_count"] == len(result["rows"]):
        recount = len({json.dumps(row, sort_keys=True) for row in result["rows"]})
        if recount != recorded:
            raise SystemExit(f"distinct rows for {key}: recorded {recorded}, recount {recount}")
    return recorded


def main() -> None:
    sample = json.loads((OUT / "classification-input.json").read_text(encoding="utf-8"))
    counts: Counter = Counter()
    rows = []
    for evidence in sample["rows"]:
        key = (evidence["file"], evidence["copy"], evidence["question_id"])
        judged = JUDGEMENTS.get(key)
        if judged is None:
            raise SystemExit(f"no hand judgement for {key}")
        classification, reason, distinct = judged
        counts[classification] += 1
        rows.append(
            {
                "file": evidence["file"],
                "copy": evidence["copy"],
                "question_id": evidence["question_id"],
                "db": evidence["db"],
                "mechanism": evidence["mechanism"],
                "test_suite_ex": evidence["test_suite_ex"],
                "gold_rows": evidence["gold_result"]["row_count"],
                "prediction_rows": evidence["prediction_result"]["row_count"],
                "distinct_rows": distinct_rows(evidence["prediction_result"], distinct, key),
                "class": classification,
                "reason": reason,
            }
        )
    total = sum(counts.values())
    document = {
        "rule": RULE,
        "first_pass": REPLACED_NOTE,
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
