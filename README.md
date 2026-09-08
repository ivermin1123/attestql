# AttestQL

[![PyPI version](https://img.shields.io/pypi/v/attestql.svg)](https://pypi.org/project/attestql/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/attestql.svg)](https://pypi.org/project/attestql/)
[![Licence](https://img.shields.io/pypi/l/attestql.svg)](LICENSE)
[![CI](https://github.com/ivermin1123/attestql/actions/workflows/ci.yml/badge.svg)](https://github.com/ivermin1123/attestql/actions/workflows/ci.yml)

You have a text-to-SQL prediction file and a benchmark that scored it. Run one command and get,
per question, whether the prediction and the gold disagree on the shipped data, the rows that
differ, and what the benchmark's own scorer would have said: for a question scored 0, the rows
that decided it, and for one scored 1, whether a comparison that keeps duplicates, order and types
agrees with the set comparison that credited it.

```text
uv tool install attestql        # or: pip install attestql
attestql demo --out demo
```

The second command runs the sandbox the package carries: the three BIRD Mini-Dev golds that
upstream reports found wrong (q1029, q879, q207) on a fixture of a few rows, each paired with a
corrected statement as its prediction, plus three synthetic questions. It writes the fixture, the
question file and the prediction file into `demo/`, audits them into `demo/audit/`, and ends with
the plain `attestql audit` command that made the run. Its output, unedited:

```text
q1029 european_football_2 R-ORD  NOT_EQUAL  smells=none  demo/audit/q1029/
q879  formula_1   R-ORD  NOT_EQUAL  smells=ordering-over-numeric-text  demo/audit/q879/
q207  toxicology  R-SET  NOT_EQUAL  smells=none  demo/audit/q207/
q900001 synthetic   R-ORD  GOLD-ONLY  smells=not-a-function-of-the-data  demo/audit/q900001/
q900002 synthetic   R-ORD  GOLD-ONLY  smells=arbitrary-cut,not-a-function-of-the-data  demo/audit/q900002/
q900005 synthetic   R-ORD  EQUAL      smells=ordering-over-numeric-text  demo/audit/q900005/
6 questions: 3 NOT_EQUAL, 5 smells fired, 0 credited by BIRD but NOT_EQUAL (0 multiplicity, 0 type, 0 order, 0 truncation), 0 timed out (0 gold, 0 prediction)
rerun: attestql audit --engine sqlite --dsn demo/fixture.sqlite --questions demo/questions.json --predictions demo/predictions.json --out demo/audit
```

Every `NOT_EQUAL` line has a directory. `demo/audit/q879/counterexample.json` says why that one
disagrees, trimmed here to the fields a reader opens first:

```text
"gold":   "... ORDER BY T2.fastestLapSpeed DESC LIMIT 1"                -> "Norwegian"
"second": "... ORDER BY CAST(T2.fastestLapSpeed AS REAL) DESC LIMIT 1"  -> "Peruvian"
"bird_ex": {"value": 0, "method": "set(second_rows) == set(gold_rows), ..."}
"differing_rows": {"in_gold_not_in_second": [["Norwegian"]], "in_second_not_in_gold": [["Peruvian"]]}
```

and `demo/audit/q879/smells.json` names the mechanism: `fastestLapSpeed` is a text column holding only
numbers, so the gold sorts `9.5` above `10` and the fastest lap is not the one it returns. The
same directory holds the two evidence records, each with the statement, the role, the engine,
the session settings, the result and its hash, and how to run it again.

**NOT_EQUAL never means the gold is wrong.** It means these two statements disagree on this data
under this rule; here are the rows; decide. The benchmark's own reading,
`set(predicted) == set(gold)`, is computed beside every verdict as `bird_ex`, and the typed
comparison beside it keeps duplicate rows, keeps order where the gold orders, and compares values
by declared type, so a prediction the benchmark credits and this tool calls `NOT_EQUAL` is listed
on the summary line by what makes the two readings differ.

## Install

Python 3.11 or later; SQLite needs nothing else, PostgreSQL needs a PostgreSQL 16 server. From
PyPI as above, or from a checkout:

```text
git clone https://github.com/ivermin1123/attestql && cd attestql
uv run attestql demo --out demo
```

The demo exits 1, because three golds disagree with their corrections, which is what it is there
to show. On your own files the command is the one its last line prints. On SQLite, `--dsn` is the path to one database file and
`--ids` picks the questions that database answers, so a benchmark of eleven databases is eleven
runs; BIRD Mini-Dev and BIRD dev ship as SQLite files and need nothing else installed. On
PostgreSQL 16 one server holds every database of the benchmark, so one run covers the whole
question file:

```text
attestql audit --dsn "host=localhost dbname=bird" \
    --questions minidev/MINIDEV/mini_dev_postgresql.json --predictions preds.json --out audit
```

A predictions file written for this tool is keyed by question id (`{"879": "SELECT ..."}`); BIRD's
own `predict_dev.json` files are keyed by position and are read with
`--predictions-keyed-by position`. Without `--predictions` the run audits the golds alone and runs
the mechanical probes that need no second statement: an ordering key that is text holding numbers,
an arbitrary or null-first cut that changes the answer, and a result that changes when the
referenced tables are copied in another row order. Exit status is 0 with no disagreement, 1 with at least one, 2 when
the tool could not run. Every flag, every line of the output and every key of `summary.json` is
described in [docs/audit-command.md](docs/audit-command.md).

## What it found

Three measurements, each on BIRD's own published files, each with its report, its artifact and
BIRD's own evaluator run beside the tool as the check.

**BIRD Mini-Dev on PostgreSQL.** Of the 1,239 predictions in BIRD's nine published Mini-Dev
prediction files that BIRD's evaluator scores 1, 164 (13.2 %) are `NOT_EQUAL` under the typed
comparison, and read by hand 69 of those (42.1 %; 5.6 % of everything BIRD credits) are wrong
answers the benchmark credited, 74 are duplicated rows a reader would forgive, and 21 are the
typed rule alone. The two readings of EX agree on 4,476 of 4,482 predictions, and every
disagreement is one float sum whose last digits depend on the order its parts are added in
([report](plans/reports/measurement-260904-0046-prediction-mode-on-real-predictions.md)).

**BIRD Mini-Dev on SQLite.** The same nine files on the eleven Mini-Dev database files, with no
server: the tool's reading of BIRD's EX and BIRD's own evaluator agree on 4,481 of 4,482, and of
the 1,650 predictions BIRD credits, 237 (14.4 %) are `NOT_EQUAL` under the typed comparison. A
sample of 50 of those 237, read by hand, is 27 wrong answers the benchmark credited, 22 duplicated
rows a reader would forgive and 1 the typed rule itself
([report](plans/reports/measurement-260907-1106-minidev-sqlite.md)).

**BIRD dev, both copies of the golds.** BIRD's 2025-11-06 quality pass rewrote 399 of the 1,534
dev golds; the gold-only probes, run over the older copy, fire on 31 of those 399 (7.8 %) against
25 of the 963 golds BIRD left alone (2.6 %), and 29 of the 31 go quiet once BIRD's own rewrite
replaces the old gold. The 25 fires on golds BIRD did not touch were read by hand: 23 are golds
that do not answer their question on this data, one is harmless, one is the tool's own rule
([report](plans/reports/measurement-260907-1435-bird-dev-sqlite.md)).

## Where the runs are published

[attestql.com](https://attestql.com) is this repository's own site, and it publishes the runs
behind the three measurements above. Each run has its own page with what it was made of and what
it found, and under it a page for every question the run's published selection carries: the two
statements, the rows they differ in, both evidence records and what each probe said. It is built
by `tools/site/build.py` out of the run directories committed under `tools/site/data/`, through
the same `attestql report` a reader runs locally, so a page there is a page you can make again;
`.github/workflows/site.yml` rebuilds and deploys it on every push to `main`.

## What was reported upstream

Six reports, filed under the owner's own GitHub and Hugging Face identity, each with its
counterexample. The replies, as of 2026-09-07:

| # | Where | What | Reply |
|---|---|---|---|
| 1 | [mini_dev issue 38](https://github.com/bird-bench/mini_dev/issues/38#issuecomment-5529732756) | q1029 orders `ASC NULLS FIRST` for "highest" | BIRD team, 2026-09-05: "We will review and correct this issue in the next patch." Issue closed |
| 2 | [mini_dev issue 39](https://github.com/bird-bench/mini_dev/issues/39) | q207 joins `bond` on `molecule_id`, 13 elements instead of 5 | BIRD team, 2026-09-05: "We will review and correct this issue in the next patch." Issue closed |
| 3 | [mini_dev issue 40](https://github.com/bird-bench/mini_dev/issues/40) | the GitHub zip and the Hugging Face dataset are different question sets | BIRD team, 2026-09-05: README changed to name the Hugging Face dataset as the one to download. Issue closed |
| 4 | [SpotIt-plus issue 1](https://github.com/ai-ar-research/SpotIt-plus/issues/1) | asked which licence applies | Withdrawn by the owner on 2026-09-05: the LICENSE does grant use after its first sentence, so the report rested on a misreading |
| 5 | [mini_dev issue 48](https://github.com/bird-bench/mini_dev/issues/48) | the PostgreSQL evaluator scores q1473 differently on two runs of the same database | none yet |
| 6 | [mini_dev issue 49](https://github.com/bird-bench/mini_dev/issues/49), [dataset discussion 3](https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/discussions/3) | 23 BIRD dev golds the 2025-11-06 pass left unchanged that do not answer their question on the shipped data | none yet |

## What it does not do

- It does not decide which statement is right. A second statement is supplied by you: a model's
  prediction, an upstream correction, a human's fix.
- It does not generate differentiating data. Two statements that agree on the shipped rows but
  differ semantically are found only by the shuffle probe, not by search.
- The probes are heuristics and say so in their own evidence; the direction probe alone is 17 %
  precise on Mini-Dev and is off by default.
- It proves nothing about correctness, security, or production use. It runs as the role you give
  it; give it a read-only one.
- It offers no Python API. The `attestql` command, its flags, its output and the JSON it writes
  are this project's only public surface, so the modules under `attestql.` are internal and their
  signatures can change in any 0.x release without notice.

## How to check rather than believe

Every number above has an owning artifact in [the claims register](docs/claims-register.md),
which also lists the claims this project deliberately does not make and dates every negative
claim, because negative claims decay. The three shipped-gold defects reproduce in the merge gate
on both engines (`tools/audit-sandbox/` for PostgreSQL; `src/attestql/demo/` for SQLite, the same
files `attestql demo` writes out) every time `just check` runs. [ADR-0013](docs/adr/0013-audit-text-to-sql-gold-with-typed-replay-evidence.md) records the
decision this tool implements and the date by which it is reconsidered if nobody uses it.

The history is short and stated: this repository was developed privately from 2026-08-25 under a
different product direction; it was reoriented on 2026-09-02 by ADR-0013 to the problem above, and
the public history starts after that. The code was written with AI assistance under the owner's
review, and the gate, not the author, is what vouches for it.

## Running the gate

`just check` is the whole of it, and it is what a change has to be green under: ruff, pyright
strict, the three repository checks, markdownlint and cspell over the documents, pytest, and then
both audit sandboxes, the PostgreSQL one in Docker on port 5497 and the SQLite one on a file. It
needs uv, `just` and Node.js, and Docker for that one recipe.
[docs/developer-environment.md](docs/developer-environment.md) is the document that owns all of
it: what each tool is there for, what the sandboxes do, and how tags and releases are cut.

## Licence

Apache-2.0 for this repository (`LICENSE`). The material excerpted from BIRD Mini-Dev and from
Spider 1.0, listed in `NOTICE`, keeps its own CC BY-SA 4.0 licence. The PostgreSQL parser,
`postgast`, is a BSD binding to `libpg_query`, PostgreSQL's own grammar as a library, and the
PostgreSQL driver, `psycopg`, is LGPL. The SQLite parser, `sqlglot`, is MIT, the SQLite driver is
the standard library's, and `jinja2`, which renders every page this project writes, is
BSD-3-Clause.
