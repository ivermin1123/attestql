# work_mem held: the same nine golds under two roles

Measured 2026-09-05 on the research server (PostgreSQL 16, container `attestql-research-pg`,
port 5499, Mini-Dev dump loaded), with the tool at the commit that made `work_mem` and
`hash_mem_multiplier` preconditions.

The nine golds are the summation-order-sensitive ones of claims-register A9: 1473, 1476, 1482,
1529, 1531, 1380, 1390, 1410, 955, taken from the Hugging Face Mini-Dev PostgreSQL file
(sha256 `7fa740ef…`, 2026-01-18) into `nine-golds.json`.

`run.sh` audits them twice: once with the auditor role at the server's own `work_mem`, once
with `ALTER ROLE auditor SET work_mem = '64kB'` set by the superuser and reset afterwards.
`control_raw_statements.py` runs the same nine statements without the tool's envelope under
each role state, which is the research report's comparison
(`plans/reports/research-260904-postgres-result-preconditions.md` section 3) with the 64 kB
coming from the role. `compare_two_runs.py` writes `comparison.json`.

## What it found

- Nine of nine EQUAL, and the same `result_hash` and the same canonical bytes on both sides.
  All nine declare R-SET, so `compare_r_set` is the rule called; `compare_r_ord` is not
  exercised by this set.
- Every record of both runs states `work_mem` 4096 and `hash_mem_multiplier` 2, the values
  `pg_settings` reports for the 4 MB and the 2 the envelope holds, whatever the role said.
- The control differs on 3 of 9, 1473, 1476 and 1482, the three the research report named.
  Without the envelope the role's 64 kB reaches the statement and moves the float aggregate.

## Why two invocations per role state

Gold-only mode writes a question's directory only where a smell fired, and 1476 and 1390 fire
none here, so each role state is also audited with a deliberate non-answer (`SELECT NULL`,
`force-a-record.json`) beside every gold, which makes the tool write all nine gold records.
The gold's own execution is the same either way: for each of the six the gold-only runs did
write, `gold_only_run_agrees` in `comparison.json` says its `result_hash` is the one the
paired run recorded.

Rerun with `WORK=<scratch dir> PGPASSWORD=<the auditor login> ./run.sh`. Only
`comparison.json` is kept here; the audit output directories stay in the scratch directory.
