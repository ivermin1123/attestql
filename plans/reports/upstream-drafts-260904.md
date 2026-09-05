# Upstream drafts, 2026-09-04

Drafts the owner sends by hand. Nothing here is posted by a session. The four reports filed
on 2026-09-04 are in `docs/claims-register.md`, section 5; this file holds the fifth.
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

The gather is not the only thing that decides that order. With `SET max_parallel_workers_per_gather = 0` already in force, the value still moves with `work_mem`: at the default 4MB the gold above returns 459.95626421124274, at `work_mem = '64kB'` it returns 459.956264211243, and q1476 and q1482, the other two float aggregates of this kind in Mini-Dev, move the same way while the remaining six summation-order-sensitive golds do not. A hash aggregate that outgrows `work_mem` spills to disk in batches and adds each batch's partial sums where the batch ended. To reproduce on a PostgreSQL 16 loaded from `BIRD_dev.sql`, in one session: `SET max_parallel_workers_per_gather = 0; SET work_mem = '64kB';` then the gold, then `SET work_mem = '4MB';` and the gold again; the last digits differ. A role or a server configured with another `work_mem` has the same effect, so two evaluators with parallel query off on both servers can still disagree on q1473.

Suggested fix, three settings in `evaluation_utils.py`: after `connect_postgresql()` returns, run `SET max_parallel_workers_per_gather = 0`, `SET work_mem = '4MB'` and `SET hash_mem_multiplier = 2` on the connection (the last two are PostgreSQL's own defaults, stated so that a server configured otherwise scores the same), or pass the three through `options='-c max_parallel_workers_per_gather=0 -c work_mem=4MB -c hash_mem_multiplier=2'` to `psycopg2.connect`. It makes every float aggregate deterministic for scoring and does not change any correct answer. SQLite and MySQL are not affected. It would also be worth a sentence in the README that the PostgreSQL EX numbers there were measured on a server with parallel query on, since they can move by one question per file for this reason.
