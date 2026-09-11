# ADR-0016: A non-finite numeric renders as its name

**Status:** Accepted, 2026-09-11.

## Context

ADR-0004 settled that a NaN is one value here. PostgreSQL holds NaN equal to NaN, groups two into
one and sorts them together above every number, so the comparison reads them as one value:
`typed_value` stands a single key in for every NaN, and the comparison of two results each holding
one reaches EQUAL.

The rendering disagreed with that. `canonical_serialize` refused a non-finite numeric, on the
reasoning that a value with no digits has nothing to place at a fixed scale. Every rule hashes both
results, so a question whose result held a NaN reached EQUAL and then raised in the hashing step,
and the run reported an error for a question it had already decided. This is on the product path
rather than a corner: a PostgreSQL `float4` or `float8` reaches a record as the decimal the server
printed for it, and `NaN`, `Infinity` and `-Infinity` are three of the things it prints.

A second defect sat behind the first. `row_difference` built its multiset by pairing each value
with its tag itself instead of calling the shared keying, so two NaNs counted as two values there
even though the comparison counted them as one, and results that agree were reported as holding a
row the other side did not. It could not be seen while the hashing step raised first.

## Decision

A non-finite numeric renders as its name, and every NaN spelling renders as one name.

1. `NaN`, `sNaN` and `-NaN` all render as `NaN`. They have to render alike because the comparison
   already holds them to be one value, and a rendering that told them apart would give two results
   it calls EQUAL two different hashes, which is the defect above in another form.
2. `Infinity` and `-Infinity` render with their sign. Decimal holds each equal to itself and to
   nothing else, so they need no stand-in and keeping the sign is what preserves that.
3. `row_difference` keys through `typed_row`, so one keying serves the verdict and the difference.
4. `FORMAT_IDENTITY` does not move. The line grammar did not change, and a record written earlier
   re-renders to the bytes its stored hashes were taken over.
5. `SerializationDescriptor.version` moves to `attestql/audit/4`, for the reason ADR-0015 gave for
   the move to `3`: the set of values a record can hold is part of what a reader compares two
   records under. No record written under `2` or `3` changes by a byte, because a non-finite cell
   could not be in one: the rendering raised, so the run wrote an error instead of a record.

The JSON record stays faithful to what the database returned. A cell holding `sNaN` is written as
`sNaN` and read back as `sNaN`, and it is the key and the rendering that collapse, exactly as
`typed_value` already did for the comparison.

## Alternatives considered

**Give the non-finite values a tag of their own, as ADR-0015 did for undecoded bytes.** A NaN is a
numeric, and ADR-0004's rule is that a value only meets a value of its own type. A tag of its own
would say a NaN is not a numeric, which would make a NaN and a number incomparable rather than
different, and no engine this tool reads says that. The undecoded-bytes case needed a new tag
because bytes are genuinely not text.

**Separate the comparison key from the record's rendering and hash the key.** It removes the need
for a rendering, and it also removes the property the R-ORD rule rests on, which is that the bytes
a reader can re-render are the bytes the comparison was made over. A hash taken over something a
reader cannot reconstruct from the record is not evidence.

**Keep refusing, and let the question report an error.** It is what shipped through 0.3.0. It means
a valid result from a valid statement is reported as a tool error, and it contradicts ADR-0004 in
the tool's own output: the comparison says EQUAL and the run says error.

**Render at the scale with a sentinel number.** Any number is a wrong answer. A result holding a
NaN would compare equal to one holding whatever number was chosen.

## Consequences

- Records written from now on state `attestql/audit/4`. A reader that knows only `3` is told so by
  the record rather than by a hash that does not match.
- A question whose result holds a NaN or an infinity receives a verdict. Through 0.3.0 it reported
  an error, so a run over a corpus with a float column could report errors that were not errors.
- The count of errors and the count of verdicts in any measurement taken before 0.3.1 over data
  holding a non-finite float are wrong by that much. No measurement in `docs/claims-register.md`
  is affected: every one of them ran on SQLite or on the PostgreSQL fixture, and neither returned a
  non-finite value, which is why the defect was found by reading rather than by a run.
- `row_difference` now reports nothing for two results holding the same NaN. Before it reported one
  row on each side, which a reader would have read as a real disagreement.

## Open questions

None. The same reasoning would apply to a non-finite value arriving from an engine added later, and
the rendering is in one place for that reason.
