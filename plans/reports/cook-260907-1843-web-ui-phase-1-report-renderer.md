# Cook report: phase 1, `attestql report`

Worked 2026-09-07 18:43 to 19:40 (Asia/Saigon) on the web UI branch in the worktree
`~/orca/workspaces/attestql/web-ui`, from `c77b1f5`. Scope: phase 1 of
`plans/260907-1730-attestql-web-ui/plan.md` only, per
`plans/260907-1730-attestql-web-ui/phase-1-report-renderer.md` and the red-team review
`plans/reports/review-260907-1806-web-ui-plan-red-team.md`. Gate green, committed.

## What landed

| File | What it is |
| --- | --- |
| `src/attestql/evidence/load.py` | a record's JSON back to an `ExecutionResult` and its descriptor; both hashes taken again |
| `src/attestql/report/render.py` | the view model and the rendering: JSON in, pages out |
| `src/attestql/report/cli.py` | the subcommand's name, help and two arguments |
| `src/attestql/report/templates/` | `base`, `run`, `question` and six partials |
| `src/attestql/report/static/` | the token scale as class hooks, and 25 lines of script |
| `src/attestql/audit/cli.py` | the `report` parser, the `report()` status function, the dispatch |
| `src/attestql/audit/smells.py` | `probe_meanings()` |
| `src/attestql/audit/postgres.py` | `session_preconditions()` |
| `pyproject.toml`, `uv.lock` | Jinja2 `>=3.1.6,<4` with the comment saying why; package data |
| four new test files, one assertion in `tests/test_audit_end_to_end.py` | below |
| `docs/audit-command.md` | a `## The report command` section in the page's own voice |

## Decisions, and why

- **Subcommand, not a second console script.** `main` already dispatches on the subcommand, so
  the addition is a parser plus two lines; a script of its own would have meant a second entry
  point and a second `--version`. Stated in `attestql/report/cli.py`'s docstring, as the phase
  asked.
- **The direction of the import is audit to report, never the other way.** `attestql.report`
  imports the evidence package, Jinja2 and the standard library. The five file names it reads
  (`summary.json` and the four per-question files) are stated in `render.py` rather than
  imported from the audit: importing the writer's constants would put both drivers and both
  parsers behind a page. `tests/test_report_imports_no_engine.py` walks the graph.
- **The renderer computes two things and reads everything else.** The two are the SQL tokens the
  two statements differ in (`difflib` over a token split, marked so the eye lands there, stated
  on the page as a comparison of two texts) and each record's two hashes retaken. Verdict,
  mechanism, readings and probe meanings are the JSON's own strings, verbatim.
- **A per-cell type tag is shown where the rows of a column disagree on it.** The design spec
  says "where a cell's type differs from its column's declared type"; the cell's tag (`str`,
  `int`) and the declared type (`TEXT`, `INTEGER`) are two vocabularies, and mapping one to the
  other is engine knowledge a renderer that reads files must not have. Disagreement between rows
  is computable from the document and catches exactly the SQLite storage-class case.
- **The strip states the question set, not the database.** `db_id` is in no JSON the audit
  writes (it is a column of the printed line only), so the fixed title line is q id, question
  set, rule, verdict; the backend identity, which is what the record does state, is on the page
  under the run block and on every record. Phase 4 may want `db_id` in the summary; that is an
  audit change and out of this phase's scope.
- **Filter views are phase 3's.** Phase 1 renders the two page kinds its requirements name; the
  pre-rendered `not-equal/`, `by-mechanism/` and `by-probe/` paths belong to the site build, and
  the index carries the verdict, class and probe columns they will filter on.
- **The stylesheet is the token scale and the structural rules, and no design.** Tokens for both
  themes, the scroll region that keeps the page body from scrolling sideways, the focus ring,
  the two tints with their glyphs. Phase 2 owns typography, spacing, states and the measurements
  at three widths.

## Red-team findings this phase had to honour

- **A1** (records are unbounded, artifacts are not): no cap of the renderer's own. Every table
  names its source and its counts: "from counterexample.json, 1 row, up to 25 shown per side",
  "from evidence-gold.json, 1,022 rows". The record's full result is inside a disclosure.
- **A2** (hash verification is Python work, not browser work): `attestql.evidence.load`, and
  "recomputed from this JSON: match" beside every hash of every record on every page. A record
  changed after the audit wrote it shows both values instead; there is a test for each.
- **A3** (the forbidden-phrase test would fail on the product's own strings):
  `tests/test_report_copy_never_judges.py` strips the Jinja out of each template and searches
  what a template author typed. Its second half is the positive control: the two `reading`
  sentences that hold the forbidden words are asserted present on the rendered page.
- **B5** (states the table lacked): NOT_COMPARABLE lists `verdict.mismatched` by name;
  `projection_names_differ` renders its reading beside the two column lists; duplicate ids,
  unused prediction positions, missing and unreadable tables, a refused fixture measurement and
  tables the shuffle did not reach are run-page rows; a timed-out side is a run-page row with
  the bound the run was given beside it.
- **B6** (smaller items): `--out` defaults to the sibling `<audit-dir>-report/`; templates and
  static files are found with `Path(__file__)` and no `importlib`; the two public accessors are
  in; the mechanism chip is a `button`.

## Tests

| File | What it observes |
| --- | --- |
| `tests/test_report_renders_an_audit_directory.py` | 14 tests over `attestql demo`, parsed with `html.parser`: the run page's counts against `summary.json`, the digests, the index and its links; a comparison page's two statements, verdict, rule, mechanism, both differing-rows sections, both published readings, both hashes and its four JSON links, present as files; a gold-only page's record and its probes in all three states; an ERROR question as a row with no page; a timed-out side with the bound; escaping of a statement holding `<script>`; a tampered record stating both hashes; byte-identical output on a second render; the default `--out`; the refusal and its status; the two accessors |
| `tests/test_report_copy_never_judges.py` | the forbidden phrases over each template's literals, and the positive control |
| `tests/test_evidence_load_round_trips.py` | every record of both sandboxes re-hashes to its `result_hash` and its `record_hash` (10 on SQLite, the PostgreSQL sandbox's under the `sandbox` marker); an unknown type tag is refused |
| `tests/test_report_imports_no_engine.py` | the import graph: no driver, no parser, one dependency outside the standard library |
| `tests/test_audit_end_to_end.py` | one added test: the PostgreSQL sandbox's own directory renders, one page per directory |

`just check`: green (lint, pyright strict, repocheck, markdownlint and cspell, 933 passed and 33
skipped, the Docker sandbox's 33, the SQLite sandbox's 50).

## Acceptance

Plan criteria 1, 2, 6 and 7 met. Criterion 1's shapes: PostgreSQL and SQLite (both sandboxes),
prediction mode and gold-only (the demo and the error run), ERROR and timed-out entries, probes
marked not applicable. The phase's Validation section: `just check` green including pyright
strict over the new package; the committed spike directory
`plans/reports/spike-260902-three-gold-defects/` is refused with the reason it holds no
`summary.json`, which is what the phase says to expect of it and is not a failure.

## Left for the phases that follow

- Design: everything in the design spec beyond the token scale, measured at 360, 768 and
  1280 px (phase 2).
- Pre-rendered filter paths, the landing and the method page (phase 3); the method page is what
  the two accessors were added for.
- `db_id` reaches no JSON file, so no page can state the database a question is about by that
  name. If the site wants it, the audit has to write it; that is an audit change, not a
  renderer one.
- The record's full result is rendered row for row, as the plan states. A 10,000-row record is
  a large page; phase 4's budgets are derived from a dry run, and this is the term that
  dominates them.
