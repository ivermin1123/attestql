# Cook: phase 4, the findings the review grouped as low risk

Date 2026-09-14, branch `ivermin1123/review-findings-phase-4`, worktree
`~/orca/workspaces/attestql/review-findings-phase-4`, on Opus. Plan file
`plans/260910-2013-review-findings/phase-4-group-b.md`. The execution detail is the group B table
of `plans/reports/review-260908-2321-seven-lane-independent-review.md`, which is in Vietnamese and
whose line numbers have drifted from `a06a5ba`; every finding was located by its description.

Eighteen findings, eleven commits, one per row of the plan's table and in the plan's order. Every
commit was made with `just check && git add -A && git commit -F <file>`, chained with `&&`, so no
commit was made over a red gate. Nothing was pushed, no pull request was opened, no GitHub setting
was touched, `tools/site-select/release.sh` and `tools/site-select/audits.sh` were never run, and
nothing under `tools/site/data/` was regenerated.

## The eleven commits

### 1. `c070764` fix(site-select): a rerun that failed is not a stage that finished

LOGIC-10, LOGIC-11. `tools/site-select/audits.sh` counted a failed rerun and went on to print
`SQLITE_DONE` and exit 0. `rerun_timeouts` now keeps a failure count, names the log of the rerun
that failed, and returns non-zero; the dispatcher carries that status to the exit status.

LOGIC-11 and the first half of LOGIC-10 were already closed on `main` by `fb9a8da`, which is why
this commit is only about the reruns. Files: `tools/site-select/audits.sh`,
`tests/test_maintainer_scripts_refuse_and_report.py` (new), `tests/test_boundary.py`. The new file
is the only test file besides the console-script test that may start a process, and the boundary
test was widened to exactly those two paths after the coordinator approved it; it also gained
`test_nothing_under_src_starts_a_process`, which nothing enforced before.

Test that fails first: `test_a_rerun_that_failed_is_reported_rather_than_counted_as_done`, with
three more beside it. Gate green.

### 2. `f9185d0` fix(report): a report states no total it cannot show

LOGIC-06, LOGIC-07. The renderer refuses a gap between the count a summary states and the question
directories beside it, unless the directory holds a `published.json`, which is what says the
directory is a selection of a run rather than the whole of it. A rerun clears
`classification.json` and `classification-source.json` from the output it is about to rewrite, so
a second render cannot carry a reading from the first.

All 121 published runs are selections, so a refusal with no exception for them would have stopped
the site build outright; the exception is the marker file and not a flag. Files:
`src/attestql/report/render.py`, `tests/test_report_renders_an_audit_directory.py`,
`tests/test_site_builds_from_the_sandbox.py`.

Test that fails first:
`test_a_directory_holding_fewer_questions_than_its_summary_counts_is_refused`. Gate green.

### 3. `07a2101` fix(audit): a question file is read at the types it states, and a bad one exits 2

LOGIC-12, LOGIC-13, LOGIC-14. A field at the wrong type is refused by name instead of coerced, an
absent field says which one it is, a question id below zero or too long to be a directory name is
refused before the run rather than after a directory a rerun cannot clear has been made, and a
write that fails mid run is a tool error with exit 2 rather than a traceback with exit 1.

Files: `src/attestql/audit/cli.py`, `docs/audit-command.md`,
`tests/test_audit_command_runs_over_a_question_file.py`. Test that fails first:
`test_a_field_at_the_wrong_type_is_refused_rather_than_converted`, with six more. Gate green.

### 4. `ca2076e` fix(audit): a prediction whose id no question has stops the run

LOGIC-08. A prediction file naming an id the question file does not hold is refused with exit 2,
naming up to twenty of them and saying how many more there are. An id the `--ids` filter left out
is not an unknown id, and position keying still accounts for what it left over.

Refusing rather than reporting was checked against the two runs that must not redden: the demo's
prediction ids all exist, and all 121 published runs were made with
`--predictions-keyed-by position`. Files: `src/attestql/audit/cli.py`, `docs/audit-command.md`,
`tests/test_audit_command_runs_over_a_question_file.py`. Test that fails first:
`test_a_prediction_naming_no_question_of_the_file_is_refused`. Gate green.

### 5. `2077a87` fix(audit): six places that stated a measurement nobody took

LOGIC-05, LOGIC-15, LOGIC-16, LOGIC-18, LOGIC-19, LOGIC-20. Shuffle coverage is reported as what
the shuffle actually reached, the fixture digest records the value just measured rather than the
one the cache held, records and summaries are written into place atomically, only SQLite's own
"no such column: rowid" answer is read as a relation without a row identity, the plan control the
shuffle probe turns off is recorded and given back, and an output directory reached through a
symlink is refused by its resolved path.

`automatic_index` becoming the tenth recorded pragma contradicted one sentence of
`docs/adr/0014-sqlite-backend-behind-the-same-evidence-record.md`; the coordinator lifted that
constraint for exactly one amending sentence, which is what the ADR now carries. An existing test
encoded the LOGIC-05 defect, asserting `applicable=True` for a statement no shuffled copy reached;
it is corrected, with a docstring saying what changed and why.

Files: `src/attestql/audit/fixture.py`, `src/attestql/audit/smells.py`,
`src/attestql/audit/sqlite.py`, `src/attestql/evidence/render.py`, `tools/audit-sandbox/run.sh`,
`tools/site-select/notes.py`, `docs/adr/0014-...md`, and six test files. Test that fails first:
`test_the_session_states_the_ten_readings_and_none_of_the_seven_preconditions`, with fifteen more.
Gate green.

### 6. `157c8a5` fix(audit): the envelope pins the schema the statement resolves against

LOGIC-04. Every statement runs inside `SET LOCAL search_path = public`, the session is read back
and refused if it did not hold it, and the value in force is recorded beside the other settings.
This moves the bytes of every PostgreSQL record, so `tools/site-select/notes.py` states it in the
release notes under the heading for record bytes.

The read back value is the server's own spelling, `public` and not `"public"`, which a first pass
had wrong and the sandbox test caught. Files: `src/attestql/audit/postgres.py`,
`docs/audit-command.md`, `tools/site-select/notes.py`,
`tests/test_audit_executor_refuses_a_session_that_drifted.py`. Test that fails first:
`test_the_envelope_pins_the_schema_an_unqualified_name_resolves_against`. Gate green.

### 7. `62c4c81` fix(audit): four corrections, none of which changes what a run concludes

CQ-L1-01, ARCH-01, ARCH-02, CQ-L3-02. A DSN whose database name contains the word password is
accepted while one naming the keyword is still refused however it is written; both backends gained
`close` and the command gives the backend back whether the run succeeded or failed; every
registered engine is asserted to parse with the parser it states; and the three readers of a whole
count became one, `src/attestql/contract/counts.py`, used by the build, the selector and the
renderer.

Files: `src/attestql/audit/backend.py`, `cli.py`, `engines.py`, `postgres.py`, `sqlite.py`,
`src/attestql/contract/counts.py` (new), `src/attestql/report/render.py`,
`tools/site-select/select_questions.py`, `tools/site/build.py`, and five test files. Test that
fails first: `test_a_dsn_carrying_the_word_but_naming_no_password_is_accepted`, with six more. Gate
green.

### 8. `8b62611` feat(audit): the summary line counts the fifth class it was already documented to

FEAT-04. The summary line prints the `other` mechanism class beside the four it printed. The README
quotes the demo's output verbatim, so line 32 of `README.md` changed with it and was checked byte
for byte against a fresh `attestql demo --out demo`.

Files: `README.md`, `src/attestql/audit/cli.py`, and four test files. Test that fails first:
`test_the_summary_line_counts_a_credited_disagreement_that_is_none_of_the_four_classes`. Gate
green.

### 9. `83f7ad1` feat(site): the pages a reader meets, and what a search engine is told about them

UI-01 to UI-06. Every page states a description and a canonical address and carries an icon; the
build writes `robots.txt`, `sitemap.xml`, a `404.html` written from its own template, and the
icon; every page title is distinguishable, which took naming a run by its group or benchmark and
its own name rather than by the benchmark alone; a record on a question page shows a bounded
reading of its result and links the whole of it; a run page has a way back up where the publisher
gave one; a report holding no question says so instead of rendering an empty table; and the one
chip that does something states `aria-pressed` and is hidden where there is no script to make it
do anything.

Bounding a result to fifty rows took the built site from 40.7 MB to 32.7 MB and the heaviest page
from 1,806 KB to 148 KB, both inside the existing budgets rather than by moving them. The built
site carries 653 pages with 653 distinct titles.

Files: `src/attestql/report/render.py`, `report.css`, five report templates,
`tools/site/build.py`, `tools/site/templates/not-found.html` (new), and two test files. Test that
fails first: `test_a_page_states_what_it_is_and_a_local_report_states_no_address`, with eleven
more. Gate green.

### 10. `27838d7` perf(audit): one reading of a result, and one reading of the role

PERF-02, PERF-03. A digest is the sha256 of a result's canonical rendering, so taking one costs a
rendering of every row. Writing a comparison rendered each result three times over, once for the
bounded view in the counterexample, once for the pair of hashes beside it and once for the record
on disk, all to arrive at the one string the comparison was already holding; the rendering is taken
once now and the string passed on. Two smells that state a digest beside a bounded view of the same
result did the same twice and now read it once. The database role is read once for a connection and
repeated after that, as the server identity and the session settings already were.

The renderings a verdict takes are not shared. R-ORD compares each result rendered with its columns
named by position, which is a different rendering from the one a digest covers, so it stays where it
is; sharing it would change what R-ORD means.

Files: `src/attestql/audit/compare.py`, `postgres.py`, `smells.py`,
`src/attestql/evidence/render.py`, and two test files. Test that fails first:
`test_writing_a_comparison_states_the_digests_it_took_and_renders_no_result_again`, beside
`test_the_database_role_is_read_once_and_repeated_after_that`. Gate green.

### 11. `9f5e7c5` chore(site): one landing page, and it is the one the build writes

HYG-03. The three links move into the landing template, the build stops reading
`site/index.html`, and that page is deleted. In that order: the build refused to run with the page
missing.

Gone with the page: `LIVE_PAGE`, `live_links`, the `_Links` parser of its navigation, the `links`
field of `Landing`, and the refusal about an `--out` inside a directory the repository no longer
has. What a page states is now read out of `tools/site/`, `README.md`, `pyproject.toml` and the
JSON of the runs and out of nothing else. The hand written page had already drifted: its copy of
the demo output was the one without `other`.

Two sentences outside the allowed list described the deleted page and were corrected with it after
the coordinator approved exactly that: the last sentence of `tools/site/README.md` and the list of
sources in `docs/developer-environment.md`. `tools/check_doc_links.py` is green, and
`.github/workflows/site.yml` names no path under `site/`, so the deletion reaches no workflow.

Files: `tools/site/build.py`, `tools/site/templates/landing.html`, `site/index.html` (deleted),
`tools/site/README.md`, `docs/developer-environment.md`,
`tests/test_site_builds_from_the_sandbox.py`. Test that fails first:
`test_the_repository_holds_one_landing_page_and_the_build_reads_no_second_one`. Gate green, and
confirmed again at the branch head because one docstring line was edited while that gate was
already running.

## What was found while doing it

- LOGIC-11 and the first half of LOGIC-10 were already closed on `main` by `fb9a8da`. The finding
  that remained was the reruns, which is what commit 1 is about.
- LOGIC-06 as written would have refused every published run: all 121 of them are selections, with
  far fewer question directories than the summary counts. `published.json` is what says a
  directory is a selection, so it is the marker the refusal excepts.
- Three tests written first did not discriminate. The LOGIC-18 one passed because `row_counts`
  raised before the code under test was reached, so it now calls `_has_a_row_identity` directly;
  two write tests passed because the encode never failed, so they use a lone surrogate that fails
  the encode after the file has been truncated.
- The first UI-02 attempt, naming a run by its benchmark and its group, still left five way
  duplicate titles on `minidev-pg`. Naming it by its group or benchmark and its own name reaches
  653 distinct titles over 653 pages.

## Left open, deliberately

- `tools/site/data/` was not regenerated, as instructed. The 121 published runs therefore hold
  records written before LOGIC-04 and LOGIC-19, so their session settings differ from what the tool
  records today by exactly the bytes the release notes describe. Refreshing them is a release
  step, not this phase's.
- PERF-02 is closed for the digest and not for the verdict. Under R-ORD each result is still
  rendered once by position to decide the verdict, which is a different rendering from the one the
  digest covers and cannot be shared without changing the rule.
- `tools/site-select/release.sh` and `audits.sh` were not run, so commit 1 is covered by its own
  tests and by nothing else. The shell is exercised through
  `tests/test_maintainer_scripts_refuse_and_report.py` with `docker` and `lsof` shims on `PATH`.
- Nothing was refactored beyond a finding. Phase 6 owns the refactors.

## Checks at the branch head

`just check` green, exit 0: ruff, ruff format, pyright strict, the three repository checks,
markdownlint, cspell, then 1,273 passed and 34 skipped, then 34 passed in the PostgreSQL sandbox
on port 5497, then 125 passed in the SQLite sandbox.
`uv run python tools/site/build.py` builds 2,181 files and 32,678,701 bytes, inside all three
budgets. Line 32 of `README.md` is byte for byte the summary line `attestql demo` prints; the
other lines of that block name the output directory, so they are the ones a run made with
`--out demo` from the repository root prints. `docs/audit-command.md` describes the refusals
commits 3, 4 and 6 added.

## Merge-gate fixes

Two coordinator-side reviewers read the twelve commits above and returned MERGE AFTER FIXES.
Three more commits, on top and never rewriting what is under them, each gate-green through the
chained form and each with a test that fails before it.

### 12. `a53847f` fix(report): a report is reconciled with what the run says it wrote

The blocking one, and the reviewer was right: LOGIC-06 as I closed it was built on a false
premise. The check read the number of questions audited as the number of question directories to
expect, and it is not one. A question that agreed and fired no probe writes no directory, so every
healthy run holding such a question was refused. Reproduced before anything was changed: `attestql
demo --out D`, then an audit of `--ids 1029` alone, which is one gold, no prediction, no probe and
exit 0, and then `attestql report` on it, which exited 2. The other half of the same mistake was
the exception for a selection, which made the check silent for exactly the case it was written
for, a published run that had lost `q879`.

The run now says what it wrote. `summary.json` holds `question_directories`, the ids whose
`q<id>/` the run wrote in the order asked, under the rule the run applies: a directory exists when
the question disagreed, a NOT_EQUAL or a NOT_COMPARABLE, or when a probe fired over it. An empty
list is a run that wrote none and is not a run that says nothing. The renderer reconciles the
directories it finds against that list: a whole run must hold exactly them and is refused naming
the ids either way, a selection may hold some of them and is refused for one the list does not
name, and an errored question writes none and is a row from the summary rather than a gap. A
summary written before the key is not refused, because every published run and every directory an
earlier release left on a reader's disk is one; those are held only to the bounds their counts
fix.

Files: `src/attestql/audit/cli.py`, `src/attestql/report/render.py`,
`src/attestql/report/templates/run.html`, `docs/audit-command.md`,
`tests/test_report_renders_an_audit_directory.py`. Seven tests, of which the first that fails is
`test_a_healthy_run_whose_only_question_agreed_and_fired_no_probe_renders`, the reproduction
itself. Gate green.

### 13. `1955fb3` docs(audit): three sentences the code had moved past, and one the code now meets

The module docstring of `src/attestql/audit/cli.py` said nothing aborts a run after it started;
one thing does since a write that fails mid run became a tool error, and it now says which. The
SQLite backend and `SessionSettings` both said nine settings a file can be asked for; there are
ten. The fourth was made true rather than corrected: the bound on a question id says an id outside
it is refused before the backend opens, and it was not, because the run read the file and the run
was handed a backend. `connect_and_audit` reads the question file before it connects, which is the
preferred fix the review named; the read needs no backend and carries nothing past that line.

Files: `src/attestql/audit/cli.py`, `src/attestql/audit/sqlite.py`,
`src/attestql/evidence/types.py`, and three test files. Tests that fail first:
`test_a_question_file_no_run_could_use_is_refused_before_a_database_is_opened` and
`test_the_two_sentences_that_count_the_readings_count_the_ones_there_are`. One existing test
changed with the behaviour: the one that proved the backend is given back after a failed run used
a missing question file to fail, which no longer reaches a backend, so it fails on the output
directory instead, and a second test states that a question file this run cannot use takes no
backend at all. Gate green.

### 14. `d5e8b11` fix(site): seven small things, one of which a killed process could leave behind

`FilterPage` takes the `within` context the run and question pages take, and its title leads with
the restriction as a question page leads with its question: over the 653 pages of the site that
takes the titles past 60 characters from 173 to 46 and the longest from 89 to 73, with all 653
still distinct. A rerun of an audit directory now removes a `.<name>.<rand>.partial` a killed
process left, which it used to leave beside the fresh run. The SQLite `query_only` envelope goes
back on whatever stopped the copies, rather than on the line after a loop anything could be raised
out of. `SEARCH_PATH` is built from `DEFAULT_SCHEMA` instead of spelling `public` again.
`tools/site/README.md` no longer documents the refusal about an `--out` inside a directory the
repository does not have, and its template list names `not-found.html`. The release note about
`search_path` says the key moves as well as the value. The symlink guard test makes everything it
makes under `tmp_path` instead of creating and removing a directory under the repository's own
`build/`.

Files: `src/attestql/report/render.py`, `src/attestql/audit/cli.py`,
`src/attestql/audit/postgres.py`, `src/attestql/audit/sqlite.py`,
`src/attestql/evidence/render.py`, `tools/site-select/notes.py`, `tools/site/README.md`, and five
test files. Four tests that fail first, of which
`test_the_envelope_goes_back_on_when_the_copies_could_not_be_made` is the one about behaviour
nothing else covered. Gate green.

### Checks after the merge-gate fixes

The reproduction renders: the one-question gold-only audit exits 0 and `attestql report` on it
exits 0, writing one page and no questions. `just check` green at the branch head: 1,284 passed
and 34 skipped, then 34 in the PostgreSQL sandbox and 130 in the SQLite sandbox.
`uv run python tools/site/build.py` builds the 121 published runs into a scratch directory, 2,181
files and 32,670,870 bytes, inside all three budgets. `docs/audit-command.md` states
`question_directories` with its writing rule, states every refusal the report command can exit 2
on, and names the two classification files a report rerun removes.

### Named in the review and deliberately not done

The review listed four as not now, and none was done: the DSN keyword parser accepts
`host=h;password=x` and options strings carrying a password; a re-raise path catches `OSError`
only; `contract/counts.py` shares message templates across its callers; and the `Backend` and
`Connection` protocols each gained a method. They are refactors, and phase 6 owns the refactors.

Status: DONE
Summary: The eighteen findings of phase 4 are closed as the eleven commits the plan names, in its
order, and the two reviewers' blocking findings and small pass are closed as three commits on top,
each with a test that fails before it and a green `just check` chained in front of it.
Concerns: the published runs under `tools/site/data/` still hold records written before the
`search_path` and `automatic_index` changes, and they state no `question_directories`, so the
renderer holds them only to the bounds their counts fix until a release regenerates them; and
`tools/site-select/audits.sh` is covered by its new tests alone, because running it is out of
scope for a worker.
