# Phase 6: the three refactors

Closes CQ-L2-01, CQ-L3-01, CQ-L2-03 and CQ-L3-05, and unblocks TEST-01 and CI-05. Depends on
phases 4 and 5, because refactoring a module while findings are still open in it doubles the work.

The owner chose all three refactors on 2026-09-10. They fix no defect that is open today, which is
why they come last, and the point of doing them at all is that the repository is public and two
modules near 2,000 lines are where a contributor gives up.

| Step | What |
|---|---|
| 1 | Rename `tools/site-select/select.py`, which shadows the standard library's `select`, and update the three call sites. This is CQ-L3-05 and it unblocks TEST-01. |
| 2 | TEST-01: direct tests for the three scripts under `tools/site-select`, which the data test currently refuses to import for the shadowing reason step 1 removes. |
| 3 | CQ-L2-03: a recursive JSON type replacing `dict[str, Any]`, narrowed by helpers at the boundary rather than by 31 casts after the fact. The review names this as where several loader defects got through, so it is the one refactor with a defect record behind it and it goes first of the three. |
| 4 | CQ-L2-01: split `cli.py` along the boundaries it already has, into parser, inputs, run and summary, with `main` left as the facade. |
| 5 | CQ-L3-01: the same for `render.py`, with `render_report` left as the public facade. |
| 6 | CI-05: a matrix branch that runs `uv build` and installs the wheel, so the packaging the release depends on is exercised before a tag. |

## Validation

No public signature changes: `attestql` the command, `render_report`, and the package's exported
names are the same before and after. `just check` green at each step, and the test count does not
fall.
