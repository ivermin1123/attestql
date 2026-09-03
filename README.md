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

AttestQL executes both statements under a read-only transaction, renders each result with a typed
canonical serializer, compares them under a stated rule (ordered sequence when the gold orders,
multiset otherwise), and writes an evidence record per execution with everything a second person
needs to re-run it. When the two disagree it writes the differing rows as a counterexample. On the
gold alone it runs mechanical probes for the defects that need no second statement.

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

The password comes from `PGPASSWORD` or `~/.pgpass`; a DSN that contains one, or any URI form, is
refused. Loading BIRD's dump prints 99 `role "..." does not exist` errors from its ownership
statements; they are harmless. The role needs SELECT on the audited tables and an existing schema it may create tables in
(`--scratch-schema`, default `attestql_scratch`); without one, the shuffle probe reports itself
as not run in `summary.json` and everything else still runs. Run one audit per scratch schema at
a time. On the full Mini-Dev gold set the run prints one line per question; three of them, and
the last line (the whole output is in `plans/reports/audit-260902-minidev-gold-only/`):

```text
q1380 student_club R-SET  GOLD-ONLY  smells=float-aggregate-order  audit/q1380/
q1389 student_club R-ORD  GOLD-ONLY  smells=arbitrary-cut  audit/q1389/
q879  formula_1   R-ORD  GOLD-ONLY  smells=ordering-over-numeric-text  audit/q879/
498 questions: 0 NOT_EQUAL, 0 NOT_COMPARABLE, 39 smells fired
```

Two copies of the Mini-Dev question set exist and they differ: the `minidev.zip` linked from the
GitHub README (498 distinct ids, q879 still ordering a text column as text) and the Hugging Face
dataset `birdsql/bird_mini_dev` (500 ids, q879 corrected, q1322 changed; 2026-01-18). The lines
above are from the zip; the same run over the Hugging Face file fires on 29 golds instead of 30,
the difference being q879. Both runs, with each file's digest and origin, are in
`plans/reports/audit-260902-minidev-gold-only/` and `plans/reports/audit-260903-minidev-hf-gold-only/`,
and `--questions-origin` writes where your file came from into every record and the summary.

Exit status is 0 with no disagreement, 1 with at least one, 2 on a tool error. `--fail-on-smell`
makes a fired probe exit 1 too. Every `audit/q<id>/` holds `counterexample.json`, the two evidence
records (`evidence-gold.json`, `evidence-second.json`) and `smells.json`; `audit/summary.json`
holds the counts, the fixture digest, and whether the shuffle ran.

## What it does

- Typed replay comparison: a type tag per cell, declared numeric scale, NULL rendering, a hash per
  result; columns are compared by position and type, never by name, as the benchmark does; R-ORD
  when the gold has a top-level ORDER BY and compares the rendered rows in order, byte for byte,
  R-SET otherwise; EQUAL, NOT_EQUAL, or
  NOT_COMPARABLE with the mismatched preconditions named (fixture digest, serialization, rule,
  ordering, and the five session settings that change rendered bytes).
- An evidence record per execution, twenty required fields, no defaults: what ran, as what role,
  on which server, under which settings, with which result and hash, and how to re-run it.
- Gold-only probes, all heuristics and labelled so: ordering over numeric-looking text; an
  arbitrary or null-first cut that changes the answer; a result that is not a function of the data
  (a seeded shuffle of the referenced tables, copied into the scratch schema, changes it), with
  float aggregates whose value depends on summation order reported under their own name; and,
  off by default behind `--experimental-s2`, direction against the question.
- BIRD's own set-equality reading is computed beside every verdict, so a counterexample states
  what the benchmark would have said.

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
default. [The claims register](docs/claims-register.md) lists every claim with its owning
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
