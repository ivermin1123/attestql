# Measurement: BIRD Mini-Dev on SQLite, gold-only and prediction mode

Date 2026-09-07, tree at `73ec41d`. SQLite 3.53.4 as Python 3.13.7 links it, `mode=ro` under `PRAGMA query_only`, no
server and no container; parser sqlglot 30.18.0. The artifact and `reproduce.sh`, which takes `MEASURE_WORK` from the
environment, are in `minidev-sqlite-260907/`; that directory (`~/.cache/attestql-measure/minidev-sqlite`) is reusable
by the next phase, which reads the same eleven databases, and deletable after.

## Inputs and method

Gold, canonical: `birdsql/bird_mini_dev`, `data/mini_dev_sqlite-00000-of-00001.json`, `f65faf4a`, sha256
`88ceb071...`, 2026-01-18. Gold, zip: `minidev.zip` (`cc48ba16...`), members `mini_dev_sqlite.json` (`4ba5fa8d...`,
500 entries, 137 and 138 duplicated, 119 and 120 absent), `mini_dev_sqlite_gold.sql` (`6fb891aa...`), eleven
`dev_databases/<db_id>.sqlite`. Predictions: nine `sql_output_kg/predict_mini_dev_*_sqlite.json` of
`bird-bench/mini_dev` at `b3d4bcbb`, sha256s in `SHA256SUMS.predictions`. Evaluator `evaluation_utils.py`
(`f6943d24...`) and `evaluation_ex.py` (`da1bbcd4...`), same commit, SQLite path unmodified. Corrected golds for
q1029, q879, q207: `tools/audit-sandbox-sqlite/predictions.json`. No BIRD file is committed. Zip runs key predictions
by position, Hugging Face by id through the zip's order (487 and 488 unused). **BIRD's reading** is `bird_ex` (EQUAL
1, ERROR 0 as BIRD scores an exception); **the cross-check** is BIRD's own `execute_sql` and `calculate_ex`, verbatim.

One `--dsn` is one file and a question file names eleven databases, so one (copy, file) is eleven runs: 2 x 10 x 11 =
220. **Merge rule**, here and in `measure.py`: the eleven summaries' counts summed, per-question lines concatenated,
run ids listed; no id appears twice. **Three processes at a time, across everything**, because a statement's budget
here is wall clock (`audit/sqlite.py`), so a starved process reports a timeout it did not earn. Under the cap 40 of
the 220 runs held a timeout line, each was rerun alone into a fresh directory (`rerun_timeouts.sh`, under-load answer
kept as `<db>.under-load`), and **all 40 survived**: golds q518 and q701, 40 s and 41 s alone with that statement past
the 30 s budget, and predictions q138, q682, q1040, q1472, on both copies.

## Per file, Hugging Face gold

| Model | Compared | EX=1 | EX=0 | ERROR | BIRD's script | Agree | EX=1 and NOT_EQUAL |
|---|---|---|---|---|---|---|---|
| gpt-35-turbo-instruct | 372 | 169 | 203 | 126 | 170 | 498 of 498 | 26 |
| gpt-35-turbo | 410 | 190 | 220 | 88 | 191 | 498 of 498 | 27 |
| gpt-4-32k | 460 | 236 | 224 | 38 | 237 | 498 of 498 | 32 |
| gpt-4-turbo | 422 | 219 | 203 | 76 | 219 | 497 of 498 | 29 |
| gpt-4 | 472 | 243 | 229 | 26 | 244 | 498 of 498 | 32 |
| llama-3-70b-instruct | 440 | 205 | 235 | 58 | 206 | 498 of 498 | 29 |
| llama-3-8b-instruct | 311 | 124 | 187 | 187 | 124 | 498 of 498 | 21 |
| mixtral-8x7b-instruct | 248 | 107 | 141 | 250 | 107 | 498 of 498 | 16 |
| phi-3-medium-128k | 366 | 157 | 209 | 132 | 157 | 498 of 498 | 25 |
| all nine | 3,501 | 1,650 | 1,851 | 981 | 1,655 | 4,481 of 4,482 | 237 |

4,482 slots per copy; Hugging Face audits 4,500 questions, the extra 18 being 119 and 120, which have no prediction.
The 981 errors: 959 the predictions' own, 15 the golds' (q518, q701 timing out), 7 a prediction naming a missing
table; by step 660 failed to execute, 314 did not parse, 7 stopped in the row counts. The zip gold gives 1,652 EX=1,
1,657 by BIRD's script, the same 237 and 4,481. **Cross-check**: 4,481 of 4,482 agree on each copy (99.98 %) against
4,476 on PostgreSQL, because here the tool reads the cells BIRD's evaluator reads. The one disagreement is q31 of
gpt-4-turbo, on both copies: gold `CAST(... AS REAL) / ...` returns 0.1344364012409514, the prediction reads the
stored column, 0.134436401240951. BIRD compares the doubles and scores 0; this tool renders a REAL at six decimal
places, so both are `0.134436` and the verdict EQUAL.

## Among EX=1: how many are loose, and what they are

237 of 1,650 (14.4 %), the same 237 on the zip. By mechanism, as the summaries count them: 230 give the gold's
distinct rows with other multiplicities, 6 the same value under another storage class, 1 differs only in row order, 0
truncation, 0 other. The test-suite reading recorded beside BIRD's refuses 231 (the multiplicity rows and the order
row), admits the 6 storage-class rows. Column names differ in 1,496 of the 2,088 NOT_EQUAL rows and decided none. Over
100 rows, so a stated sample was classified by hand: by (model, question id), every 4th taken, first 50
(`classify.py`); no phi-3 row is drawn.

| Class | Rows of 50 | Questions | What it means |
|---|---|---|---|
| A: a wrong answer the benchmark credited | 27 | 16 | a list at least twice the answer's length where the question asks for the things, not the rows; a scalar repeated once per row of the table it was computed over |
| B: harmless | 22 | 14 | one distinct row repeated; DISTINCT added by the prediction; a list under twice the answer with every row present |
| C: the tool's rule, not the question's | 1 | 1 | the same number as INTEGER against REAL |

**Precision of NOT_EQUAL on BIRD-credited predictions: 27 of 50 (54.0 %) are wrong answers, 49 of 50 (98.0 %) real
differences in the rows.** On PostgreSQL, 42.1 % and 87.2 %.

**Among EX=0.** Against the three corrected golds: on Hugging Face 3 of the 1,851 EX=0 rows are right by BIRD's own
reading (gpt-35-turbo, gpt-4-32k, gpt-4 on q207), on the zip those 3 plus gpt-4 on q879, so 4; none on q1029, where
every prediction is NOT_EQUAL against the correction too. The reverse, a 1 earned by reproducing a wrong gold: 5 rows
on the zip, 0 on Hugging Face, all q879, whose zip gold orders the speeds as text. **Zip against Hugging Face**, same
predictions: q879 moves in six files (five 1 to 0, gpt-4 0 to 1), q1322 in two (gpt-4, phi-3, 0 to 1), 119 and 120
audit gold-only, nothing else. For `mini_dev` issue 40.

## SQLite against PostgreSQL, over the same 500

**Gold-only.** On the Hugging Face copy PostgreSQL fired 39 smells on 29 golds, SQLite 25 on 20: `arbitrary-cut` 15,
`not-a-function-of-the-data` 9, `ordering-over-numeric-text` 1, `float-aggregate-order` 0, direction probe off. On the
zip, 26 on 21: the same plus `ordering-over-numeric-text` on q879, the only delta between the copies on either engine.
Nineteen questions differ between the engines, every id in [differences.json](minidev-sqlite-260907/differences.json):

| Class of difference | Questions | Why |
|---|---|---|
| `float-aggregate-order` never arises | 8 | SQLite adds REALs with a Kahan-Babuska-Neumaier compensation, so the backend answers the order-sensitive type set with the empty set (register A28); three of the eight carry byte-identical golds, so it is the engine and not the translation |
| the shuffled copies no longer move the answer | 4 | `arbitrary-cut` on an unordered bound and `not-a-function-of-the-data` both rerun the gold over shuffled copies and fire only when the answer changes; these four golds are the same text in both copies, so what changed is the order the rows are read in |
| the SQLite gold leaves NULL placement to the engine | 4 | each is `ORDER BY <key> LIMIT 1` over a tie, and the PostgreSQL translation writes `NULLS FIRST` or `NULLS LAST` where the SQLite copy writes nothing and the parser fills in the default; `not-a-function-of-the-data` is quiet here, `arbitrary-cut` still fires on all four |
| the translation says something else | 3 | q37 divides by `NULLIF(...)` and orders `ASC NULLS FIRST` on PostgreSQL, plainly here; q1168 reads years with `EXTRACT` against `STRFTIME`; q1209 is `DISTINCT ON (Birthday)` against a plain `DISTINCT` |

**Verdicts.** 1,736 of 4,482 readings differ, over 463 questions. Three things change at once, so this bounds the
difference rather than attributing it: a prediction file per dialect, a translated gold, the engine. 1,298 are a
refusal on one engine and a verdict on the other (1,019 PostgreSQL could not run or parse and SQLite could, 279 the
reverse). Of the 378 with a verdict on both, 141 go EQUAL to NOT_EQUAL (SQLite mechanism 58 storage class, 70
differing values, 9 multiplicity, 3 truncation, 1 order), 237 go NOT_EQUAL to EQUAL (PostgreSQL mechanism 136 value,
89 type, 12 multiplicity); the other 60 keep the verdict and move BIRD's reading.

## Three rows

1. [q846, gpt-4](minidev-sqlite-260907/examples/hf-gpt-4-q846/counterexample.json), the run's only NOT_EQUAL by row order: same five driver
   references, the gold ordered by `q1 DESC`, the prediction re-reading them through an `IN` subquery. R-ORD, BIRD 1, test-suite 0.
2. [q45, gpt-35-turbo-instruct](minidev-sqlite-260907/examples/hf-gpt-35-turbo-instruct-q45/counterexample.json): gold projects `AvgScrWrite`, cell
   INTEGER 507; prediction wraps it in `AVG()`, cell REAL 507.0. Same number, NOT_EQUAL by type. BIRD 1, test-suite 1. The sample's only class C.
3. [q1035, gpt-4](minidev-sqlite-260907/examples/hf-gpt-4-q1035/counterexample.json): gold returns 161 distinct `team_fifa_api_id`, prediction the
   same ids over 356 rows, and the question asks for the teams. BIRD 1. Class A.

## What the tool did not catch, and gaps found in use

- A prediction differing in meaning that returns the same rows on the shipped data: nothing searches for differentiating data, and a gold naming
  `main.<table>` never reaches the shuffled TEMP copies. Wrong golds beyond the three with a correction, how wrong an EX=0 prediction is, and two
  doubles differing past the sixth decimal place (q31, the one row of 4,482 where it mattered) are unmeasured too.
- The first attempt kept everything under `/private/tmp` and lost 114 runs to a reboot on 2026-09-06.
- It also ran twenty processes at load 61 for 19 gold timeouts no serial rerun reproduced.
- Open: no timeout is counted in the summary line or `summary.json`, so a gold that could not finish shows only in the per-question lines; the
  six-decimal rendering of a REAL can hide a difference BIRD's evaluator sees (q31), so a record should say what precision decided a numeric
  comparison; `--statement-timeout` at 30 s refuses two golds.
- Unresolved: whether that rendering should move, and to what, is the owner's call, the constant being shared with PostgreSQL and every digest moving
  with it; and whether the 40 s golds are a cost worth reporting upstream.
