# Plan: the AttestQL web UI, a static evidence viewer rendered by the CLI

Status: ACCEPTED 2026-09-07 18:40 by the owner (Pages plan: Free; phase 5 accepted), after the
red-team review `plans/reports/review-260907-1806-web-ui-plan-red-team.md`. Written 2026-09-07.
Research behind it: `plans/reports/research-260907-1730-attestql-web-ui-direction.md`.

## Outcome

A person who follows a link to attestql.com lands on a page that says in one sentence what the
tool is, shows the headline finding with its source, and gives the ten-minute command. Every
published disagreement and every fired probe has its own URL, a page that tells one story in a
fixed order and links to the JSON it was rendered from. A person who ran an audit of their own
gets the same pages by running `attestql report audit/`.

## Constraints

- The evidence record and the four JSON files stay the contract. HTML is a view of them, never
  evidence, and every page links to its JSON.
- One renderer, in Python, inside the package. No second renderer in JavaScript.
- No server, no accounts, no execution of a visitor's SQL.
- The page never judges. Forbidden words are tested for. The hand classification appears as a
  human reading, labelled as such, beside the tool's verdict and never merged with it.
- Every outward step (repository workflow, Pages, DNS) runs under the owner's personal
  identity, the one the repository lives under; nothing is posted or published on the owner's
  behalf without their word.
- The gate stays `just check`. New code passes ruff, pyright strict, the repository checks, the
  markdown checks and the tests.
- `site/index.html` and `README.md` belong to the main session (its message of 2026-09-07
  18:05) and are not edited here. The built site lives in `build/site/` from `tools/site/`, and
  deploys to a preview project `attestql-ui`; the live project `attestql`, the domain and the
  DNS record are not touched. Replacing what attestql.com serves is an owner step.
- `counterexample.json` previews 25 rows per side and a bounded difference; the two evidence
  records hold every row and their hashes cover every row. Pages show rows from the records,
  state where each table came from, and never modify, trim or re-issue a record.
- The account is on the Cloudflare Pages Free plan (owner, 2026-09-07): 20,000 files per site,
  25 MiB per file. The build's own budget is 8,000 files, under half the limit, so a run can be
  added without a re-plan. Pages exist only for the questions the site is about (the
  credited-but-NOT_EQUAL rows, fired-probe golds, the hand-classified rows, the unjust-zero and
  unjust-one cases); full runs are release assets.
- Phase 1 starts from `5e156d7` or later (the `attestql demo` commit); the worktree is there.

## Non-goals (this plan)

- A paste-two-statements playground (needs a server and a security boundary; only on demand).
- Cross-run comparison pages (the NOT_COMPARABLE verdict exists; a page for it comes when two
  published runs of one benchmark exist).
- PyPI: attestql 0.2.1 is published (`5d44e07`); nothing to do here.

## Acceptance criteria

1. `attestql report <audit-dir> --out <dir>` renders a run page and one page per question
   directory from any directory `attestql audit` wrote, PostgreSQL or SQLite, gold-only or
   prediction mode, including ERROR and timed-out questions and probes marked not applicable.
2. Rendering the SQLite sandbox audit and the PostgreSQL sandbox audit in the test suite produces
   pages whose key elements are asserted structurally; the forbidden-phrase test passes.
3. At 360, 768 and 1280 px, with the longest real content (a result whose `row_count` is 10,000
   and whose artifact shows 25, a 600-character statement, an unbroken origin URL, a 16-column
   projection), no horizontal page scroll, no clipped text, body contrast at least 4.5:1 and
   large text at least 3:1, both computed.
4. `uv run python tools/site/build.py` builds the site from `tools/site/data/` in under two
   minutes and under the size budget stated in phase 3; the preview project serves it over
   HTTPS; attestql.com is unchanged until the owner's switch.
5. Every published CLI run (nine per prediction benchmark, one or two per gold-only benchmark)
   has a run page under its benchmark whose counts match its `summary.json`; every selected
   question has a page whose content matches its artifacts; ERROR and timed-out questions are
   rows of the run page from the summary and have no page of their own. Amended 2026-09-08: on
   SQLite one connection is one database file, so a prediction file there is a group of eleven
   runs rather than one run, and the criterion is read per run under its group, with the group
   stating the sums of its eleven by the merge rule the SQLite measurement reports state.
6. Every record on every page carries "recomputed from this JSON: match" from the loader of
   phase 1, and the built site stays under the file and size budgets phase 4 derives.
7. `just check` is green at the end of every phase.
8. The drop zone of phase 5 renders both sandbox audits and the stress directory with no request
   outside the site, including a record with a timestamp column.

## Phases

| Phase | File | Depends on | Delivers |
| --- | --- | --- | --- |
| 1 | `phase-1-report-renderer.md` | nothing | DONE: `attestql report`, templates, tests |
| 2 | `phase-2-design-and-verification.md` | 1 | DONE: tokens applied, states designed, figures, rendered and measured at three widths |
| 3 | `phase-3-site-build-and-deploy.md` | 2 | DONE 2026-09-08: `tools/site/` build, landing and method pages, the index filters, preview at <https://attestql-ui.pages.dev>, reviewed |
| 4 | `phase-4-publish-runs.md` | 1 (data), 3 (deploy) | DONE 2026-09-08: 121 runs published and reconciled, 348 questions selected under the budget, the whole runs as release assets on `v0.2.2`, preview at <https://attestql-ui.pages.dev> with the real rows and no banner |
| 5 | `phase-5-in-browser-viewer.md` | 1, 3 | drop zone for private audits, one renderer via Pyodide; about 6.3 MB compressed, loaded on demand; hash verification lives in phase 1 |

Order: 1, 2, 3, 4, 5. Phase 4 comes before 5 because the published rows are what visitors come
for; the drop zone serves the smaller group with a private audit, and depends on nothing in 4.

Shared by every phase: `design-spec.md` (tokens, typography, layout, states, motion, copy rules).

Model routing per the owner's rule: phases 1, 3 and 4 are implementation and run on Opus; phase
2's verification verdicts and the review gate of every phase run on Fable.

## Risks and rollback

- The renderer lands in the package with Jinja2 as a dependency (owner's decision 2026-09-07).
  Removing it removes `attestql report`, the templates directory, their tests and the
  dependency; the audit path is untouched.
- `tools/site/` and `build/site/` are the site; removing them removes it and changes nothing
  on attestql.com. Published JSON under `tools/site/data/` is regenerable from the CLI and the
  public data.
- The domain stays on the `attestql` project throughout; the preview project can be deleted at
  any time.
- A concurrent session commits to `main`. Every phase rebases on `main` before it starts and
  touches no file that session is editing (`README.md`, `site/index.html`,
  `docs/audit-command.md`, `release.yml`, the register, and since `5e156d7` the `demo`
  package, `tests/test_boundary.py`, `NOTICE`, `pyproject.toml` package data) except by the
  additions each phase file names: the `report` subcommand in `cli.py`, the Jinja2 dependency,
  two public accessors in `smells.py` and `postgres.py`, the OFL text in `NOTICE`. Reviewed against
  these constraints 2026-09-07:
  `plans/reports/review-260907-1806-web-ui-plan-red-team.md`.
