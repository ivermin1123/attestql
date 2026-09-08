# Phase 2: a SQLite TEXT cell that is not valid UTF-8

## Context

Register A43: two Spider 1.0 dev golds (q455 and q456 on `wta_1`) fail as gold-side execution
errors because a stored TEXT cell is not valid UTF-8 and Python's `sqlite3` raises in its decoder.
The 26 predictions of those two questions cannot be compared either. The bytes are the data; the
tool refuses the row rather than recording what the file holds.

## Requirements

- A TEXT cell whose bytes are not valid UTF-8 is recorded losslessly and compared byte for byte.
- It stays a TEXT cell. Under R-SET a value only meets a value of its own storage class, so an
  undecodable TEXT and a BLOB holding the same bytes stay two values, and a BLOB stays refused.
- The canonical serialization gains one type tag. The record's own `serialization` version moves
  with it so that a reader knows which vocabulary a record was written under, and every record
  written before this phase still verifies against its own stated version.
- The loader reads the new tag back into the same value, so a record round-trips.

## Decision to record in an ADR

`FORMAT_IDENTITY` (`attestql/canonical-serialization/1`) names the line grammar and does not move:
the cells are still `tag:payload` and an old record re-renders to the bytes it was written with,
which is what `load` recomputes a stored hash against. The type-tag vocabulary is what changed, and
that is what `SerializationDescriptor.version` states, so the audit's descriptor moves from
`attestql/audit/2` to `attestql/audit/3`. Alternative rejected: bumping `FORMAT_IDENTITY`, which
would re-render every old record under a header it was not written with and report every stored
hash as a mismatch.

The tag is `text-bytes` and its payload is the lowercase hex of the raw bytes; it names what the
cell is, a TEXT value this reader could not decode, so a BLOB that becomes recordable later takes a
tag of its own rather than this one. The backend returns
such a cell as a `bytes` subclass declared beside the serialization, so the storage class stays
TEXT and a plain `bytes` (a BLOB) still has no rendering and is still refused at the value.

## Files

- `src/attestql/evidence/serialize.py`: the subclass, `canonical_type_tag`, `render_value`.
- `src/attestql/evidence/render.py`: the JSON shape of the cell.
- `src/attestql/evidence/load.py`: the reading back.
- `src/attestql/audit/sqlite.py`: `text_factory`, `_storage_class`, `_as_recorded`, the digest
  rendering, and the module docstring.
- `src/attestql/audit/cli.py`: `SERIALIZATION.version`.
- `docs/adr/0015-*.md` and `docs/adr/0000-index.md`.
- Tests: `tests/test_canonical_serialization.py`, `tests/test_evidence_load_round_trips.py`,
  `tests/test_audit_audits_a_sqlite_file.py`, `tests/test_audit_sandbox_sqlite.py`.

## Steps

1. Add the value type to the serialization, the renderer and the loader, with tests that a record
   holding one round-trips and that its hash recomputes.
2. Teach the SQLite backend to produce it, and keep the BLOB refusal exactly where it is.
3. Move the descriptor version, and check every place that pins `attestql/audit/2` (tests, docs,
   the report renderer and the site data).
4. Write ADR-0015 and add it to the index.
5. Prove the gap is closed on the data that found it: audit the two `wta_1` golds of Spider dev
   from the cached inputs, gold-only, and record the result in the register row.

## Validation

- A record holding an undecodable TEXT cell round-trips, and its two hashes recompute.
- A record written before this phase still verifies (a stored fixture record in the tests, rendered
  under `attestql/audit/2`, recomputes its hashes unchanged).
- q455 and q456 of Spider dev audit instead of erroring.
- `just check` green.

## Risk

The comparison keys on `(tag, value)`; `bytes` is hashable and compares byte for byte, so R-SET
needs no change. The risk is a place that assumed every cell is one of seven tags. Pyright strict
and the loader's own refusal message are what find those, and the phase does not land until the
whole gate is green.

## Rollback

One commit. Reverting it restores the refusal; records written in between state version 3 and a
reverted reader would refuse them, so the revert is only clean while nothing has been published.
