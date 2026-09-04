# R-B: PostgreSQL settings and environment facts that can change a SELECT's bytes, rows or order

<!-- cspell:ignore datcollate datcollversion daticulocale collversion collprovider colliculocale hashagg seqscan seqscans mergejoin hashjoin geqo psycopg fformat funcnames coltypes libicu glibc auditor superuser TIMESTAMPTZ debit yearmonth budgeting libc Autovacuum datestyle intervalstyle workmem datlocprovider -->

Method: read `docs/adr/0013`, `0004`, `claims-register.md` and the audit/evidence source under
`src/attestql`; scanned `pg_settings` (364 rows); parsed the 500 Hugging Face golds with
`parse_statement` and ran all 500 once; ran targeted demos on `bird` (libc `en_US.utf8`),
`bird_c` (`C`), `bird_icu` (ICU `en-US`), all PostgreSQL 16.15. Every number is backed by a
script and output file in `plans/reports/research-260904-postgres-result-preconditions/`, which
pass `ruff check`/`format`.

## 1. Inventory

`src/attestql/audit/postgres.py`: `PRECONDITION_SETTINGS` = `TimeZone, DateStyle, IntervalStyle,
extra_float_digits` (line ~87); `RECORDED_SETTINGS` = `statement_timeout, search_path,
server_version, server_version_num, transaction_read_only, max_parallel_workers_per_gather`
(line ~96); `pg_database.datcollate` (line ~320) is a fifth precondition, added in
`SessionSettings`/`SESSION_PRECONDITIONS`. Every SELECT runs inside `BEGIN READ ONLY` with
`SET LOCAL max_parallel_workers_per_gather = 0` (`NO_PARALLEL_AGGREGATION`, line ~304).

Dismissed `pg_settings` categories (no path to a SELECT's bytes, order, row set or meaning under
a read-only single-statement transaction): Autovacuum; Connections/Authentication; Error
Handling; File Locations; Lock Management; Replication (4); Reporting/Logging (3); Resource
Usage/Background Writer, /Vacuum Delay, /Disk, /Kernel; Statistics/Cumulative, /Monitoring;
Write-Ahead Log (5); Developer Options and most Preset Options (read-only/debug-only), kept
only where named below.

| Factor | Recorded | Precondition | Can change | Measured |
|---|---|---|---|---|
| datcollate + provider (libc/ICU) | collate only | yes | order (text), row set under LIMIT | section 2 |
| DateStyle | yes | yes | bytes; **crashes psycopg's loader** for non-ISO on `timestamptz` | `datestyle_timestamptz_demo.json` |
| TimeZone | yes | yes | bytes of any `timestamptz` | `timezone_demo.json`: `12:00:00+00` vs `08:00:00-04` |
| extra_float_digits | yes | yes | bytes of `float4`/`float8` (`NumericFromFloatText`) | `extra_float_digits_demo.json`: 15 vs 16 sig. digits |
| IntervalStyle | yes | yes | bytes; **crashes psycopg's default loader** for non-`postgres` styles | `intervalstyle_demo.json` |
| bytea_output | no | no | nothing psycopg hands back (note below) | `bytea_output_demo.json`: identical |
| lc_time, lc_numeric | no | no (unreached) | `to_char` day/month names, grouping/decimal marks | `lc_time_demo.json`, `lc_numeric_demo.json`: identical (only English-family locales installed here) |
| lc_monetary | no | no | `to_char(..,'L..')` currency symbol | `lc_monetary_demo.json`: `$   1234.50` vs no-symbol padded `1234.50` |
| client_encoding | no | no | nothing psycopg hands back (note below) | `client_encoding_demo.json`: identical |
| server_encoding | not recorded | n/a (immutable/db) | bytes, cross-database only | not demonstrated; recording gap noted below |
| search_path | yes | no | **statement meaning**: which table an unqualified name reads | `search_path_demo.json`: two different rows, two schemas |
| standard_conforming_strings | no | no | bytes of a literal containing `\` | `standard_conforming_strings_demo.json`: `a\nb` vs newline |
| backslash_quote, escape_string_warning | no | no | admissibility/a `WARNING` only, not a successful result's bytes | `backslash_quote_demo.json`: identical; [docs](https://www.postgresql.org/docs/16/runtime-config-compatible.html) say the warning is diagnostic-only |
| array_nulls | no | no (unreached: no arrays in corpus) | row set (`NULL` as element) vs statement failure | `array_nulls_demo.json`: parses vs `InvalidTextRepresentation` |
| work_mem / hash_mem_multiplier, enable_hashagg | no | no | **float aggregate value**, even with gather forced off (work_mem); grouped order in principle (hashagg) | `hashagg_workmem_demo.json`: 3 of 9 (work_mem), 0 of 9 (hashagg), section 3 |
| enable_seqscan/sort/hashjoin/mergejoin, page costs, default_statistics_target, ANALYZE state | no | no | tie order under an under-specified `ORDER BY` only | `planner_switch_demo.json`: no diff (no index to flip a plan; ADR-0004 needs a total order anyway) |
| max_parallel_workers_per_gather, parallel_* costs, min_parallel_table_scan_size | yes | forced to 0 | float/grouped-aggregate summation order | forced off; A9/A21/A22 measured the flips this prevents |
| jit, jit_above_cost | no | no | in principle (FMA vs separate ops); none observed | `jit_demo.json`: identical, arm64 host |
| synchronize_seqscans | no | no | row order of an unordered scan under concurrent load ([docs](https://www.postgresql.org/docs/16/runtime-config-compatible.html): "can result in unpredictable changes in the row ordering") | not reproduced here, needs a race with another session |
| default_transaction_read_only, statement_timeout, isolation level | mostly yes | no | nothing: `BEGIN READ ONLY` hard-coded; timeout -> error not bytes; one `SELECT` = one snapshot at any level | code pointer (`_execute`); isolation not stress-tested vs a writer |
| money, bytea, array (serializer gaps) | no | no | money: psycopg returns a plain string tagged `str`, rides on `lc_monetary`; `canonical_type_tag` has no case for `bytes`/list, raises `UnsupportedValue` | unreached: 0 of each in base columns and in all 500 result types |

Why "no difference" for `bytea_output`/`client_encoding`: psycopg3's text `bytea` loader
auto-detects hex vs escape regardless of the GUC, and decodes to `str` with the encoding it
tracked at connect time, not a later `SET LOCAL client_encoding`; both a measured empty diff.
**Crash, not just bytes.** `DateStyle`/`IntervalStyle` are more than rendering preconditions:
`timestamptz` under a non-ISO `DateStyle` and `interval` under a non-`postgres` `IntervalStyle`
raise `NotImplementedError` from psycopg's own loader before any comparison runs
(`datestyle_timestamptz_demo.json`, `intervalstyle_demo.json`); `date` alone tolerates
`DateStyle`. This is why `postgres.py` registers `TextFromInterval` (line ~194) ahead of the
default loader, confirmed here as load-bearing, not cosmetic.

## 2. Collation

Per [PostgreSQL 16 docs](https://www.postgresql.org/docs/16/collation.html), "a deterministic
collation ... considers strings to be equal only if they consist of the same byte sequence."
`bird`, `bird_c`, `bird_icu` are all deterministic (default), so `=`, `<>`, `GROUP BY`,
`DISTINCT` are byte comparisons on all three regardless of collation; only `<`,`>`,`<=`,`>=`,
`ORDER BY`, `MIN`, `MAX` read it. Measured: a 16-gold sample (5 `GROUP BY`-, 5 `=`-, 5
`LIKE`-over-text, the corpus's 1 ordering comparison over text) is identical in row set and
order on all three databases (`deterministic_collation_demo.json`).

Parsing the 500 golds: 88 R-ORD, 412 R-SET, 0 refused. Text-typed `ORDER BY` key (direct column
reference): 11 golds (1392, 1078, 1102, 846, 847, 931, 824, 220, 232, 115, 129) -- several order
by columns look date-named (`birthday`, `element`) but are Mini-Dev-typed `text`. `MIN`/`MAX`
over text: 0. `GROUP BY` over text: 27. Equality/`<>` over text: 355. `LIKE` over text: 17.
Ordering comparison over text: 1 (q1133).

Running the 11 text-`ORDER BY` golds on all three databases (`collation_order_diff.json`):
**0 of 11 change row order, 0 of 11 change row set** -- every one is a `LIMIT 1` or a small
distinct-first-letter result the three collations agree on by chance here. The mechanism is
demonstrated separately with a 6-row constructed table (`collation_demo.sql`, one output file
per database): `bird_c` sorts `Apple, Banana, Zebra, able, apple, banana` (byte order); `bird`
and `bird_icu` both sort `able, apple, Apple, banana, Banana, Zebra` (dictionary order, case as
tiebreak), agreeing with each other on this input though the algorithms differ in general.

What the tool records: `datcollate` only. Not recorded, measured here: `datlocprovider` (`c`
vs `i`), `daticulocale`, `datcollversion`
([`pg_database` columns](https://www.postgresql.org/docs/16/catalog-pg-database.html)).
Measured (`collation_versions.txt`): `bird` -> provider `c`, `en_US.utf8`, version `2.41`
(glibc, matches the container's stated glibc); `bird_c` -> provider `c`, `C`, no version;
`bird_icu` -> provider `i`, `en_US.utf8`/`en-US`, version `153.128`.
`pg_collation_actual_version()` agrees with the recorded version on both (no drift; freshly
loaded). Cross-host risk is **not measured here**: one container, one glibc build. The
[wiki on locale data changes](https://wiki.postgresql.org/wiki/Locale_data_changes) states
glibc 2.28 (2018) "brought a major update to the locale data," changing sort order on Debian
10+, Ubuntu 18.10+, RHEL/Rocky/AlmaLinux 8+, macOS 11+; a `datcollate`-only precondition cannot
detect two hosts naming the same `en_US.utf8` on different glibc builds.

## 3. Reach in this corpus (`gold_run_all.json`, `run_all_golds.py`)

Date literals a DateStyle could re-read: 24 golds, 33 literals, all ISO-shaped (`YYYY-MM-DD`),
0 ambiguous slash-style -- 0 input-ambiguity reach; the loader-crash risk still applies to any
`timestamptz` result column (0 of 500, below). Backslash in a string literal: 0. `to_char`: 29
golds, 0 locale-dependent day/month patterns. `to_date`/`to_timestamp`: 0. Result column types
across all 500 (`cursor.description`, 0 errors): text 322, int8 176, float8 85, float4 36,
numeric 33, date 8, bool 1 -- 0 timestamptz/interval/bytea/money despite 11 timestamptz and 19
date base columns; every gold touching one casts or extracts from it first. Unordered `LIMIT`
(R-SET, `LIMIT`, no `ORDER BY`, what `synchronize_seqscans` or a plan change can bite): 4 golds
(1144, 1014, 751, 349), underspecified by the gold itself. Float aggregate
summation-order sensitivity: re-derived from `plans/reports/sweep-260902-gold-only-probes/
fired.json`'s shuffle-probe evidence at 1e-4 relative tolerance: **9 golds** (1473, 1476, 1482,
1529, 1531, 1380, 1390, 1410, 955), matching claims-register A9. At the tool's forced
`max_parallel_workers_per_gather = 0`: `enable_hashagg = off` changes 0 of 9;
**`work_mem = '64kB'` changes 3 of 9** (1473, 1476, 1482) -- forcing parallelism off is
necessary but not sufficient (`hashagg_workmem_demo.json`).

## 4. Ranking

**Flips silently today (not a precondition, not recorded):** collation provider/version
(`datcollate` is recorded, provider/version are not); `work_mem`/`hash_mem_multiplier` (3/9
float golds, measured); `synchronize_seqscans` (mechanism per docs, not measured); `search_path`
(statement meaning, recorded but never blocks); `array_nulls` (parse-time, unreached here).
**Flips but is recorded:** `max_parallel_workers_per_gather` (forced to 0, why A21/A22's flips
close); `statement_timeout`, `transaction_read_only`, `server_version` (never change bytes,
only whether the run happens).
**Cannot flip:** `enable_*`/cost GUCs/`default_statistics_target` for R-SET (order disregarded,
`_row_multiset` in `replay.py`); for R-ORD only when `ORDER BY` is total per ADR-0004 (no
index to flip a plan on here, not a general proof); `bytea_output`, `client_encoding`,
`backslash_quote`, `escape_string_warning`, `lc_time`/`lc_numeric` here (no divergent locale
installed); `default_transaction_read_only` (hard-coded); `jit` (none observed, arm64).
**Recommend:** add `datlocprovider`, `daticulocale`, `datcollversion` to `RECORDED_SETTINGS` (one
`pg_database` query, closes the measured doc gap); treat `work_mem` as a precondition or force
it beside `NO_PARALLEL_AGGREGATION` (measured 3/9 flip); add `server_encoding` to
`RECORDED_SETTINGS`, currently absent and unstated in any record.

## What changes in AttestQL

- (code) `src/attestql/audit/postgres.py` `RECORDED_SETTINGS`: add `datlocprovider`,
  `daticulocale`, `datcollversion` (via `pg_database`) and `server_encoding` -- section 2/3.
- (code) `src/attestql/audit/postgres.py` envelope (beside `NO_PARALLEL_AGGREGATION`): force or
  record `work_mem` -- measured 3/9 float-aggregate flip at forced-off parallelism, section 3.
- (claim) `docs/claims-register.md` A9: the float-summation-order claim should name `work_mem`
  beside `max_parallel_workers_per_gather` as a cause -- section 3.
- (non-claim) cross-host collation drift (glibc/ICU version changing `ORDER BY`) is real per
  PostgreSQL's own docs but not measured on this one-container setup -- section 2.
- (no change: measured correct) `DateStyle`/`IntervalStyle` as preconditions and the existence
  of `TextFromInterval`: load-bearing beyond bytes, a loader crash not a mismatch, section 1.
- (no change: measured negative here) `enable_*`/cost GUCs/`jit` -- no observed flip in this
  corpus/host; correctly outside `PRECONDITION_SETTINGS`, section 1/4.
