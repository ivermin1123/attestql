# ADR-0004: Replay equality is R-ORD or R-SET, declared per result

**Status:** Accepted. **Date:** 2026-08-25. **Supersedes:** the earlier "byte-identical result"
wording in the Slice 1 brief. **Amended:** 2026-08-30, the Open question below is answered by
ADR-0009 (in the private history before publication), which fixes Q13's result grain at
one row per segment; 2026-09-04, what a NaN is under R-SET is stated at the end, and what a
type is under R-SET is stated at the end of the decision; 2026-09-07, what the two rules read
a number as is stated at the end of the decision.

## Context

The brief originally required that a reviewer re-running an evidence record obtain a
"byte-identical result on unchanged data". Review found the phrase ambiguous in both directions.

Byte equality is meaningless without a fixed ordering and a fixed serialization: two runs of a query
with no `ORDER BY` can return the same rows in a different order and fail byte comparison while
being the same answer. And byte equality is the wrong test when row order carries no meaning: an
unordered breakdown by segment has no canonical row order to compare.

## Decision

Replay equality is **exactly one of two rules, chosen per result and recorded in the evidence
record**.

**R-ORD**, when row order is part of the result contract. The query carries a total deterministic
ordering with ties broken by a unique key, the result is rendered under the recorded canonical typed
serialization, and the re-run must produce a byte-identical rendering.

**R-SET**, when row order is not part of the result contract. The re-run must produce the same
multiset of rows under typed comparison: same column set and types, same row multiplicity, values
equal under the recorded type-aware rules for numeric precision, timestamps and nulls. Row order is
disregarded.

Assignment across the canonical set: R-ORD for Q3, Q4, Q9, Q10, Q13, Q14, Q15 (trends, rankings,
ordered distributions, single-winner picks). R-SET for Q1, Q2, Q5, Q6, Q7, Q8, Q11, Q12 (scalars and
unordered breakdowns). Q16 is the deliberately ambiguous question and carries **no** rule; it must
not be constructible with one.

Both rules apply only when fixture version, schema version, metric-definition versions, policy
version, validator version, execution limits and evaluation clock all match the recorded values. A
mismatch yields **not comparable**, which is a third outcome and is not a failure. A record that does
not declare its rule is not a valid evidence record.

**Storage class is type, amended 2026-09-04.** Under R-SET a value only meets a value of its own
storage class, and which classes an engine has is the engine's to say. On PostgreSQL that is what
this rule has always applied: an `int8` and a `numeric` both holding 1 are two values, and a result
that returns one where the other was recorded is not equal. On SQLite, where a column has no
declared type and every value carries its own class, an INTEGER `1` and a REAL `1.0` are two values
for the same reason and by the same rule. The rule is therefore engine-neutral and needs no second
form: a comparator reads the class the engine returned a value at, never a class of its own making.
ADR-0014 records where the second engine goes and what the record states about it.

**The two rules can disagree about one pair of numbers, amended 2026-09-07.** R-ORD compares
the canonical rendering, where a numeric is written at the serialization's `numeric_scale` of
six, and R-SET compares the values as the result returned them, because a rounding step must not
decide membership of a row set (owner decision of 2026-08-31, recorded in `compare_r_set`). So
two numbers that first differ past the sixth decimal are EQUAL under R-ORD and NOT_EQUAL under
R-SET, and neither reading is the other's mistake: a result whose order is the answer is compared
by what it renders to, and a result that is a set is compared by what it holds. The case is not
hypothetical. Mini-Dev q31 on SQLite returns `0.1344364012409514` where the prediction returns
`0.134436401240951`, both render to `0.134436`, and the gold's rule is R-ORD, so the verdict is
EQUAL (`plans/reports/measurement-260907-1106-minidev-sqlite.md`). A record declares its rule,
which is what lets a reader of two verdicts see which reading produced each.

## Alternatives considered

**Byte-identical everywhere.** Rejected as ambiguous, and false for unordered results.

**Semantic equality everywhere.** Rejected. It discards the ordering guarantee for rankings and
trends, where the order is the answer.

**Let the comparator infer which rule applies.** Rejected. Inference makes the guarantee implicit,
and an implicit guarantee is the kind a reviewer cannot check.

## Consequences

- Every R-ORD question must express a **total** order. A ranking with an unstable tail is not
  reproducible, which is the failure this rule exists to prevent.
- Acceptance criterion A4 and failure criterion F3 both name R-ORD and R-SET and carry the same
  precondition set, so they cannot drift apart.
- "Not comparable" must be surfaced honestly rather than reported as a pass or a fail.

## Open questions

Q13's result grain (one row per segment, or one row per segment per month) determines whether its
ordering key is sufficient for a total order. Must be decided before M2.

**Answered on 2026-08-30 and left standing above rather than rewritten.**
ADR-0009 (in the private history before publication) decides that "per month"
qualifies the account and not the output, so the grain is one row per segment and the ordering
key above is total. The decision was made before this note and neither document recorded it;
that gap is what this note closes.

## What a NaN is, amended 2026-09-04

R-SET above requires values equal under the recorded type-aware rules and names numeric
precision, timestamps and nulls. It did not say what a NaN is, and a float column returns one.

**A NaN is one value: equal to a NaN and to nothing else.** That is what PostgreSQL does with
it. The server holds NaN equal to NaN, groups two of them into one row and sorts them together
above every number, and this tool reads a result the server produced. So two results each
holding a NaN at a cell are equal there, a NaN on one side only is a difference like any other,
and a run of NaN ordering keys spanning a bound is the tie the arbitrary-cut smell exists to
find. Each infinity is one value under the same reading, which Python's `Decimal` already gives.

Python does not give the NaN rule: two NaN values compare unequal there and each hashes by its
own identity, so a multiset keyed on the value as it came back counts one answer as two and
reports two runs of one statement as a disagreement. The rule is therefore stated once, in
`typed_value`, and every comparison this tool makes keys its rows through it.

The canonical rendering is unchanged and still refuses a non-finite numeric, so an R-ORD
comparison over a result holding one has no bytes to compare rather than a rule of its own. That
is the same refusal as before this amendment: what is decided here is how a comparison that
counts rows keys the value, not how a rendering writes it.
