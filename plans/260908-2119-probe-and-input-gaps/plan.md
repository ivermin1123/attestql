# One probe and three input gaps, 2026-09-08

Status 2026-09-08 22:10: all four done on `main` (`0ad15ca`, `e5d6899`, `0ff052f`, `b003a3d`),
the gate green before each, measured in
[measurement-260908-2200-probe-and-input-gaps.md](../reports/measurement-260908-2200-probe-and-input-gaps.md)
and recorded as register rows A45 to A48. The order ran 1, 4, 3, 2: the WAL copy of phase 4 is what
let the measurement read `card_games` from the read-only input cache.

The GLM research batch of 2026-09-07 (`plans/260907-1822-glm-research-lanes/`, register rows A41
to A44) ended with one probe worth building and three gaps found in use. This plan builds them.
Nothing here changes what a verdict means: a smell stays a heuristic, and the two engine changes
widen what can be recorded and read rather than what counts as equal.

## Phases

| Phase | What | File |
|---|---|---|
| 1 | The `duplicate-full-row` gold-only smell, measured before it is claimed | [phase-1-duplicate-full-row.md](phase-1-duplicate-full-row.md) |
| 2 | A SQLite TEXT cell that is not valid UTF-8 is recorded, not refused | [phase-2-undecodable-text.md](phase-2-undecodable-text.md) |
| 3 | A predictions file with one statement per line | [phase-3-plain-line-predictions.md](phase-3-plain-line-predictions.md) |
| 4 | A WAL database on read-only media | [phase-4-wal-read-only.md](phase-4-wal-read-only.md) |

Phases 1, 3 and 4 are independent. Phase 2 changes the value vocabulary a record can hold and is
the only one that moves a version, so it lands on its own and before nothing.

## Outcome

- A gold whose own result repeats whole rows is read again, with the fire count measured on a
  named corpus before the register says anything about it.
- The two `wta_1` Spider golds of A43 are audited instead of failing in Python's decoder.
- The 12 plain-line prediction files of A44 are read by the tool as shipped.
- A WAL SQLite file on read-only media is audited, and the copy that made that possible is named
  in the run's own output.

## Constraints

- Read-only auditing: no phase writes to a database under audit.
- One backend, one comparator, one record (ADR-0013, ADR-0014). A new value type is stated in the
  serialization and read back by the loader, not special-cased in a backend.
- No dataset-specific munging in the tool. DAIL-SQL's comment cut and ATLAS's database suffix stay
  in the measurement scripts that need them.
- `just check` is the gate: ruff, pyright strict, repocheck, docs, pytest, both sandboxes.
- Normal commits on `main`, no rewrite, no force push. The owner pushes and tags.

## Non-goals

- BLOB results stay refused. Phase 2 covers a TEXT cell whose bytes are not valid UTF-8, which is
  the gap A43 measured, and nothing else.
- No new claim about PostgreSQL. Both engine changes are SQLite's.
- No release. The version in `pyproject.toml` is left where it is; the owner decides the tag.
- No upstream post about any of it.

## Acceptance

- Every phase ships with tests that fail without its change, and the sandbox tests state the new
  behaviour where the sandbox can show it.
- Phase 1's register row states a fire count measured at the shipped version on a named corpus,
  with a stated sample read by hand, the way A31 and A34 state theirs.
- `docs/audit-command.md` documents the new probe, the new flag and the copy a WAL file needs.
- Register rows are added for what was measured, and the ADR index carries the decision of phase 2.
