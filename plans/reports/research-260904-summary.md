# Research summary, 2026-09-04: four read-only topics, what each changes in AttestQL

<!-- cspell:ignore sqlglot datlocprovider daticulocale datcollversion birdsql libpg libc -->

Four reports on branch `research-260904`, one commit each, nothing built, nothing posted upstream:
[R-A, result readings](research-260904-result-readings.md),
[R-B, PostgreSQL preconditions](research-260904-postgres-result-preconditions.md),
[R-C, published gold errata](research-260904-published-gold-errata.md),
[R-D, SQLite before a backend](research-260904-sqlite-before-backend.md).
Every number is measured in the report's directory. Ranked by what can flip a verdict today.

## Flips a verdict silently today

- (code) `work_mem` changes 3 of the 9 float aggregates of Mini-Dev (q1473, q1476, q1482) with
  the gather already forced to 0; neither recorded nor a precondition. Force it beside
  `NO_PARALLEL_AGGREGATION` in `audit/postgres.py` or precondition it; A9 names it. R-B 3.
- (code) Record the collation provider and version: `datlocprovider`, `daticulocale`,
  `datcollversion`, `server_encoding` join `RECORDED_SETTINGS`. Here 0 of the 11 golds with a
  text ordering key change across libc en_US.utf8, C and ICU en-US. R-B 2.
- (non-claim) Cross-host collation drift (same `datcollate` name, another glibc or ICU build) is
  real per PostgreSQL's documentation and not measured: one host. R-B 2.

## Changes how a verdict is read, not the verdict

- (code) `test_suite_ex` beside `bird_ex` in `audit/compare.py`, the counterexample and
  `summary.json`: test-suite's `result_eq` disagrees with `bird_ex` on 37 of the 170 rows, 46 %
  class A; other readings are near-total (Spider 2.0, 143) or near-empty. R-A 3.
- (claim) A17's 40.6 % is `bird_ex`-relative: the same rows read 25 % to 71 % under the other
  evaluators' own refused sets. Add the clause, keep the number. R-A 3.
- (claim) N2, dated: Vanna, Alpha-SQL, XiYan-SQL, CHASE-SQL ship no gold comparison. R-A 1.

## Claims on record that need the owner's own read

- (claim) The SpotIt+ `LICENSE` (both repositories, one commit of 2026-02-15, unchanged) opens
  "All rights reserved" and then grants use under a modified-BSD text; ADR-0013, N3 and the filed
  issue U4 say "no grant of use". Verified from the raw file by the coordinator. R-C 1.
- (claim) `birdsql/bird_sql_dev_20251106` (CC BY-SA 4.0) rewrites 399 of 1,534 dev golds, fixes
  q1029, leaves q879, replaces q207; Mini-Dev ids are BIRD dev ids (496 of 500 identical). R-C.

## ADR-0014, corrected by measurement before anything is built

- (claim) sqlglot 30.18.0 parses every gold of BIRD dev and both Mini-Dev SQLite copies;
  libpg_query refuses 127, 45 and 46, all backticks or `LIMIT offset, count`; the double-quoted
  literal risk occurs once in 2,534 golds and never as a literal. R-D 1.
- (non-claim) SQLite golds are not dynamically typed in practice: 0 of 806 stored columns and 0
  of 2,034 result columns mix a storage class; `1 == 1.0 == True` decides no score. R-D 4, 5.
- (code, when built) `PRAGMA query_only` is the envelope; record `sqlite_version`, `encoding`,
  `compile_options`, `collation_list`, `case_sensitive_like`, `reverse_unordered_selects`. R-D 4.
- (no change, measured) `DateStyle`/`IntervalStyle` preconditions are load-bearing (psycopg's
  loader raises); planner switches and `jit` flipped nothing; q565 covers the empty guard. R-B, R-A.

## Three things to do now

1. Owner re-reads the SpotIt+ `LICENSE`; decides on N3, the ADR-0013 paragraph and issue U4.
2. `audit/postgres.py`: force or precondition `work_mem`; record provider, ICU locale, collation
   version and `server_encoding`; refresh A9 and A2a.
3. `audit/compare.py`: `test_suite_ex` beside `bird_ex`; A17 qualified as `bird_ex`-relative.

Status: DONE_WITH_CONCERNS (the SpotIt+ misreading already filed upstream; drift unmeasured).
