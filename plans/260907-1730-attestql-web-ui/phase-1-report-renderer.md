# Phase 1: `attestql report`, the renderer

## Context

The audit writes `summary.json` at the run root and, per question, `counterexample.json`,
`evidence-gold.json`, `evidence-second.json` and `smells.json` (gold-only: the gold record and
the smells). Their layouts are in `src/attestql/audit/compare.py` (`counterexample_json`),
`src/attestql/audit/smells.py` (`smells_json`) and `src/attestql/audit/cli.py` (`_summary_json`).
This phase turns a directory of them into HTML. It reads the JSON as a reader would, through the
format strings, and never imports the audit's in-memory types, so a page can be rendered from a
directory produced by another machine.

## Requirements

- Starts from `5e156d7` or later: the `demo` subcommand is in `cli.py` and the sandbox data is
  in `attestql.demo`. New subcommand `attestql report <audit-dir> --out <dir>` beside `audit`
  and `demo`; `--out` defaults to the sibling `<audit-dir>-report/`, never inside the audit
  directory, whose rerun cleanup would leave a stale report beside a fresh run. Refuses a
  directory without `summary.json` and states why. Exit 0 on success, 2 on a tool error.
- Renders `index.html` (the run page) and `q<id>/index.html` per question directory, copies or
  links the JSON beside each page, and writes one stylesheet and one script file once.
- Handles every question shape: comparison (counterexample present), gold-only (record and
  smells), and the ERROR and timed-out entries the summary lists without a directory (confirmed:
  a `SideFailed` question is counted and printed and never reaches `_write_question`).
- Handles both engines by reading the record: a PostgreSQL record states the seven session
  preconditions; a SQLite record states none and its columns carry storage classes.
- Jinja2 as a dependency of the package (owner's decision 2026-09-07), pinned by range like
  `psycopg`, with a comment stating why it is there.
- `attestql.report` imports only the standard library, Jinja2 and `attestql.evidence`; a test
  walks its import graph and fails on `psycopg`, `postgast` or `sqlglot`, so the renderer stays
  runnable where no engine is (phase 5).
- Deterministic output: rendering the same directory twice yields byte-identical files.
- `attestql.evidence.load`: a record's JSON back to an `ExecutionResult` and its descriptor
  (`dec` to `Decimal`, `ts` and `date` through `fromisoformat`, columns, `truncated`), so that
  `result_digest` can be recomputed from the file. Every record on every page carries
  "recomputed from this JSON: match" or the two differing values. `record_hash` is recomputed
  the same way (sorted keys, the key removed).
- Templates and static files are located with `Path(__file__)`; `tests/test_boundary.py`
  forbids `importlib` beyond `importlib.metadata`.
- Two public accessors, one in `smells.py` for the probe meanings (now `_MEANS`) and one in
  `postgres.py` for the seven preconditions, so the method page of phase 3 imports nothing
  private.

## Files

- `src/attestql/report/__init__.py`, `src/attestql/report/render.py` (load JSON, build the view
  model, render), `src/attestql/report/cli.py` (argument parsing, wired into
  `attestql.audit.cli:main` as a subcommand or as a second console script; pick whichever the
  existing `main` makes smaller, and state the choice in the module docstring).
- `src/attestql/report/templates/`: `base.html`, `run.html`, `question.html`, partials for the
  verdict strip, the statement pair, the rows table, the probes, the record, the rerun block.
- `src/attestql/report/static/report.css`, `src/attestql/report/static/report.js` (token
  highlight, strip condense, disclosure; the page is complete without it).
- `pyproject.toml`: the Jinja2 dependency, package data for templates and static files.
- `tests/test_report_renders_an_audit_directory.py`, `tests/test_report_copy_never_judges.py`,
  `tests/test_evidence_load_round_trips.py` (every result of both sandboxes loads and re-hashes
  to its recorded `result_hash`; every record to its `record_hash`).

## Steps

1. Write the view model as plain dataclasses built from the JSON dictionaries, one per page. No
   caps of its own: the artifacts are bounded already (`ROWS_IN_ARTIFACT` 25, a bounded
   difference, `ROWS_IN_EVIDENCE` 10), so the model carries `rows_shown`, `row_count`,
   `rows_shown_per_side` and `truncated` through and the template states them.
2. Write the templates in the order the design spec fixes for the question page; no styling
   yet beyond the token names as class hooks.
3. Wire the subcommand and the dependency.
4. Tests, structural, using `html.parser` from the standard library: the run page names the
   format strings, the digests and the counts from `summary.json`; a comparison page holds both
   statements, the verdict, the rule, the mechanism, the two differing-rows sections with their
   labels, BIRD's reading, the test-suite reading, both hashes and the four JSON links; a
   gold-only page holds the record and the probes with `fired`, quiet and not-applicable each
   rendered; an ERROR question is listed on the run page with its side and message.
5. Fixture: `attestql demo --out` (the packaged SQLite sandbox, `attestql.demo`) runs without
   a container, so the renderer tests render its output; the PostgreSQL sandbox test in
   `tests/test_audit_end_to_end.py` gains one assertion that the same directory renders.
6. The forbidden-phrase test reads the template literals (see the design spec's copy rules; the
   JSON's own `reading` strings contain "wrong" and are not its subject).
7. Determinism test: render twice, compare bytes; the renderer reads no clock and writes no
   generation time.
8. Import-graph test as stated in the requirements.
9. `attestql.evidence.load`, its round-trip test, and the recomputed-hash line on the record
   partial.

## Validation

- `just check` green, including pyright strict over the new package.
- Rendering the committed spike directory `plans/reports/spike-260902-three-gold-defects/`
  is not required (it predates the format strings) and is documented as such.

## Risk and rollback

- Jinja2 autoescaping must be on for every template; SQL and engine messages are untrusted text.
  A test renders a statement containing `<script>` and asserts it is escaped.
- Rollback: delete `src/attestql/report/`, the dependency, the test files.
