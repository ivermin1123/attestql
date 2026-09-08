# Developer environment and quality gates

Target: Python 3.11+, developed on 3.13; CI runs both. This document records the tooling
decisions and why each tool is here.

**Principle carried from the rest of the project:** a rule that lives only in prose is a rule that
drifts. Every convention this repository states should be mechanically checkable, and every check
should be runnable with one command.

This document follows the house Python setup checklist (detect, decide, add, verify, report). Where
it departs from that checklist, section 9 says so and why.

---

## 1. What the repository has today

Detected 2026-08-25, before any tooling work:

| Concern | State |
|---|---|
| Package manager | **None.** No `uv.lock`, no `poetry.lock`, no `requirements.txt`. `pyproject.toml` declares `[project.optional-dependencies] test = ["pytest"]`, which is a pip-era pattern with no lockfile behind it |
| Build backend | setuptools |
| Python pin | **None.** `requires-python = ">=3.11"`, no `.python-version` |
| Lint, format, type check | **None** |
| Tests | pytest, `[tool.pytest.ini_options]` configured |
| Hooks, task runner, CI, editor config | **None** |
| `.gitignore` | present but missing `.ruff_cache`, `.mypy_cache`, `dist`, `build`, `.env` |

Nothing here is a decision to preserve. That makes the choices below initial choices rather than
migrations, which is why none of them needed a compatibility argument.

## 2. Tool choices

| Concern | Tool | Why this one |
|---|---|---|
| Package manager and lockfile | **uv** | There is no incumbent, so this is a first choice rather than a migration, and uv is the default for new projects here. On 2026-08-25 neither `uv` nor `just` was on the developer machine, while Node.js was; both have since been installed with Homebrew. Without a lockfile, `just check` is not reproducible across machines, which is the single largest gap in the current setup. |
| Build backend | **setuptools, kept** | It works, and changing a build backend is on the "ask first" list. uv drives any PEP 517 backend, so there is nothing to gain. |
| Python pin | **`.python-version`** at 3.13 | `requires-python = ">=3.11"` stays: the code supports 3.11 upward, developers run 3.13. |
| Lint and format | **Ruff** | One tool replaces flake8, isort, pyupgrade and black. Config lives in `pyproject.toml`, so there is no second file to drift. |
| Type checking | **Pyright**, strict | Pylance **is** pyright. Choosing pyright for the gate too means editor and gate run the same engine on the same config, which removes an entire class of "clean in the editor, red in the gate" arguments. mypy was the alternative and would have created exactly that divergence. Never both. |
| Tests | **pytest** | Already in use. |
| Coverage | **not added** | A coverage threshold on a repository that is largely stubs-that-raise would measure the wrong thing and invite tests written to move a number. |
| Hooks | **pre-commit** | Fast checks run before a commit exists. Check-only: every hook refuses, none rewrites a file. The two upstream fix-in-place hooks, `trailing-whitespace` and `end-of-file-fixer`, are not used; `.editorconfig` handles whitespace at save time. |
| Task runner | **justfile** | The house standard. `pyproject.toml` has no scripts section the way `package.json` does, so humans and any future CI need one file that defines the commands. Requires `brew install just`. |
| Editor config | **.editorconfig** | Consistent whitespace in every editor; the only editor configuration that is committed. |
| Markdown | **markdownlint** | Documentation is a primary deliverable here and an external reviewer reads it. Broken tables and inconsistent headings are defects in the deliverable, not cosmetics. |
| Spelling | **cspell** | Same reason. The documents are read by people outside the team. |

## 3. Ruff rule selection

`["E", "F", "I", "UP", "B", "SIM", "RUF", "S"]`, with `ignore = ["E501"]` because the formatter owns
line length. Line length 100, matching how the documentation is already wrapped.

The first seven are the house default. **`S` (flake8-bandit) is the one addition, and it is the
interesting one.** It flags `exec` (S102), `eval` (S307) and every `subprocess` call (S602 to S607).
Those are exactly the primitives this project already prohibits and already checks with an AST walk
in `tests/test_boundary.py`. Turning `S` on means the prohibition is enforced twice by independent
mechanisms, and the lint fires while you are typing rather than when the suite runs.

**`ANN` was considered and rejected.** Pyright strict already requires the annotations `ANN` would
ask for, and it reports them more precisely. Two checkers asking for the same thing produces two
error lists to reconcile and no extra safety.

### `S101` is allowed across the test tree, and that is not a subprocess exemption

`S101` (assert used) fires on every bare `assert`, which is how pytest expresses every
assertion. Measured against the pre-convergence tree it produced **192 findings in `tests/`**
and nothing actionable. It is therefore allowed for pytest files as a per-directory ignore.

Two limits on that allowance, both load-bearing:

**It covers `S101` only.** Every other `S` rule stays active in `tests/`, including `S602` to
`S607`, which are the rules the subprocess allowance below depends on. Allowing `S101` and
allowing `subprocess` are unrelated decisions, and conflating them would silently disarm the
control this configuration exists to double-enforce.

**No other blanket test exemption is permitted.** `S101` earns its allowance because the
finding is an artifact of how pytest is written, not because `tests/` is a lower-standard
area. Any further relaxation is a separate decision with its own justification.

### The subprocess allowance, which is narrower than it first looked

Two test files mention `subprocess` today. `tests/test_boundary.py` names it as a **string** in
its prohibited-primitive list rather than calling it, and a string is not a finding.
`tests/test_audit_end_to_end.py` really does start a process, because the only observation that
proves the console script resolves to the command a stranger is told to run is running it.

Nothing is granted in `pyproject.toml`: `[tool.ruff.lint.per-file-ignores]` holds the `S101`
allowance and nothing else. The one call carries a `# noqa: S603` on its own line, and the
permission that matters is `tests/test_boundary.py`'s own: an exact path, asserted by a test that
fails the day that file stops importing `subprocess`, so the allowance cannot outlive its reason.
Never a glob: a hedge that matches a pattern is how a boundary quietly stops being one.

**History.** An earlier draft of this section named `test_fixture_determinism.py` and
`test_fixture_generation.py` as the other two holders. Both were deleted with the fixture they
generated when ADR-0013 retired the product path, and their allowance went with them.

## 4. Repository-specific checks

Automating these three is the main reason this milestone exists. Until it, they were run by hand
every time by the coordinating session; each is now a script, and the last paragraph of this
section says where each runs.

**Typography.** No em dash (U+2014), no en dash (U+2013), no numero sign (U+2116) in any `.md` or
`.py` file authored by this project. The only exemption is a verbatim quotation of someone else's
text, inside a blockquote. Manual checking has already failed once: the first draft of the tooling
prompt, whose subject is automating this check, contained three em dashes.

**Documentation links.** Every relative link in `README.md` and under `docs/` resolves to a file
that exists. A reviewer following a dead link concludes the document is stale, and they are usually
right.

**ADR index consistency.** Every file in `docs/adr/` appears in `docs/adr/0000-index.md` and every
index entry points at a file that exists. An unlisted ADR is invisible; an index entry with no file
is a broken promise.

Each is a small script under `tools/`, each exits non-zero on failure, each wired into `just check`
and pre-commit. Each must have a test proving it **fails** on a deliberately bad input: a checker
never seen to fail is not known to work.

## 5. One command

`just check` runs seven recipes in order and stops at the first failure: `lint` (ruff lint, then
ruff format in check mode), `typecheck` (pyright strict), `repocheck` (typography, documentation
links, ADR index), `docs` (markdownlint and cspell over `README.md`, `docs/**/*.md` and
`plans/**/*.md`), `test` (pytest), and then both sandboxes. It is what a milestone verification
runs, and it does not end at pytest.

`sandbox` is the one that needs more than Python: it starts a pinned PostgreSQL 16 container on
**port 5497** through `tools/audit-sandbox/run.sh`, loads the fixture that reproduces the three
shipped-gold defects, and runs the `sandbox`-marked tests against it through a read-only auditor
login. **Docker and that port are part of the merge gate.** Neither a missing Docker nor a taken
port is a skip: ADR-0013 point 11 puts this run in the gate, so either one fails `just check`
rather than passing it quietly. `sandbox-sqlite` needs neither, because a SQLite database is a
file: it builds the fixture where a person can open it with `sqlite3` and runs the
`sandbox_sqlite`-marked tests, which do not skip themselves in `just test` either.

`just fix` applies only the auto-fixable subset (`ruff format`, `ruff check --fix`). Automatic fixing
stops at the boundary of anything that changes meaning.

## 6. Building the site

`uv run python tools/site/build.py` renders every run under `tools/site/data/` with
`attestql report`, then the landing and the method page from `tools/site/templates/`, into
`build/site/`, which git ignores. It prints the file count, the total bytes and the wall time,
and it fails, naming what pushed it over, at more than 8,000 files, more than 40 MB in total, or
any single page over 2 MB; those sit under the Cloudflare Pages Free plan's own 20,000 files and
25 MiB a file, so a run can be added to a passing build without a re-plan. The published runs
arrived on 2026-09-08 and `tools/site/data/` holds them, so a build renders those and no page
carries a banner; while that directory holds no benchmark the build audits the sandbox the package
carries and shows that instead, under the benchmark `sandbox` and the run `demo`, with a banner on
every page saying so. Which of the two happens is decided by the data and never by an edit to a
template. It reaches no network and no database: everything on both pages is read out of
`pyproject.toml`, `README.md`, `site/index.html` and the JSON of the runs. `tools/site/README.md` has the deploy command for the preview project. Since 2026-09-08 `.github/workflows/site.yml` runs the same build on every push to `main` and publishes it to attestql.com, and on a manual run to the preview; `tools/site/README.md` names the two secrets it reads.

## 6a. Tags and releases

**Tags.** `v<version>`, matching `project.version` in `pyproject.toml`. Pushing one runs
`.github/workflows/release.yml`, which runs the same `just check` gate, builds the wheel, installs
it, asks it its version and refuses to publish when that is not the tag, then uploads to PyPI
through the `pypi` environment's trusted-publisher identity, so no token is stored. New tags are
**annotated** (`git tag -a v0.4.0 -m "..."`), so the tag carries a tagger, a date and a message of
its own. The seven tags this repository already has are not consistent about that (`v0.1.1`
through `v0.2.0` are annotated, `v0.2.1`, `v0.2.2` and `v0.3.0` are lightweight) and are left as
they are: a published tag is history, and rewriting one to tidy its object type would move a
reference other people already hold.

**Which tags get a GitHub release.** Every tag that publishes a version to PyPI. The workflow
makes none: it publishes to PyPI and stops, so the release page is made by hand at the tag, and
`tools/site-select/release.sh upload <tag>` creates it when there is none in order to attach the
per-run archives, which is why `v0.2.2` carries 22 assets and `v0.3.0` carries none. Three tags
have published to PyPI so far and two carry a release page; `v0.2.1` does not and is left as it
is. `v0.1.1` through `v0.2.0` predate PyPI entirely and get none.

**What the notes are drawn from.** What the version changed and where the evidence for it is,
in the words the repository already uses: the claims register rows the release added or moved
(`docs/claims-register.md`), the ADR that decided anything the release changed, and the reports
under `plans/reports/` that own the numbers. Nothing is measured for the notes; a number that
appears there has an owning artifact behind it already.

## 7. Editor

No editor configuration is committed. `.editorconfig` carries the whitespace rules, and the gate
carries everything else; an editor that runs ruff, pyright in strict mode and the markdownlint and
cspell extensions agrees with `just check` without further settings.

## 8. Not adopted

**Coverage gate.** See section 2.

**mypy.** Pyright is chosen; running both produces disagreements on edge cases and no extra safety.

**Auto-fix on commit.** Pre-commit is check-only: every hook refuses, none rewrites a file under
you. A hook that edits during a commit makes the committed content differ from what was reviewed,
so the two upstream fix-in-place hooks, `trailing-whitespace` and `end-of-file-fixer`, are not
used. Trailing whitespace and the final newline are handled at save time through `.editorconfig`.

**tox or nox.** One supported environment. A matrix runner would be scaffolding for a variation that
does not exist.

**`requirements.txt`.** Two sources of truth. If a deploy target ever needs one, generate it with
`uv export`.

## 9. Departures from the house checklist, recorded

**CI is added, but no document may claim it gates anything until it has run green once.** The
checklist calls for `.github/workflows/ci.yml`, and the file costs nothing and works the moment a
remote exists. The risk was never the file; it is a document asserting the project is gated when no
run has happened. That risk is handled by the constraint above rather than by omitting the file.
An earlier draft of this plan omitted CI entirely, which was the wrong fix for the right worry.

**`ANN` omitted from ruff.** Reason in section 3.

**`S` added to ruff.** Reason in section 3.

## 10. Consequence to accept honestly

Turning pyright strict on against an existing tree will produce a first-run list of findings. Those
are fixed in this milestone, in a **separate commit** from the config, so that the diff introducing
the gate and the diff satisfying it can be read apart. The first-run count is recorded before
anything is fixed, because that number is the measurement of what the gate is worth. No finding is
silenced with a blanket ignore to make the first run green.

### Sizing evidence, and what it is not

Measured on 2026-08-25 against the **pre-convergence** tree, before the M1 contract corrections
landed: **35 ruff findings** with the `S101` allowance applied, and **177 pyright strict errors**
across 38 files.

Those are **sizing evidence, not expected final counts.** The convergence pass changed source and
added tests, so both numbers are stale by construction. The MT executor measures its own first-run
counts against the tree as it finds it, and reports those. A milestone that reports these two
numbers back has not measured anything.

Known deliberate findings, such as the seeded `random.Random` the fixture requires, a local pickle
round-trip in a test, and the cross-process determinism test's `subprocess` use, each need a narrow
justified suppression. **They are not pre-authorized here.** The MT executor locates them in the
current tree, confirms each is genuinely deliberate, and justifies each one individually.
