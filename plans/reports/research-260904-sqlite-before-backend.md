# R-D: SQLite gold and BIRD's SQLite evaluator, measured before a backend

<!-- cspell:ignore sqlglot libpg pglast birdsql minidev postgast typeof Nafta bareword CLOB FLOA DOUB NOCASE RTRIM -->

Scope: BIRD dev (1,534 golds), Mini-Dev SQLite HF copy (500) and zip copy (500), against the
11 shared databases (`D/zip/minidev/MINIDEV/dev_databases`); files, sha256, URLs, pinned
commits and the CC BY-SA 4.0 licence source are in `provenance.json`. Scripts/derived JSON
here; sqlglot venv, evaluator code and full typing dumps stay in `$W`. Python: worktree uv env
unless noted (3.13.7, `sqlite3.sqlite_version` 3.53.4); sqlglot venv 3.12.11.

## 1. Parsers: sqlglot vs libpg_query (postgast)

sqlglot 30.18.0, installed 2026-09-04. `sqlglot.parse_one(sql, read="sqlite",
error_level=RAISE)` parses every gold: 1534/1534 bird_dev, 500/500 both Mini-Dev copies
(`sqlglot_parse.py`). Zero failures, so no five to list as representative; `RAISE`
rejects garbage SQL and IIF lands in a real node, not a swallowed blob. Transpilation
fidelity is out of scope.

`parse_statement` (postgast/libpg_query) refuses far more (`postgast_parse.py`,
`postgast_summary.json`):

| set | total | parsed | refused | sqlglot+/libpg- | sqlglot- |
|---|---|---|---|---|---|
| bird_dev | 1534 | 1407 | 127 | 127 | 0 |
| minidev_hf | 500 | 455 | 45 | 45 | 0 |
| minidev_zip | 500 | 454 | 46 | 46 | 0 |

All refusals trace to two constructs, matched by question_id (`postgast_failures_*.json`): a
backtick identifier (123/43/43; tokenizer breaks on the backtick, error position is whatever
bareword follows, e.g. q0 `` `Free Meal Count (K-12)` ``, q695 `` `Name` ``) and MySQL/SQLite's
`LIMIT offset,count` (4/2/3; "LIMIT #,# syntax is not supported"; q50 `LIMIT 6, 1`). Nothing
else refuses: 0 placeholders, 0 multi-statement, 0 non-SELECT. Double-quoted literal read
silently as an identifier (`double_quote_confirm.py`): three synthetic statements with
a double-quoted token naming no column/table all `parse_statement` without error, but this
barely occurs in the corpus: one gold carries any double-quoted token (bird_dev q1101, table
`"Match"`, real, not a literal), zero carry a genuine literal (`census_summary.json`).

## 2. Feature census (sqlglot AST; regex fallback stated per row)

Counts of golds carrying the construct at least once (`census.py`,
`census_summary.json`):

| construct | bird_dev | hf | zip | construct | bird_dev | hf | zip |
|---|---|---|---|---|---|---|---|
| backtick | 123 | 43 | 43 | subquery in FROM | 33 | 24 | 24 |
| IIF | 149 | 89 | 89 | CTE | 9 | 6 | 6 |
| any date func | 123 | 54 | 52 | EXISTS | 2 | 2 | 2 |
| CAST AS REAL/FLOAT | 152 | 93 | 92 | UNION | 1 | 1 | 1 |
| CAST AS INTEGER | 3 | 2 | 2 | INTERSECT/EXCEPT | 2 | 1 | 2 |
| int division (approx) | 1 | 0 | 0 | SUBSTR | 58 | 27 | 27 |
| LIMIT, no ORDER BY | 6 | 4 | 4 | INSTR | 7 | 3 | 3 |
| text vs numeric (approx) | 28 | 6 | 6 | ROUND | 4 | 4 | 4 |
| window (OVER) | 5 | 5 | 5 | DISTINCT | 179 | 61 | 62 |
| GROUP BY bare col (approx) | 16 | 5 | 6 | COUNT(\*) | 26 | 14 | 14 |
| LIKE | 42 | 21 | 21 | COUNT(col) | 453 | 156 | 158 |
| \|\| | 2 | 1 | 1 | GLOB | 0 | 0 | 0 |

Approximated items use `pragma_table_info` declared-affinity (`INT*` INTEGER, `CHAR*`/`CLOB`/
`TEXT*` TEXT, `REAL`/`FLOA*`/`DOUB*` REAL, else BLOB/NUMERIC, sqlite.org/datatype3.html 3.1)
through the statement's FROM aliases, `COUNT(...)` as INTEGER, unresolved columns skipped: a
floor, not exact. The one int-division hit, q1279 (thrombosis_prediction), is `COUNT(...)/
COUNT(...)` with no CAST; every other ratio is defensively CAST first, so unguarded
truncation is rare here, not common.

## 3. BIRD's SQLite evaluator

`D/minidev_repo/evaluation_ex.py`/`evaluation_utils.py` and, at
`AlibabaResearch/DAMO-ConvAI`, `bird/llm/src/evaluation.py` (`$W/damo_evaluation.py`; both
pinned commits and sha256 in `provenance.json`): the same evaluator, Mini-Dev split it in
two. Lines below are Mini-Dev's.

- `sqlite3.connect(db_path)` (utils.py:47), no `detect_types`: `text_factory` `str`,
  `isolation_level` `""` by default; `cursor.execute` then `fetchall()` both sides (:61-64).
- Verdict `set(predicted_res) == set(ground_truth_res)` (ex.py:20), not stated in code, only a
  consequence of Python equality (`bird_eval_semantics.py`): `1 == 1.0 == True` and
  hash alike, a set merges them; `b"x" != "x"`; two empty results match; a `nan` from one fetch
  never equals another's (fresh float objects; SQLite's `x/0` is `NULL`, never NaN, per
  sqlite.org/lang_expr.html). Tuples need equal length/position: no column-name alignment.
- `func_timeout(meta_time_out, ...)`, default 30.0 (:117); `FunctionTimedOut`/`Exception` both
  set `res=0` (:36-41), building a `"timeout"`/`"error"` list never read again before the final
  `{"sql_idx", "res"}` (:42): no message kept, pass/fail only. `Pool` appends in completion
  order (:46-66), `sort_results` re-sorts by `sql_idx` first (:106-107,145): order-neutral.
  Split: predicted on `"\t----- bird -----\t"`, gold on `"\t"` per line, `.strip()`ped first
  (utils.py:86,98-99). Feature versions (sqlite.org/changes.html): IIF 3.32.0, window
  functions 3.25.0, RETURNING 3.35.0, RIGHT/FULL JOIN 3.39.0; this machine's 3.53.4 is past
  every construct in section 2.

## 4. Python sqlite3 measurements

**(a) stored columns.** One scan per table (`storage_class_census.py`), 806 columns, 3,898,138
rows (ADR-0013's 3,898,114 plus the 24 `sqlite_sequence` rows). Zero hold more than one non-null
storage class as stored; the 8 that disagree with declared affinity are all `sqlite_sequence`
(undeclared, BLOB affinity, expected): the real risk is at the *expression* level, not stored.

**(b) every gold's result columns** (`run_golds_typing.py`, 30 s cap, own subprocess so
a hang is killed on schedule, both sets 2034/2034 covered): minidev_hf 493 ok, 7 timeout;
bird_dev 1501 ok, 33 timeout, 0 errors either set. 0 result columns mix int/float or
text/number anywhere, 0 golds where a bare Python `set()` of the gold's own rows is smaller
than one keyed on `(type, value)` per cell (`typing_summary.json`).

**(c) REGEXP.** No function registered: `no such function: REGEXP`; after
`create_function("REGEXP", 2, ...)` it runs; zero golds anywhere call REGEXP. **(e)
query_only:** `PRAGMA query_only=1` and plain `mode=ro` both refuse an INSERT with the same
text, `attempt to write a readonly database`.

**(d) read-only and WAL** (copy of `student_club` in `$W`, `PRAGMA journal_mode=WAL` plus a
write). `mode=ro` opens and reads correctly with `-wal`/`-shm` present, removed, or with
`immutable=1`. Of the 11 shipped databases, `card_games` already ships in WAL mode; the other
ten are `delete` (read-only `PRAGMA journal_mode`, changes nothing).

**(f) per-connection state.** `sqlite_version()` 3.53.4; `collation_list` BINARY, NOCASE,
RTRIM; `encoding` UTF-8; `compile_options` in full (`measurements_c_to_f.json`). Default LIKE
is ASCII case-insensitive; `case_sensitive_like=1` turns that off. `reverse_unordered_selects
=1` reverses row order on an unordered gold (q1500, 976 rows, same multiset). Float text:
Python `repr(1/3)` is the 16-digit shortest round-trip `0.3333333333333333`;
`CAST(1.0/3 AS TEXT)` gives the 17-digit `0.33333333333333332`, both the identical double, but
SQLite's docs promise "about 15.95 significant decimal digits" (sqlite.org/datatype3.html),
`printf` 16 (26 with `!`): the renderers agree on value, not digits.

## 5. Against ADR-0014

- Point 1 (no declared column type): confirmed for stored data and results alike (0 mixing in
  4a/4b); the live risk sits at the *expression* level (`/`, `IIF`, a date function), never a
  column as stored.
- Point 4, grammar: confirmed as section 1 measured it (two refusal shapes only; the
  double-quoted risk real but rare).
- Open Q1 (R-SET "a value only meets a value of its own type"): narrowed. Stored data never
  mixes class, 1/1,534 golds has an unguarded int division, 0/2,034 result sets mix type at
  the column level: a SQLite backend rarely hits R-SET's case, but rarely is not never (q1279,
  q879).
- Open Q2 (BIRD's Python equality vs a typed reading): answered here. `1 == 1.0 == True` never
  merges a gold's own rows and `x/0 = NULL` keeps NaN out, so EX and a typed R-SET would not
  diverge on `1` vs `1.0`; both still diverge on q1279's truncated match.
- Open Q3 (Spider vs BIRD dev first): out of scope; not measured here.

## What changes in AttestQL

- (claim) claims-register: sqlglot 30.18.0 parses 100% of BIRD dev and both Mini-Dev SQLite
  copies; postgast refuses 127/1534, 45/500, 46/500, all backtick/`LIMIT #,#`. The
  double-quoted-literal risk ("Any engine but PostgreSQL") is real but measured at 1/2,534
  occurrences and 0 genuine literals: narrowing, not dismissing, it.
- (non-claim) do not claim "SQLite golds are dynamically typed in practice": stored data
  (0/806) and every gold's result set (0/2,034) are uniform; the variance is expression-level.
- (code) ADR-0014 point 2 (`audit/sqlite.py`, unbuilt): `PRAGMA query_only=1` gives the
  read-only envelope's refusal text for free, no `BEGIN READ ONLY` analogue needed; point 3
  (parser): the allowlist re-stated over sqlglot's tree can rely on 0 overlap between the
  backtick/`LIMIT #,#` refusal reasons and any other found.
- (no change: measurement only) 4b full coverage, both sets: 2034/2034, 0 errors, 0 mixing,
  0 python-set-merges (`typing_summary.json`).
