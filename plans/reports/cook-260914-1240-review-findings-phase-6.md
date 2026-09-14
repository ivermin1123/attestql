# Cook: phase 6, the three refactors and the packaging check

Date 2026-09-14, branch `ivermin1123/review-findings-phase-6` off `main` at `3300fbb`, worktree
`~/orca/workspaces/attestql/review-findings-phase-4`, on Opus. Plan file
`plans/260910-2013-review-findings/phase-6-structure.md`, whose six rows close CQ-L3-05, TEST-01,
CQ-L2-03, CQ-L2-01, CQ-L3-01 and CI-05.

Six steps. Step 1 was already closed on main and is skipped, with the evidence below; the other
five are one commit each, and a sixth commit repairs the documentation pointers the two splits
broke. Every commit was made with `just check && git commit`, chained with `&&`, so no commit was
made over a red gate. Nothing was pushed, no pull request was opened, no GitHub setting was
touched, `tools/site-select/audits.sh` and `release.sh` were never run, wrangler was never run,
and nothing under `tools/site/data/` was regenerated.

## Step 1, CQ-L3-05, already closed on main and skipped

The finding asked for `tools/site-select/select.py` to be renamed, because a module named `select`
on `pythonpath` shadows the standard library's. The rename is already on main: the directory holds
`select_questions.py`, `manifest.py`, `notes.py`, `question_ids.py`, `audits.sh` and `release.sh`,
and no `select.py`. Nothing under `src/`, `tests/`, `tools/`, `docs/`, `justfile` or
`pyproject.toml` names the old module.

Every surviving mention is in `plans/`: the phase 4 plan and its report, the review that raised the
finding, the measurement of the publish run, the journal of 2026-09-08, and this phase's own plan
file. Those are dated records of what was true on their day and are not rewritten, which is the
same rule phase 5 applied to the 23 report scripts. No commit was made for this step.

## The six commits

### 1. `06e742f` test(site-select): the scripts that decide what the site publishes are tested directly

TEST-01. The maintainer scripts under `tools/site-select` decide what reaches attestql.com and
what a release archive holds. At `3300fbb` four test files imported one of them,
`test_selection_empties_only_its_own_directory`, `test_site_builds_from_the_sandbox` and
`test_the_budget_cut_leaves_every_benchmark_a_share` importing `select_questions` and
`test_release_notes_describe_what_was_built` importing `notes`; `manifest.py` and
`question_ids.py` had no test at all. A new file,
`tests/test_the_scripts_that_choose_what_the_site_publishes.py`, covers what the four leave: run
discovery, the release-asset line every run is given, the whole of `manifest.py`, and
`question_ids.py`. Nine tests, no network and no Docker; every fixture is a
directory tree and a tar archive built in `tmp_path`.

It extends rather than duplicates. The budget cut stays in
`tests/test_the_budget_cut_leaves_every_benchmark_a_share.py`, the output directory's lifecycle in
`tests/test_selection_empties_only_its_own_directory.py`, and the release notes in
`tests/test_release_notes_describe_what_was_built.py`; the new file's own docstring says so, so a
reader looking for one of those three is sent to it rather than finding a second copy.

The manifest's digests and per-run counts are read whole: an archive's `sha256`, its `bytes`
against the built file's own size, and `per_run`, one entry per run and each holding that run's
own count. A run that wrote no question directory is asserted to be counted as zero rather than
left out, because a page that cannot state how many questions there are and a page that states
zero are not the same silence. An assets directory holding no archive is asserted to be a refusal
with nothing on stdout, since an empty manifest would read to the selector as a release that
published nothing.

`RECORD_BYTES_MOVED` and the release-notes text the dispatch named are already covered, whole, by
`tests/test_release_notes_describe_what_was_built.py`:
`test_the_notes_state_what_moved_in_the_bytes_of_a_record` reads the section and every path in it,
and `test_a_release_that_moved_no_record_byte_renders_no_such_section` sets the tuple empty and
asserts the section is gone. Copying either into the new file would make two places to change, so
the new file does not repeat them and says where they are.

Files: `tests/test_the_scripts_that_choose_what_the_site_publishes.py` (new, 294 lines). Gate
green, 1,298 passed.

The merge gate found the digest unchecked. The test that says it reads the manifest's digest
asserted nothing about one, and the only `sha256` in the file was the value another test plants in
a manifest it writes itself, so the script could have stated any digest and this passed. Commit
`400b9b1` takes the digest again from the archive the test built; with the script's digest replaced
by sixty-four zeros the test fails at that line.

### 2. `e814afa` refactor(contract): what a document this tool reads is, proved at the boundary

CQ-L2-03. Every document this tool reads was written by somebody else, `json.loads` answers `Any`,
and the assumption that a field was an object or an array was made by a `cast` after the fact. A
cast is not a check: it states a shape, the checker stops asking, and a document of another shape
walks past it to whatever attribute access comes next, which is where the review found several
loader defects.

`src/attestql/contract/document.py` is new and small: `JsonValue`, the recursive alias for what
JSON's grammar guarantees; `JsonObject`; and two readings, `an_object` and `an_array`, each taking
the caller's own refusal so that nothing here raises an error of its own. Both messages are
written once, so every reader gives one answer. The module is 73 lines and holds no state.

The readers now annotate what `json.loads` gave them once, at the line where the document arrives,
and every `isinstance` below that line narrows the union with nothing to cast.
`src/attestql/evidence/load.py` went from two casts to none and delegates its `_object` and
`_list` to the shared readings, keeping `UnreadableRecord` as its refusal;
`src/attestql/report/render.py` went from six to none, keeping `ReportRefused`;
`src/attestql/audit/cli.py` lost its six JSON casts. The 27 `cast` calls left in the command read
an argparse `Namespace` attribute, which is a different `Any` with a different answer, and are out
of this finding's scope. `src/attestql/audit/fixture.py` keeps three, stated: its whole reader sits
inside a handler that answers `None`, so a refusal there has nowhere to go.

This is not the type of what the tool writes. `src/attestql/evidence/render.py` keeps
`dict[str, Any]` for its writers with a docstring pointing here: applying the recursive alias to
the writers produced 405 pyright errors, all of them `dict` invariance, because a literal built as
`dict[str, int]` is not assignable to `dict[str, JsonValue]`. A writer that builds a document
cannot be handed a malformed one, so the two are different problems.

The narrowing found a defect while it was being applied. The columns loop in `evidence/load.py`
iterated the array without asking whether each entry was an object, so a column that was a string
reached an attribute access and raised `AttributeError` rather than `UnreadableRecord`;
`tests/test_evidence_load_round_trips.py` gained a test for it.

Files: `src/attestql/contract/document.py` (new), `src/attestql/evidence/load.py`,
`src/attestql/audit/cli.py`, `src/attestql/report/render.py`, `src/attestql/evidence/render.py`,
`tests/test_evidence_load_round_trips.py`, `tests/test_site_builds_from_the_sandbox.py`. Gate
green, 1,306 passed.

### 3. `3c90f32` refactor(audit): the command splits into the four boundaries it already had

CQ-L2-01. `src/attestql/audit/cli.py` was 2,182 lines holding four jobs that barely touched each
other. It is now `src/attestql/audit/cli/`, a package of the same four: `parser.py` builds the
argument parser and holds the descriptors, `inputs.py` reads the question and prediction files,
`run.py` runs an audit and the demo, and `summary.py` counts and writes what a run produced.
`errors.py` holds `ToolError` alone, because all four raise it and none owns it, and
`__main__.py` is the twelve lines that make `python -m attestql.audit.cli` work.

`__init__.py` is the facade: 182 lines, the module docstring that was the file's, the
`main` dispatch, and the exports. `attestql.audit.cli:main` is still the console-script entry
point in `pyproject.toml` and is unchanged.

Nothing was rewritten. Every function kept its body, its docstring and its tests; the split was
made by slicing the original file at statement boundaries, copying the import block into each new
module, pruning it with `ruff check --fix`, and resolving the undefined names that were left.
Eight names lost the underscore they carried while the file was one module, because pyright's
`reportPrivateUsage` fires when an underscore name is imported across a module boundary and a name
two modules share is not private. The list is below.

`tests/test_boundary.py` carries one exemption for the module that reads
`importlib.metadata`, and it moved with the code: `COMMAND_MODULE` is now
`src/attestql/audit/cli/parser.py`, with a line saying the exemption moved with the split.

Files: `src/attestql/audit/cli.py` deleted, `src/attestql/audit/cli/` added (seven modules),
`tests/test_boundary.py`. Gate green, 1,342 passed. Verified by hand:
`uv run attestql --version` and `uv run python -m attestql.audit.cli --version` both print
`attestql 0.3.1`.

### 4. `d3c3acd` refactor(report): the renderer splits into loading, the model, the pages and the indexes

CQ-L3-01. `src/attestql/report/render.py` was 2,177 lines holding four jobs in the same way. It is
now `src/attestql/report/render/`: `load.py` reads an audit's JSON documents and reconciles them
against what the run says it wrote, `models.py` is the dataclasses a page is made of, `pages.py` is
the Jinja2 rendering and the writing, `indexes.py` builds the filter pages from a rendered run, and
`errors.py` holds `ReportRefused`.

`__init__.py` is the facade and holds `render_report` itself, unchanged, so every caller that
imports it from `attestql.report.render` still does.

Two things had to move with the code. The template and static directories are found from
`__file__`, and the package sits one directory below where the module sat, so `TEMPLATES` and
`STATIC` are now `Path(__file__).parent.parent / ...` with a line saying why. And 31 names crossing
a new boundary lost their underscore, listed below; fourteen of them were also given a name that
says what they read, because `_list`, `_object` and `_text` are fine as file-local helpers and are
not fine as a module's exports.

`tests/test_report_imports_no_engine.py` still passes: the report package still reaches Jinja2 and
the standard library and nothing that reaches a database. It parametrises over the modules
reachable from the package, so it grew by the five new ones.

Files: `src/attestql/report/render.py` deleted, `src/attestql/report/render/` added (six modules),
`tests/test_site_builds_from_the_sandbox.py`, whose one reader of a private name now imports the
renamed public one. Gate green, 1,377 passed.

### 5. `c0a430c` ci(wheel): the packaging is exercised on every push and not first at a tag

CI-05. `release.yml` already builds the wheel, installs it and runs the demo out of it, but it does
that on the tag, where a wheel that left a template or a data file behind is found with the version
already cut and the fix costs another tag. `ci.yml` gained a `wheel` job that runs the same check
on every push, on both supported versions rather than on the one the release builds with, because
one pure-Python wheel serves both and they do not resolve the same dependency tree.

`just check` cannot see any of this. It runs against `src/`, with every file where the repository
put it; what a wheel holds is the build backend's decision. The job's environment holds the wheel
and its dependencies and nothing else, and the command is reached by path out of it, so an import
or a data file that only works from a checkout fails there.

The demo's exit status is asserted rather than left to end the step. Three of its six golds
disagree with their corrections, so it exits 1 by design, as `docs/audit-command.md` states: a step
that took 0 for success would redden every run, and one that dropped the status would pass a demo
that had crashed. The guard was checked both ways by hand.

Both actions are pinned by commit SHA, the same two pins the `check` job uses. Permissions are the
file's own `permissions: contents: read` at the top level, which is the whole workflow's grant and
the minimum a job that only reads the repository needs; the new job asks for nothing more.

Files: `.github/workflows/ci.yml`. No test: nothing in the suite reads this file, and the check it
adds is the run itself. Gate green.

The merge gate found two holes in the step and one in the file's first line, fixed in `507885b`.
The demo renders nothing, so `templates/` and `static/` were never read out of the wheel and the
claim above about a missing template was not one this job could make; the step now renders the
demo's own audit through `attestql report` and asks for a page with bytes in it, which is the
command that reads them and whose resolution of them this branch moved. An uncaught exception exits
1 as well, so the summary line the demo prints last is read too. Both of those need the demo's own
status through a `tee`, which needs `pipefail`, which the implicit default shell does not set, so
the step names `shell: bash`; measured in a scratch directory against a wheel built from this tree,
the steps exit 0 under `bash -eo pipefail` and exit 1 before the report under `bash -e`. And the
file's first line said it runs the same checks as `just check`, which one job does and the other
deliberately does not.

### 6. `e83c497` docs(claims): the register names the modules the command now lives in

Six rows of `docs/claims-register.md` pointed at `src/attestql/audit/cli.py`, which is a package
after commit 3, so a reader following one of them found nothing. Each now points at the module that
holds the thing the row names: A13 at `cli/` and its `run.py` and `summary.py`, A40 at `cli/run.py`
for `run_demo`, A46 and the R-ORD row of section 3 at `cli/parser.py` for `SERIALIZATION` and its
`numeric_scale`, A47 at `cli/inputs.py` for `read_predictions`, and A48 at `cli/run.py`.

ADR-0014's dependency inventory still names `audit/cli.py` at 1,280 lines and is left alone: it
counts the lines of a tree at the named commit `9e4627d` and is the measurement of that day, not a
pointer to today's.

Files: `docs/claims-register.md`. Gate green.

## Line counts, before and after

| Before | Lines | After | Lines |
|---|---|---|---|
| `src/attestql/audit/cli.py` | 2,182 | `src/attestql/audit/cli/__init__.py` | 182 |
| | | `src/attestql/audit/cli/__main__.py` | 12 |
| | | `src/attestql/audit/cli/errors.py` | 13 |
| | | `src/attestql/audit/cli/inputs.py` | 473 |
| | | `src/attestql/audit/cli/parser.py` | 412 |
| | | `src/attestql/audit/cli/run.py` | 794 |
| | | `src/attestql/audit/cli/summary.py` | 509 |
| | | total | 2,395 |
| `src/attestql/report/render.py` | 2,177 | `src/attestql/report/render/__init__.py` | 243 |
| | | `src/attestql/report/render/errors.py` | 17 |
| | | `src/attestql/report/render/indexes.py` | 162 |
| | | `src/attestql/report/render/load.py` | 431 |
| | | `src/attestql/report/render/models.py` | 518 |
| | | `src/attestql/report/render/pages.py` | 1,037 |
| | | total | 2,408 |

Each package is a little longer than the file it replaced: 213 lines for the command and 231 for
the renderer. That is the import block each module needs and the docstring each one carries, and it
is the price of the boundaries being real. The largest module left is 1,037 lines, down from 2,182.

## Every re-export added

Nine names. `__all__` lost nothing anywhere, which was checked by importing both wheels, main's and
this branch's, and comparing every module's `__all__`.

Four in `attestql.audit.cli`, all of them constants a test or a maintainer script imports from the
command and that now live in `inputs.py` or `parser.py`:

- `BIRD_PREDICTION_SUFFIX`
- `DEFAULT_SCRATCH_SCHEMA`
- `QUESTION_DIRECTORY`
- `QUESTION_ID_LIMIT`

Five in `attestql.report.render`, all of them names `tools/site/build.py` or a test imports from
the renderer and that now live in `load.py` or `models.py`:

- `PUBLISHED_FILE`
- `QUESTION_DIRECTORY`
- `STATIC_DIRECTORY`
- `Published`
- `published_asset`

## The names that lost their underscore

A name two modules share is not private, and pyright's `reportPrivateUsage` says so. None of these
was ever in `__all__`, so none is a public signature; they are named here because a reader of the
diff will meet them.

Eight in the command, all in `summary.py` and imported by `run.py` or `__init__.py`: `_Counted` to
`Counted`, `_Measured` to `Measured`, `_count_credited` to `count_credited`, `_line` to
`question_line`, `_summarise` to `summarise`, `_summary_json` to `summary_json`, `_summary_line` to
`summary_line`, `_write_summary` to `write_summary`.

Thirty-one in the renderer. Seventeen kept their name: `_as_text`, `_cell_text`,
`_clear_the_render_before_this_one`, `_credited`, `_data_file`, `_listed_directories`,
`_mechanism_counts`, `_object_of`, `_object_or_none`, `_optional_integer`, `_optional_text`,
`_probe_fired`, `_question_directories`, `_question_page`, `_refuse_a_gap_nothing_explains`,
`_refuse_an_out_inside_the_audit` and `_run_page`.

Fourteen were also given a name that says what they read, because a one-word helper is fine
file-local and is not fine as a module's export: `_beside` to `beside_the_run`, `_count` to
`count_in_words`, `_document` to `read_document`, `_facts` to `facts_of`, `_filters` to
`filter_pages`, `_integer` to `integer_at`, `_list` to `array_at`, `_list_of` to `array_of`,
`_object` to `object_at`, `_objects` to `objects_at`, `_origin` to `origin_of`, `_strings` to
`strings_at`, `_text` to `text_at`, `_write` to `write_pages`.

## The wheel job, run by hand

The job's two shell steps were extracted from `.github/workflows/ci.yml` with a YAML parser,
`${{ matrix.python }}` replaced by `3.11`, and run verbatim under `bash -e` with `RUNNER_TEMP`
pointed at a scratch directory. They exited 0. The steps as run:

```text
uv build
uv venv --python "3.11" "$RUNNER_TEMP/wheel"
uv pip install --python "$RUNNER_TEMP/wheel/bin/python" --no-cache dist/*.whl

"$RUNNER_TEMP/wheel/bin/attestql" --version
demo_status=0
"$RUNNER_TEMP/wheel/bin/attestql" demo --out "$RUNNER_TEMP/demo" || demo_status=$?
test "$demo_status" -eq 1
```

What they printed: `uv build` wrote `attestql-0.3.1-py3-none-any.whl` and `attestql-0.3.1.tar.gz`;
the install resolved nine packages into the fresh environment, `attestql==0.3.1` from the local
file plus `jinja2`, `markupsafe`, `postgast`, `protobuf`, `psycopg`, `psycopg-binary`, `sqlglot`
and `typing-extensions`; `attestql --version` printed `attestql 0.3.1`; the demo printed its six
question lines, its summary line `6 questions: 3 NOT_EQUAL, 5 smells fired, 0 credited by BIRD but
NOT_EQUAL (0 multiplicity, 0 type, 0 order, 0 truncation, 0 other), 0 timed out (0 gold, 0
prediction)` and its rerun line, wrote `audit/`, `fixture.sqlite`, `questions.json` and
`predictions.json` into the scratch directory, and exited 1.

The guard was checked against the two statuses it must refuse. A demo exiting 0 and a demo exiting
2 each made the step exit 1 and print `attestql demo exited 0` and `attestql demo exited 2`.

## Checks at the branch head

`just check` green, at every commit and at the head: ruff check and format, pyright strict with 0
errors, the three repository checks, markdownlint and cspell, 1,377 passed and 34 skipped, then the
PostgreSQL sandbox at 34 and the SQLite sandbox at 130.

**The test count.** 1,283 on main at `3300fbb`, 1,377 at the head, which is 94 more. The arithmetic
is exact: TEST-01's nine tests, the one test the columns-loop defect needed, 78 from
`tests/test_boundary.py`, which parametrises six cases over every file under `src/attestql/` and
`tests/` and met thirteen new ones (one for the JSON contract, six for the command package, five
for the renderer package, one new test file), and 6 from
`tests/test_report_imports_no_engine.py`, which parametrises over the modules reachable from the
report package and met the five new renderer modules and the JSON contract.

**`attestql demo` is byte for byte unchanged.** Main at `3300fbb` and this branch were each built
into a wheel, installed into their own fresh environment, and run into the same output path. The
console output is identical, `diff` reporting nothing. The 26 files written are the same 26, and
their content is identical once the fields that are per-run by construction are set aside: the run
id, `data_as_of` and `executed_at`, each record's `record_hash`, which covers those, the elapsed
seconds, and the SQLite file identity inside the fixture digest, which changes because the demo
builds `fixture.sqlite` fresh every time.

**The site still builds to the same bytes.** `uv run python tools/site/build.py --out <scratch>`
over the 121 published runs: 2,181 files, 32,670,870 bytes, 3.1 s. Both numbers are what the
dispatch stated.

**No public signature moved.** `attestql --help`, `attestql audit --help`, `attestql report --help`
and `attestql demo --help` are byte for byte identical between the two wheels, so every flag and
every default is unchanged. `attestql --version` prints `attestql 0.3.1` from both, and from
`python -m attestql.audit.cli` as well. A tool error exits 2 from both. The demo's `summary.json`
compared identical field for field, which is the summary's JSON keys. `render_report` is imported
from where it was. Every module's `__all__` is a superset of main's, losing nothing and adding the
nine re-exports above.

## Open

**Names that were module attributes but never exported, accepted as intended.** Splitting a
module means names that happened to sit in its namespace are no longer reachable through it. In
the renderer those are `GOLD`, `SECOND`, `GOLD_ONLY`, `GOLD_GLYPH`, `SECOND_GLYPH`, `SQL_TOKEN`,
`ALWAYS_TAGGED`, `ASSET_SCHEME`, `OUT_SUFFIX`, `CLEARED_FILES`, `CLASSIFICATION_FILE`,
`CLASSIFICATION_SOURCE_FILE`, `QUESTIONS_FILE`, `NAMED_IN_A_REFUSAL`, `HandReading` and `Beside`,
and in the command `NO_SMELL` and `NAMED_IN_A_REFUSAL`, alongside the imported names any module
carries, `json`, `argparse`, `difflib` and the rest. The coordinator accepts this at the merge
gate as intended and not as a regression: this tool's contract is its command line and its record
layout, not the attributes of a module; none of these was ever in either facade's `__all__`; no
file in this repository read one of them that way, and the gate covers `tools/` as well as `src/`
and `tests/`; and both facades export exactly what `__all__` always did plus the nine re-exports
above. A reader outside this repository who imported one would have to change the import.

**The five casts that stay.** `src/attestql/audit/fixture.py` keeps three, because its whole reader
sits inside a handler that answers `None` and so has no refusal to raise, and
`tests/test_the_deploy_runs_the_wrangler_it_locked.py` keeps two for the same reason a test may:
it reads two files it also writes the assertions for. Both are stated where they are, not silent.

**The `wheel` job has not run.** Its steps were run by hand on this machine, on Python 3.11 and on
macOS. Until a GitHub run is observed green, the file is configuration and not evidence, which is
the rule `docs/developer-environment.md` section 9 already sets for `ci.yml`.
