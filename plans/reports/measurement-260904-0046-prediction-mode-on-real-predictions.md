# Measurement: prediction mode on BIRD's own Mini-Dev predictions

Date: 2026-09-04, on the tree at `dfb0c96` (`a3bac13` records where both input files came from and
reads BIRD's positional files; `dfb0c96` stops a bare `SELECT` from ending a run; both found here).
Server: PostgreSQL 16.15, `postgres@sha256:c1b378...`, a throwaway container removed afterwards.
Every run's `summary.json`, BIRD's own scoring, the verdicts, the counts, the hand classification
and four counterexamples are in `prediction-mode-260904-real-predictions/`; `reproduce.sh` there rebuilds all of it.

## Inputs

Gold, canonical: `birdsql/bird_mini_dev`, `data/mini_dev_pg-00000-of-00001.json`, commit
`f65faf4a`, sha256 `7fa740ef...`, 2026-01-18. Gold, GitHub zip: `minidev.zip` (`cc48ba16...`),
members `minidev/MINIDEV/mini_dev_postgresql.json` (`d2731292...`) and `_gold.sql`
(`8922d94a...`), 2024-06-19. Predictions: the nine
`llm/exp_result/sql_output_kg/predict_mini_dev_*_postgresql.json` of `bird-bench/mini_dev` at
`b3d4bcbb`, added 2024-06-19 (`8c7df91a`) and unchanged since, each sha256 in `reproduce.sh`.
BIRD's evaluator: `evaluation/evaluation_utils.py` (`f6943d24...`) and `evaluation_ex.py`
(`da1bbcd4...`) at the same commit, 2024-10-25. The corrected golds for q1029, q879 and q207 are
`tools/audit-sandbox/predictions.json`. `bird-bench/mini_dev` has no LICENSE file; its README
badge says CC BY-SA 4.0 and calls the prediction files reference output. None of its files is
committed; the four counterexamples that quote a question, a gold and a prediction are in `NOTICE`.

**Pairing.** BIRD's files are keyed `"0"`..`"499"` by position in the zip's question file, and its
script pairs prediction `i` with gold line `i`; the zip runs read them with
`--predictions-keyed-by position`. The Hugging Face file drops the zip's repeats of 137 and 138 and
appends 119 and 120, so a position past 486 names another question there; the Hugging Face runs use
the same files re-keyed by id through the zip's order (`predictions_by_question_id.py`), the lowest
position winning where 137 and 138 repeat (487 and 488 unused; in 4 of 9 files those answers
differ). **BIRD's reading** is the tool's `bird_ex` (EQUAL is 1, ERROR is 0 as BIRD scores an
exception); **the cross-check** imports BIRD's `execute_sql` and `calculate_ex` verbatim, only the
connection replaced.

## Per file, Hugging Face gold

| Model | Compared | EX=1 | EX=0 | ERROR | BIRD's script | Agree | EX=1 and NOT_EQUAL | A / B / C |
|---|---|---|---|---|---|---|---|---|
| gpt-35-turbo-instruct | 309 | 134 | 175 | 189 | 134 | 497 of 498 | 19 | 9 / 8 / 2 |
| gpt-35-turbo | 313 | 138 | 175 | 185 | 138 | 498 of 498 | 23 | 10 / 11 / 2 |
| gpt-4-32k | 364 | 177 | 187 | 134 | 178 | 495 of 498 | 25 | 9 / 9 / 7 |
| gpt-4-turbo | 370 | 182 | 188 | 128 | 183 | 497 of 498 | 28 | 9 / 14 / 5 |
| gpt-4 | 376 | 183 | 193 | 122 | 182 | 496 of 498 | 19 | 6 / 8 / 5 |
| llama-3-70b-instruct | 340 | 148 | 192 | 158 | 149 | 497 of 498 | 19 | 8 / 9 / 2 |
| llama-3-8b-instruct | 240 | 93 | 147 | 258 | 93 | 498 of 498 | 12 | 8 / 3 / 1 |
| mixtral-8x7b-instruct | 170 | 73 | 97 | 328 | 73 | 498 of 498 | 14 | 6 / 6 / 2 |
| phi-3-medium-128k | 279 | 112 | 167 | 219 | 111 | 497 of 498 | 11 | 4 / 6 / 1 |
| all nine | 2,761 | 1,240 | 1,521 | 1,721 | 1,241 | 4,473 of 4,482 | 170 | 69 / 74 / 27 |

The 1,721 errors are the predictions' own (1,260 failed on the server, 444 did not parse, 17 named
a missing table). On the zip gold BIRD's script scores 135, 139, 179, 183, 182, 150, 93, 73 and 111
here, 1 to 11 above what the `mini_dev` README publishes per file, without naming server or gold.

**Cross-check.** 4,473 of 4,482 readings agree (99.8 %; 4,471 on the zip), and every disagreement
is one of two things. Six rows on each gold return the same number as `float8` on one side and
`numeric` on the other (q1057, q800 twice, q168, q960 twice): psycopg2 hands BIRD a `float` and a
`Decimal`, unequal in Python unless the float is exact, so BIRD scores 0 where the tool's set reading
over its own decimal-loaded values says 1; the typed verdict on all six is NOT_EQUAL by type
([q1057](prediction-mode-260904-real-predictions/examples/hf-gpt-35-turbo-instruct-q1057/counterexample.json)).
The rest is q1473, three files (five on the zip): a `SUM` over `float8` whose last digits depend on
summation order, so both harnesses flip between runs; the `float-aggregate-order` smell fires on it.

## Among EX=1: how many are loose, and what they are

170 of 1,240 (13.7 %). By mechanism: 138 return the gold's distinct rows with other multiplicities,
32 the same values under another declared type, 0 differ only in row order (none did, over 25 to 65
compared R-ORD golds per file), 0 by truncation (results are never bounded). Column names differ in
165 of the 1,070 EQUAL rows and decided nothing. All 170 rows (56 distinct questions) were
classified by hand; the rule and every reason are in `classify.py`:

| Class | Rows | Questions | What it means |
|---|---|---|---|
| A: a wrong answer the benchmark credited | 69 | 24 | another table or projection; a scalar repeated per row of an unrelated table; a list at least twice the answer's length where the question asks for the things, not the rows |
| B: harmless | 74 | 20 | one distinct row repeated; DISTINCT added by the prediction; a list under twice the answer with every row present |
| C: the tool's rule, not the question's | 27 | 12 | the same number as `int8` against `numeric` or `float8` against `numeric` |

**Precision of NOT_EQUAL on BIRD-credited predictions: 69 of 170 (40.6 %) are wrong answers; 143
of 170 (84.1 %) are real differences in the rows.** Per file, A alone runs from 31.6 % (gpt-4) to
66.7 % (llama-3-8b): under half of what the tool flags among credited predictions is a wrong answer,
the rest is duplicated rows a reader would forgive, and a sixth is the typed rule itself, which BIRD
credits 21 times of 27 and refuses 6 times by the float accident above. Of the 1,240 credited
predictions, 69 (5.6 %) are wrong answers by this reading.

## Among EX=0: unjust zeros, against the three known corrections

Four unjust zeros by BIRD's own reading: gpt-4 and gpt-4-turbo on q1029 and on q207, 0 against both
shipped golds and 1 against the correction (gpt-4-turbo's q207 set-equal with duplicated rows); 4
of 1,521 EX=0 rows, counted only where a correction exists. The reverse is larger:
gpt-35-turbo-instruct and gpt-35-turbo score 1 on q207 by reproducing the gold's wrong join, and
they, gpt-4-32k and llama-3-70b score 1 on q879 on the zip by reproducing its text ordering, 0 on
the Hugging Face gold: 6 unjust ones on the zip, 2 on HF. **Zip against Hugging Face**, same predictions:
eight verdicts in nine files change with the copy of the gold, q879 from 1 to 0 in four files
(gpt-35-turbo-instruct, gpt-35-turbo, gpt-4-32k, llama-3-70b) and q1322 from 0 to 1 in three
(gpt-4-turbo, gpt-4, phi-3); q1473 changes once (phi-3) by summation order, not by the gold; 119
and 120 have no prediction and audit gold-only. For `mini_dev` issue 40.

## Three rows

1. q565, llama-3-70b ([counterexample](prediction-mode-260904-real-predictions/examples/hf-meta-llama-3-70b-instruct-2-q565/counterexample.json)):
   the gold returns a "well-finished" label, the prediction a `bool`; both return no row on this
   data, so BIRD credits an answer to another question. NOT_EQUAL by type. Class A.
2. q1035, gpt-4 ([counterexample](prediction-mode-260904-real-predictions/examples/hf-gpt-4-q1035/counterexample.json)):
   161 distinct team ids against 356 rows; the question asks for the teams. BIRD 1. Class A.
3. q1473, phi-3, zip run ([counterexample](prediction-mode-260904-real-predictions/examples/zip-phi-3-medium-128k-instruct-1-q1473/counterexample.json)):
   `SUM` over `float8`, 459.95626421124297 against 459.95626421124325, NOT_EQUAL and BIRD 0; the
   Hugging Face run of the same pair agrees to sixteen digits, EQUAL and BIRD 1.

## What the tool did not catch

- A prediction that differs from the gold in meaning and returns the same multiset on the shipped
  rows: q173 reads `trans` for `order` and was seen only because a join multiplied its one row.
- Wrong golds beyond the three with a correction, and how wrong an EX=0 prediction is: the
  differing rows are recorded, nothing is measured over them.

## Gaps found while using it

1. BIRD's positional files were paired by id, silently (fixed, `a3bac13`); a bare `SELECT` as a
   prediction ended the whole run with a traceback (fixed, `dfb0c96`).
2. Open: the tool's BIRD reading disagrees with BIRD's harness on `float8` against `numeric` rows
   (six of 4,482), so `bird_ex` should adapt float columns as psycopg2 does; neither the summary
   line nor `summary.json` counts EX=1 and NOT_EQUAL; an ERROR line does not name the failed side.

## Note, 2026-09-04 evening

The whole measurement was rerun at `cf0b033` and the agreement number moved: 4,478 of 4,482 on the
Hugging Face gold and 4,473 on the zip, against 4,473 and 4,471 here. The tool's reading of BIRD's
EX now loads float columns as psycopg2 does, so the six `float8` against `numeric` rows agree and
leave the EX=1 and NOT_EQUAL set, which falls to 164 (138 multiplicity, 26 type; hand classes
69/74/21); q1473 is EQUAL and read 1 on more files now that every statement runs without parallel
workers; and q707 of `meta-llama-3-70b` leaves the compared set as a timeout under its serial plan,
so the errors are 1,722. The numbers above are left as they were measured: they are the record of
the run at `41621c0`. The rerun and its comparison are in
`plans/reports/session-260904-autonomous-run/remeasure-at-cf0b033/`.
