# The audit command

`attestql audit` runs a question file against one database and writes one line per question, a
directory per disagreement or fired probe, a summary line and `summary.json`. This page is the
reference for its flags, its output and its keys; the README is the short version. The text here
was the README's own until version 0.2.1 and moved when the README was cut down to what a first
reader needs. `attestql --version` prints the installed release, read off the installed
distribution, and exits 0; it sits on the command rather than on a subcommand, because what it
answers is which release is installed and not what one of the commands does.

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
not columns, a REAL comes back as the decimal that round-trips it, a TEXT cell whose bytes are not
valid UTF-8 is recorded as those bytes under the tag `text-bytes` rather than failing the statement
in the decoder (ADR-0015), a BLOB is still refused at the value, no session setting is a
precondition because a file has no session, there is no role and no grant, and the parser is
sqlglot's SQLite dialect rather than the engine's own grammar. Extension loading is never enabled
on the connection, so a statement that calls `load_extension` is refused by the engine when it
runs and loads nothing. One `--dsn` is one file, so a benchmark of eleven databases is eleven runs,
each with `--ids` naming the questions that database answers.

A SQLite file whose header says WAL, which BIRD's `card_games` is, needs a `-shm` and a `-wal`
beside it before it can be read at all, so a directory that cannot be written to refuses the open.
The run answers that one refusal by copying the file and any sidecars into a private directory and
reading the copy: it says so on stderr with the size and the temporary directory, states in every
record's session settings under `read_through_private_copy` that a byte-identical private copy was
read, keeps the identity, the size and the content signal on the original because the original is
what was audited, and removes the copy when the run ends. The record states the fact and not the
path, because the directory is fresh on every run. A copy that cannot be made, for want of disk or
because a sidecar cannot be read, is a refusal like any other and leaves nothing behind. It costs
what the file weighs, 262 MB for `card_games`, and two runs over the same file make two copies, so
audit such a database one run at a time or count the disk. The alternative, telling SQLite the file
is immutable, is not taken: it is a promise about the file that the run cannot check.

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

Most published prediction files hold no keys at all: one statement per line, in the order of the
question file. `--predictions-format lines` reads one, where a line's position is its key, so that
reading is position keying and asking for question ids there is refused. A line ends at a line feed
and at nothing else, and the carriage return of a CRLF file comes off the end of its line; the
newline that ends the last line is not a line of its own. Every empty line is a position, at the end
of the file as well as between statements, and is that question's error line the way the number `0`
is under the JSON shape. The BIRD suffix comes off a line as it does off a value. An edit that only
one publisher's file needs, such as a comment cut or a database name appended to every statement, is
made before the file reaches this tool.

`--questions-origin`, `--questions-date`, `--predictions-origin` and `--predictions-date` record
where each of the two files came from and what date its origin states, beside the sha256 this tool
computes for it, in `summary.json` and in every evidence record. The data the server holds came
from a file too: `--data-file` names the dump it was loaded from, which this tool digests and
never reads, and `--data-origin` and `--data-date` state where that file came from, so all three
sources are recorded alike. `--data-as-of` states the instant that data is as of, which every
evidence record carries and `summary.json` states beside `data_as_of_source`; without it the
instant the run started is used and the source says which of the two it was. It takes an ISO 8601
instant that states an offset, refuses one that does not, and is recorded in UTC. Both engines
take it alike.

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
the status, and a run whose every question errored is the one that exits 2, because it audited
nothing at all. A run with nothing to audit is not that case: a question file holding no question
asked nothing and exits 0. An `--ids` naming no question the file holds is a different thing
again, a tool error before the run starts, and exits 2. The line names the side that failed,
`gold`, `prediction` or `run` for the measurement around the two, before the message.

An `audit/q<id>/` written for a question that had a prediction holds four files:
`counterexample.json`, the two evidence records (`evidence-gold.json`, `evidence-second.json`)
and `smells.json`. A gold-only question was compared with nothing, so there is no counterexample
and no second record, and its directory holds the two files there are: the gold's own record,
`evidence-gold.json`, and `smells.json`. `audit/summary.json` holds the counts, the fixture
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

`--fixture-digest` says how deep that measurement goes. The default, `counts`, takes the schema
digest and the exact row count of each table a statement names. `full` takes a digest of every row
of those tables as well, which reads all of them: on Mini-Dev that costs about fourteen seconds
against half a second for the other two. The depth is part of the cache key, so one depth is never
served for the other, and `summary.json` states it under `fixture.depth`. Both engines digest the
rows and not the order they are stored in, so a shuffled copy digests as the table it was copied
from; the function differs and is written in front of the value, `md5` over the server's own row
text on PostgreSQL and `sha256` over the rendered rows on SQLite.

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
whose value depends on summation order reported under their own name; a result that returns the
same whole row more than once where the statement never said DISTINCT; and, off by default behind
`--experimental-s2`, direction against the question. All six run on either engine and read the
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

`--shuffle-seed`, 1 by default, is the seed those copies are ordered by, so one run reproduces
another. The order it fixes is the engine's: a copy is written `ORDER BY md5(<seed> || t::text)`
on PostgreSQL and in the order of a sha256 of the seed and the source row's rowid on SQLite, so
one seed is one order per engine and not one order across the two. `--shuffle-row-limit`, 300,000
rows by default, is the size above which a table is not copied at all; the skip is recorded with
the count that caused it, and a limit below one row is refused.

`--plan-variant` is off by default and adds a second rerun beside the shuffled one: the same
statement over the same rows, with the engine steered away from the plan it chose. What the
steering is belongs to the engine. On PostgreSQL it is `enable_seqscan`, `enable_hashjoin` and
`enable_mergejoin` off for that statement alone; on SQLite it is the one plan control a reader can
reach, the transient index the engine builds for a join it has no index for. Without the flag the
probe records `plan_variant` as not run with that as its reason, and a gold that was reread
neither way reports the probe as not applicable rather than as having survived a rerun.

The duplicate-row probe is the one that asks the database nothing: it counts the rows the gold
itself returned, under the keys the comparison counts them by, so two rows are one row here exactly
when the comparator holds them equal. It fires on a repeat that was seen, which a bounded result can
still hold, and reports itself not applicable when the statement states DISTINCT, when the result
was cut and held no repeat, or when it holds fewer than two rows.

The precision of each probe, measured over all 498 Mini-Dev golds with every fired row classified
by hand, is in
[the measurement report](../plans/reports/measurement-260902-2226-gold-only-probes-mini-dev.md):
67 % actionable over the fires, and the direction probe alone 17 %, which is why it is off by
default. That measurement predates the duplicate-row probe; what it fires on, and how often, is in
the claims register.

## The report command

`attestql report <audit-dir>` reads the JSON one audit wrote and writes a page for the run and a
page for each question, with the JSON each page was rendered from copied beside it. It reads the
files and reaches no database, so a directory produced on another machine, by either engine,
renders here: the pages are built from the `format` strings the documents declare and from
nothing else. `--out` says where they go and defaults to the audit directory's own sibling,
`<audit-dir>-report/`, because a rerun of the audit clears the audit directory and a report
written inside one would be left there, stale, beside a fresh run. Exit status is 0 when the
pages were written and 2 when the directory could not be rendered: a directory holding no
`summary.json` was not written by this tool, and the line says so with nothing written. An
`--out` naming the audit directory itself, or a directory inside it, is refused for the same
reason the default is a sibling.

The output directory follows the rule the audit's own does. The first render leaves a
`.attestql-report` marker in it; a render into a directory that has the marker removes what the
render before it wrote (`index.html`, `summary.json`, every `q<id>/`, `not-equal/`,
`by-mechanism/`, `by-probe/` and `static/`) before
writing anything, so what is in there is one report and not two, and anything else you put there
stays. A non-empty directory without the marker is refused with nothing in it touched.

`index.html` is the run: the counts, what the run was made of (both file digests with whatever
origin the run was told, the server, the parser, the serialization, the fixture digest, the
shuffle and the session as the engine reported it), the states the run has to state about itself
(duplicate ids, prediction positions not compared, tables missing or unreadable, tables the
shuffle did not reach, statements the budget stopped), and an index of every question. A question
whose statement could not be run wrote no directory, so it is a row of that index read from the
summary's own error list, with the side that stopped and the engine's message, and has no page.

The index is also written restricted, under an address for each restriction, because a static
host reads no query string: `not-equal/index.html` holds the rows whose verdict is NOT_EQUAL,
`by-mechanism/<class>/index.html` the rows a counterexample put in that class, and
`by-probe/<name>/index.html` the rows whose gold fired that probe. Each is the run page's own
index with rows left out, links back to the whole, and is written only where a row satisfies
it.

`q<id>/index.html` is one question, in a fixed order: what was asked, the two statements with the
tokens they differ in marked, the rows the two results differ in, what BIRD's own check and the
test-suite check would have said, and then the results, the probes in all three states, both
evidence records and the instruction for running each statement again. The page states the
verdict, the mechanism and every `reading` string as the JSON holds them and adds no judgement of
its own; a test reads the templates' own literals and forbids a short list of phrases there.

Three files no audit writes are read where a publisher put them beside the summary. A
`questions.json` holding `question_id`, `db_id` and the question text names the database each
question is about, which reaches no file the audit writes, and the strip of a question page then
states that database in front of the question set. A `classification.json` with a
`classification-source.json` beside it, saying where the copy came from, what date it carries and
which of its rows are this run's, puts one "read by hand" row on each question it holds a row
for, showing the class and the reason verbatim with that date; the tool's verdict and a person's
reading are two blocks on the page and are never merged; where that note also carries a `classes`
object, the row states what the class means in the words of the document that defines it. A
`published.json` holding a name, an `https://` URL, a size and a sha256 puts the address of the
whole run on the run page, and where it also holds `directories`, how many question directories
the archive has, the page states how many of them have a page here. A directory this tool wrote
holds none of the three and renders exactly as it did before they existed.

Beside every record's two hashes the page states `recomputed from this JSON: match`, or the two
values when they differ. The line is not a repetition of the file: `attestql.evidence.load` reads
the record back into the result and the descriptor it was rendered under, takes `result_hash`
over that rendering again and `record_hash` over the document with that one key removed, and
compares. A record whose bytes changed after the audit wrote it says so on the page.

Where a table cannot say the thing, the page draws it: an SVG built in Python from the same
numbers the tables state, with its data source in its `<title>` and the same numbers in words
under it. The run page draws its verdicts and its probes; a question is drawn only where its
class has a shape, which is the rows that moved, the rows one result holds more of, and the
result that is the first rows of the other.

The pages print. The sticky line at the top becomes an ordinary heading, every disclosure opens
so paper holds what the screen would have held after you opened them all, every link prints where
it goes, and nothing animates. The stylesheet, the script and the fonts are written under
`static/` beside the pages, so a report is a directory you can move, serve or open with nothing
fetched from a network.

Rendering the same directory twice writes the same bytes: no clock is read and no generation time
is written, so a report can be committed or published and re-made without a diff.
