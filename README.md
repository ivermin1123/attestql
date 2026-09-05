# AttestQL

Audit text-to-SQL gold and predictions on PostgreSQL with typed replay evidence.

## The problem

Text-to-SQL benchmarks score a prediction by executing it and the gold statement on one shipped
database and comparing the two results as Python sets: `set(predicted) == set(gold)`. That
comparison drops duplicate rows, ignores order even when the question asks for one, and compares
values loosely across types. It also cannot tell you when the gold itself is wrong, and it often
is: the CIDR 2026 audit by Jin et al. measured 52.8 % annotation error in BIRD Mini-Dev and
66.1 % in Spider 2.0-Snow ([paper](https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf)). Reports of
wrong gold sit open on the benchmark trackers with nobody able to say, mechanically, where two
statements disagree.

AttestQL executes both statements under a read-only transaction with the server's parallel gather
turned off, so that a float sum is added in one order and two runs of one statement cannot differ
in a late digit, renders each result with a typed canonical serializer, compares them under a
stated rule (ordered sequence when the gold orders, multiset otherwise), and writes an evidence
record per execution with everything a second person needs to re-run it. When the two disagree it
writes the differing rows as a counterexample. On the gold alone it runs mechanical probes for the
defects that need no second statement.

**NOT_EQUAL never means the gold is wrong.** It means these two statements disagree on this data
under this rule; here are the rows; decide.

## Try it in ten minutes

You need PostgreSQL 16 (Docker is fine), Python 3.11 or later, and `uv`. The package is not on
PyPI yet, so install it from a checkout:

```text
uv tool install .            # or: uv sync, then prefix every command with uv run
```

Load BIRD Mini-Dev, the public benchmark this tool is demonstrated on
([bird-bench/mini_dev](https://github.com/bird-bench/mini_dev), CC BY-SA 4.0), and give the tool
one schema it may write scratch tables into:

```text
unzip minidev.zip
createdb bird
psql -d bird -f minidev/MINIDEV_postgresql/BIRD_dev.sql
psql -d bird -c 'CREATE SCHEMA attestql_scratch'
```

Audit the gold statements alone:

```text
attestql audit --dsn "host=localhost dbname=bird" \
    --questions minidev/MINIDEV/mini_dev_postgresql.json --out audit/
```

Or compare your predictions against the gold (`{"879": "SELECT ..."}`, or BIRD's own
`predict_dev.json`):

```text
attestql audit --dsn "host=localhost dbname=bird" \
    --questions minidev/MINIDEV/mini_dev_postgresql.json --predictions preds.json --out audit/
```

BIRD's own prediction files under `llm/exp_result/` are keyed by the position of the entry in the
question file rather than by question id, because its evaluation pairs prediction `i` with gold
line `i`; read one with `--predictions-keyed-by position`, and under the default keying a file of
that shape is refused rather than paired with whichever questions happen to carry those numbers.
`--questions-origin`, `--questions-date`, `--predictions-origin` and `--predictions-date` record
where each of the two files came from and what date its origin states, beside the sha256 this tool
computes for it, in `summary.json` and in every evidence record. The data the server holds came
from a file too: `--data-file` names the dump it was loaded from, which this tool digests and
never reads, and `--data-origin` and `--data-date` state where that file came from, so all three
sources are recorded alike.

The password comes from `PGPASSWORD` or `~/.pgpass`; a DSN that contains one, or any URI form, is
refused. Loading BIRD's dump prints 99 `role "..." does not exist` errors from its ownership
statements; they are harmless. The role needs SELECT on the audited tables and an existing schema it may create tables in
(`--scratch-schema`, default `attestql_scratch`); without one, the shuffle probe reports itself
as not run in `summary.json` and everything else still runs. A run holds its scratch schema from
before it makes the copies until after it drops them, so a second audit told the same schema waits
a minute for it and then reports its own shuffle as not run: give concurrent audits a schema each.
On the full Mini-Dev gold set the run prints one line per question; three of them, and the last
line (the whole output is in `plans/reports/audit-260902-minidev-gold-only/`):

```text
q1380 student_club R-SET  GOLD-ONLY  smells=float-aggregate-order  audit/q1380/
q1389 student_club R-ORD  GOLD-ONLY  smells=arbitrary-cut  audit/q1389/
q879  formula_1   R-ORD  GOLD-ONLY  smells=ordering-over-numeric-text  audit/q879/
498 questions: 0 NOT_EQUAL, 39 smells fired
```

Two copies of the Mini-Dev question set exist and they differ: the `minidev.zip` linked from the
GitHub README (498 distinct ids, q879 still ordering a text column as text) and the Hugging Face
dataset `birdsql/bird_mini_dev` (500 ids, q879 corrected, q1322 changed; 2026-01-18). The lines
above are from the zip; the same run over the Hugging Face file fires on 29 golds instead of 30,
the difference being q879. Both runs, with each file's digest and origin, are in
`plans/reports/audit-260902-minidev-gold-only/` and `plans/reports/audit-260903-minidev-hf-gold-only/`.

Exit status is 0 with no disagreement, 1 with at least one, 2 on a tool error. `--fail-on-smell`
makes a fired probe exit 1 too. Every `audit/q<id>/` holds `counterexample.json`, the two evidence
records (`evidence-gold.json`, `evidence-second.json`) and `smells.json`; `audit/summary.json`
holds the counts, the fixture digest, whether the shuffle ran, the session the run was made in (the
server's version string beside its number) and the parser that judged every statement (the
validator, the `postgast` release and the libpg_query grammar version). `fixture.unreadable_tables`
names the tables a gold uses that the catalogue holds but the role may not SELECT from, beside
`fixture.missing_tables`, the ones the catalogue does not hold at all; the first is repaired with a
GRANT and the second in the question file, and either makes every question that uses the table an
error line rather than a verdict, which names the side that failed, `gold`, `prediction` or `run`
for the measurement around the two, before the message. With `--predictions` the summary line and
`credited_but_not_equal` in the file count the comparisons BIRD's own `set(predicted) == set(gold)`
scores 1 and the typed comparison calls NOT_EQUAL, by what makes them: `multiplicity` (the same
distinct rows at other counts), `type` (the same values at other declared types), `order`,
`truncation` (one result the first rows of the other) and `other` for a disagreement that is none of
those; a gold-only run compared nothing against that reading and states null.
`credited_but_not_equal.by_test_suite_ex` counts the same comparisons under the test-suite reading,
`1` for the ones it credits with BIRD and `0` for the ones it refuses with this tool.
`predictions.positions_unused` is empty unless `--predictions-keyed-by position` is given, where it
names every position of the prediction file that lost to a lower position naming the same question:
the question file holds one entry twice, the lowest position is the prediction that is compared, and
the rest are recorded rather than silently dropped. The first run into a directory leaves a
`.attestql-run` marker in it; a rerun into a directory that has the marker clears that run's
`q<id>/` directories and `summary.json` before it writes anything, so what is in there is one run's
evidence and not two, and a non-empty directory without the marker is refused with nothing in it
touched. `fixture.json`, the fixture cache keyed by the server and the schema digest, stays, and so
does anything else you put there. A cached measurement is used only when the server's own per-table
counters still say what they said when it was taken, so data reloaded or edited under an unchanged
schema is measured again rather than read back from the file.

`--statement-timeout SECONDS`, 30 by default, bounds every statement the run sends, gold and
prediction alike. A statement that reaches it is that question's ERROR line, naming the side that
failed before the server's message; the record of the execution carries the timeout it actually ran
under and `summary.json` the one the run was given. Every statement runs with the server's parallel
gather off and with `work_mem` at 4 MB and `hash_mem_multiplier` at 2, PostgreSQL 16's own defaults
written out rather than inherited, so that a float sum is added in one order and two runs of one
statement cannot differ in a late digit: a gather adds the partial sums in whatever order the
workers returned them, and a hash aggregate that outgrows the memory bound spills and adds them per
spilled batch, which moves three of the nine summation-order-sensitive Mini-Dev golds between 64 kB
and 4 MB. All three are read back inside the statement's own transaction and the execution is
refused if the session does not hold them, and holding them makes some plans slower here than on the
same server at its own defaults.
q707 of Mini-Dev is the worked example: its gold runs in 50 ms, and the `meta-llama-3-70b-instruct`
prediction for it runs in 0.22 s with two parallel workers and in 41 s warm to 105 s cold without
them, so it needs `--statement-timeout 120` to be compared at all. Four of the 4,482 prediction
slots of the committed prediction-mode measurement time out at the default, on two questions; the
timings behind this paragraph are in `plans/reports/session-260904-autonomous-run/q707-timeouts/`.

## What it does

- Typed replay comparison: a type tag per cell, declared numeric scale, NULL rendering, a hash per
  result; columns are compared by position and type, never by name, as the benchmark does; R-ORD
  when the gold has a top-level ORDER BY and compares the rendered rows in order, byte for byte,
  R-SET otherwise; a NaN is one value there, equal to a NaN and to nothing else, as PostgreSQL
  groups and orders it; EQUAL, NOT_EQUAL, or
  NOT_COMPARABLE with the mismatched preconditions named (fixture digest, serialization, rule,
  ordering, and the seven session settings that change rendered bytes or the order a float sum is
  added in: `TimeZone`, `DateStyle`, `IntervalStyle`, `extra_float_digits`, the database's default
  collation, `work_mem` and `hash_mem_multiplier`). Within one run both
  records are built under the same preconditions, so that verdict does not occur there; it is
  for comparing two records from two runs, and a record carries everything that comparison
  reads.
- An evidence record per execution, twenty-one required fields, no defaults: what ran, as what role,
  on which server, under which settings, with which result and hash, and how to re-run it.
- Gold-only probes, all heuristics and labelled so: ordering over numeric-looking text; an
  arbitrary or null-first cut that changes the answer; a result that is not a function of the data
  (a seeded shuffle of the referenced tables, copied into the scratch schema, changes it), with
  float aggregates whose value depends on summation order reported under their own name; and,
  off by default behind `--experimental-s2`, direction against the question. The copies are
  reached by the search path, which a name that states its own schema never consults, so a gold
  that writes `public.x` or `"Other".x` is reported as not covered by the shuffle rather than
  rerun against a copy of it. Which answer a copy gives depends on the plan it is read with, and
  the plan on the planner's statistics: the run records `last_analyze`, `last_autoanalyze` and
  `n_mod_since_analyze` per table, in the probe's own evidence and in the summary, and never runs
  ANALYZE. A probe that fires on one run and is quiet on the next over the same data is that, and
  the two records show it.
- BIRD's own set-equality reading is computed beside every verdict, so a counterexample states
  what the benchmark would have said. The test-suite reading of Zhong, Yu and Klein 2020
  (`result_eq` of `ruiqi-zhong/test-suite-sql-eval`) is recorded beside it as `test_suite_ex`: it
  keeps duplicate rows, keeps row order when the gold's text holds ORDER BY, and still admits a
  projection whose columns came back in another order. Its DISTINCT strip is not mirrored, because
  that evaluator rewrites both statements and runs them again and these rows are already fetched,
  so it stands for that evaluator's answer only where neither statement holds a DISTINCT.

## What it does not do

- It does not decide which statement is right. A second statement is supplied by you: a model's
  prediction, an upstream correction, a human's fix.
- It does not generate differentiating data. Two statements that agree on the shipped rows but
  differ semantically are found only by the shuffle probe, not by search.
- It runs on PostgreSQL only. SQLite, where BIRD originally lives, is the first expansion candidate
  and is not built; the executor interface is engine-neutral so that it can be.
- It proves nothing about correctness, security, or production use. It runs as the role you give
  it; give it a read-only one.
- Its parser is PostgreSQL 17's grammar (`libpg_query`), so a statement that only PostgreSQL 17
  accepts parses here and then fails on a PostgreSQL 16 server; that failure is the question's
  own error line, not a verdict.

## How to check rather than believe

Everything this README claims has an artifact. The three defects that upstream trackers reported
(BIRD Mini-Dev q1029, q879, q207) reproduce in `tools/audit-sandbox/` on a fixture of a few rows
against a read-only role, and `tests/test_audit_end_to_end.py` runs the command on it, inside a
container, every time `just check` runs. The same three on the real Mini-Dev dump, with their
records and hashes, are in `plans/reports/spike-260902-three-gold-defects/`. The gold-only probes were
measured over all 498 Mini-Dev statements and every fired row was classified by hand:
[the measurement report](plans/reports/measurement-260902-2226-gold-only-probes-mini-dev.md)
gives the precision per probe, including the one that is only 17 % and is therefore off by
default. Prediction mode was run on BIRD's own nine PostgreSQL prediction files for Mini-Dev
(4,482 predictions, the Hugging Face gold), with BIRD's own evaluator run beside it as the check;
the numbers below are that run repeated at the commit `cf0b033`. The two readings of EX agree on
4,478 of 4,482, five more than the first run because the tool's reading of BIRD's EX now loads
float columns as psycopg2 hands them over; what disagrees is q1473, a `SUM` over `float8` whose
last digits depend on the order its partial sums are added in. Of the 1,239 predictions BIRD scores
1, 164 (13.2 %) are NOT_EQUAL under the typed comparison: 138 return the gold's rows with other
multiplicities, 26 the same values under another declared type, none differ only in order. Read by
hand, 69 of those 164 (42.1 %; 5.6 % of everything BIRD credits) are wrong answers the benchmark
credited, 74 are duplicated rows a reader would forgive, and 21 are the typed rule and not the
question. Of the 1,521 predictions BIRD scores 0, 4 are right against a corrected gold, counted only
where a correction exists (q1029, q207); the reverse, a 1 earned by reproducing a wrong gold, occurs
6 times on the GitHub zip's golds and 2 on the Hugging Face file's. Against the first run the count
BIRD credits moved by one and the loose rows by six: those six float rows are no longer read as 1,
q1473 is EQUAL now that every statement runs without parallel workers, and q707 of
`meta-llama-3-70b` times out under its serial plan.
[The prediction-mode report](plans/reports/measurement-260904-0046-prediction-mode-on-real-predictions.md)
holds the per-file table, the hand classification and the two tool defects the run found.
[The claims register](docs/claims-register.md) lists every claim with its owning
artifact, and every negative claim there carries the date it was measured, because negative
claims decay. [ADR-0013](docs/adr/0013-audit-text-to-sql-gold-with-typed-replay-evidence.md)
records the decision this tool implements and the date by which it is reconsidered if nobody
uses it.

The history is short and stated: this repository was developed privately from 2026-08-25 under a
different product direction, a governed data agent over a synthetic schema; it was reoriented on
2026-09-02 by ADR-0013 to the problem above, and the public history starts after that. The
private archive of the earlier history exists and can be provided on request. The code was
written with AI assistance under the owner's review, and the gate, not the author, is what
vouches for it.

## Licence

Apache-2.0 for this repository (`LICENSE`). The material excerpted from BIRD Mini-Dev, listed in
`NOTICE`, keeps its own CC BY-SA 4.0 licence. The SQL parser, `postgast`, is a BSD binding to
`libpg_query`, PostgreSQL's own grammar as a library; the driver, `psycopg`, is LGPL.
