# L3: more public BIRD dev prediction files, credited-but-NOT_EQUAL across systems

<!-- cspell:ignore minidev birdenv CodeS hoangle RUCKB LHTB -->

You are a research worker on AttestQL, a CLI that replays a text-to-SQL gold against a database
and reports where a second statement disagrees with it. This lane is read-only measurement: it
changes no product code, posts nothing upstream, asks no human anything. Decide, state the
assumption in the report, continue.

## Question

Register row A37 measured prediction mode on BIRD dev with the only two dev prediction files
BIRD itself published, both GPT-3.5-turbo: of the 899 predictions BIRD credits, 90 (10.0 %) are
NOT_EQUAL under the typed comparison. Widen it: which other public BIRD dev prediction files
exist under a clear licence, and across those systems, how many credited predictions are
NOT_EQUAL and by what mechanism, and how many credits move when the 2025-11-06 gold replaces
the 2024-06-27 one.

Known before you start: `RUCKBReasoning/codes` (Apache-2.0) ships eight files under `results/`,
`predict_dev-codes-{1b,3b,7b,15b}-bird.json` and the same four `-with-evidence`. The coordinator
looked at CHESS, OmniSQL, MAC-SQL, DTS-SQL, XiYan-SQL, NL2SQL360, SQL-R1, E-SQL, MAG-SQL, RSL-SQL,
TA-SQL, N-rep, Middleware, NL2SQL-Benchmark, LHTB, ontology2sql without finding a dev prediction
file by a quick path grep; a real look at each may find one. A repository with no LICENSE file
(OmniSQL, MAC-SQL, E-SQL, TA-SQL, Middleware) is not usable; record it and move on.

## Environment

macOS 25.5 (darwin), 18 GB RAM shared with a second lane. Python 3.13 is `python3` (no
`python`), `uv`, `just`, Node 24 via nvm, `gh` authenticated as the owner's personal account
(read-only use: `gh api`, `gh search code`). SQLite is the 3.53.4 that Python links. Timezone
Asia/Saigon. Never more than three SQLite processes at once in total for this lane. A timeout is rerun
once, alone; one that survives that rerun is final. Expect q518 (`card_games`) and q701
(`codebase_community`) on the gold side, and a few predictions of their own.

Your worktree is an Orca child of the main checkout, branched from `main`; work only inside it
and inside `MEASURE_WORK`. Never touch `/Users/hoangle/Desktop/code/attestql` itself.

## Inputs, read-only, never write into this directory

`~/.cache/attestql-measure/inputs/` (`SHA256SUMS` beside them): `dev/dev_20240627/dev.json`
(1,534 entries, sha256 `630272f2…`), `dev/dev_20240627/dev_databases/<db_id>/<db_id>.sqlite`
(the eleven databases of `dev.zip`, `cdd6d19f…`; every run uses these), `dev_20251106.json`
(BIRD's 2025-11-06 pass, `ffd80183…`).

Set `MEASURE_WORK=~/.cache/attestql-measure/l3` and
`ATTESTQL_INPUTS=~/.cache/attestql-measure/inputs`. The earlier scripts read fixed relative
paths, so make exactly these links inside `MEASURE_WORK`: `data/dev/dev_20240627` to
`$ATTESTQL_INPUTS/dev/dev_20240627`, `data/dev/dev_databases` to
`$ATTESTQL_INPUTS/dev/dev_20240627/dev_databases`, and
`data/hf/dev_20251106-00000-of-00001.json` to `$ATTESTQL_INPUTS/dev_20251106.json`.
Prediction files you download go under `$MEASURE_WORK/data/preds/` with a
`SHA256SUMS.predictions`. The inputs directory is read-only at the filesystem level: BIRD's own evaluator opens a
database read-write, and the permission is what stops it. Do not change its mode. Install the tool once from your worktree:
`uv venv "$MEASURE_WORK/venv" --python 3.13 && uv pip install --python "$MEASURE_WORK/venv/bin/python" <worktree>`,
then `ATTESTQL="$MEASURE_WORK/venv/bin/attestql"`.

## Read first, in the worktree

- `docs/audit-command.md`: flags, the prediction file formats (`--predictions-keyed-by
  position` for BIRD-shaped files, the entry that holds no statement since 0.2.1).
- `plans/reports/measurement-260907-1435-bird-dev-sqlite.md`, section "Prediction mode": the
  measurement this lane widens; copy its table.
- `plans/reports/bird-dev-sqlite-260907/`: `run_predictions.sh`, `predictions_readable.py`,
  `bird_ex_official.py` (BIRD's own `evaluation.py` from `AlibabaResearch/DAMO-ConvAI` commit
  `dec31ae3`, run unmodified in its own `birdenv` with `func_timeout`), `measure_predictions.py`,
  `question_ids.py`, `rerun_timeouts.sh`, `reproduce.sh`.
- `plans/reports/prediction-mode-260904-real-predictions/classify.py` and
  `minidev-sqlite-260907/classify.py`: the hand-classification rule and sample rule used before.
- `docs/claims-register.md` rows A16, A17, A29, A30, A37.

## Method

1. **Hunt.** Search GitHub (`gh search code`, `gh api` trees) and Hugging Face for BIRD dev
   prediction files: 1,534 entries, dev question order or dev ids, SQL text. For each candidate
   record repository, commit, path, licence (SPDX from the repository and from any per-file
   notice), file format, sha256, and whether the entries are positional or keyed. Take every file
   under a licence that permits redistribution of a derived measurement (MIT, Apache-2.0, BSD,
   CC-BY family); refuse the rest and say why. Stop hunting after the CodeS eight plus whatever
   two hours of search find (GitHub code search allows 10 requests a minute); list what was
   searched in `sources.json`. **Pairing is an assertion, per file.** The CodeS files are 1,534
   strings keyed `"0"` to `"1533"`, each ending in `\t----- bird -----\t<db_id>`, and that
   `db_id` equals `dev.json`'s at every position: check it for every file read by position. A
   file without the suffix needs another witness that it answers this dev order (the tool's
   error rate by database, or ids in the file) or is refused; without this a shifted file yields
   a wrong number silently.
2. **Read as shipped.** Some files hold an entry that is no statement (a `0`, an empty string,
   a "SELECT" with a `\t----- bird -----\tdb_id` suffix as BIRD's own files do); record every
   such position per file the way `predictions_readable.py` does, and let the tool's own
   handling (one error line per such entry) do the rest.
3. **Run.** For each file and each copy of the gold (2024-06-27, 2025-11-06): prediction mode,
   one run per database with `--ids`, `--engine sqlite`, the origin and date flags as
   `run_predictions.sh` states them, the default 30 s budget, three processes at a time, every
   timeout rerun alone. Then BIRD's own `evaluation.py` unmodified on the same file and gold in
   `birdenv`. Per (file, copy): compared, EX=1, EX=0, ERROR by side and step, BIRD's own score,
   agreement of the tool's `bird_ex` reading with BIRD's evaluator on all 1,534, and EX=1 and
   NOT_EQUAL by mechanism (`multiplicity`, `type`, `order`, `truncation`, `other`, the names the
   tool writes in `summary.json` under `credited_but_not_equal.by_mechanism`) with the
   `test_suite_ex` reading beside it; the per-question readings live in
   `q<id>/counterexample.json`, written only for a NOT_EQUAL or a fired probe.
   `prediction-measurement.json`.
4. **Credits that move with the gold.** Per file: predictions credited on one copy and not the
   other, both directions, with ids; how many of those ids are among the 399 rewritten golds
   (`measure.py` of the earlier artifact holds the normalisation and the split).
   `credits-moved.json`.
5. **Hand sample.** Over all credited-but-NOT_EQUAL rows, a stated sample of 50 (ordered by
   file and id, every k-th): wrong answer the benchmark credited, harmless, the tool's rule
   alone, one sentence each; `classification.json`, the rule in `classify.py`.
6. **Report** `plans/reports/research-260907-HHMM-dev-predictions-across-systems.md` (HHMM
   the Asia/Saigon time you write it), under 150 lines, 100-column wrap: the files found and
   refused with licences; the per-file table on both copies; agreement with BIRD's evaluator;
   the credited-but-NOT_EQUAL share per system and pooled, against A37's 10.0 %; the credits
   moved by the gold change; the hand sample; "Unresolved questions"; last section "What changes
   in AttestQL" (which numbers belong in the register beside A37, and any file shape the tool
   could not read as shipped).

## Artifact and rules

- `plans/reports/research-260907-dev-predictions-across-systems/`: every script,
  `sources.json`, `SHA256SUMS.predictions`, `prediction-measurement.json`,
  `credits-moved.json`, `classification.json`, the per-run `summary.json` copies under `tool/`,
  BIRD's evaluator outputs under `official/`, a `reproduce.sh` that takes `MEASURE_WORK` and
  `ATTESTQL_INPUTS` from the environment, downloads only what is absent from the inputs and
  each prediction file by URL, verifies every sha256 and regenerates all of it.
- Every number in the report comes from one of those JSON files. No BIRD file and no
  prediction file is committed: they are cited by URL, commit and sha256.
- Scripts pass `uv run ruff check plans` and `uv run ruff format --check plans` (pre-commit
  lints `plans/**/*.py`; SQL built from strings carries `# noqa: S608` as the earlier scripts
  do). The report passes `just docs` (markdownlint and cspell over `plans/**/*.md`; words cspell
  does not know go in a `<!-- cspell:ignore ... -->` comment at the top, as the existing reports
  do) and `just repocheck`: no em dash, en dash or numero sign anywhere in a `.md` or `.py`
  (write a hyphen or a comma), every link in the report resolves, the ADR index is untouched.
- No change under `src/`, `tests/`, `docs/`, `tools/`. A tool bug you hit, or a file the tool
  cannot read as shipped, is a paragraph in the report, not a fix.
- Commit on your branch with conventional commits and no AI reference; do not push, do not
  merge. Run `just docs`, `just repocheck` and the two ruff commands before the final commit.
- At each checkpoint run
  `orca worktree set --worktree active --comment "<checkpoint>"`: hunt done (N files),
  runs done, sample done, report committed and gate green, or blocked.

## End your last message with

```text
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Summary: one or two sentences with the headline numbers
Concerns/Blockers: optional
```
