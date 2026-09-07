# The audit command

`attestql audit` runs a question file against one database and writes one line per question, a
directory per disagreement or fired probe, a summary line and `summary.json`. This page is the
reference for its flags, its output and its keys; the README is the short version. The text here
was the README's own until version 0.2.1 and moved when the README was cut down to what a first
reader needs.

## The demo

`attestql demo --out DIR` is the one command that needs no files of yours. It writes the sandbox
the package carries into `DIR`: `fixture.sqlite`, built from the packaged `fixture.sql`, beside
copies of `questions.json` and `predictions.json`, then runs the ordinary audit over the three into
`DIR/audit` and prints, after the summary line, the `attestql audit` command that made the run, so
the next thing a reader types is that line with their own files in it. All three files are
rewritten on every demo and `DIR/audit` follows the rerun rule below, so a second demo into the
same directory is a clean rerun. The exit status is the audit's, which is 1 here because three of
the golds disagree with their corrections. The golds of q1029, q879 and q207 are BIRD Mini-Dev's
own SQLite copy, reproduced under their CC BY-SA licence as `NOTICE` records; the rows they run
against are this repository's synthetic fixture. `tools/audit-sandbox-sqlite/build.py` builds the
file alone, through the same builder, for whoever wants to open it with `sqlite3`.

## Engines and connections

The default engine is PostgreSQL 16 and `--dsn` takes libpq keyword form
(`"host=localhost dbname=bird"`). The password comes from `PGPASSWORD` or `~/.pgpass`; a DSN that
contains one, or any URI form, is refused. Loading BIRD's dump prints 99 `role "..." does not
exist` errors from its ownership statements; they are harmless. The role needs SELECT on the
audited tables and an existing schema it may create tables in (`--scratch-schema`, default
`attestql_scratch`); without one, the shuffle probe reports itself as not run in `summary.json`
and everything else still runs. A run holds its scratch schema from before it makes the copies
until after it drops them, so a second audit told the same schema waits a minute for it and then
reports its own shuffle as not run: give concurrent audits a schema each.

SQLite, where BIRD originally lives, is available behind the same evidence record
(`--engine sqlite --dsn <path to the file>`), and what differs is stated in the record rather than
hidden: a column carries the storage class its cells came back at because SQLite types values and
not columns, a REAL comes back as the decimal that round-trips it, no session setting is a
precondition because a file has no session, there is no role and no grant, and the parser is
sqlglot's SQLite dialect rather than the engine's own grammar. Extension loading is never enabled
on the connection, so a statement that calls `load_extension` is refused by the engine when it
runs and loads nothing. One `--dsn` is one file, so a benchmark of eleven databases is eleven runs,
each with `--ids` naming the questions that database answers.

The PostgreSQL parser is PostgreSQL 17's grammar (`libpg_query`), so a statement that only
PostgreSQL 17 accepts parses here and then fails on a PostgreSQL 16 server; that failure is the
question's own error line, not a verdict.

## The question file and the predictions file

The question file is BIRD's own format: a list of entries with `question_id`, `db_id`, `question`
and `SQL`, and `evidence` and `difficulty` where the file has them. `--ids` keeps only the
questions it names. A file that states
two different questions under one id stops the run; an id repeated with the same entry is one
question.

A predictions file written for this tool is keyed by question id (`{"879": "SELECT ..."}`). BIRD's
own prediction files under `llm/exp_result/` are keyed by the position of the entry in the
question file rather than by question id, because its evaluation pairs prediction `i` with gold
line `i`; read one with `--predictions-keyed-by position`, and under the default keying a file of
that shape is refused rather than paired with whichever questions happen to carry those numbers.
A value may carry BIRD's own suffix (`\t----- bird -----\t<db_id>`), which is stripped. An entry
that is the number `0` or an empty string, which is how BIRD dev's own `predict_dev.json` marks a
prediction the model did not produce, is that question's error line and not a refusal of the
file; a question the file does not name at all is audited gold-only.

`--questions-origin`, `--questions-date`, `--predictions-origin` and `--predictions-date` record
where each of the two files came from and what date its origin states, beside the sha256 this tool
computes for it, in `summary.json` and in every evidence record. The data the server holds came
from a file too: `--data-file` names the dump it was loaded from, which this tool digests and
never reads, and `--data-origin` and `--data-date` state where that file came from, so all three
sources are recorded alike.

Two copies of the Mini-Dev question set exist and they differ: the `minidev.zip` linked from the
GitHub README (498 distinct ids, q879 still ordering a text column as text) and the Hugging Face
dataset `birdsql/bird_mini_dev` (500 ids, q879 corrected, q1322 changed; 2026-01-18). BIRD's own
README names the Hugging Face dataset as the one to download since 2026-09-05. Both copies were
run gold-only, with each file's digest and origin, in
`plans/reports/audit-260902-minidev-gold-only/` and `plans/reports/audit-260903-minidev-hf-gold-only/`.

## The output

One line per question: the id, the database, the replay rule (`R-ORD` when the gold has a
top-level `ORDER BY`, `R-SET` otherwise), the verdict (`EQUAL`, `NOT_EQUAL`, `GOLD-ONLY` without a
prediction, `ERROR` when a statement could not be run), the probes that fired, and the directory
when one was written. Three lines of the full Mini-Dev gold-only run and its last line, from
`plans/reports/audit-260902-minidev-gold-only/` (a run at version 0.1.1, before the summary line
counted the statements that reached the budget):

```text
q1380 student_club R-SET  GOLD-ONLY  smells=float-aggregate-order  audit/q1380/
q1389 student_club R-ORD  GOLD-ONLY  smells=arbitrary-cut  audit/q1389/
q879  formula_1   R-ORD  GOLD-ONLY  smells=ordering-over-numeric-text  audit/q879/
498 questions: 0 NOT_EQUAL, 39 smells fired
```

Exit status is 0 with no disagreement, 1 with at least one, 2 on a tool error. `--fail-on-smell`
makes a fired probe exit 1 too. An `ERROR` line is none of the three: the other questions decide
the status, and only a run that answered no question at all exits 2. The line names the side that
failed, `gold`, `prediction` or `run` for the measurement around the two, before the message.

Every `audit/q<id>/` holds `counterexample.json`, the two evidence records (`evidence-gold.json`,
`evidence-second.json`) and `smells.json`; `audit/summary.json` holds the counts, the fixture
digest, whether the shuffle ran, the session the run was made in (the server's version string
beside its number) and the parser that judged every statement (the validator, the `postgast`
release and the libpg_query grammar version). `fixture.unreadable_tables` names the tables a gold
uses that the catalogue holds but the role may not SELECT from, beside `fixture.missing_tables`,
the ones the catalogue does not hold at all; the first is repaired with a GRANT and the second in
the question file, and either makes every question that uses the table an error line rather than
a verdict. With `--predictions` the summary line and `credited_but_not_equal` in the file count
the comparisons BIRD's own `set(predicted) == set(gold)` scores 1 and the typed comparison calls
NOT_EQUAL, by what makes them: `multiplicity` (the same distinct rows at other counts), `type`
(the same values at other declared types), `order`, `truncation` (one result the first rows of the
other) and `other` for a disagreement that is none of those; a gold-only run compared nothing
against that reading and states null. `credited_but_not_equal.by_test_suite_ex` counts the same
comparisons under the test-suite reading, `1` for the ones it credits with BIRD and `0` for the
ones it refuses with this tool. `predictions.positions_unused` is empty unless
`--predictions-keyed-by position` is given, where it names every position of the prediction file
that lost to a lower position naming the same question: the question file holds one entry twice,
the lowest position is the prediction that is compared, and the rest are recorded rather than
silently dropped.

The first run into a directory leaves a `.attestql-run` marker in it; a rerun into a directory
that has the marker clears that run's `q<id>/` directories and `summary.json` before it writes
anything, so what is in there is one run's evidence and not two, and a non-empty directory without
the marker is refused with nothing in it touched. `fixture.json`, the fixture cache keyed by the
server and the schema digest, stays, and so does anything else you put there. A cached measurement
is used only when the server's own per-table counters still say what they said when it was taken,
so data reloaded or edited under an unchanged schema is measured again rather than read back from
the file.

## The statement budget

`--statement-timeout SECONDS`, 30 by default, bounds every statement the run sends, gold and
prediction alike. A statement that reaches it is that question's ERROR line, naming the side that
failed before the server's message; the record of the execution carries the timeout it actually
ran under and `summary.json` the one the run was given. The summary line ends with how many
statements reached the bound, the golds counted apart from the predictions, and `summary.json`
lists their question ids under `timed_out`; a run where nothing reached it says so with two
zeroes rather than leaving the reader to count the error list. Every statement runs with the server's
parallel gather off and with `work_mem` at 4 MB and `hash_mem_multiplier` at 2, PostgreSQL 16's
own defaults written out rather than inherited, so that a float sum is added in one order and two
runs of one statement cannot differ in a late digit: a gather adds the partial sums in whatever
order the workers returned them, and a hash aggregate that outgrows the memory bound spills and
adds them per spilled batch, which moves three of the nine summation-order-sensitive Mini-Dev
golds between 64 kB and 4 MB. All three are read back inside the statement's own transaction and
the execution is refused if the session does not hold them, and holding them makes some plans
slower here than on the same server at its own defaults.

q707 of Mini-Dev is the worked example: its gold runs in 50 ms, and the `meta-llama-3-70b-instruct`
prediction for it runs in 0.22 s with two parallel workers and in 41 s warm to 105 s cold without
them, so it needs `--statement-timeout 120` to be compared at all. Four of the 4,482 prediction
slots of the committed prediction-mode measurement time out at the default, on two questions; the
timings behind this paragraph are in `plans/reports/session-260904-autonomous-run/q707-timeouts/`.
On SQLite the budget is wall clock, enforced by the process rather than by a server, so a machine
under load reaches it sooner; two Mini-Dev golds (q518, q701) and three BIRD dev golds do not
finish inside 30 s there alone.

## The comparison

- Typed replay comparison: a type tag per cell, declared numeric scale, NULL rendering, a hash per
  result; columns are compared by position and type, never by name, as the benchmark does; R-ORD
  when the gold has a top-level ORDER BY and compares the rendered rows in order, byte for byte,
  R-SET otherwise; a NaN is one value there, equal to a NaN and to nothing else, as PostgreSQL
  groups and orders it; EQUAL, NOT_EQUAL, or NOT_COMPARABLE with the mismatched preconditions
  named (fixture digest, serialization, rule, ordering, and the seven session settings that change
  rendered bytes or the order a float sum is added in: `TimeZone`, `DateStyle`, `IntervalStyle`,
  `extra_float_digits`, the database's default collation, `work_mem` and `hash_mem_multiplier`).
  Within one run both records are built under the same preconditions, so that verdict does not
  occur there; it is for comparing two records from two runs, and a record carries everything that
  comparison reads.
- An evidence record per execution, twenty-one required fields, no defaults: what ran, as what
  role, on which server, under which settings, with which result and hash, and how to re-run it.
  The record names the engine it ran on, once, in its session settings, and each column of the
  result carries that engine's own declared type for it. Those settings are one block whichever
  engine wrote the record: the engine, then the seven PostgreSQL preconditions, stated in full on
  PostgreSQL and absent on an engine that has no session to read them from, then everything else
  that session reported.
- BIRD's own set-equality reading is computed beside every verdict, so a counterexample states
  what the benchmark would have said. The test-suite reading of Zhong, Yu and Klein 2020
  (`result_eq` of `ruiqi-zhong/test-suite-sql-eval`) is recorded beside it as `test_suite_ex`: it
  keeps duplicate rows, keeps row order when the gold's text holds ORDER BY, and still admits a
  projection whose columns came back in another order. Its DISTINCT strip is not mirrored, because
  that evaluator rewrites both statements and runs them again and these rows are already fetched,
  so it stands for that evaluator's answer only where neither statement holds a DISTINCT.
- A pair of numbers equal under R-ORD is not therefore equal under R-SET: R-ORD compares the
  canonical rendering, where a numeric is written at six decimals, and R-SET compares the values
  as the result returned them, so two numbers that first differ past the sixth decimal are EQUAL
  under one rule and NOT_EQUAL under the other, and a reader of two verdicts reads which rule each
  was given. The claims register states this as a non-claim.

## The probes

Gold-only probes, all heuristics and labelled so: ordering over numeric-looking text; an arbitrary
or null-first cut that changes the answer; a result that is not a function of the data (a seeded
shuffle of the referenced tables, copied into scratch storage, changes it), with float aggregates
whose value depends on summation order reported under their own name; and, off by default behind
`--experimental-s2`, direction against the question. All five run on either engine and read the
engine's own rules rather than PostgreSQL's: where the nulls of an ordering key go without a
`NULLS FIRST` or `NULLS LAST` to say (last under `ASC` on PostgreSQL, first on SQLite), what a
numeric cast of an ordering key is written as, and which result types hold an aggregate whose last
digits are its summation order. On SQLite that last set is empty, because the engine adds a REAL
aggregate with a compensation, so a float cell that moves under the shuffle there is reported as
depending on the storage order rather than forgiven as arithmetic. The copies are reached by the
search path on PostgreSQL and by SQLite resolving an unqualified name in `temp` first, and neither
consults a name that states its own schema, so a gold that writes `public.x`, `"Other".x` or
`main.x` is reported as not covered by the shuffle rather than rerun against a copy of it. Which
answer a copy gives depends on the plan it is read with, and the plan on the planner's statistics:
the run records `last_analyze`, `last_autoanalyze` and `n_mod_since_analyze` per table, in the
probe's own evidence and in the summary, and never runs ANALYZE. A probe that fires on one run and
is quiet on the next over the same data is that, and the two records show it.

The precision of each probe, measured over all 498 Mini-Dev golds with every fired row classified
by hand, is in
[the measurement report](../plans/reports/measurement-260902-2226-gold-only-probes-mini-dev.md):
67 % actionable over the fires, and the direction probe alone 17 %, which is why it is off by
default.
