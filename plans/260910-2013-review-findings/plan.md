# Acting on the seven-lane review

The review is
[plans/reports/review-260908-2321-seven-lane-independent-review.md](../reports/review-260908-2321-seven-lane-independent-review.md).
It carries 95 standing findings with a location, a reproduction and a suggested fix for each, so
this plan does not restate them: a phase names the findings it closes and the report is the
execution detail. What this plan adds is the order, because several of these changes constrain
each other, and the decisions the owner made on 2026-09-10 for the twelve items the report could
not decide alone.

## Owner decisions of 2026-09-10

| Item | Decision |
|---|---|
| LOGIC-22, R-ORD | Correct the ADR-0004 wording to the syntactic rule the code applies. |
| PERF-01, row budget | A budget that refuses. Over it, the question is an ERROR; no result is ever cut. |
| LOGIC-21, permutation budget | Same shape: a node budget that refuses, and the departure from the reference evaluator is written down. |
| META-01, ruleset | Block deletion and force-push, require CI on pull requests, the owner still pushes to main directly. |
| HYG-01, plans/ size | Raw output moves to release assets; the text reports and small summaries stay, each naming its asset and digest. |
| ARCH-03, kernel port | Remove it. |
| SEC-02, Node tools | Lock the dependency tree for wrangler only, which is the one that runs with a credential. |
| CI-03, semver on 0.x | Features go to a minor, fixes to a patch, starting now. |
| Three refactors | Do all three: split `cli.py`, split `render.py`, and replace `dict[str, Any]` with a recursive JSON type. |
| HYG-09, AI trailer | Rewrite the three commits and repair every consequence. |
| HYG-04, absolute paths | Generators write repository-relative paths; an existing report is corrected when it is next regenerated. |
| SEC-04, token length log | Unchanged. It is the owner's own decision of 2026-09-08. |

## Phases

| Phase | What it closes | Depends on | Status |
|---|---|---|---|
| [1](phase-1-history.md) | HYG-09, and the largest single item of HYG-01 | none | done 2026-09-11 |
| [2](phase-2-evidence-and-protection.md) | HYG-01 remainder, META-01 | phase 1 | open |
| [3](phase-3-the-two-high-findings.md) | LOGIC-02, LOGIC-17, LOGIC-03, and release 0.3.1 | phase 1 | done 2026-09-12 |
| [4](phase-4-group-b.md) | 18 findings the review grouped as low risk | phase 3 | open |
| [5](phase-5-decided-behaviour.md) | LOGIC-22, LOGIC-21, PERF-01, ARCH-03, SEC-02, CI-03, HYG-04 | phase 3 | open |
| [6](phase-6-structure.md) | The three refactors, CQ-L3-05, TEST-01, CI-05 | phase 4, phase 5 | open |

Phase 1 comes first for two reasons that are not preference. The ruleset of phase 2 blocks
force-push, so a rewrite has to precede it or be undone to run. And the 11.1 MB measurement file
that phase 2 would otherwise only untrack was added in `43d2a04`, after the rewrite point, so one
rewrite can both strip the trailer and drop that blob from history rather than two.

## Acceptance criteria for the whole plan

- `just check` is green at every commit, and CI is green on every push.
- No claim in `docs/claims-register.md` points at a commit that does not exist.
- Every published release still resolves to the tree it was built from.
- No finding is closed by weakening a test or by narrowing what the tool refuses to claim.
- A behaviour change that moves a number already published on the site is measured again, and the
  claims register records the new measurement rather than the old one.
