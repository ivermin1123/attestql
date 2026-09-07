# L1: BIRD's 399 rewritten dev golds, what changed in the answer and what changed in the SQL

<!-- cspell:ignore minidev sqlglot crosstab hoangle -->

You are a research worker on AttestQL, a CLI that replays a text-to-SQL gold against a database
and reports where a second statement disagrees with it. This lane is read-only measurement: it
changes no product code, posts nothing upstream, asks no human anything. Decide, state the
assumption in the report, continue.

## Question

BIRD rewrote 399 of its 1,534 dev golds in the 2025-11-06 pass. The gold-only probes fire on 31
of the 399 on the old copy (register row A35), and the report that measured it guessed that the
368 others are "about what the question means". Measure instead: on dev.zip's own data, how
many of the 399 rewrites change the answer at all, in what way, what changed in the SQL, and
which of those changes a probe that reads only the gold and the data could see in principle.

## Environment

macOS 25.5 (darwin), 18 GB RAM shared with a second lane. Python 3.13 is `python3` (no
`python`), `uv`, `just`, Node 24 via nvm. SQLite is the 3.53.4 that Python links. Timezone
Asia/Saigon. Never more than three SQLite processes at once in total for this lane. A timeout is rerun
once, alone; one that survives that rerun is final. Expect three: q518 (`card_games`) and q701
(`codebase_community`) on the 2024 golds, and the 2025-11-06 rewrite of q1131
(`european_football_2`).

Your worktree is an Orca child of the main checkout, branched from `main`; work only inside it
and inside `MEASURE_WORK`. Never touch `/Users/hoangle/Desktop/code/attestql` itself.

## Inputs, read-only, never write into this directory

`~/.cache/attestql-measure/inputs/` (`SHA256SUMS` beside them):

- `dev/dev_20240627/dev.json`: 1,534 entries, the 2024-06-27 copy (sha256 `630272f2…`).
- `dev/dev_20240627/dev_databases/<db_id>/<db_id>.sqlite`: the eleven databases of `dev.zip`
  (`cdd6d19f…`). Every run in this lane uses these.
- `dev_20251106.json`: 1,534 entries, BIRD's 2025-11-06 pass, dataset `birdsql/bird_sql_dev_20251106`
  commit `3c11fb19` (sha256 `ffd80183…`).

Set `MEASURE_WORK=~/.cache/attestql-measure/l1` and
`ATTESTQL_INPUTS=~/.cache/attestql-measure/inputs`. The earlier scripts read fixed relative
paths, so make exactly these links inside `MEASURE_WORK`: `data/dev/dev_20240627` to
`$ATTESTQL_INPUTS/dev/dev_20240627`, `data/dev/dev_databases` to
`$ATTESTQL_INPUTS/dev/dev_20240627/dev_databases`, and
`data/hf/dev_20251106-00000-of-00001.json` to `$ATTESTQL_INPUTS/dev_20251106.json`.
The inputs directory is read-only at the filesystem level: BIRD's own evaluator opens a
database read-write, and the permission is what stops it. Do not change its mode. Install the tool once from your worktree:
`uv venv "$MEASURE_WORK/venv" --python 3.13 && uv pip install --python "$MEASURE_WORK/venv/bin/python" <worktree>`,
then `ATTESTQL="$MEASURE_WORK/venv/bin/attestql"`.

## Read first, in the worktree

- `docs/audit-command.md`: flags, the question and prediction file formats, what the output
  directory holds.
- `plans/reports/measurement-260907-1435-bird-dev-sqlite.md`: the report this lane extends;
  copy its shape.
- `plans/reports/bird-dev-sqlite-260907/`: `measure.py` holds the normalisation that splits the
  two copies into 399 rewritten, 172 text-only, 963 unchanged; `question_ids.py`, `run_tool.sh`
  and `rerun_timeouts.sh` show one run per database with `--ids`, three at a time, timeouts rerun
  alone; `gold-only-old.json` lists which golds fired which probe on the old copy;
  `check_inputs.py` the digests.
- `docs/claims-register.md` rows A34 to A37.

## Method

1. **Split.** Reuse the normalisation from `measure.py`; write `split.json` with the three id
   lists and assert 399 / 172 / 963. A different count is a stop: report it, do not continue.
2. **Replay the rewrite as a prediction.** The question file is the old `dev.json`; the
   predictions file is the 2025-11-06 SQL keyed by question id (`{"<id>": "<sql>", ...}`), built
   for the 399 ids. One run per database (`--engine sqlite`, `--dsn` and `--data-file` the
   database, `--ids` the 399 ids that fall on that database, `--questions-origin`,
   `--questions-date`, `--predictions-origin`, `--predictions-date`, `--data-origin`,
   `--data-date` as the earlier scripts state them), the default 30 s statement budget, three
   processes at a time, a timeout rerun once alone. Record per id in `verdicts.json`: EQUAL or
   NOT_EQUAL, the mechanism the tool names (`multiplicity`, `type`, `order`, `truncation`,
   `other`), `mechanism.multiset_equal`, the `bird_ex` and `test_suite_ex` readings, and for an
   error which side failed and how (parse, execute, timeout). The per-question readings live in
   `q<id>/counterexample.json` of the run directory, written only for a NOT_EQUAL or a fired
   probe; an EQUAL question has no directory and both readings are 1 by construction. The replay
   rule is the old gold's (R-ORD when it orders, R-SET otherwise), so a rewrite that adds or
   drops ORDER BY is judged under the old rule; say so in the report. Prediction mode reruns the
   gold-only probes on the 399: assert the fires equal `gold-only-old.json` (the shuffle is
   seeded) and report any drift. Run the 172 text-only ids the same way as a harness check,
   `--ids` their share per database: their SQL is unchanged, so expect 171 EQUAL and q701 an
   error line (its gold takes 192 s alone); any other verdict is a finding about the run, not
   the gold. In the 399, q1131's rewrite is a prediction-side timeout and stays one.
3. **Diff the SQL.** With the `sqlglot` the venv holds (record its version), dialect `sqlite`,
   parse both statements of each of the 399 (record any that fail). Classify what changed at
   clause level: projection, DISTINCT, tables in FROM, JOIN condition, WHERE, GROUP BY, HAVING,
   ORDER BY key, ORDER BY direction only, LIMIT or OFFSET, aggregate function, CAST or type,
   subquery or CTE shape, whole rewrite (tables differ or more than three clauses differ).
   `sqlglot.diff` or a per-clause canonical comparison, your choice; write the rule in the script,
   keep the full set of touched clauses per id and one primary class by a stated precedence.
   `ast-diff.json`.
4. **Cross-tabulate** result class from step 2 against primary SQL class from step 3, and mark
   in each cell how many of the ids fired a probe per `gold-only-old.json` (31 expected in
   total). `crosstab.json`, and the table in the report.
5. **Read a sample by hand.** For each SQL class, up to 8 ids (sorted, every k-th so the sample
   is stated; at most 13 classes of 8, 104 readings): read question, evidence, both statements and the two results. Record in
   `readings.json` one of: semantic (the rewrite changes what is asked, or fixes the SQL to what
   the question asked), structural (a defect visible without the question: DISTINCT missing, a
   cut at a tie, an ungrouped column beside an aggregate, a join key, a direction the data shows
   as a tie), cosmetic (same rows), and one sentence why. Give per class an estimate of the share
   a gold-only check could catch, with the reason.
6. **Report** `plans/reports/research-260907-HHMM-bird-rewrites-what-changed.md` (HHMM the
   Asia/Saigon time you write it), under 150 lines, 100-column wrap: inputs by URL and sha256;
   the headline (N of 399 give the same answer on this data: verdict EQUAL or
   `mechanism.multiset_equal` true for the multiset reading, `bird_ex` 1 for the set reading;
   M differ, by mechanism; errors by side, the three timeouts named); the crosstab; the 31 fires against the
   classes; the hand readings; candidate gold-only checks with the count of rewrites each would
   have caught and which need the question; "Unresolved questions"; last section "What changes
   in AttestQL" (what A35's "miss 368" should say instead, which candidates are worth building,
   with numbers).

## Artifact and rules

- `plans/reports/research-260907-bird-rewrites/`: every script, `split.json`, `verdicts.json`,
  `ast-diff.json`, `crosstab.json`, `readings.json`, the per-database `summary.json` copies
  under `tool/`, and a `reproduce.sh` that takes `MEASURE_WORK` and `ATTESTQL_INPUTS` from the
  environment, downloads only what is absent from the inputs, verifies every digest and
  regenerates all of it (copy the earlier `reproduce.sh` pattern).
- Every number in the report comes from one of those JSON files. No BIRD file is committed:
  no question file, no database, no SQL dump.
- Scripts pass `uv run ruff check plans` and `uv run ruff format --check plans` (pre-commit
  lints `plans/**/*.py`; SQL built from strings carries `# noqa: S608` as the earlier scripts
  do). The report passes `just docs` (markdownlint and cspell over `plans/**/*.md`; words cspell
  does not know go in a `<!-- cspell:ignore ... -->` comment at the top, as the existing reports
  do) and `just repocheck`: no em dash, en dash or numero sign anywhere in a `.md` or `.py`
  (write a hyphen or a comma), every link in the report resolves, the ADR index is untouched.
- No change under `src/`, `tests/`, `docs/`, `tools/`. A tool bug you hit is a paragraph in the
  report, not a fix.
- Commit on your branch with conventional commits and no AI reference; do not push, do not
  merge. Run `just docs`, `just repocheck` and the two ruff commands before the final commit.
- At each checkpoint run
  `orca worktree set --worktree active --comment "<checkpoint>"`: inputs verified, replay done,
  diff and crosstab done, readings done, report committed and gate green, or blocked.

## End your last message with

```text
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Summary: one or two sentences with the headline numbers
Concerns/Blockers: optional
```
