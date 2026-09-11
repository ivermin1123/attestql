# Red-team review of the web UI plan

Reviewed 2026-09-07 18:06 (Asia/Saigon): `plans/260907-1730-attestql-web-ui/` (plan, design spec,
five phases) and `plans/reports/research-260907-1730-attestql-web-ui-direction.md`. Two passes: the
author's own attack with tool checks against the code and the artifacts, and an independent
reviewer that had not seen the conversation. Findings are ranked; each names its evidence and the
fix applied to the plan.

## A. Findings from the author's checks

### A1. Two of the artifacts are bounded and one is not; the plan treated them alike (major)

Evidence: `src/attestql/evidence/render.py:39` `ROWS_IN_ARTIFACT = 25` and `result_json` writes
`rows[:bound]` with `rows_shown`; `counterexample_json` calls it with that default for both
sides; `row_difference_json` writes `rows_shown_per_side`; `src/attestql/audit/smells.py:85`
`ROWS_IN_EVIDENCE = 10`. But `record_json` (`render.py:179` to `190`) writes the result "in full
rather than bounded: the record holds all of it and the hash below covers all of it".

Why it breaks the plan: the design spec's "full results rendered to 200 rows, the rest in the
JSON" pointed at the counterexample, which holds 25; the rows are in the two evidence records,
every one of them, up to the execution limit of 10,000. Phase 4's size arithmetic ignored the
records; a 10,000-row, 16-column record is megabytes. (The independent reviewer, finding B1,
caught the second half of this; the author's first pass had read the records as bounded too.)

Fix: the page's row tables read the evidence records and say so; the counterexample's 25 rows
per side are the preview the page opens with. No cap of the renderer's own; the page states
`row_count` and, for the counterexample preview, `rows_shown` against it. Phase 4's budgets are
derived from a dry run of the selection script, not written by hand.

### A2. Hash verification needs a loader that does not exist, and does not need a browser (major)

Evidence: `attestql.evidence` has `json_row` (rows to JSON) and no inverse; `result_hash` is
`result_digest` over every row; the record holds every row (A1).

Why it breaks the plan: phase 5 promised browser-side recomputation as a reason to load Pyodide
on published pages. The recomputation is possible for every record, but it is Python work that
`attestql report` can do at render time and print beside the hash, and `record_hash` is
checkable with any JSON tool (sorted keys, the key itself removed). The browser adds nothing to
that except a second place for the same code to run.

Fix: phase 1 gains `attestql.evidence.load` (a record's JSON back to an `ExecutionResult`, with
a round-trip test over both sandboxes that every result re-hashes to its `result_hash`) and a
render-time line on every record, "recomputed from this JSON: match". Phase 5 keeps only the
drop zone for private audits.

### A3. The forbidden-phrase test would fail on the product's own strings (major)

Evidence: `compare.py:167` "does not state which of them is wrong"; `smells.py:904` "it does not
state that the statement is wrong"; `smells.py:146` "a different but equally correct statement
can return other rows and score zero"; the README's principle sentence contains "wrong".

Why it breaks the plan: design spec and phase 1 forbade "wrong", "correct", "score" anywhere on a
page, and the pages render the JSON's `reading` strings verbatim.

Fix: the test runs over template literals only, not over JSON-sourced text, and forbids the
affirmative forms ("is correct", "is wrong", "incorrect", "accuracy", "score:" as a label). The
principle sentence is allowed by name.

### A4. Phase 3 collided with the main session's ownership of the site (blocker until fixed)

Evidence: message from the main session 2026-09-07 18:05: attestql.com is live on Pages project
`attestql`, deployed by hand with `npx wrangler@4.129.0 pages deploy <repo>/site --project-name
attestql --branch main` from outside the repository; `site/index.html` and `README.md` are being
changed there (an `attestql demo` opening); experiments go to a separate project such as
`attestql-ui`; the domain is not to be moved without the owner.

Why it breaks the plan: phase 3 put the build under `site/`, generated the landing from the
README, and wrote a workflow deploying to the live project on every push to `main`.

Fix: build tooling and data move to `tools/site/`, output to the gitignored `build/site/`;
`site/index.html` and `README.md` are not touched; the built site deploys to `attestql-ui`
with the documented command; switching attestql.com to it is an owner decision recorded as a
step the owner performs. The workflow is deferred until that switch.

### A5. Nine prediction files are nine runs, and the page map had one (major)

Evidence: `_write_question` writes one second statement per question per run; the measurement
ran the nine files as nine audits.

Fix: page map gains a benchmark level: `/runs/<benchmark>/<run>/` where a run is one CLI run;
the benchmark page lists its runs and sums nothing that the runs' own summaries do not state.

### A6. The hand classification join was under-specified (minor)

Evidence: `prediction-mode-260904-real-predictions/classification.json` holds
`per_file[<prediction file>].rows[]` with `question_id`, `class`, `mechanism`, `reason`;
`bird-dev-sqlite-260907/classification.json` holds `rows[]` with `question_id`, `db`, `probes`,
`class`, `why`, and `counts`.

Fix: phase 4 names those paths as the join keys; the site shows `class` and the reason verbatim
under "read by hand" with the file's date.

### A7. A "trimmed copy" of a record would have served altered evidence (blocker, removed)

Evidence: phase 4's size lever proposed trimming `result.rows` in copies "marked as trimmed". The
record's `record_hash` covers its content; a trimmed copy is not the record.

Fix: the lever is gone. With bounded artifacts it is not needed; if a run is still too large,
whole questions are left out of the site and the full audit is published as a release asset.

### A8. ERROR questions have no directory (holds)

Evidence: `cli.py:1071` to `1083`: a `SideFailed` appends to `counted.errors`, counts the
verdict and prints the line; `_write_question` is not reached. The plan's treatment (listed on
the run page from the summary, no page) is right.

### A9. Contrast holds

Computed for every named pair in both themes: lowest is `--warn` on `--second-tint` in light at
5.43:1; everything else between 5.7:1 and 16.4:1. Nothing under 4.5:1.

## B. Findings from the independent reviewer

The reviewer read the plan, the code and the artifacts without the conversation. Its report
found the same A3, A5, A6 and A7 with more evidence, corrected A1 and A2 as recorded above, and
added the following. Disposition: accepted and applied unless marked.

### B1. Cloudflare Pages Free plan holds 20,000 files per site; the page map overshot it (blocker)

Evidence: Pages limits page (updated 2026-09-05), 20,000 files on Free, 100,000 on paid. The
plan gave a page to every NOT_EQUAL question, and NOT_EQUAL includes every prediction the
benchmark scores 0: about 1,680 directories per gold copy on PostgreSQL and 2,088 on SQLite
(the measurement reports' "all nine" rows), five files each, before the gold-only runs.

Fix: pages only for the questions the site is about: `credited_but_not_equal` rows of each
prediction run, fired-probe golds, the hand-classified rows, and the unjust-zero and unjust-one
cases; a few hundred directories. Full runs are published as release assets the run page links
to. The plan tier is read in the dashboard and written into phase 3; the file count and size
budgets are re-derived from a dry run of the selection script before any number is written.

### B2. Live collision with the main session's `attestql demo` refactor (major, now landed)

Evidence: at review time the main checkout held the uncommitted move of
`tools/audit-sandbox-sqlite/{fixture.sql,predictions.json,questions.json}` into
`src/attestql/demo/`, a `demo` subcommand parser in `cli.py`, `pyproject.toml` package data,
`NOTICE`,
`tests/test_boundary.py`. It landed as `3a1287f` at about 18:15. The plan named the old path in
phases 1 to 3, wired `report` into the same parser, and listed none of these files as contested.
Also stale: "PyPI pending" (0.2.1 is published, `53bddf7`) and "nine commits not yet pushed"
(`origin/main` was at `74e0d27`).

Fix: the worktree is fast-forwarded to `3a1287f`; phase 1 starts from there; the fixture comes
from `attestql.demo` and the landing block from `attestql demo --out`; the collision list names
`cli.py`, `pyproject.toml`, `NOTICE`, `tests/test_boundary.py`, `tools/audit-sandbox-sqlite/`;
the PyPI non-goal is gone.

### B3. Pyodide: the wheel's dependencies and the time zone database (major)

Evidence: the wheel's `Requires-Dist` names `psycopg[binary]`, `postgast` (C, no wasm wheel) and
`sqlglot` (not in Pyodide's lock, so a plain install would reach PyPI); `serialize.py` calls
`ZoneInfo` for `ts` cells and Pyodide ships no IANA database and no `tzdata`; neither sandbox
fixture has a timestamp column, so the planned test would pass while Mini-Dev pages with
timestamps fail.

Fix: the wheel installed with Pyodide's package installer with dependency resolution off, the
`tzdata` wheel bundled and installed first, a
timestamp column in the stress fixture. Written into phase 5.

### B4. "Filters are links with query parameters, so the page works with no JavaScript" (major)

Evidence: a static host ignores the query string. Fix: filter views are pre-rendered under
paths (`/runs/<benchmark>/<run>/not-equal/`, `/by-mechanism/type/`, `/by-probe/<name>/`), few
values each; no query-string filtering.

### B5. States the table lacked (minor, applied)

NOT_COMPARABLE writes a directory within one run when preconditions differ between the two
records (`verdict.mismatched`); a statement refused before execution (`step` "statement") is an
ERROR that ran nothing and the page says so; `projection_names_differ` carries a reading that
the names did not decide the verdict and must be shown beside the two column lists;
`question_set.duplicate_ids`, `predictions.positions_unused` and `fixture.refused` are run-page
rows. The timed-out copy source was wrong: it is `result.statement_timeout_ms` on the record of
the side that ran, and the summary's `settings.statement_timeout_seconds` and `timed_out` for
the side that did not.

### B6. Smaller items (applied)

- `--out` default `<audit-dir>/report/` would survive the audit's own rerun cleanup and sit
  stale beside a fresh run; the default is a sibling `<audit-dir>-report/`.
- `tests/test_boundary.py` forbids `importlib` beyond `importlib.metadata`; templates and static
  files are located with `Path(__file__)`.
- The method page needs public accessors for the probe meanings (`_MEANS` is private in
  `smells.py`) and the seven preconditions (in `postgres.py`); phase 1 adds them.
- The light tints were 1.04:1 and 1.09:1 against the paper, imperceptible, which is decoration;
  deepened in the spec with every text pair recomputed above 4.5:1. `--rule` at 1.37:1 is fine
  for table lines and not as a chip's only edge; chips get a fill.
- The print stylesheet disables the entrance animation; the mechanism chip is a button, not a
  focusable span.
- The landing's demo block carries a `run_id` and a time that differ per build; accepted and
  stated on the page as the build's own run.
- A workflow step for Node was missing; moot while the workflow is deferred.

### Rejected or deferred

- None rejected. The reviewer's suggestion to host records in an R2 bucket is deferred: release
  assets on GitHub need no new account surface and serve the same purpose for now.

## What holds after both passes

Format strings; the four-file directory layout for comparison and gold-only questions; ERROR
questions without a directory; `summary.json` carrying every key the run page needs; the
standard-library-only import boundary of `attestql.evidence`, `kernel` and `contract`; Pyodide
314.0.6 with Jinja2 and MarkupSafe in its lock; the 25 MiB per-file limit; every text colour
pair above 4.5:1 in both themes; `record_hash` verifiable from the JSON alone.

## Unresolved questions

- The Pages plan tier of the personal account (Free or paid) sets the file budget; read it in
  the dashboard before phase 3.
- Whether the owner accepts phase 5 as a drop zone only, now that hash verification lives in
  phase 1.
