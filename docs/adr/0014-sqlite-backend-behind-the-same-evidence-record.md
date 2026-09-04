# ADR-0014: A SQLite backend behind the same evidence record

**Status:** Accepted, 2026-09-04, by the owner. The sentence this record was drafted under is
kept as history: drafted without the owner during the autonomous run of that day
(`plans/reports/session-260904-autonomous-run.md`); nothing here is built, and the estimate
below is a reading of the code as it stands at `9e4627d`, not a plan. What the owner accepted,
the same day, is the decision below and the three answers under Resolved.

## Context

The largest public text-to-SQL golds are SQLite, not PostgreSQL: BIRD dev (1,534 questions,
11 databases), Spider 1.0 dev (1,034), and the SQLite file of Mini-Dev itself (500). The
PostgreSQL sets beyond Mini-Dev are gated or absent
(`plans/reports/research-260904-next-postgres-targets.md`: BIRD-CRITIC's gold is released by
email, BIRD-Interact and LiveSQLBench publish no gold, Spider 2.0 has no PostgreSQL variant).
A tool that audits gold and predictions only on PostgreSQL therefore reaches one public set of
500 questions and stops. The question this ADR answers is what a second engine costs and what
it would make of the evidence record, before anyone writes it.

**What the tool is built on that is PostgreSQL's.** The inventory script
`plans/reports/session-260904-autonomous-run/pg_dependency_inventory.py` counts, per file
under `src/attestql/`, the lines that name the driver, the parser, the system catalogues, the
session envelope, PostgreSQL SQL idioms, or PostgreSQL type names. At `9e4627d`:

| File | Lines | Depends on PostgreSQL through |
|---|---|---|
| `audit/postgres.py` | 860 | everything: psycopg (26 lines), catalogues (15), envelope (36), idioms (8), types (18) |
| `audit/statements.py` | 465 | postgast, the libpg_query grammar (58 lines): every parse, every rendering back to text, the allowlist |
| `audit/cli.py` | 1280 | 7 lines: constructing the backend and naming the session settings |
| `audit/compare.py` | 543 | 7 lines: session settings and the catalogue's type names in records |
| `audit/smells.py` | 904 | 15 lines: column types from the catalogue, the census regex, the tie detector's types |
| `audit/backend.py` | 243 | 6 lines of documentation; the protocol itself names no engine |
| `kernel/types.py`, `evidence/*.py`, `contract/clock.py` | 1,806 | the field name `pg_type` on every column, the five session settings a record must state |
| everything else | 397 | none |

6,498 lines in 21 files; the lines that name PostgreSQL directly are about 220, but they sit
in two places that decide everything else: the parser that admits a statement and the record
that describes a result.

**Where SQLite differs in kind, not in syntax.** Four things the record states have no
SQLite counterpart. (1) A column has no declared result type: SQLite types values, not
columns, and `typeof()` can differ from row to row within one column. (2) There is no
session to precondition: no `TimeZone`, `DateStyle`, `IntervalStyle`, `extra_float_digits`;
the collation is per column or per expression. (3) There is no server, no role, no read-only
transaction to read back; a file opened with `mode=ro` is what read-only means. (4) The
grammar: BIRD's SQLite golds use double-quoted string literals, backtick identifiers and
`IIF`, `strftime`, `CAST(x AS REAL)`; libpg_query rejects the backticks and reads a
double-quoted literal as an identifier, silently, which is worse than a refusal.

## Decision

1. One evidence record, one comparator. R-ORD and R-SET (ADR-0004), the canonical
   serialization, the fixed clock and the record builder stay engine-neutral and are not
   forked. What a SQLite result cannot state is stated as such, not faked: the column's type
   field carries the value's storage class per cell when the column has no declared type, and
   the comparator treats a column whose storage class varies across rows as typed per cell.
   Two public contracts carry this and are amended before anything else is written.
   `ColumnType.pg_type` becomes `declared_type`: the engine's own name for the type, read in
   the namespace of the `engine` the session settings block names once per record, so no
   column carries an engine prefix of its own and a PostgreSQL record's canonical bytes do not
   change. And the session settings block gains that `engine`, which is what allows the five
   PostgreSQL settings to be absent for SQLite. The record's producer `version` and the
   summary, counterexample and smells format strings are each bumped when their own layout
   changes, and the canonical serialization's format identity when a rendering's bytes change:
   a version a reader compares two documents under states that both were written to one
   layout, so it moves with the layout and with nothing else. ADR-0013 renamed the record's
   `schema_version` away without leaving a rule for the strings that replaced it; this is that
   rule.
2. One backend per engine behind the `Backend` protocol in `audit/backend.py`, which already
   names no engine. `audit/sqlite.py` implements: a read-only file connection; `existing_tables`
   and `column_types` from `sqlite_master` and `pragma_table_info`; row counts as today; content
   digests computed in Python over rows fetched in a stated order (SQLite has no `md5`, no
   `string_agg` with ordering); shuffled copies as `CREATE TABLE ... AS SELECT` into an attached
   scratch database ordered by a Python-side hash of the row and the seed; the census regex
   through a registered `REGEXP` function; no lock (one process, one file), no envelope beyond
   `PRAGMA query_only`.
3. One parser per engine behind a small `ParsedStatement` protocol that `statements.py`
   already shapes (tables, replay rule, sort keys, placeholders, the allowlist verdict). The
   SQLite parser is sqlglot's SQLite dialect (MIT) rather than libpg_query, and the allowlist
   is re-stated over its tree. The validator version string names which parser judged the
   statement, as the summary's `parser` block does since `efd9d00`.
4. The smells split by what they read: the ones that read the tree and the result (limit
   ties, nulls-first, float order) move unchanged; the ones that read the catalogue (numeric
   text, column types) go through the backend and get a SQLite answer where one exists.

## Estimate

Stays as it is: `evidence/`, `contract/`, `kernel/ports.py`, most of `cli.py` and
`compare.py`, about 4,000 lines. Splits into an engine module beside the PostgreSQL one:
`postgres.py` (860) and `statements.py` (465), and a SQLite sibling of each, of a similar
size. Changes in place: `kernel/types.py` and `evidence/types.py` for the two schema
amendments, `smells.py` for the catalogue seam, about 150 lines. The measured numbers of the
README stay PostgreSQL numbers; a SQLite run gets its own report and register rows.

## Alternatives considered

- Translate SQLite gold to PostgreSQL and audit it there. Rejected: the audit would then
  judge a translation, and BIRD's SQLite semantics (dynamic typing, `1/2 = 0`, string
  comparison of numbers) are the very things a wrong gold hides behind.
- Fork the record into a SQLite family. Rejected: two records would need two comparators, two
  serializations and two sets of claims, and the point of the tool is one reading of one
  evidence format.
- Do nothing until a PostgreSQL set beyond Mini-Dev is public. This was the default until the
  owner accepted this record on 2026-09-04, and nothing was built before that; the 60-day
  window of ADR-0013 point 10 has still not closed, and a SQLite run does not close it.

## Consequences

- A second engine touches the two public contracts, the record schema and the parser
  version string, before it touches any code, so the schema amendment is the first commit and
  is reviewed alone.
- The README's claims stay engine-qualified: "on PostgreSQL" is not dropped from a sentence
  because SQLite arrived.
- The gate grows a second sandbox with no container: a SQLite file built from the fixture SQL
  in the test run.

## Resolved

The three questions this record was drafted with, answered by the owner on 2026-09-04.

- **Storage class is type.** Under R-SET a value only meets a value of its own storage class,
  so a SQLite `1` (INTEGER) and a `1.0` (REAL) are two values, because that is the rule the
  comparator already applies on PostgreSQL, where an `int8` and a `numeric` holding the same
  amount are two values; ADR-0004 now states it engine-neutrally.
- **`bird_ex` on SQLite is BIRD's own SQLite scorer, imported verbatim:**
  `set(predicted) == set(gold)` over `fetchall()` with Python equality, where
  `1 == 1.0 == True`, computed beside the verdict as it is on PostgreSQL and with the record
  noting that Python equality is part of that reading, because a reading of the benchmark that
  is not the benchmark's own answers for nobody.
- **BIRD dev (1,534 questions) is the first SQLite set to run,** Spider 1.0 after it, because
  BIRD is the set whose gold this tool has already audited on PostgreSQL and the two runs can
  then be read against each other.
