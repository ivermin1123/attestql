# Phase 1: the `duplicate-full-row` gold-only smell

## Context

L1 measured BIRD's 399 dev rewrites of 2025-11-06 (register A41,
`plans/reports/research-260907-1934-bird-rewrites-what-changed.md`). Of the rewrites that change
the answer, 23 are golds whose old result repeats whole rows and whose rewrite adds DISTINCT, and
22 of those 23 fire none of the three shipped probes. It is the largest gold-only class the lane
found. L3 measured the same shape from the other side: of 1,751 predictions BIRD credited that the
typed comparison calls unequal, 1,697 differ by multiplicity alone, and 18 of a 50-row hand sample
are wrong answers that repeat rows (register A44).

The candidate L1 counted needs the rewrite to see the added DISTINCT. A probe has only the gold, so
what ships is the half a gold can state: the result repeats whole rows and the statement did not
ask for that.

## Requirements

- A fifth smell named `duplicate-full-row`, gold-only, quiet by default in the sense every smell is:
  it states a reading order and never a verdict, and carries `heuristic: true` and a `means`.
- It fires when the gold's own result holds at least one row more than once and the statement's
  outer select does not state DISTINCT.
- It is not applicable when the statement states DISTINCT, when the result holds fewer than two
  rows, or when the result was truncated (the repeats may be an artefact of the cut).
- It asks the database nothing. Its evidence is the result already in hand.
- Evidence: the row count, the distinct row count, the largest repeat count, and up to
  `ROWS_IN_EVIDENCE` repeated rows with their counts, rendered through `typed_row` like every other
  smell's rows.
- The name joins `SMELL_NAMES` so a summary counts it at zero, and `probe_meanings()` gains its
  sentence.

## Files

- `src/attestql/audit/smells.py`: the constant, the function, the entry in `SMELL_NAMES`,
  `all_smells` and `probe_meanings`, and the module docstring's "What each one asks".
- `tests/test_audit_smells_read_the_gold_and_the_data.py`: fires, stays quiet under DISTINCT, is
  not applicable on a one-row and on a truncated result, and its evidence names the repeated rows.
- `tests/test_audit_sandbox_sqlite.py` and `src/attestql/demo/`: the sandbox states the new count if
  a demo gold repeats rows; if none does, the sandbox is left alone and the tests say so.
- `docs/audit-command.md`: the probe list.
- `docs/claims-register.md`: one row with the measured fire count.

## Steps

1. Read `parse.distinct` and confirm what it answers for a set operation and for a subquery, since
   `set_operation` and `from_has_subquery` are the shapes other smells refuse to guess on.
2. Write the smell and its tests. Run `uv run pytest -k smells`.
3. Run the whole gate.
4. Measure before claiming: gold-only over the Mini-Dev SQLite golds of both published copies
   (`mini_dev_sqlite.json` of `minidev.zip` and the Hugging Face copy, the corpus of A31), work
   directory outside the repository, inputs from `~/.cache/attestql-measure/inputs`. Count the
   fires, and read a stated sample by hand: is the repeat the answer the question asked for, or a
   join that fanned out? A31 and A34 are the pattern for what the row then says.
5. Commit the code and the tests, then the register row with the measurement.

## Validation

- `uv run pytest` green, `just check` green.
- The measurement's fire count and its sample are in the register row, with the corpus named and
  the version stated, and the report or artifact that holds the numbers is linked.

## Risk

A smell that fires on every `GROUP BY` whose projection drops a key would be noise. The measurement
is what decides whether the shipped rule is the one above or a narrower one; if the fire rate on
Mini-Dev is far above the 25 smells A31 counted for three probes, the phase stops and the rule is
narrowed (for instance to a result whose repeats are more than half its rows) before it is claimed.

## Rollback

One commit, one module, one name in `SMELL_NAMES`. Reverting the commit removes the probe and its
row; no record shape and no verdict depends on it.
