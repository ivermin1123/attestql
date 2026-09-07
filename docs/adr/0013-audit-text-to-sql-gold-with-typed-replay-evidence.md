# ADR-0013: AttestQL audits text-to-SQL gold and predictions with typed replay evidence, and the Slice 1 product path is retired

**Status:** Accepted. **Date:** 2026-09-02. Proposed and accepted the same day, with six owner
amendments folded in before acceptance.

## Context

The owner's reorientation of 2026-09-02: open source, built to be used and not sold; the problem
must be real and provable outside this repository on public data; large changes are expected;
what survives is the evidence record, deterministic serialization, the replay comparator, the
evaluation clock, the AST allowlist validator and the honesty rules. The discovery report
(`plans/reports/discovery-260902-1856-real-problem-candidates.md`) ranked five candidates and the
owner accepted the first.

**The problem and its evidence.** Text-to-SQL evaluation scores by execution match on one shipped
database, and the gold it scores against is often wrong. BIRD's evaluator is
`set(predicted) == set(gold)` over `fetchall()`, so duplicates, order and types never count. Wrong
gold sits open and unanswered on four trackers ([mini_dev #38](https://github.com/bird-bench/mini_dev/issues/38),
[mini_dev #24](https://github.com/bird-bench/mini_dev/issues/24),
[Spider2 #203](https://github.com/xlang-ai/Spider2/issues/203),
[DAMO-ConvAI #227](https://github.com/AlibabaResearch/DAMO-ConvAI/issues/227)); CIDR 2026 measured
52.8 % annotation error in BIRD Mini-Dev and 66.1 % in Spider 2.0-Snow
([p5-jin](https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf)). No installable tool takes a gold,
a prediction and a PostgreSQL database and says where they differ (checked 2026-09-02; this
negative claim decays like every other).

**The spike, stated honestly.** A spike (its artifacts: `plans/reports/spike-260902-three-gold-defects/`;
its code stays in the private history before publication) reproduced three
upstream-reported defects on the Mini-Dev PostgreSQL dump (q1029, q879, q207). On those three
real rows the verdict coincides with BIRD's: EX is 0 and the comparator says NOT_EQUAL. What the
tool adds on real data is the record, the counterexample rows, and two smells that fired
correctly. Value beyond BIRD's evaluator is so far proven only on two constructed predictions,
where EX says 1 and the comparator says NOT_EQUAL. No README is written before the Phase 3
measurement of the gold-only probes over all of Mini-Dev. Mechanism, one page:
`plans/reports/mechanism-260902-2055-gold-audit-detection.md`.

**SpotIt+** ([arXiv 2603.04334](https://arxiv.org/abs/2603.04334),
[source](https://github.com/atremante26/SpotItPlus)), trial-run 2026-09-02 at commit `abee2ba`:
runs without a key, purely symbolic in MySQL dialect over a bundled schema file, never reads the
data; found the q207 join defect at bound 2, called q1029 "Equivalent" at the suggested bound
(the bound must exceed the LIMIT), and cannot detect q879 because it strips CAST inside ORDER BY.
It cannot say which statement is wrong, writes no record, and its LICENSE is all rights reserved
with no grant of use. Research-grade; not reused now, and not built on later even if the licence
changes. Amended 2026-09-04: the LICENSE was misread. Its first sentence reserves all rights and
its second grants use, modification and redistribution under the modified-BSD text it reproduces
(one commit, `fbf5460`, 2026-02-15, unchanged at `abee2ba`; the repository now lives at
`ai-ar-research/SpotIt-plus`). The decision not to reuse or build on it stands on the grounds
above, not on the licence; the register's N3 and U4 carry the correction.

**The user.** The owner, grading model-generated SQL against golden statements, which is the M6
task; and anyone who maintains or evaluates against a text-to-SQL benchmark. One sentence: a
benchmark maintainer runs one command on Mini-Dev PostgreSQL and gets the list of gold statements
that look wrong, each with a counterexample and an evidence record.

## Decision

1. **AttestQL becomes an audit tool for text-to-SQL gold and predictions.** The name stays: what
   is attested is that a stated answer survives typed replay. "Governed data agent", "natural
   language" and "proof" leave every forward-looking document.
2. **The first artifact is `attestql audit`.** A stranger runs:

   ```text
   uv tool install .        # from a checkout, until the package is on PyPI
   psql -d bird -f MINIDEV_postgresql/BIRD_dev.sql
   attestql audit --dsn "host=localhost dbname=bird" \
       --questions mini_dev_postgresql.json --predictions preds.json --out audit/
   ```

   One line per question, one directory per NOT_EQUAL, a summary line with the counts, and
   `audit/summary.json`:

   ```text
   q879  formula_1   R-ORD  NOT_EQUAL  smells=ordering-over-numeric-text  audit/q879/
   q1030 financial   R-SET  EQUAL
   498 questions: 2 NOT_EQUAL, 0 NOT_COMPARABLE, 3 smells fired
   ```

   Exit status: 0 no disagreement, 1 at least one NOT_EQUAL, 2 tool error. Counts live in the
   summary, never in the exit code. Without `--predictions` the gold-only probes run (s1, s3, s4
   of the mechanism page, s2 against the question text); they exit 0 by default because smells
   are heuristics, and `--fail-on-smell` makes them exit 1 for anyone who wants CI to block.
3. **Mechanism in release 1:** strict typed replay (M1) and disagreement records with smells (M2).
   Differentiating data (M3) waits for release 2 and will not be built on SpotIt+. The verdict
   compares answers under the ordering the question demands; each statement's own ORDER BY is
   recorded as data; NOT_COMPARABLE is reserved for a precondition mismatch.
4. **Engine.** PostgreSQL first: typed replay needs real column types, and SQLite's dynamic typing
   is itself the source of the type class of defects (q879). SQLite is the first expansion
   candidate because original BIRD runs on it. The executor interface and the record's backend
   identity field are engine-neutral from the first commit; no SQLite is built now.
5. **The evidence record is re-cut for a benchmark comparison,** per the 29-field mapping in
   `field-mapping.json` of the spike (private history before publication): 15 fields keep, 5 rename
   (`resolved_interpretation` to question metadata, `metric_definition_versions` to
   `question_set_version`, `execution_limits` to `session_settings_in_force`, `schema_version` to
   `fixture_schema_digest` taken as a parameter, `execution_metadata` to `executed_at` and
   `row_count`), 9 tenant and policy fields drop. `ReplayRule` and `SortKey` move into
   `evidence/`; a sort key becomes an expression. No defaults, as before.
6. **Preconditions.** Fixture digest, serialization descriptor, replay rule, canonical ordering,
   and exactly these session settings, the ones that change rendered bytes or order: `TimeZone`,
   `DateStyle`, `IntervalStyle`, `extra_float_digits`, and the database's default collation
   (`pg_database.datcollate`). Every other setting, `server_version_num` included, is recorded
   and never blocks. The fixture digest is computed from the server, not from a file: per
   referenced table, the schema digest (columns, types, nullability from `information_schema`)
   plus the exact row count; measured on Mini-Dev, 0.24 s for the schema of all 75 tables and
   0.26 s for the counts of 3,898,114 rows. A content digest per table (md5 of the sorted text
   rows) took 14.4 s for the whole dump and is optional (`--fixture-digest full`); whichever is
   used is computed once per run and cached in `audit/fixture.json`. The dump file's sha256 (2.6 s
   for 1.0 GB) is recorded when the file is given and is never a precondition.
   Amended 2026-09-05: two settings join the five. Turning the gather off does not fix the order a
   float sum is added in, because a hash aggregate that outgrows `work_mem` spills and adds each
   spilled batch's partial sums where the batch ended: 3 of the 9 summation-order-sensitive
   Mini-Dev golds return other last digits at `work_mem = '64kB'` than at 4 MB with the gather
   already off
   (`plans/reports/research-260904-postgres-result-preconditions/hashagg_workmem_demo.json`).
   The executor therefore holds `work_mem` at 4 MB and `hash_mem_multiplier` at 2, PostgreSQL 16's
   own defaults, on every execution, reads both back and refuses on drift, and a record states what
   its statement ran under rather than what the session was configured with.
7. **Retired, in two commits after the tag `slice1-final` on the last commit before deletion
   (both, and the tag, in the private history before publication).**
   First a refactor commit: the record stops depending on the catalogue (point 5). Then one pure
   deletion commit: `planner/`, `questions/`, `sql/`, `golden/`, `fixture/`, `answer/`,
   `contract/metrics.py`, `contract/schema.py`, `security/` (about 8,800 source lines with their
   tests); the executor's one surviving property, session settings read back and refused on
   drift, is ported into a read-only executor of about 150 lines. The 16-question catalogue is
   deleted, not kept as a fixture: Mini-Dev rows with real defects are the fixture now. `tools/`
   keeps only the sandbox runner, reshaped; the other harnesses go, artifacts staying in history.
   `kernel/` and `contract/clock.py` stay off the product path. Milestones M0 to M6 close;
   `docs/slice1-product-decision-brief.md` and `docs/slice1-implementation-plan.md` get a
   superseded banner; ADR-0002, 0005, 0007, 0008, 0009, 0011, 0012 are superseded by this record;
   ADR-0003, 0004, 0006 stand. The S0 register narrows to S0-02, S0-03, S0-07, S0-08.
   Amended 2026-09-03, before publication: `kernel/adapters/` (the vendored V2.9 validator and
   its adapter) leaves the tree with the GPL parser it imports, so `kernel/` keeps only the
   shared result types and the port protocols; ADR-0001, 0006 and 0010, the superseded ADRs, the
   Slice 1 documents and every report of the retired code stay in the private history before
   publication, up to that date, which the owner can provide on request.
8. **Licence.** Apache-2.0. `pglast` (GPLv3 or later) stays as the validator's parser, declared in
   the README; swapped only when someone outside asks to embed the validator. Amended 2026-09-02:
   the audit itself parses each statement to choose the rule and read the ordering
   (`audit/statements.py`), so the parser is on the product path after all; the README declares
   the runtime dependency, and a permissive binding is the first candidate change after the tag.
   Amended 2026-09-03, before publication: the parser is `postgast`, a BSD-2-Clause binding to
   `libpg_query`, pinned exactly; over the 498 Mini-Dev golds it agrees with the previous parser
   on every recorded field except the spelling of four casts (`x::real` for `CAST(x AS real)`),
   and the replay rule matches the sweep 498 of 498. Nothing GPL remains in the tree, and the
   material excerpted from BIRD is listed in `NOTICE` under its own CC BY-SA 4.0 licence.
9. **Upstream engagement.** Sessions draft; the owner reviews and files under their own identity.
10. **Falsification, 60 days after the first public push** (amended 2026-09-03; the tag `v0.1.0`
    that first named this window is in the private history before publication)**.** At least one of: an upstream gold row
    corrected or acknowledged as wrong with our counterexample cited; a person outside this
    repository uses the tool and leaves an issue or a pull request. Neither means reconsider.
    Met on 2026-09-05, by acknowledgement: the BIRD team answered the q1029 and q207 reports
    with "we will review and correct this issue in the next patch" and changed the Mini-Dev
    README on the zip-versus-Hugging-Face report; no gold row is corrected yet (register,
    section 5).
11. **Size of release 1.** About 900 new source lines and 600 test lines. The merge gate gains an
    end-to-end run on a small PostgreSQL fixture reproducing the three defects.

## Alternatives considered

- **The other four candidates:** ranked below on evidence and cost in the discovery report; the
  format becomes this tool's output, the clock a precondition field awaiting a need.
- **Keep the catalogue as a conformance fixture:** rejected, point 7.
- **Bounded equivalence in release 1:** rejected; one defect class, a verifier's cost, no
  reusable implementation; our value is replay on real data with a record.

## Consequences

- Phase 3, in the owner's order: stop the spike server; measure the gold-only probes over all
  498 Mini-Dev rows and hand-check the fired rows (precision under one half demotes gold-only
  mode to an experimental flag the README does not advertise); tag and delete; build the audit;
  gate it end to end; rewrite the README with the sentence that NOT_EQUAL never means the gold is
  wrong; refresh the claims register; draft the issues; tag `v0.1.0`.
- The first upstream batch is five issues: the three gold rows, the duplicated ids 137 and 138 in
  `mini_dev_postgresql.json`, and a polite question on the SpotIt+ repository asking the authors
  to choose a licence, since the paper says open source and the file grants nothing. BIRD issues
  cite the SpotIt paper (ICLR 2026), never the repository.
- "Attest" means a typed replay with the preconditions named; NOT_EQUAL means "these two disagree
  here, decide". The validator's zero-wrong-answer claim is not re-asserted for this tool.
