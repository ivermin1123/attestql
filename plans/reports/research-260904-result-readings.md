<!-- cspell:ignore psycopg BIRD's DAMO ConvAI calculate_ex livesqlbench defog kungfuai HKUSTDial XGenerationLab Pourreza XiYan Zhong Klein bird_ex R-SET forgiven unjust ruiqi -->

# R-A: how public evaluators read a result, and what each makes of the 170 rows

Sources, hashes, commits: `research-260904-result-readings/sources.json`. Full per-evaluator
dimension table (item 1's table): `research-260904-result-readings/evaluator-matrix.md`, summarized
below. Scripts, run in order to reproduce `results.json`/`aggregate.json`/`cells.json`:
`build_pairs.py`, `readings.py`, `execute_pairs.py`, `aggregate.py`.

## 1. What each evaluator's own comparator does

- **BIRD Mini-Dev / original BIRD / BIRD VES**: `set(predicted) == set(gold)` over `fetchall()`
  tuples, no dialect-specific handling beyond the driver; VES only times pairs this check passed.
  `N1`, already in the claims register.
- **Spider 1.0 exact match**: compares parsed SQL AST components (SELECT/WHERE/GROUP/ORDER), never
  executes; not a result reading. **Spider 1.0 execution accuracy**: executes on SQLite but maps
  columns by AST value-unit identity through a foreign-key map, not position; list-equality per
  column, always order-sensitive. Needs a parsed AST and schema map to reuse; out of scope here.
- **test-suite-sql-eval** (`result_eq`, EMNLP 2020, arXiv 2010.02840): multiset equality over every
  column permutation; DISTINCT stripped from both statements' text by CLI default before they run,
  so rows carry raw join fanout; order-sensitive iff the stripped gold text has ORDER BY. Designed
  for several distilled DB copies requiring agreement on all; only one DB is available here.
- **Spider 2.0** (`compare_pandas_table`): per-gold-column existence check against predicted pandas
  columns, any position, 1e-2 numeric tolerance, NaN to 0; equal row counts required for any column
  pairing, so any multiplicity difference fails either way; row order matters unless a per-instance
  `ignore_order` flag says otherwise (Mini-Dev has none; mapped here from the gold's own ORDER BY).
- **BIRD-CRITIC-1 / LiveSQLBench** (each ships its own `ex_base`): BIRD's `set()` check plus
  date-to-string coercion, plus a guard BIRD lacks: **either side empty scores 0**, so two
  statements both correctly returning no rows are refused, not credited. LiveSQLBench also rounds
  Decimal/float to 2 dp (`ROUND_HALF_UP`), order-sensitive (list equality) when per-instance
  metadata says so. Neither ships one fixed comparator: a per-instance `test_cases` snippet calls
  `ex_base`, optionally after `remove_distinct`; the shared primitive is reused here.
- **defog-ai/sql-eval** (`compare_df`): unconditionally drops duplicate rows both sides (stronger
  than any declared DISTINCT), matches columns by name after alphabetical sort, sorts rows unless
  category/question text says `order`/`sort`/`arrange`; NaN filled with `-99999`, colliding with a
  real `-99999` value.
- **Vanna, Alpha-SQL, XiYan-SQL, CHASE-SQL**: none carry gold-comparison code at the pinned commit.
  Vanna's accuracy paper is 180 hand-judged trials. Alpha-SQL's reward model is a precomputed
  self-consistency score or (commented out) a `frozenset`-grouped majority vote among the model's
  own candidates, never a gold; it does not reuse BIRD's function. XiYan-SQL's named repository is a
  paper/README page, no code. CHASE-SQL has no official repository; the closest public code
  (`kungfuai/chase-sql`, unofficial) has no evaluator.

## 2. Applying six executable readings to the 170 rows

Executable readings (operate on two already-fetched result sets): BIRD's `set()` check re-executed
faithfully in a fresh psycopg2 environment (own venv, not the tool's), test-suite's `result_eq`
(real DISTINCT-stripped re-execution, not a post-hoc approximation), BIRD-CRITIC's `ex_base`,
LiveSQLBench's `ex_base`, defog's `compare_df`, Spider 2.0's `compare_pandas_table`. All 170 pairs
(`classification.json`'s `per_file[<model>].rows`) ran gold and prediction on the research server,
one psycopg2 connection and read-only transaction per statement, `SET LOCAL
max_parallel_workers_per_gather = 0` and `statement_timeout = '30s'`, rolled back after each pair;
0 errors over 340 statements (170 pairs times two, plus 164 more where stripping DISTINCT for
test-suite changed the text). Fetched rows are in `$W/pairs_data/` (not this repository).

**BIRD re-statement check.** My own `set(gold) == set(pred)` gives `True` on 164 of 170, `False` on
exactly 6, all class C (declared-type mismatch), matching `A16`'s six known float8-against-numeric
slots exactly: q1057 (gpt-35-turbo-instruct), q168 (gpt-4-32k), q800 (gpt-4-32k, gpt-4), q960
(gpt-4-turbo, gpt-4). Reproduces `A16` independently: a native psycopg2 float and a `Decimal`
compare unequal in Python when the float has no exact decimal representation, same server value.

**Cross-tab, forgiven (reading says EQUAL) vs refused (reading says NOT_EQUAL), by hand class:**

| reading | A forgiven/refused (of 69) | B forgiven/refused (of 74) | C forgiven/refused (of 27) | total forgiven/refused (of 170) | A-share of refused |
|---|---|---|---|---|---|
| bird_ex (re-executed) | 69/0 | 74/0 | 21/6 | 164/6 | 0 % |
| test-suite `result_eq` | 52/17 | 60/14 | 21/6 | 133/37 | 46 % |
| BIRD-CRITIC `ex_base` | 64/5 | 74/0 | 21/6 | 159/11 | 45 % |
| LiveSQLBench `ex_base` | 64/5 | 72/2 | 27/0 | 163/7 | 71 % |
| defog `compare_df` | 67/2 | 74/0 | 21/6 | 162/8 | 25 % |
| Spider 2.0 `compare_pandas_table` | 0/69 | 0/74 | 27/0 | 27/143 | 48 % |

Question ids per cell: `cells.json`; raw per-row verdicts: `results.json`; counts: `aggregate.json`.

No row is refused by all six readings; the most any row is refused by is 4 of 6 (2 class-A, 6
class-C sharing the float artifact). 47 class-A and 60 class-B rows are refused by exactly one
reading (usually Spider 2.0): the readings disagree with each other about as much as they disagree
with `bird_ex` -- six different, only partly overlapping signals, not one signal read six ways.

**Spider 2.0** refuses on multiplicity alone (row-count mismatch fails before its column check
runs): essentially all of A and B, and forgives all of C (type-blind tolerance) -- near the mirror
of AttestQL's own split (138 by multiplicity, 32 by declared type). **defog** is weakest at real
wrong answers (25 % A-share): unconditional `drop_duplicates` absorbs most of what A and B share.
**LiveSQLBench** has the best A-share (71 %) but fewest refusals (7): rounding forgives all of C,
its empty-guard and order-sensitivity catch only a few A beyond `bird_ex`.

**Not applicable, one line each:** Spider 1.0 exact match compares SQL text, nothing to feed it two
row sets for. Spider 1.0 execution accuracy needs a parsed AST and foreign-key map to identify
columns; a positional approximation is just AttestQL's own R-ORD reading, already computed.
test-suite-sql-eval's multi-database agreement needs distilled `bird` copies not available here;
`result_eq` above runs single-database. Spider 2.0's multi-gold wrapper does not apply (one gold
per question). Vanna, Alpha-SQL, XiYan-SQL, CHASE-SQL carry no comparator (section 1).

## 3. What this means for AttestQL

**Compute and record.** test-suite's `result_eq` (DISTINCT-stripped, column-permutation-tolerant
multiset equality) disagrees with `bird_ex` on 37 of 170, more than any reading except Spider 2.0,
and unlike Spider 2.0 is not just "refuses every multiplicity difference" (46 % A-share vs
`bird_ex`'s fixed 0 %). Worth a second field, `test_suite_ex`, beside `bird_ex` in
`src/attestql/audit/compare.py` (sibling to `bird_ex()`), in `counterexample_json` and
`summary.json`: the one reading whose disagreement with AttestQL is neither near-total (Spider 2.0)
nor near-empty (`bird_ex`, defog).

**One sentence only, no new field.** BIRD-CRITIC's and LiveSQLBench's empty-both-sides refusal is
already subsumed: q565, the empty-vs-empty class-A row both catch, is flagged today via
`mechanism: type` (a text label column against a `bool` column), independent of row count. A
claims-register sentence suffices: Vanna and Alpha-SQL/XiYan-SQL/CHASE-SQL strengthen `N2` (no
installable tool reports where a gold and a prediction differ) -- none ship gold-comparison code
either. Spider 2.0's type-blind, multiplicity-strict design is worth one sentence next to
`ADR-0004`'s NaN amendment, an external instance of drawing the "same row" line differently from
the owner's 2026-08-31 decision that a coercion step must not decide row-set membership -- not a
reason to change it.

**Changes how a claim reads, not the claim.** `A17`'s 40.6 % precision (69 of 170 wrong answers
credited) is precision against one fixed denominator: rows where `bird_ex` says EQUAL and typed
says NOT_EQUAL. Under LiveSQLBench's own reading as the flagging rule the same 170 rows show 71 %
precision on its 7-row refused set; under Spider 2.0's, 48 % on 143 rows: the percentage is a
property of which rows a reading refuses, not a fixed fact about the 170. `A17` should keep
`bird_ex` as its baseline (what the benchmark scores), and could add a clause that 40.6 % is
`bird_ex`-relative, not an estimate holding under every public reading.

## What changes in AttestQL

- (claim) Add `test_suite_ex` beside `bird_ex`: `src/attestql/audit/compare.py` gains a function
  alongside `bird_ex()`, rendered in `counterexample_json`/`summary.json`; new claims-register row
  cites `ruiqi-zhong/test-suite-sql-eval` `result_eq`, commit `48cb78ec`.
- (claim) `docs/claims-register.md` N2: add "no model-generation harness examined (Vanna, Alpha-SQL,
  XiYan-SQL, CHASE-SQL) ships gold-comparison code either", dated 2026-09-04.
- (claim) `docs/adr/0004-replay-equality-r-ord-r-set.md`: one sentence beside the NaN amendment
  citing Spider 2.0's type-blind, multiplicity-strict `compare_pandas_table` as an external instance
  of the same line drawn differently.
- (non-claim) `A17`'s 40.6 % precision: no number changes; add a clause that it is `bird_ex`-
  relative, since other readings' own refused sets show 25 % to 71 % over the same 170 rows.
- (no change: already subsumed) BIRD-CRITIC's/LiveSQLBench's empty-both-sides refusal: q565 shows
  AttestQL's existing declared-type check already catches what that guard catches.
- (no change: not comparable) Spider 1.0 exact match, Spider 1.0 execution accuracy, BIRD VES: none
  read two result sets the way AttestQL's replay does.

## Unresolved

- Whether `test_suite_ex` belongs beside `bird_ex` (always computed) or as an opt-in probe like the
  gold-only smells (`ADR-0013` point 2's `--fail-on-smell`): evidence for the field, no placement
  recommendation. The DISTINCT-stripped re-execution used the tool's declared gold/prediction
  pairing only, not the zip gold, so whether the disagreement rate holds there too is not measured.

Status: DONE
Summary: Read nine evaluator families at pinned commits; ran six executable readings against all
170 real gold/prediction pairs on the research server (0 errors), verified the BIRD re-statement
against the six known float/Decimal rows, recommend one new field (`test_suite_ex`) beside `bird_ex`.
