# Measurement: BIRD dev on SQLite, two copies of the golds, recall against BIRD's own rewrite

Date 2026-09-07, tree `6a43c01`. SQLite 3.53.4 as Python 3.13.7 links it, `mode=ro` under
`PRAGMA query_only`, no server or container, sqlglot 30.18.0. Artifact: `bird-dev-sqlite-260907/`.

## Inputs and method

Two copies of the same 1,534 questions. Old: `dev.zip` (`cdd6d19f…`, Last-Modified 2024-06-29),
member `dev_20240627/dev.json`, sha256 `630272f2…`. New: BIRD's 2025-11-06 quality pass,
`birdsql/bird_sql_dev_20251106` at dataset commit `3c11fb19` (2026-01-18, CC BY-SA 4.0),
`data/dev_20251106-00000-of-00001.json`, sha256 `ffd80183…`, R-C's digest unchanged; that dataset
holds a second revision of the name, the 2025-11-12 upload (`87c7f0ea…`), differing in q180 alone.

**The eleven databases are not Mini-Dev's**: six are, five are not (`inputs.json`). `formula_1`,
`thrombosis_prediction` and `toxicology` carry more rows in dev (806 `Examination` rows against
106, 12,333 `atom` against 9,111); `california_schools` and `european_football_2` share schema and
counts and differ in one table each. 211 of 2,269 `satscores` CDS codes lost a leading zero, so
211 rows that join to `schools` in Mini-Dev's copy do not in dev's, and `Player` heights are REAL
in dev and truncated integers in Mini-Dev. Every run uses dev.zip's own.

A dev question file names eleven databases and `--dsn` takes one file, so a copy is eleven runs,
each with `--ids` holding that database's ids. The **merge rule** sums the eleven summaries'
counts, concatenates their per-question lines, lists their run ids; no id is in two of the eleven.
**Three processes at a time**, a statement's budget here being wall clock: 18 of the 66 runs held a
timeout line, each was rerun alone (`rerun_timeouts.sh`, the `*.under-load/` copy beside it) and
all 18 survived. The 399 / 172 / 963 split is recomputed from the two files under R-C's
normalisation and asserted equal to R-C's lists, so a moved dataset fails the run rather than
quietly moving a denominator.

## Gold-only, per probe and per copy

| Probe | 2024-06-27 | 2025-11-06 |
|---|---|---|
| `arbitrary-cut` | 47 | 24 |
| `not-a-function-of-the-data` | 36 | 20 |
| `ordering-over-numeric-text` | 4 | 3 |
| `float-aggregate-order` | 0 | 0 |
| **golds with at least one** | **62 of 1,532** | **35 of 1,531** |

Audited is 1,532 and 1,531, not 1,534: q518 (`card_games`, 38 s alone) and q701
(`codebase_community`, 192 s) miss the 30 s budget in both copies, and so does the 2025-11-06
rewrite of q1131, whose 2024 text takes 0.3 s. `float-aggregate-order` is 0 on 1,534 golds as on
500 (A28); the direction probe is `--experimental-s2` and stayed off.

## Recall against BIRD's own rewrite

BIRD rewrote 399 of the 1,534 golds in its 2025-11-06 pass, changed only the question or evidence
text of 172, left 963 alone. Measured on the old copy, which is what those rewrites correct:

| Group | Size | Fired | Share | `arbitrary-cut` | `not-a-function` | `ordering-text` |
|---|---|---|---|---|---|---|
| **SQL rewritten by BIRD** | **399** | **31** | **7.8 %** | 26 | 19 | 1 |
| text only | 172 | 6 | 3.5 % | 3 | 4 | 0 |
| left alone | 963 | 25 | 2.6 % | 18 | 13 | 3 |

**Recall of the gold-only probes against BIRD's own corrections is 31 of 399, 7.8 %**, three times
the 2.6 % base rate on the golds BIRD left alone. They are no QC pass: they miss 368 of the 399.
What they do fire on, BIRD's rewrite agrees with: **29 of the 31 stop firing once the 2025-11-06
gold replaces the 2024 one**, while every gold whose SQL BIRD left alone still fires, so what
changed is the rewrite and not the run. Still firing: q94, cutting at a tie, and q1135, a fixed
direction with a tie left at the fifth. Newly firing: q1284, an `LDH ASC` to `DESC` fix leaving
patients tied at the top, and q11, replaced by a far larger query.

## The 25 golds BIRD left alone that a probe fired on, read by hand

All 25 read against the data by hand, not sampled; `classification.json` carries every reason.

| Class | Questions | What it means |
|---|---|---|
| wrong | 23 | the gold does not answer its question on this data. Eighteen cut at a tie the data does not break (q766 has 63 rows tied on the largest strength value naming 36 heroes; q57's "333rd highest" sits inside a seven-row tie); two sort NULL first and answer with a row holding no value (q81, q847); q1004 is a bare `SUM` with no `GROUP BY` beside two ungrouped columns; q484 never cuts, returning 155 rows where 12 carry the highest cost asked for; q1144 cuts with no ordering |
| harmless | 1 | q893: the top two drivers hold equal points, so the rows come back in another order and BIRD compares them as a set |
| the tool's rule | 1 | q423: the key is a text column of numbers, read as sorted as text, and the question asks for alphabetical order |

## Overlap with the published errata

| List (R-C's `errata-ids.json`) | Ids | Fired and listed | Listed, not fired | Fired, not listed |
|---|---|---|---|---|
| Wretblad 2024 financial | 52 | 3 (q94, q101, q115) | 49 | 59 |
| Wretblad 2024 sampled | 27 | 1 (q30) | 26 | 61 |
| CIDR 2026 Jin Table 2 | 18 | 0 | 18 | 62 |
| `bird-bench/mini_dev` issues | 10 | 1 (q879) | 9 | 61 |
| the three this repo tracks | 3 | 1 (q879) | 2 | 61 |
| SpotIt counterexamples | none published | | | |

SpotIt has no row: R-C read the paper in full and it releases no id list and no code, so the
phase's premise does not hold. The overlaps are small both ways: the lists are mostly semantic,
the probes ask whether the data decides the answer at all, and 59 of the 62 fires are unlisted.

## A note on q879 and q207, reported to nobody

q879 asks one question in all three publications and gets two answers on the database: Mini-Dev's
Hugging Face copy casts the speed to REAL before ordering and returns `Brazilian`, both dev copies
sort the same text column and return `Italian`, wrong for the reason `mini_dev` issue 24 gave in
September 2025, fixed in one product and, five months later, shipped without the fix in the dev
pass, where the probe still fires. q207 is the other shape, question and SQL replaced together:
the old text joins `connected` on `atom_id` alone and returns 14 elements where the database holds
5, the defect the owner filed as issue 39; the new SQL joins on `bond_id` and does return those 5,
so the join is genuinely fixed, but it answers a different five-column question whose last column
promises "up to 3 molecules" and puts its `LIMIT 3` outside an already-collapsing `GROUP_CONCAT`.

## Prediction mode

A public dev prediction file with a clear licence exists, so it was run. Searched: the
`bird-bench` GitHub repos (`mini_dev` ships only the 500-question files, the other twelve are
other benchmarks), both Hugging Face datasets (golds only), and `AlibabaResearch/DAMO-ConvAI`,
where BIRD dev's own code lives and which ships `bird/llm/exp_result/{turbo_output,turbo_output_kg}
/predict_dev.json`, GPT-3.5-turbo without and with the evidence, 1,534 entries each, MIT. Scored
beside the tool by BIRD's unmodified `evaluation.py` at `dec31ae3`.

| Copy | File | Compared | EX=1 | EX=0 | ERROR | BIRD's script | Agree | EX=1 and NOT_EQUAL |
|---|---|---|---|---|---|---|---|---|
| 2024-06-27 | `turbo_output` | 1,249 | 349 | 900 | 285 | 349 (22.75 %) | 1,534 of 1,534 | 36 |
| 2024-06-27 | `turbo_output_kg` | 1,178 | 550 | 628 | 356 | 550 (35.85 %) | 1,534 of 1,534 | 54 |
| 2025-11-06 | `turbo_output` | 1,248 | 345 | 903 | 286 | 345 (22.49 %) | 1,534 of 1,534 | 37 |
| 2025-11-06 | `turbo_output_kg` | 1,178 | 532 | 646 | 356 | 532 (34.68 %) | 1,534 of 1,534 | 54 |

**The tool's reading of BIRD's EX and BIRD's own evaluator agree on 6,136 of 6,136 comparisons**,
every question of every file against both copies, no disagreement of any kind, where the same
check on Mini-Dev left one row over. Of the 899 predictions BIRD credits on the old copy, 90 are
NOT_EQUAL (10.0 %) under the typed comparison: 86 give its distinct rows with other
multiplicities, 2 differ only in row order, 2 by storage class; the test-suite reading refuses 88 of
the 90. Column names differ in 1,037 of the 1,618 NOT_EQUAL rows and decided none. Of
`turbo_output`'s 285 errors, 279 are the prediction's own (187 failed to execute, 94 did not
parse), 2 the gold timeouts, 4 a prediction naming a table the database lacks.

## What the tool did not catch, and gaps found in use

- 368 of the 399 golds BIRD itself rewrote. The probes ask whether the data decides the answer;
  most of BIRD's own corrections are about what the question means, which nothing here reads.
- q1029, whose `ASC` orders "highest", fires no probe in either copy: the probe that would read a
  direction against its question is off by default, at 17 % actionable.
- BIRD's two dev prediction files cannot be read as they ship. A prediction the model did not
  produce is the JSON number `0` (54 of 1,534 in `turbo_output`, 14 in `turbo_output_kg`) and the
  tool refuses the whole file for one. Upstream's `package_sqls` substitutes a single space, which
  then fails and scores 0; `predictions_readable.py` does the same and records every position. The
  tool should do that, or name the entry it refused and carry on.
- The 30 s budget is a real limit here: three golds and seven predictions exceed it, and a timeout
  is counted nowhere but the per-question line.
- Five of the eleven databases differ between `dev.zip` and `minidev.zip`, with no note in either
  publication. Nothing in the tool reads a database against another copy of itself: found by hand,
  checking a digest the phase expected to match.

## Unresolved questions

- Which copy of `california_schools` is wrong about the 211 `satscores` CDS codes, and whether any
  dev gold joins through them.
- Whether the rewrite of q207 is a fix or a new defect: it repairs the join and adds a `LIMIT` that
  limits nothing. Not judged here, not reported.
- Whether q518, q701 and the rewritten q1131 are a benchmark cost worth reporting upstream.
