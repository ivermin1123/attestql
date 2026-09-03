# ADR-0004: Replay equality is R-ORD or R-SET, declared per result

**Status:** Accepted. **Date:** 2026-08-25. **Supersedes:** the earlier "byte-identical result"
wording in the Slice 1 brief. **Amended:** 2026-08-30, the Open question below is answered by
ADR-0009 (in the private history before publication), which fixes Q13's result grain at
one row per segment.

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
