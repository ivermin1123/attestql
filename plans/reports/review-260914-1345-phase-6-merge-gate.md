# Merge gate for phase 6 of the review-findings plan

Reviewed 2026-09-14 from 13:45, branch `ivermin1123/review-findings-phase-6` at `b1a80a9` over
`main` at `3300fbb`, seven commits, 24 files, 5,269 lines added and 4,393 removed, of which
4,359 are the two modules that became packages. The branch is the work of
`plans/reports/cook-260914-1240-review-findings-phase-6.md`. Two independent reviewers read it
in parallel, one over the code (the recursive JSON type, the two splits, the boundary tests),
one over the CI job, the maintainer-script tests, the documents and the report's numbers. The
coordinator ran `just check` on the branch head first: 1,377 passed and 34 skipped, then 34 in
the PostgreSQL sandbox and 130 in the SQLite sandbox, exit 0.

Before either reviewer started, the coordinator compared every top-level definition of the old
`audit/cli.py` (88 names) and `report/render.py` (127 names) with the new packages at the AST
level, after normalising the names that went from private to public: every name is present, and
124 lines differ in total, all of them type annotations (`Json` to `JsonObject` or `JsonValue`),
removed `cast(` calls, and the two asset paths `STATIC` and `TEMPLATES` gaining one `.parent`
because `pages.py` sits one directory deeper. The reviewers were given that result and told to
spend their effort on what it cannot see.

Verdict of both reviewers: **merge after fixes**. Neither found a defect in what the tool concludes
or writes. The fixes were dispatched to the same worker as new commits on the same branch and landed
as `2128133` (the guarded entry point, the two docstring counts, the orphan docstring and the five
pointers), `400b9b1` (the digest assertion), `507885b` (the wheel job's step and the workflow
header) and `9211d4f` (the report and row A13). The coordinator ran `just check` on the fixed head
`9211d4f`: 1,377 passed and 34 skipped, then 34 in the PostgreSQL sandbox and 130 in the SQLite
sandbox, exit 0. The branch merged into `main` as `12f1c29` on 2026-09-14, over the documents commit
`3337f42` that had reached `main` in the meantime, and `just check` ran on the merged tree: 1,377
passed and 34 skipped, then 34 in the PostgreSQL sandbox and 130 in the SQLite sandbox, exit 0.

## What blocked the merge

**The `-m` entry point exits on import.** `src/attestql/audit/cli/__main__.py` raised
`SystemExit(main())` at module level, so `import attestql.audit.cli.__main__` ended the process
with status 2; anything that walks and imports the package (pydoc, a doctest run over `src/`)
would die there. Its docstring also gave a false reason: the old module had no `__name__` guard,
so `python -m attestql.audit.cli` at `3300fbb` imported the module and ran nothing. The `-m` form
is new with the package, which the file now says, under the guard.

**The wheel job did not check what its comment said.** The new `wheel` job in `ci.yml` installs
the built wheel into an empty environment and runs `attestql demo`, and its comment says a wheel
that left a template behind is found there. The demo renders nothing, so `templates/` and
`static/` were never read from the wheel, on the branch that moved how `pages.py` resolves them.
`test "$demo_status" -eq 1` also accepted the status of an uncaught Python exception. The step
now keeps the demo's output, requires the `6 questions: 3 NOT_EQUAL` summary line as
`release.yml` does, and renders the demo's audit with `attestql report` out of the wheel. The
reviewer had already confirmed by hand that the current wheel holds twelve templates and eight
static files and renders seven pages, so this closed a gap in the check and not a defect.

**The digest test asserted no digest.** The new test named for the manifest's size, digest and
per-run counts asserted the tag, name, address, size and directories and never the `sha256`; the
only digest in the file was one the test planted itself. The commit message of `06e742f` and the
report both said the digest was covered. One line now compares the manifest's digest with
`hashlib.sha256` over the archive the test built.

## Carried into the same fix pass

An orphan docstring in `render/pages.py` contradicting the one above it; two `errors.py`
docstrings counting modules that do not use them; five bare pointers to `cli.py` and `render.py`
in `engines.py`, `parse.py`, `select_questions.py` and `tools/audit-sandbox/run.sh`; row A13 of
the claims register naming `postgres.py` for a DSN refusal that lives in `parser.py` and
`engines.py`; the report's sentence about prior test coverage (four test files imported the
scripts; `manifest.py` and `question_ids.py` had none) and a line count off by one; and the
workflow header that no longer described a file with a job `just check` cannot see.

## Decided at the gate

Names that were attributes of the old `cli.py` and `render.py` but not in their `__all__` (sixteen
in the renderer, two in the command) are not attributes of the new facades. Accepted as
intended: the tool's contract is the command line and the record layout, no file in the
repository read them, and the facades export what `__all__` always did plus nine re-exports whose
consumers are named in the report. `__main__.py` stays, guarded, though the plan never asked for
it: a package cannot be run with `-m` without one, and the file is twelve lines.

## Left open, on record

`tests/test_report_imports_no_engine.py` asserts a tautology at line 184, where the set it
compares against is the set it defined; the assertions beside it carry the check. It predates the
branch. The `wheel` job has not yet run on a GitHub runner; its shell lines were run by hand from
a wheel built off the head, and by the repository's own rule no document claims it gates
anything until it has run green once.

## What the reviewers verified clean

The behaviour change the branch claims is real and reproduced both ways: a record whose `columns`
entry is not an object raised `AttributeError` at `3300fbb` and raises `UnreadableRecord` naming
the value now, which `render_report` turns into a `ReportRefused` with the directory named. Zero
`cast(` remain in `evidence/load.py` and the renderer, the command's six JSON casts are gone, and
the 22 casts left in the parser are `argparse.Namespace` casts unchanged from `3300fbb`. The
boundary helpers produce the exact strings the inline checks produced, so no message-matching test
moved. Pyright strict accepts the recursive alias with no new ignore. `attestql.audit.cli:main`
is unchanged in `pyproject.toml`; the console script, `python -m` and the wheel-installed command
all run. The `__all__` of each facade lost nothing and gained the nine names the report lists,
with consumers in `tests/` and `tools/report-stress/`. No circular import among the new modules;
the old `figures` cycle is still cut by `TYPE_CHECKING`. `STATIC` and `TEMPLATES` resolve to the
same directories as before and the package data lands in the wheel. `tests/test_boundary.py`
moved its exemption to `cli/parser.py` by exact path and still covers every new module by
`rglob`. The nine maintainer-script tests exercise real refusal paths of unchanged scripts
(`git diff` over `tools/` is empty) with no network, no Docker and every fixture under
`tmp_path`. Both action pins match their tags' commits, `permissions` is `contents: read`, the job
installs the wheel and not the checkout. The register's six new pointers each name the module
that holds the symbol; no path to the old files survives in `docs/`, `README.md`, `tools/` or
`src/`. Every number in the report re-derived: 1,411 collected, the +94 exact by file
(9 + 1 + 78 + 6), 2,181 files and 32,670,870 bytes, four `--help` texts byte-identical, line
counts equal to the diff stat. cspell, markdownlint and the typography check clean; no AI mention
in any of the seven commit messages, all of which pass the repository's own hook.
