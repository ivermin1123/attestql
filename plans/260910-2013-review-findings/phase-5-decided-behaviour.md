# Phase 5: the behaviour the owner decided

Closes LOGIC-22, LOGIC-21, PERF-01, ARCH-03, SEC-02, CI-03 and HYG-04. Depends on phase 3.

**LOGIC-22, R-ORD.** ADR-0004 asks for a total deterministic ordering with ties broken by a unique
key; the code assigns R-ORD to any statement with a top-level ORDER BY, and
`docs/audit-command.md` describes the code correctly. The wording of the ADR is corrected to the
rule the code applies, with a paragraph saying what follows from it: a gold whose ordering is not
total can produce NOT_EQUAL with mechanism `order`, and that is a documented non-claim rather than
a defect. No record byte changes.

**PERF-01 and LOGIC-21, two budgets that refuse.** A result wider or longer than the budget makes
that question an ERROR naming the budget it crossed. Nothing is ever cut and no verdict rests on a
search that was abandoned, so ADR-0013's invariant against silent truncation is untouched: there
is no truncation at all, silent or otherwise. The permutation budget makes this tool differ from
the reference evaluator it deliberately imitates on a pathological input, and that difference is
written down where the imitation is claimed.

**ARCH-03, the kernel port.** `QueryExecutor` and `SqlValidator` are not on the audit path, and
`admit()` is called after the statement has run. ADR-0013 retired the product path they belonged
to. They are removed, and the ADR index records that the cluster went with it. Keeping a class
named validator that runs after execution invites a reader to believe in a boundary that is not
there.

**SEC-02, the Node tools.** wrangler runs with a Cloudflare token, so its dependency tree is
locked. markdownlint and cspell run with no credential and read files only, so they stay on npx at
a pinned version.

**CI-03, semver.** The release document states that from 0.3.1 on, a feature goes to a minor and a
fix to a patch, and that 0.2.1 and 0.2.2 carried features under the older practice.

**HYG-04, absolute paths.** The report generators write paths relative to the repository. The
1,001 existing files are not rewritten: a report is evidence of the day it carries, and it is
corrected when it is next regenerated for another purpose.

## Validation

A test for each budget, at the boundary and past it. `just check` green. The removal of the kernel
cluster leaves no import behind, and `tools/check_adr_index.py` stays green.
