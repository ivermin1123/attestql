# Merge gate for phase 5 of the review-findings plan

Reviewed 2026-09-14 from 10:40, branch `ivermin1123/review-findings-phase-5` at `cd06ca4` over
`main` at `9a545a0`, eight commits, 48 files, 2,656 lines added and 456 removed. The branch is the
work of `plans/reports/cook-260914-1015-review-findings-phase-5.md`. One independent reviewer read
the code half (the two budgets, the kernel removal, the ADR-0004 wording); the coordinator read the
rest (the wrangler lock, the semver statement, the relative-path generators) and ran `just check`
on the branch head: 1,278 passed and 34 skipped, then 34 in the PostgreSQL sandbox and 130 in the
SQLite sandbox, exit 0. The suite is six tests smaller than at the phase 4 merge because the kernel
cluster's tests went with the cluster and seventeen were added.

Verdict: **merge after fixes**. The fixes were dispatched to the same worker and landed as four
commits on the same branch: `b5d3050` (the budget counts rows compared, default 20,000,000, from a
measured 1,944,582 rows per second at the slowest of four shapes times ten seconds), `8cdd4f7`
(the SQLite content digest reads a page at a time and a table past the row budget is a tool
error before the run), `f287657` (the five small items and the Dependabot `npm` block) and
`9e36ac7` (the report, with the corrected counts: the kernel removal dropped 17 tests and 6
boundary parametrisations, and the widest published search spends 4 units over 3 columns and
1,664 rows). The coordinator read the four diffs and ran `just check` on the fixed head
`9e36ac7`: 1,283 passed and 34 skipped, then 34 in the PostgreSQL sandbox and 130 in the SQLite
sandbox, exit 0. The branch merged into `main` as `bbbe9fa` on 2026-09-14; its tree is the
branch head's, so that gate is the merge's.

## What blocked the merge

**The node budget bounded nodes, not the work.** The column permutation search now stops past a
number of partial orders visited, but the check at every leaf rebuilds the whole second result, so
the cost of a search that stays inside the budget grows with the rows compared: measured on this
machine, eight columns whose every column holds the same values against 500 rows took 9.8 seconds
for 109,601 nodes, and the same shape at the row budget of 200,000 rows would run for hours with no
error fired and no clock covering it. The decision: the budget counts the rows compared across the
search rather than the nodes, and its default is set from the measured rate so that the worst
search inside it finishes in the order of ten seconds on this machine, stated as a measurement and
never as a wall-clock guarantee.

**One unbounded read survived PERF-01.** The SQLite content digest, reached with
`--fixture-digest full`, still read a whole table through `fetchall` with no bound, on the engine
BIRD dev ships as files. The row budget applies there too: a table longer than it makes the fixture
digest a tool error before the run, naming the table and saying the default digest needs no such
read. PostgreSQL digests on the server and was never exposed.

**Three measured claims did not survive re-measurement.** The kernel removal's commit body says
the suite lost 23 tests; the reviewer counts 17 collected cases. The budget documentation says the
widest published search visits 4 partial orders over a tree of 16; the reviewer's instrumentation
of the same 252 pairs found 2 nodes and a widest paired result of 3 columns. Both are corrected or
re-measured with the real code before the numbers stand in a document.

## Carried into the same fix pass

A stray string after a method definition in the PostgreSQL backend; ADR-0014 still naming the
deleted `kernel/ports.py` among what stays; a test still named for the kernel ports; one sentence
saying the shuffle and plan-variant executions share the row budget, which they do; an unhandled
`ComparisonRefused` in the stress tool; and an `npm` block in the Dependabot configuration so the
wrangler lock is bumped like the other two ecosystems.

## For the owner

A refused test-suite reading voids a verdict the tool had already computed under R-ORD or R-SET:
the comparison runs first and the permutation search is BIRD's secondary reading, so a budget hit
there discards an EQUAL or NOT_EQUAL that did not rest on the abandoned search. That is the
recorded decision of 2026-09-10 (the question is an ERROR) and the branch keeps it; whether the
verdict should instead stand with the secondary reading marked as refused is a question about the
counterexample record's shape and is the owner's to answer.

## What was verified clean

The boundary tests sit at the boundary on all three budgets; `truncated` is false on every path
and no partial record or directory is written on a refusal; the exit status is unmoved by an error
except for the pre-existing rule that a run with nothing answered exits 2; the 200,000-row default
reproduces exactly (605 published records, the largest 15,429 rows); the demo reaches neither
budget; `bird_ex` is untouched; the kernel removal leaves no live import and changes no record
field; the ADR-0004 paragraph matches the code in both statement readers and the reference document
agrees; the deploy workflow installs the locked tree with `npm ci` and runs the binary by path, the
action pins by commit stand, and the two file readers stay on `npx` at the justfile's versions; the
semver statement is backed by a count over `git log` per tag; 23 generator scripts read their work
directory from the environment and no report or data file was rewritten; ruff, pyright strict, the
three repository checks, cspell and markdownlint clean; no forbidden typography; no AI mention in
any commit message.
