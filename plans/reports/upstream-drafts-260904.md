# Upstream drafts, 2026-09-04

Drafts the owner sends by hand. Nothing here is posted by a session. The four reports filed
on 2026-09-04 are in `docs/claims-register.md`, section 5; this file holds the fifth, the sixth
and the seventh.
Each paragraph of a body is one line: GitHub renders a line break wherever a file wraps, so a
body is pasted as it stands and never re-wrapped.

## 5. bird-bench/mini_dev: EX for q1473 differs between two runs of the PostgreSQL evaluator

Where: new issue on `bird-bench/mini_dev`. Evidence: register row A22,
`plans/reports/session-260904-autonomous-run/remeasure-at-head/official-flips.json`, and the
five-run probe of the gold in
`plans/reports/session-260904-autonomous-run/q707-timeouts/q1473-gold-five-runs.txt`; for the
`work_mem` paragraph, `plans/reports/research-260904-postgres-result-preconditions/hashagg_workmem_demo.json`
and `plans/reports/session-260904-autonomous-run/work-mem-precondition/comparison.json`.

Title: PostgreSQL: q1473 scores differently on two runs of evaluation_ex.py against the same database

Body:

I scored the nine PostgreSQL prediction files in `llm/exp_result/sql_output_kg` twice with `evaluation/evaluation_ex.py` (commit b3d4bcb, only `connect_postgresql` pointed at my server), against the same PostgreSQL 16 database loaded once from `BIRD_dev.sql`. Nothing changed between the two runs, and q1473 (debit_card_specializing) got a different EX the second time in five of the eighteen file/gold pairs (nine files, scored against the zip gold and against the Hugging Face gold): gpt-4-turbo, phi-3-medium, gpt-4-32k and meta-llama-3-70b went from 1 to 0, and meta-llama-3-8b from 0 to 1. Every other question scored the same both times.

The gold is

```sql
SELECT AVG(T2.Consumption) / NULLIF(12, 0)
FROM customers AS T1 INNER JOIN yearmonth AS T2 ON T1.CustomerID = T2.CustomerID
WHERE SUBSTR(T2.Date, 1, 4) = '2013' AND T1.Segment = 'SME'
```

`Consumption` is `real`, so the average is a float sum. With the server default `max_parallel_workers_per_gather = 2` the aggregate runs as partial sums in parallel workers, combined in whichever order the workers finish, and float addition is not associative, so the last digits change from run to run. Five runs of the gold in psql on the same data gave 459.95626421124325, 459.9562642112432, 459.9562642112432, 459.9562642112432 and 459.95626421124285; with `SET max_parallel_workers_per_gather = 0` in front, five runs gave 459.95626421124274 five times. `calculate_ex` compares `set(predicted_res) == set(ground_truth_res)`, which is exact on floats, so a prediction that computes the same average gets 1 or 0 depending on which run it lands in.

The gather is not the only thing that decides that order. With `SET max_parallel_workers_per_gather = 0` already in force, the value still moves with `work_mem`: at the default 4MB the gold above returns 459.95626421124274, at `work_mem = '64kB'` it returns 459.956264211243, and q1476 and q1482, the other two float aggregates of this kind in Mini-Dev, move the same way while the remaining six summation-order-sensitive golds do not. With a smaller `work_mem` the planner joins the two tables differently (a hash join split into more batches, or another join method), so the rows reach the aggregate in another order and the float sum is added in that order. To reproduce on a PostgreSQL 16 loaded from `BIRD_dev.sql`, in one session: `SET max_parallel_workers_per_gather = 0; SET work_mem = '64kB';` then the gold, then `SET work_mem = '4MB';` and the gold again; the last digits differ. A role or a server configured with another `work_mem` has the same effect, so two evaluators with parallel query off on both servers can still disagree on q1473.

Suggested fix, three settings in `evaluation_utils.py`: after `connect_postgresql()` returns, run `SET max_parallel_workers_per_gather = 0`, `SET work_mem = '4MB'` and `SET hash_mem_multiplier = 2` on the connection (the last two are PostgreSQL's own defaults, stated so that a server configured otherwise scores the same), or pass the three through `options='-c max_parallel_workers_per_gather=0 -c work_mem=4MB -c hash_mem_multiplier=2'` to `psycopg2.connect`. It makes every float aggregate deterministic for scoring and does not change any correct answer. I only checked PostgreSQL. It would also be worth a sentence in the README that the PostgreSQL EX numbers there were measured on a server with parallel query on, since they can move by one question per file for this reason.

## 6. birdsql/bird_sql_dev_20251106: 23 golds the 2025-11-06 pass left wrong

Where: a discussion on the Hugging Face dataset `birdsql/bird_sql_dev_20251106`, the channel its
maintainer uses (the Q336 fix of 2026-01-25 was opened and closed there), with one comment
linking it from `AlibabaResearch/DAMO-ConvAI` issue 39, the standing panel of annotation issues.
Evidence: register rows A34 to A36 and
`plans/reports/bird-dev-sqlite-260907/classification.json` (every reason), measured at the
commit `plans/reports/measurement-260907-1435-bird-dev-sqlite.md` names. Sent 2026-09-07 after the merge that put that directory on `main`, as `bird-bench/mini_dev` issue 49
with a link comment on DAMO-ConvAI issue 39, then as discussion 3 on the Hugging Face dataset once a
login existed; register U6.

Title: 23 golds in this pass still cut at a tie, sort NULL first, or sort numbers as text

Body:

I ran three mechanical checks over every gold of the 2024 `dev.json` and of this 2025-11-06 pass, executing each statement on the `dev_databases` that ship with `dev.zip`: does a `LIMIT` cut through rows the data leaves tied, does an `ORDER BY` key hold NULLs that sort first, and is a numeric-looking `ORDER BY` key stored as text. Nothing semantic; the checks only ask whether the shipped data determines the answer the gold returns.

Of the 399 golds this pass rewrote, 31 fired on the old text and 29 of those stop firing on the new one, so the rewrite and the checks mostly agree. Of the 963 golds left unchanged, 25 fired. I read all 25 against the data by hand: 23 do not answer their question on this data, 1 is harmless (q893, two drivers tied on points, same set either way), 1 is my check being stricter than the question (q423 asks for alphabetical order of a text column that happens to hold digits).

The 23, by what goes wrong:

| Mechanism | Questions | What happens on the shipped data |
|---|---|---|
| `LIMIT` cuts through a tie | 30, 57, 82, 392, 766, 802, 906, 1002, 1034, 1090, 1117, 1144, 1290, 1365, 1389, 1517 | the rows tied at the cut carry different values for the column asked; q766 has 63 rows tied on the largest strength naming 36 heroes, q392 has 418 cards on the earliest ruling date and returns 3 of them, q57 asks for the 333rd highest inside a seven-row tie |
| NULL sorts first under `ASC` | 81, 847 | the gold returns a row with no value in the ordering key (a school with no latitude; a driver who set no qualifying time) instead of the lowest one |
| numbers sorted as text | 879, 927 | `fastestLapSpeed` is a text column, so 9.5 sorts above 10 and the fastest speed is not the one returned; q879 is the case from `bird-bench/mini_dev` issue 24, fixed in Mini-Dev's Hugging Face copy but still here |
| aggregate beside ungrouped columns | 1004 | a bare `SUM` with no `GROUP BY` next to two ungrouped columns: the total is every driver's wins added up (7,890) and the name beside it is one arbitrary row's |
| no cut where the question asks for the top | 484 | the gold orders by converted mana cost and never limits, returning all 155 Italian cards of the set where 12 carry the highest cost |
| average of ids | 523 | the projected average is a sum of ids divided by a count of ids, and several release dates share the count the gold cuts at |

Why it matters for scoring: the evaluator compares result sets, so on a tie-cut gold a prediction that picks another of the tied rows, which is just as correct, scores 0, and on q81 and q847 a prediction that filters the NULLs out scores 0 for being right.

Per-question reasons, the probe outputs, and a script that reruns all of it against `dev.zip` are here: <https://github.com/ivermin1123/attestql/tree/main/plans/reports/bird-dev-sqlite-260907> (the hand reading is `classification.json`). Happy to open one issue per question or send a corrected SQL for each if that is easier for you.

## 7. bird-bench/mini_dev: five of the eleven databases differ between dev.zip and minidev.zip

Where: new issue on `bird-bench/mini_dev`, the tracker whose README links both zips. Evidence:
register row A38, `plans/reports/bird-dev-sqlite-260907/inputs.json` (`databases_against_minidev`)
and `check_inputs.py` (digest, then schema, row counts and per-table row digests), measured
2026-09-07 at the commit `plans/reports/measurement-260907-1435-bird-dev-sqlite.md` names.
Sent 2026-09-07 10:54 UTC as `bird-bench/mini_dev` issue 50 on the owner's word; register U7.

Title: Five of the eleven dev databases differ between dev.zip and minidev.zip

Body:

The two zips the README links carry the same eleven `dev_databases`, but only six of the files are the same. I checked <https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip> (sha256 `cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630`, Last-Modified 2024-06-29) against <https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip> (sha256 `cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f`, downloaded 2026-09-02) by file digest first, then by schema, row count per table and a digest of each table's rows where the files differed. `card_games`, `codebase_community`, `debit_card_specializing`, `financial`, `student_club` and `superhero` are byte-identical. The other five are not, and neither README says so.

| Database | Table | dev.zip | minidev.zip |
|---|---|---|---|
| formula_1 | lapTimes | 420,369 rows | 400,524 rows |
| formula_1 | pitStops | 6,070 | 5,815 |
| formula_1 | qualifying | 7,397 | 6,967 |
| formula_1 | races | 976 | 954 |
| formula_1 | results | 23,657 | 23,179 |
| thrombosis_prediction | Examination | 806 | 106 |
| toxicology | atom | 12,333 | 9,111 |
| toxicology | bond | 12,379 | 9,156 |
| toxicology | connected | 24,758 | 18,312 |
| california_schools | satscores | same count, 211 of 2,269 `cds` codes without their leading zero | the same codes with the zero |
| european_football_2 | Player | same count, `height` stored as REAL | `height` stored as a truncated integer |

The schemas agree in all five. In `formula_1`, `thrombosis_prediction` and `toxicology` the dev copy simply holds more rows. In `california_schools` the row counts agree and 211 of the 2,269 `satscores.cds` values lost their leading zero in dev's copy, so those 211 rows join to `schools` in Mini-Dev's copy and do not in dev's. In `european_football_2` the counts agree and `Player.height` is a REAL in dev and a truncated integer in Mini-Dev.

Why it matters: a Mini-Dev question is a dev question, and its gold runs against whichever copy the user unpacked. A gold over `formula_1`, `toxicology` or `thrombosis_prediction` can return other rows on the two copies, and a gold that joins `satscores` to `schools` returns other rows on `california_schools`. Two people scoring the same predictions against "the dev databases" can get different EX for that reason alone, and the README of neither repository says which copy is the one the golds were written against.

Two questions, then: which copy is the intended one for Mini-Dev, and could the README of each zip state the sha256 of the other and the five differences? The check itself is a short script; I am happy to send it, or the per-table row digests, if that helps.
