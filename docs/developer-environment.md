# Developer environment and quality gates

Target: Python 3.11+, developed on 3.13; CI runs both. This document records the tooling
decisions and why each tool is here.

**Principle carried from the rest of the project:** a rule that lives only in prose is a rule that
drifts. Every convention this repository states should be mechanically checkable, and every check
should be runnable with one command.

This document follows the house Python setup checklist (detect, decide, add, verify, report). Where
it departs from that checklist, section 8 says so and why.

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
`S607`, which are the rules the subprocess exemption below depends on. Allowing `S101` and
allowing `subprocess` are unrelated decisions, and conflating them would silently disarm the
control this configuration exists to double-enforce.

**No other blanket test exemption is permitted.** `S101` earns its allowance because the
finding is an artifact of how pytest is written, not because `tests/` is a lower-standard
area. Any further relaxation is a separate decision with its own justification.

### The subprocess exemption, which is narrower than it first looked

Three test files mention `subprocess`: `test_boundary.py`, `test_fixture_determinism.py` and
`test_fixture_generation.py`. They do not all mention it for the same reason. `test_boundary.py`
almost certainly names it as a **string** in its prohibited-primitive list rather than calling it,
and a string is not a finding.

The exemption is therefore granted per file, by exact filename, and **only to files that actually
import or invoke subprocess**, determined by reading them rather than by grepping for the word.
Never a glob: a hedge that matches a pattern is how a boundary quietly stops being one.

This is separate from the `S101` allowance above. `S101` is granted to the test tree; the
subprocess rules are granted to named files and to nothing else.

## 4. Repository-specific checks

These three are run by hand today, every time, by the coordinating session. Automating them is the
main reason this milestone exists.

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

`just check` runs, in order: ruff format check, ruff lint, pyright, the three repository checks,
markdownlint, cspell, then pytest. It is what a milestone verification runs.

`just fix` applies only the auto-fixable subset (`ruff format`, `ruff check --fix`). Automatic fixing
stops at the boundary of anything that changes meaning.

## 6. Editor

No editor configuration is committed. `.editorconfig` carries the whitespace rules, and the gate
carries everything else; an editor that runs ruff, pyright in strict mode and the markdownlint and
cspell extensions agrees with `just check` without further settings.

## 7. Not adopted

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

## 8. Departures from the house checklist, recorded

**CI is added, but no document may claim it gates anything until it has run green once.** The
checklist calls for `.github/workflows/ci.yml`, and the file costs nothing and works the moment a
remote exists. The risk was never the file; it is a document asserting the project is gated when no
run has happened. That risk is handled by the constraint above rather than by omitting the file.
An earlier draft of this plan omitted CI entirely, which was the wrong fix for the right worry.

**`ANN` omitted from ruff.** Reason in section 3.

**`S` added to ruff.** Reason in section 3.

## 9. Consequence to accept honestly

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
