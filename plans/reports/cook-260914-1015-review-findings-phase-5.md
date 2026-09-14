# Cook: phase 5, the findings whose behaviour the owner decided

Date 2026-09-14, branch `ivermin1123/review-findings-phase-5` off `main` at `9a545a0`, worktree
`~/orca/workspaces/attestql/review-findings-phase-4`, on Opus. Plan file
`plans/260910-2013-review-findings/phase-5-decided-behaviour.md`, whose seven rows carry the
owner's decisions of 2026-09-10.

Seven findings, seven commits, one per item and in the order the dispatch gave them. Every commit
was made with `just check && git add -A && git commit -F <file>`, chained with `&&`, so no commit
was made over a red gate. Nothing was pushed, no pull request was opened, no GitHub setting was
touched, `tools/site-select/audits.sh` and `release.sh` were never run, wrangler was never run,
nothing was deployed, and nothing under `tools/site/data/` was regenerated.

## The seven commits

### 1. `44eb2d3` docs(adr): R-ORD is the rule the code applies, and what that rule does not claim

LOGIC-22. ADR-0004 asked R-ORD for "a total deterministic ordering with ties broken by a unique
key". `audit/statements.py` assigns R-ORD to any statement with a top-level `ORDER BY`, nothing
measures totality and nothing ever did, and `docs/audit-command.md` has described the code
correctly since publication. The decision paragraph now states the rule the code applies and says,
dated, what it asked for until this date and who that wording was written for: the sixteen
questions of the retired product path, whose ordering keys were chosen with the record in hand.

A paragraph beside it says what the rule does not claim. A gold whose ordering keys do not break
every tie is compared in the order its rows came back, so two statements that agree on the row set
can be NOT_EQUAL with mechanism `order`; `docs/claims-register.md` already says NOT_EQUAL never
means the gold is wrong, and the `arbitrary-cut` probe exists to find that exact shape. The
alternative, measuring totality and giving such a gold an outcome of its own, is named and
rejected: it would have the tool decide on a gold's behalf the thing the tool exists to put in
front of a reader. The Consequences bullet about a total order is kept and dated rather than
deleted.

Files: `docs/adr/0004-replay-equality-r-ord-r-set.md`. No test: the plan asked for none, no record
byte changes, and `tools/check_adr_index.py` stayed green. Gate green.

### 2. `38d3d8f` feat(audit): a result this tool will not hold is an error, and is never cut

PERF-01. Both backends read a whole result into memory. A result the tool will not hold is now
that question's ERROR naming the bound and the count, raised before the rows are held, and nothing
is ever cut: `truncated` stays false because there is no truncation, silent or otherwise, so
ADR-0013's invariant is untouched. `ROW_BUDGET` is a module constant with no flag behind it.

**The measurement behind 200,000.** The 605 evidence records published under `tools/site/data`
were read for their `row_count`: the largest is 15,429, in
`tools/site/data/minidev-pg/gpt-4-turbo/q1088/evidence-second.json`, and the largest the packaged
demo produces is 4. The bound is the first round number past ten times the largest measured
result.

What each engine can promise differs and the document says so. PostgreSQL knows `cursor.rowcount`
before a fetch, so the refusal happens before a row becomes a Python object. SQLite has no count
before reading, so the backend fetches one row past the bound and refuses on what it holds: one
page more than the budget, never the whole result.

Files: `src/attestql/audit/backend.py` (`ROW_BUDGET`,
`refuse_a_result_past_the_row_budget`), `src/attestql/audit/postgres.py`,
`src/attestql/audit/sqlite.py`, `docs/audit-command.md`, and two test files. Four tests, two per
engine, at the boundary and past it; the first that fails is
`test_a_result_past_the_row_budget_is_that_question_s_error_and_is_never_cut`, over a generated
table on SQLite, with `test_a_result_past_the_row_budget_is_refused_before_a_row_becomes_an_object`
the PostgreSQL half on a fake connection. Gate green.

### 3. `39d30b0` feat(audit): a column-order search this tool will not finish is an error

LOGIC-21. `_admitted_column_permutations` searches column orders with no bound, and the search
tree grows as `a(k) = k * a(k-1) + 1`. Past `PERMUTATION_NODE_BUDGET` partial orders the search
raises `ComparisonRefused`, which is that question's ERROR line with step `comparison`, and no
verdict rests on a search that was abandoned.

**The measurement behind 1,000,000.** The 256 comparison pairs on record, 252 published and 4 in
the demo, were instrumented: their results are 1 to 3 columns wide, the most partial orders any
search visits is 4, and the whole tree over the widest of them is 16. Ten times the largest
measured count would be 160, which is too tight to be a bound on a pathological input rather than
on the measured ones, so this default is set by what must still complete: a nine-column result
whose every column holds the same values is 986,410 partial orders and finishes, a ten-column one
is 9,864,101 and does not, and twelve columns is 479,001,600 leaves. The bound sits between the
ninth and the tenth.

This is a deliberate departure from the reference evaluator the tool imitates, and it is written
down in `docs/audit-command.md` where `bird_ex` is described, beside the partial-order bound. The
claims register is the coordinator's and was not touched.

Files: `src/attestql/audit/compare.py` (`PERMUTATION_NODE_BUDGET`, `ComparisonRefused`),
`src/attestql/audit/cli.py`, `docs/audit-command.md`, and two test files. Three tests; the first
that fails is `test_a_search_past_the_node_budget_is_that_question_s_error`. The search's `any()`
short-circuits, so a pair wide enough to exhaust a realistic budget never reaches it; the tests
put the budget on the exact edge of a small search instead, where 4 passes and 3 refuses, and the
docstring says so. `test_a_reading_this_tool_will_not_finish_is_one_question_s_error_line` is the
end-to-end half: `compare_statements` raises `ComparisonRefused` directly and the per-question
handler in the run loop is what turns it into one error line. Gate green.

### 4. `92ca39c` refactor(kernel): the port cluster goes, and a record takes the values it states

ARCH-03. `QueryExecutor`, `SqlValidator` and `ExecutionContext` were not on the audit path, and
`admit()` was called after the statement had already run. `src/attestql/kernel/ports.py` is
deleted, `ExecutionContext` is gone from `kernel/types.py`, and the width proof the `admit()` call
produced (`WIDTH_POLICY_VERSION`, `width_proof`, `_widest`, `_admitted`) is gone from
`audit/compare.py`. `build_evidence_record` takes `executed_sql`, `validator_version` and
`checks_passed` instead of a `ValidatedStatement`, and its parameter check reads the placeholders
of the SQL that ran.

The shared result types stay, because the audit still reaches `ColumnType`, `ExecutionResult`,
`ExecutionLimits` and `BoundParameter`; the plan removes the ports and the ritual, not the types.
An amendment paragraph in the module docstring records that nothing under `src/` now imports
`ValidatedStatement`, `admit`, `ResultWidthProof`, `ProjectedColumnWidth`, `ValidationRejected` or
`KernelVersions`, and that they are left standing on purpose. ADR-0013 point 7 gained one
`Amended 2026-09-14` sentence saying the port protocols went with the context and the call.

Files: `src/attestql/kernel/ports.py` (deleted), `src/attestql/kernel/types.py`,
`src/attestql/evidence/build.py`, `src/attestql/audit/compare.py`,
`docs/adr/0013-audit-text-to-sql-gold-with-typed-replay-evidence.md`, `tests/conftest.py`,
`tests/test_stub_surface.py`, `tests/test_evidence_record_builder.py`. No import is left behind
and pyright strict is green. Gate green.

This commit is where the suite gets smaller; the count is reconciled below.

### 5. `cf53776` ci(site): the deploy's wrangler comes from a locked tree, and the gate's readers stay on npx

SEC-02. `npx --yes wrangler@4.129.0` ran in the step holding `CLOUDFLARE_API_TOKEN`. The pin fixed
the top of the tree and nothing under it: every transitive dependency was resolved from the
registry at deploy time, with no integrity hash and no commit in this repository stating what
would run beside the token. A `package.json` and a `package-lock.json` now hold that one
dependency at the same 4.129.0, resolving 91 packages with an integrity hash each. The workflow
installs them with `npm ci`, which refuses a lockfile that has parted from its manifest, and the
Publish step runs the binary that install produced, named by path. The action pins by commit are
untouched and so is everything the step does with the token itself.

markdownlint and cspell stay on `npx` at the versions the justfile pins, and neither is in
`package.json`. They read files, hold no credential, and run inside `just check` where a maintainer
is already reading the output. `node_modules/` was already ignored and `just check` installs no
Node dependency. `docs/developer-environment.md` gained the policy paragraph, and
`tools/site/README.md` carries the same two commands for the manual preview deploy, so the
documented path and the workflow's path are one.

Files: `.github/workflows/site.yml`, `package.json` (new), `package-lock.json` (new, 1,541 lines),
`docs/developer-environment.md`, `tools/site/README.md`,
`tests/test_the_deploy_runs_the_wrangler_it_locked.py` (new). Four tests, of which three fail
first; `test_the_deploy_installs_the_locked_tree_and_runs_the_binary_it_made` is the one about the
change, and `test_the_deploy_still_pins_every_action_it_uses_by_commit` passed from the start and
is there to keep the SHA pins. wrangler was not run and nothing was deployed. Gate green.

### 6. `ec82122` docs(release): which number a release moves, and the four patch releases that carried a feature

CI-03. The release section said which tags exist, which get a release page and what their notes are
drawn from, and never which number a release moves, so features were published in patch releases
without anything being contradicted. From 0.3.1 on, a release carrying a `feat` commit moves the
minor and a release carrying only fixes, documentation and data moves the patch; the major stays
at 0. Phases 4 and 5 carry `feat` commits, so the next release is 0.4.0, which the section says.

**The measurement, counted with `git log <previous tag>..<tag>` on 2026-09-14.** `v0.1.2` carried
1 `feat` commit, `v0.1.3` carried 7, `v0.2.1` carried 3 and `v0.2.2` carried 1, the one that
shipped `attestql demo`; each is a patch release holding a feature. `v0.2.0` and `v0.3.0` moved the
minor and carried 5 and 15. `v0.3.1` carried none of its 25 commits, so it is already the release
the rule describes, which is why the rule starts there. The published tags are not renamed.

**One departure from the dispatch, deliberate.** The dispatch named 0.2.1 and 0.2.2 as the two that
carried features under the older practice. The same reading of `git log` finds two more, `v0.1.2`
and `v0.1.3`, so the document names four. A document that named half of them would be a second
thing to correct later; the decision itself, the rule and where it starts, is unchanged.

Files: `docs/developer-environment.md`. No test: this states a convention a person applies when
tagging, nothing mechanical reads it, and the gate that could check it is a release that has not
happened. Gate green.

### 7. `c8183ec` fix(reports): a generator states a path relative to the run, not to the machine that ran it

HYG-04. Twenty-three scripts under `plans/reports/` held an absolute path naming this machine: a
home directory, or a per-session scratch directory carrying a session identifier. Sixteen scripts
of the two research directories of 2026-09-04 read their scratch directory from `MEASURE_WORK`
now, the name every later measurement here already uses, with the run's own directory as the
default. Five paths that pointed inside a checkout are derived from the script's own location:
`parse_golds.py` reaches `src/`, `build_overlap.py` its own directory, `build_pairs.py` and
`compare_head.py` the report directory beside them, and `postgast_parse.py`'s usage line names the
checkout. Five generators wrote a path into the document they produce and now state it relative to
the work directory, through one local helper that leaves a path from outside that directory as it
is: the databases directory in the three `bird_ex_official.py`, the gold-set path in
`verify_inputs.py`, and the source of a copy in `prepare_database.py`, whose next line already
wrote its target that way.

`tools/site-select/` needed nothing. The one path it records is already written relative to the
repository (`Classification.relative`), which is why no file under `tools/site/data` holds an
absolute one, as the finding itself measured.

**What was not rewritten.** 999 tracked files still carry the old path: 992 JSON, 6 Markdown and 1
PDF. Nearly all of them are the `backend_identity` of a SQLite run, which is the identity the tool
records for the file it opened and part of the record format, not something a generator writes. A
report is evidence of the day it carries, so these are corrected when they are next regenerated
for another purpose.

Files: 23 scripts, listed in the commit body. No test and no repository check: the guard would be
a new `tools/check_*.py` walking the tree for absolute paths, and the item allowed one only if it
already had a natural home among the three existing checks, none of which is about paths. The
generators changed here cannot be run without the measurement inputs, which are gigabytes and live
outside the repository. Gate green.

## Checks at the branch head

`just check` is green at `c8183ec`: **1,278 passed and 34 skipped**, then 34 in the PostgreSQL
sandbox and 130 in the SQLite sandbox. ruff, pyright strict, the three repository checks,
markdownlint and cspell all pass.

`attestql demo` produces the same run it did on `main`. Compared against a build of `9a545a0` in a
temporary worktree: the printed block is identical line for line, both runs write the same 26
files, `fixture.sqlite` is byte-identical, and of the 24 JSON documents 22 are byte-identical once
the clock, the run id and the hashes over them are set aside. The two that differ are
`fixture.json`, whose per-table content signal carries the file's own change counter, and
`summary.json`, which differs in two elapsed times. No evidence record and no counterexample moved
a byte.

`uv run python tools/site/build.py` builds the 121 published runs into a scratch directory: 2,181
files and 32,670,870 bytes, the same numbers phase 4 measured, inside all three budgets.

`docs/audit-command.md` names both budgets. The row budget has a section of its own stating
200,000, the measured 15,429 and 4 behind it, what each engine can promise and the ERROR it
produces; the node budget is stated where `bird_ex` is described, with 1,000,000, the measured 4
and 16, and the nine-column and ten-column trees that fix it.

## The test count, which is lower than the dispatch asked for

The dispatch asked for a count not lower than 1,284, phase 4's number. The head is **1,278**, six
lower, and every step of it is accounted for:

| Commit | Count | Change |
|---|---|---|
| phase 4 head | 1,284 | |
| `44eb2d3` | 1,284 | documentation only |
| `38d3d8f` | 1,288 | +4, the row budget |
| `39d30b0` | 1,291 | +3, the node budget |
| `92ca39c` | 1,268 | **-23**, the removed port cluster |
| `cf53776` | 1,278 | +10, four tests and the six `test_boundary.py` makes over a new test file |
| `ec82122`, `c8183ec` | 1,278 | no test |

The 23 are the cluster ARCH-03 removed and nothing else, confirmed by diffing
`pytest --collect-only -q` before and after: 6 boundary parametrisations over the deleted
`kernel/ports.py`, 3 port stubs, 11 readings of `ExecutionContext`, the port signature test, the
port registration test, and the comparison of a record's parameters against what the validator
admitted. A test of a class that no longer exists cannot be kept, so the criterion as written
cannot hold beside ARCH-03; the seventeen tests the other commits added are what is left of it.

## Open

- The suite is 1,278 rather than the 1,284 the dispatch named, for the reason above. Nothing was
  deleted that was not about the removed cluster.
- `docs/developer-environment.md` names four patch releases that carried a feature where the
  dispatch named two. The measurement is in the commit body and above.
- HYG-04 closed without a mechanical guard, by the item's own condition. If the coordinator wants
  one, it is a new `tools/check_*.py` walking the tree for an absolute path naming a home or a
  scratch directory, and it would be green today.
- The 999 tracked files holding the old path are untouched by decision, and `backend_identity`
  will keep holding an absolute path: it is the identity of the file the run opened. What keeps a
  published run clean is running the audit from a neutral root, which the site tooling already
  does.
- A hook fired three times during this session on the substring `rt_` inside test file names such
  as `test_report_tokens_meet_contrast.py`, reporting a credential-shaped value. No credential was
  read or printed; the match is on a filename.

Status: DONE
Summary: The seven findings of phase 5 are closed as seven commits in the dispatch's order, each
gate-green through the chained form, with a test that fails first wherever behaviour changed and a
stated reason where none was added.
Concerns: the suite is six tests smaller than the stated acceptance because ARCH-03 removed 23
tests of the cluster it deleted; and SEC-02's lockfile is asserted but never exercised, because
running wrangler or deploying is out of scope for a worker, so the first real proof of `npm ci` in
that workflow is its next run on `main`.
