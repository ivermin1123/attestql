# Phase 3: the two High findings still in the published release, and 0.3.1

Closes LOGIC-02, LOGIC-17 and LOGIC-03, then releases. Depends on phase 1 only because a release
tag should be cut on history that will not be rewritten again.

## What is wrong

`LOGIC-01` was fixed in `07adbf0`. The other two High findings of the review are still in the
0.3.0 that a user installs from PyPI.

**LOGIC-02.** Both results are hashed for every rule, and the hashing step refuses a value that is
not finite. So an R-SET result holding NaN becomes an ERROR instead of receiving a verdict, while
ADR-0004 says only R-ORD has no bytes to compare. This is on the product path: a PostgreSQL float
column reaches it through `NumericFromFloatText`. The fix is a type-aware representation for the
non-finite sentinels in the digest, or a comparison key separated from the record's rendering.

**LOGIC-17** only becomes visible once LOGIC-02 is fixed: `_multiset` keys on `(tag, value)`
rather than through `typed_row`, so two NaN rows count as different and a false row difference is
reported.

**LOGIC-03.** The SQLite rewrite keeps DISTINCT and adds the ORDER BY key to the select list,
which widens the grain the deduplication applies to, so `arbitrary-cut` fires on a result that
already holds every distinct row. The fix is to add the key only when the original statement
already projects an equivalent expression, and otherwise to mark the smell not applicable with a
reason.

## The published numbers

LOGIC-03 changes how often `arbitrary-cut` fires, and that count is published on attestql.com and
recorded in `docs/claims-register.md`. The measurement has to run again over the same inputs, and
the register has to record the new number and the commit that produced it. An old number left
standing beside new code is the failure this repository exists to catch.

## The release

Under the semver rule the owner set on 2026-09-10, these are fixes, so they go out as 0.3.1. The
release notes say plainly that 0.3.0 carried three defects that could end a run or misreport a
smell, and which of them a user was exposed to.

## Validation

- A test for each finding that fails before the fix and passes after it.
- The re-measured smell counts, the claims register and the site agree.
- `just check` green, CI green, and a clean install of 0.3.1 from PyPI runs the demo.

## Done 2026-09-12

`67a804d` closed LOGIC-02 and LOGIC-17 together, because the second is only reachable once the
first is fixed: a non-finite value gets a rendering (ADR-0016) and the R-SET multiset keys its
cells through the same typed keying the comparison uses. `ee41966` closed LOGIC-03. Each came with
a test that fails on the tree before it.

The published numbers were re-measured by making all 121 of the site's runs again, plus the
2024-06-27 copy of BIRD dev that register row A34 compares, and the register records the new
numbers as A49 to A52 with the old ones left dated where they stand. Two things came out of that
which were not in this phase's plan and are in the report: what an order-dependent gold probe sees
on PostgreSQL depends on the planner's statistics, so `audits.sh` now runs `ANALYZE` after a dump
load, and the budget cut in the selector took the largest question of the whole selection, which
gave one benchmark zero question pages once `duplicate-full-row` brought 613 directories with it.

0.3.1 is on PyPI and the tag carries the runs whole. Validation: `just check` and CI green at
every commit, a clean install of 0.3.1 from PyPI runs the demo and writes records stating
`attestql/audit/4`, and the site attestql.com serves the refreshed runs (register N7).
