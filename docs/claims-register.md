# Claims register

**Measured 2026-09-03 and 2026-09-04**, at the `v0.1.2` tag. Every claim this project makes, the artifact that owns
it, and who checked it. A claim is only as good as its owning artifact.

**Negative claims decay.** A statement that something does not exist or has not happened is true
only at the date beside it and must be re-measured, not inherited.

Verification parties: **IMPL** the implementing session; **COORD** the coordinating session, which
re-ran or re-derived independently; **OWNER** the owner by hand.

## 1. What exists

| # | Claim | Owning artifact | Verified by |
|---|---|---|---|
| A1 | `attestql audit` runs a gold and a second statement on PostgreSQL inside a read-only transaction, with the session settings read back and the run refused on drift | `src/attestql/audit/postgres.py`, `tests/test_audit_executor_refuses_a_session_that_drifted.py` | IMPL, COORD |
| A2 | Projections are compared by position and declared type; a prediction that names a column differently from the gold is EQUAL when the values agree, and the counterexample notes the names | `src/attestql/evidence/replay.py`, `tests/test_replay_equality.py`, `tests/test_audit_compares_a_gold_with_a_second_statement.py` | IMPL, COORD |
| A2a | The verdict is EQUAL, NOT_EQUAL or NOT_COMPARABLE; NOT_COMPARABLE names the mismatched preconditions: fixture digest, serialization, rule, ordering, and the settings `TimeZone`, `DateStyle`, `IntervalStyle`, `extra_float_digits`, database collation | `src/attestql/evidence/replay.py`, `tests/test_replay_equality.py` | IMPL, COORD |
| A3 | The evidence record has twenty required fields and no defaults; an incomplete record cannot be built | `src/attestql/evidence/record.py`, a test asserts the exact field tuple | IMPL, COORD |
| A4 | Canonical serialization is deterministic across processes and renders int, decimal, bool, text, date, timestamp and NULL; floats are loaded from the server's text form as decimals under the `extra_float_digits` precondition | `src/attestql/evidence/serialize.py`, `tests/test_canonical_serialization.py` | IMPL, COORD |
| A5 | The three upstream-reported gold defects of BIRD Mini-Dev (q1029, q879, q207) reproduce on the real dump with the golds of the GitHub zip `minidev.zip` (sha256 `cc48ba16…`, downloaded 2026-09-02): BIRD EX 0, comparator NOT_EQUAL, differing rows recorded. On the Hugging Face file (`birdsql/bird_mini_dev`, 2026-01-18) q879 is corrected and q1029 and q207 are not | `plans/reports/spike-260902-three-gold-defects/` (the spike's records and counterexamples); re-derived with independent SQL | IMPL, COORD |
| A6 | The same three reproduce on a few-row fixture, against a read-only role, inside the merge gate: the command runs in a container every time `just check` runs, and its console script is started as its own process | `tools/audit-sandbox/`, `tests/test_audit_end_to_end.py`, `justfile` recipe `sandbox` | IMPL, COORD |
| A7 | Two constructed predictions score 1 under BIRD's set equality and NOT_EQUAL under the typed comparison (DISTINCT dropped; order reversed) | `tests/test_audit_sandbox_smoke.py`; the spike's constructed-prediction records stay in the private history before publication | IMPL, COORD |
| A8 | Over all 498 distinct golds of the GitHub zip `minidev.zip` (sha256 `cc48ba16…`, downloaded 2026-09-02) the gold-only probes fired on 52; classified by hand: 11 gold defects, 22 evaluation hazards, 16 no action, 3 sweep artifacts; actionable precision 67 %, the direction probe alone 17 % | `plans/reports/measurement-260902-2226-gold-only-probes-mini-dev.md`; `plans/reports/sweep-260902-gold-only-probes/` | IMPL, COORD by hand |
| A9 | Nine of the 498 golds of the GitHub zip `minidev.zip` (sha256 `cc48ba16…`, downloaded 2026-09-02) (1.8 %) return a float aggregate whose value changes with summation order | `plans/reports/sweep-260902-gold-only-probes/fired.json`; q1380 re-run by hand on the server | COORD |
| A10 | In the GitHub zip `minidev.zip` (sha256 `cc48ba16…`, downloaded 2026-09-02), `mini_dev_postgresql.json`, `_sqlite.json` and `_mysql.json` each hold 500 entries and 498 distinct ids; 137 and 138 are duplicated byte-identically and 119 and 120 are absent. The Hugging Face file of 2026-01-18 holds 500 distinct ids, corrects q879 and changes q1322; nothing else differs | `plans/reports/minidev-260903-zip-against-hf/` (`diff.json`, `comparison.md`), checked 2026-09-03 | COORD |
| A11 | The shuffle probe writes only tables, only into a scratch schema that already exists and the role may create in, inside an explicit read-write transaction under an advisory lock; it creates no schema, drops none, and leaves no table behind; a missing or unwritable scratch schema is reported in `summary.json`, not fatal | `src/attestql/audit/postgres.py`, the executor tests, `tests/test_audit_end_to_end.py` (the scratch schema is empty after the run) | IMPL, COORD |
| A12 | The command runs over the full Mini-Dev PostgreSQL gold set of the GitHub zip `minidev.zip` (sha256 `cc48ba16…`, downloaded 2026-09-02) on a pinned PostgreSQL 16 and finishes with exit status 0 in gold-only mode | `plans/reports/audit-260902-minidev-gold-only/` (`stdout.txt`, `summary.json`): 498 questions, 39 smells fired on 30 golds, 0 errors, exit 0, 62 s, on `postgres@sha256:c1b378...`, run 2026-09-03 on the tree tagged `v0.1.1`; the addendum of the measurement report classifies the rows the sweep did not | COORD |
| A12b | The same command over the Hugging Face file of the question set (`birdsql/bird_mini_dev`, `data/mini_dev_pg-00000-of-00001.json`, sha256 `7fa740ef…`, 2026-01-18): 500 questions, 39 smells fired on 29 golds, 0 errors, exit 0, 85 s; against the zip run the only gold that stops firing is q879, corrected upstream, and q94's tie label moves as the addendum explains | `plans/reports/audit-260903-minidev-hf-gold-only/` (`stdout.txt`, `summary.json` with the origin recorded), run 2026-09-03 | COORD |
| A13 | A lost connection, a gold naming a table the database does not hold, and a URI DSN are each one question's error line or one refusal; `summary.json` is always written | `src/attestql/audit/cli.py`, `postgres.py`, `tests/test_audit_command_runs_over_a_question_file.py`, `tests/test_audit_survives_a_lost_connection.py` | IMPL, COORD |
| A14 | The parser is `postgast` 0.1.0 (BSD-2, `libpg_query`); over the 498 Mini-Dev golds it agrees with the previous parser on every recorded field except the spelling of four casts, and the replay rule matches the sweep 498 of 498 | `plans/reports/parser-260903-postgast-against-pglast/` (`compare_parsers.py`, `current-parser.json`, `previous-parser.json`, `comparison.md`) | IMPL, COORD re-ran |
| A15 | The test suite passes and the gate is green on Python 3.13 and 3.11 | `just check` at the tag on Python 3.13: 525 passed, 20 skipped in the default suite, the 20 sandbox-marked tests passing under `just sandbox`, which `just check` runs; the same suite and pyright strict on Python 3.11 in a separate environment: 525 passed, 0 errors | IMPL, COORD |

## 2. What is known about the neighbours (negative claims, dated)

| # | Claim | Owning artifact | Verified by |
|---|---|---|---|
| N1 | BIRD's evaluator is `set(predicted_res) == set(ground_truth_res)` over `fetchall()` | [evaluation_ex.py](https://github.com/bird-bench/mini_dev/blob/main/evaluation/evaluation_ex.py), read 2026-09-02 | COORD |
| N2 | No installable tool takes a gold, a prediction and a PostgreSQL database and reports where they differ | `plans/reports/discovery-260902-1856-real-problem-candidates.md`, searched 2026-09-02 | COORD |
| N3 | SpotIt+ runs without a key, is symbolic in MySQL dialect, found q207 at bound 2, missed q1029 at bound 2, cannot detect q879 (strips CAST in ORDER BY); its LICENSE is all rights reserved | trial 2026-09-02 at commit `abee2ba`, `plans/reports/mechanism-260902-2055-gold-audit-detection.md` | IMPL, COORD |
| N4 | Nobody outside this repository has used the tool | measured at the tag; the falsification date is 60 days after it (ADR-0013 point 10) | OWNER |
| N5 | The package is not published on PyPI and the repository has no public remote | measured 2026-09-03, at the tag; publication is the owner's step after it | COORD |

## 3. Claims deliberately NOT made

| Non-claim | Why it matters |
|---|---|
| NOT_EQUAL means the gold is wrong | It means two statements disagree on this data under this rule. Deciding is a person's job; the record makes it a short one |
| The probes are precise | They are heuristics: 67 % actionable over the Mini-Dev fires, and the direction probe 17 %, which is why it is off by default |
| Any engine but PostgreSQL | SQLite is the first expansion candidate; nothing is built |
| Differentiating data | Pairs that agree on the shipped rows are found only by the shuffle probe |
| Two audits may share one scratch schema at the same time | The advisory lock serializes the copies' creation and removal, not the whole run; a second run can recreate a copy the first is reading. Run one audit per scratch schema at a time |
| The validator admits no wrong statement for this tool | The AST allowlist validator in `kernel/` is off the product path, bound to the retired synthetic schema, and its claim is not re-asserted here |
| Any security, privacy or production property | The tool runs as the role you give it; use a read-only role |
| Proof of correctness | "Attest" means a typed replay with the preconditions named, nothing more |

## 4. History

Claims about the V2.9 evidence harness, Slice 1 milestones M0 to M6 and the WP2 PostgreSQL
authority evidence were retired with their code by ADR-0013 on 2026-09-02. The register as it stood
then, and every artifact it named, is in the private history before publication,
which the owner can provide on request.

## 5. Upstream engagement

Filed 2026-09-04 by the owner under their personal GitHub identity, as ADR-0013 point 9 requires.
Each row is evidence for the falsification criterion of ADR-0013 point 10; a maintainer's reply or
a corrected gold is recorded here when it happens, with its date, and not before.

| # | Where | What was reported | Link |
|---|---|---|---|
| U1 | `bird-bench/mini_dev` issue 38, comment | q1029 orders `ASC NULLS FIRST` for "highest"; both copies of the question set carry it | [comment](https://github.com/bird-bench/mini_dev/issues/38#issuecomment-5529732756) |
| U2 | `bird-bench/mini_dev` issue 39 | q207 joins `bond` on `molecule_id` and returns 13 elements instead of 5; same defect as DAMO-ConvAI 227 | [issue 39](https://github.com/bird-bench/mini_dev/issues/39) |
| U3 | `bird-bench/mini_dev` issue 40 | the GitHub zip and the Hugging Face dataset differ: ids 137 and 138 duplicated and 119 and 120 missing in the zip, q879 and q1322 with different golds | [issue 40](https://github.com/bird-bench/mini_dev/issues/40) |
| U4 | `ai-ar-research/SpotIt-plus` issue 1 | the paper calls SpotIt+ open source while its LICENSE reserves all rights; asks which licence applies | [issue 1](https://github.com/ai-ar-research/SpotIt-plus/issues/1) |

Replies received: none yet (checked 2026-09-04).
