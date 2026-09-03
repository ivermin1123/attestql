# Mechanism: what the gold audit detects that BIRD's evaluator misses, and how

Date: 2026-09-02. One page, as the owner asked; precondition B of the reorientation. Every number
comes from `plans/reports/spike-260902-three-gold-defects/` (commit `spike(gold-audit)`) unless a link says
otherwise; the coordinator re-derived the three results with independent SQL on the same server.

## What BIRD's evaluator does

`calculate_ex` in
[evaluation_ex.py](https://github.com/bird-bench/mini_dev/blob/main/evaluation/evaluation_ex.py)
is `set(predicted_res) == set(ground_truth_res)` over `cursor.fetchall()` on the one shipped
database. Four consequences: duplicate rows collapse; order never counts, even when the question
asks for one; values compare by Python equality across int, float, Decimal and bool; and nothing
can tell the evaluator that the gold itself is wrong.

## Three failure classes

| Class | What happens | Instance |
|---|---|---|
| F1 loose match | prediction differs in multiplicity, order or type; EX says 1 | two constructions on Mini-Dev data, below |
| F2 coincidence | two different statements, same output on the shipped data; EX says 1 | SpotIt's class; release 2 |
| F3 wrong gold | a correct prediction gets EX 0 and nobody notices | rows A, B, C from the upstream trackers |

## The mechanism, release 1

**M1. Strict typed replay comparison, existing code.** Both statements execute under a read-only
transaction with the session settings read back. Each result is rendered by the canonical
serializer (type tag per cell, declared numeric scale, NULL rendering) and hashed. The replay rule
is read off the gold: R-ORD when it carries a top-level ORDER BY, R-SET (multiset) otherwise, and
the rule is recorded. The ordering used for R-ORD is the one the question demands, applied to both
records, so the verdict compares two answers and not two ORDER BY clauses; each statement's own
ordering is kept as data. The verdict is EQUAL, NOT_EQUAL or NOT_COMPARABLE with the mismatched
preconditions named. Same data, so still execution match, but strict: it removes F1.

**M2. Disagreement records with adjudication smells, new and small.** Every NOT_EQUAL between the
gold and a second statement becomes one record carrying both results, the differing rows as
bounded multisets, both hashes, and mechanical smells computed from the gold's AST and the data:

- s1 ordering over numeric-looking text: an ORDER BY key is a text column whose values all parse
  as numbers, and the bounded result changes under a numeric cast (row B);
- s2 direction against the question: highest, most, max, top with ASC, or the reverse (row A);
- s3 bounded by an unordered or null-first key: LIMIT without a total order, or NULLS FIRST on a
  nullable key;
- s4 not a function of the data: the gold re-run with another plan or on a shuffled copy gives
  another result under the chosen rule.

Smells are heuristics and the record says so. They rank a NOT_EQUAL list so a maintainer reads the
likely-wrong gold first; they never decide. The second statement is supplied, not generated: a
model's prediction, an upstream correction, a human's fix. The golden-oracle pattern remains the
definition of "a second derivation" and is not written per benchmark question.

**M3, release 2, not now: differentiating data for F2.** Constraint-respecting perturbation of the
shipped instance for pairs that are EQUAL on it, or replaying both statements on a witness
instance from a bounded verifier and emitting the record. Deferred: the one verifier that exists
cannot be reused (section below), and our value there is the replay on real data plus the record.

## What release 1 does not detect

F2 beyond the s4 probe; wrong gold that has no smell and no second statement; errors in the
question text itself; anything on an engine other than PostgreSQL.

## Evidence on the three rows and the two constructions

| Row | Upstream report | BIRD EX | Rule | Verdict | Gold gives | Correction gives |
|---|---|---|---|---|---|---|
| A q1029 european_football_2 | [mini_dev #38](https://github.com/bird-bench/mini_dev/issues/38), open | 0 | R-ORD | NOT_EQUAL | 20, 20, 20, 23 | 80, 78, 78, 77 |
| B q879 formula_1 | [mini_dev #24](https://github.com/bird-bench/mini_dev/issues/24), closed, unfixed | 0 | R-ORD | NOT_EQUAL | Italian (91.610 as text) | Brazilian (257.320) |
| C q207 toxicology | [DAMO-ConvAI #227](https://github.com/AlibabaResearch/DAMO-ConvAI/issues/227), open | 0 | R-SET | NOT_EQUAL | 13 elements | 5 elements; 8 in gold only |
| constructed: C's correction without DISTINCT | none, constructed | 1 | R-SET | NOT_EQUAL | 5 rows | c 2291 times, o 296, n 128, s 100 |
| constructed: A's correction, rows reversed | none, constructed | 1 | R-ORD | NOT_EQUAL | 80, 78, 78, 77 | 77, 78, 78, 80 |

Probes: s1 fired on B (`results.fastestlapspeed` is text; 23,179 rows, 18,185 null, 0 empty, 0
non-numeric; top 5 by text 91.610, 89.540, 257.320 against top 5 numeric 257.320, 256.324,
255.874); s2 fired on A (`highest`, `max`, `top` against `ASC`; the column has no NULL, so NULLS
FIRST is inert and the defect is direction alone); s4 was quiet on A and B and, on C, the multiset
held while the row order changed three ways, which is why C is R-SET. Every row carries an evidence
record for gold and for correction with the hash of each result. One record field could not be
filled honestly: `schema_version` is written from the Slice 1 constant by the builder; the artifact
names it and carries the observed schema digest beside it. Found for free: `mini_dev_postgresql.json`
holds 500 entries with 498 distinct ids, 137 and 138 duplicated.

## Relation to SpotIt+

Trial on 2026-09-02, [source](https://github.com/atremante26/SpotItPlus) at commit `abee2ba`; raw
runs kept in the session scratchpad, not in the repository.

- Licence: the LICENSE file is "all rights reserved" with no grant of use; the paper's "open
  source" is not what the file says. Nothing of it can be vendored or depended on.
- All three modes run without an API key; the "LLM" mode is a precomputed constraints file.
- Purely symbolic over a bundled schema file in MySQL dialect; never reads the data; ignores the
  question text; cannot say which statement is wrong; overwrites its two output files on every
  run; a bounded "Equivalent" is not distinguished from a proven one.
- On the three rows: C found at bound 2 in 0.77 s with a 33-line witness that reproduces in
  SQLite; A "Equivalent" at bound 2 because the bound must exceed the LIMIT, found at bound 3 in
  7.5 s with a 247-line witness, 265 s at bound 5; B undetectable by design, the encoder strips
  CAST inside ORDER BY, so text and numeric ordering encode identically.
- Callable as a library through a `sys.path` insertion; the caller supplies schema and constraints.

Complement, not overlap. It answers "can these two statements differ on some small instance" for
join and predicate structure. The audit answers "do they differ on this data under this typed
rule, and here is the record", and catches the type and direction classes it cannot.
