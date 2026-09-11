# L2: the same golds on BIRD's two copies of the dev databases

<!-- cspell:ignore minidev satscores frpm CDSCode birdenv hoangle Kaggle -->

You are a research worker on AttestQL, a CLI that replays a text-to-SQL gold against a database
and reports where a second statement disagrees with it. This lane is read-only measurement: it
changes no product code, posts nothing upstream, asks no human anything. Decide, state the
assumption in the report, continue.

## Question

BIRD ships the eleven dev databases twice, inside `dev.zip` and inside `minidev.zip`, and five
of the eleven differ (register row A38): `formula_1`, `thrombosis_prediction` and `toxicology`
carry more rows in dev, `california_schools` and `european_football_2` share counts and differ
in one table each, 211 of 2,269 `satscores` CDS codes having lost a leading zero and `Player`
heights being REAL in dev and truncated integers in Mini-Dev. The owner reported the fact as
`mini_dev` issue 50. Measure what follows from it: how many dev and Mini-Dev gold answers depend
on which copy was downloaded, how many of BIRD's own Mini-Dev prediction scores flip with the
copy, and which copy of `california_schools` carries the right CDS codes.

## Environment

macOS 25.5 (darwin), 18 GB RAM shared with a second lane. Python 3.13 is `python3` (no
`python`), `uv`, `just`, Node 24 via nvm. SQLite is the 3.53.4 that Python links. Timezone
Asia/Saigon. Never more than three SQLite processes at once in total for this lane. A timeout is rerun
once, alone; one that survives that rerun is final. Expect the 2025-11-06 rewrite of q1131
(`european_football_2`) to time out on both copies.

Your worktree is an Orca child of the main checkout, branched from `main`; work only inside it
and inside `MEASURE_WORK`. Never touch `/Users/hoangle/Desktop/code/attestql` itself.

## Inputs, read-only, never write into this directory

`~/.cache/attestql-measure/inputs/` (`SHA256SUMS` beside them):

- `dev/dev_20240627/dev.json` (1,534 entries, sha256 `630272f2…`) and
  `dev/dev_20240627/dev_databases/<db_id>/<db_id>.sqlite`, the copy of `dev.zip` (`cdd6d19f…`).
- `minidev/minidev/MINIDEV/mini_dev_sqlite.json` (500 entries, `4ba5fa8d…`) and
  `minidev/minidev/MINIDEV/dev_databases/<db_id>/<db_id>.sqlite`, the copy of `minidev.zip`
  (`cc48ba16…`). Mini-Dev ids are dev ids.
- `mini_dev_sqlite_hf.json`: the Hugging Face copy of the Mini-Dev gold, dataset
  `birdsql/bird_mini_dev` commit `f65faf4a` (sha256 `88ceb071…`); the copy that corrects q879.
- `dev_20251106.json`: BIRD's 2025-11-06 pass of the dev golds (`ffd80183…`).

Set `MEASURE_WORK=~/.cache/attestql-measure/l2` and
`ATTESTQL_INPUTS=~/.cache/attestql-measure/inputs`. The earlier scripts read fixed relative
paths, so make exactly these links inside `MEASURE_WORK`: `data/dev/dev_20240627` to
`$ATTESTQL_INPUTS/dev/dev_20240627`, `data/dev/dev_databases` to
`$ATTESTQL_INPUTS/dev/dev_20240627/dev_databases`, `data/hf/dev_20251106-00000-of-00001.json`
to `$ATTESTQL_INPUTS/dev_20251106.json`, `data/zip/minidev` to
`$ATTESTQL_INPUTS/minidev/minidev`, and `data/hf/mini_dev_sqlite-00000-of-00001.json` to
`$ATTESTQL_INPUTS/mini_dev_sqlite_hf.json`; `check_inputs.py` takes the minidev databases from
`MINIDEV_DATABASES` (set it to `$ATTESTQL_INPUTS/minidev/minidev/MINIDEV/dev_databases`; its
default is an old work directory). The inputs directory is read-only at the filesystem level: BIRD's own evaluator opens a
database read-write, and the permission is what stops it. Do not change its mode. Install the tool once from your
worktree:
`uv venv "$MEASURE_WORK/venv" --python 3.13 && uv pip install --python "$MEASURE_WORK/venv/bin/python" <worktree>`,
then `ATTESTQL="$MEASURE_WORK/venv/bin/attestql"`.

## Read first, in the worktree

- `docs/audit-command.md`: flags, file formats, the output directory.
- `plans/reports/measurement-260907-1435-bird-dev-sqlite.md` (section "Inputs and method" and
  the last two sections) and `measurement-260907-1106-minidev-sqlite.md`: the reports this lane
  extends; copy their shape.
- `plans/reports/bird-dev-sqlite-260907/`: `check_inputs.py` and `inputs.json` (the 22 database
  digests and which tables differ), `question_ids.py`, `run_tool.sh`, `rerun_timeouts.sh`,
  `gold-only-old.json` (probe fires on dev.zip's copy, reuse rather than rerun).
- `plans/reports/minidev-sqlite-260907/`: `reproduce.sh` (the nine prediction files under
  `bird-bench/mini_dev` commit `b3d4bcbb` with `SHA256SUMS.predictions`, and BIRD's
  `evaluation_ex.py` and `evaluation_utils.py` at the same commit), `bird_ex_official.py`,
  `predictions_by_question_id.py`, `run_tool.sh`.
- `docs/claims-register.md` rows A29 to A38.

## Method

1. **Verify.** Digest all 22 database files; assert six pairs identical and five differing
   exactly as `inputs.json` says. Per differing database, row counts of every table in both
   copies: `tables.json`.
2. **Replay each gold on both copies.** Write `replay_pairs.py`: for every gold on the five
   differing databases, execute the statement on the dev copy and on the minidev copy through
   Python's `sqlite3` with the tool's envelope (`file:...?mode=ro` URI, `PRAGMA query_only`, a
   30 s deadline enforced by a progress handler), three processes at a time, timeouts rerun
   alone. Compare with two stated readings, both on the values as `sqlite3` returns them: BIRD's own
   (`set(rows) == set(rows)`) and the multiset of rows; and beside them a typed reading that
   counts a cell as different when `typeof` differs. Python's `==` makes `182 == 182.0`, and the
   `Player` heights differ in storage class on every one of the 11,060 rows of the two copies,
   so the typed count is what shows it; write the rule in `replay_pairs.py`. Class per id:
   identical multiset; same set, other multiplicities; different rows (row counts on each copy,
   and the first differing row); typed difference only; error or timeout on one copy. Three gold
   sets: `dev.json` (2024-06-27), `dev_20251106.json`, and the Hugging Face Mini-Dev gold; 700,
   700 and 237 golds fall on the five databases, about 3,300 executions; `pairs.json` per gold
   set.
3. **Probes per copy.** Run the tool gold-only on both copies of the five databases with the
   2024-06-27 golds (ten runs, `--ids` per database, the flags as `run_tool.sh` states them), at
   the worktree's own version, so a fire that differs is the copy and not the version;
   `gold-only-old.json`, measured at tree `6a43c01`, is the cross-check for the dev copy. Which
   golds fire on one copy and not the other: `smells-by-copy.json`.
4. **Prediction scores per copy.** BIRD's nine Mini-Dev SQLite prediction files scored by
   BIRD's own unmodified `evaluation_ex.py` (SQLite path; `evaluation_utils.py` imports
   `psycopg2` and `pymysql` at the top, so give it its own `birdenv` holding `psycopg2-binary`,
   `pymysql` and `func_timeout`, as the earlier `reproduce.sh` does) against the Hugging Face
   gold on the minidev copy (the shipped pairing) and on the dev copy: per file, how many of the
   500 positions (498 distinct ids) score differently and in which direction;
   `score-flips.json`. The earlier `bird_ex_official.py` hardcodes the minidev database
   directory, so copy it into the artifact with a database-directory argument; the earlier
   `official/hf/*.json` hold the shipped pairing's scores and are the cross-check. Take the files
   and digests from `reproduce.sh` and `SHA256SUMS.predictions`; verify before use.
5. **CDS codes.** Inside each copy, count `satscores.cds` values that match a `schools.CDSCode`
   and the ones that do not (`frpm.CDSCode` too); CDS codes are 14 digits, so the copy where
   211 rows stop joining is the one that lost the zero (expected: in the dev copy 211 of 2,269
   `satscores.cds` are 13 characters and 2,058 join `schools`; in the minidev copy all are 14
   and 2,269 join; `frpm` has fewer rows, so its join count differs by 162, not 211, and that
   is not a failed check): `cds.json`. Then try the California
   Department of Education's public school directory (start at
   `https://www.cde.ca.gov/ds/si/ds/pubschls.asp`, the tab-separated download); if it downloads,
   record URL, date and sha256, and check the 211 codes zero-padded against it; if the site
   refuses, say so and rest on the internal join count. List the dev and Mini-Dev golds whose SQL
   names both `satscores` and `schools` (or `frpm`), and whether their answers differ between
   copies (from step 2).
6. **Player heights.** List the `european_football_2` golds whose SQL names `height` as a word
   (13 expected; none writes `Player.height` literally, the column comes through an alias) and
   whether their answers differ between copies, by value and by type (`182.88` REAL in dev,
   `182` INTEGER in minidev). No source check (the origin dataset needs a Kaggle login); say so.
7. **Report** `plans/reports/research-260907-HHMM-two-database-copies.md` (HHMM the
   Asia/Saigon time you write it), under 150 lines, 100-column wrap: inputs by URL and sha256;
   per database and per gold set the golds whose answer depends on the copy, under both readings,
   with two or three examples; probes that fire on one copy only; the score flips per prediction
   file and in total; the CDS verdict; the heights; a section "For the owner: a follow-up to
   `mini_dev` issue 50" with the numbers and ids in draft text, one line per paragraph, not
   posted; "Unresolved questions"; last section "What changes in AttestQL" (the tool records the
   fixture digest already; say whether anything more is worth doing, with the numbers).

## Artifact and rules

- `plans/reports/research-260907-two-database-copies/`: every script, `tables.json`,
  `pairs.json` (three), `smells-by-copy.json`, `score-flips.json`, `cds.json`, the
  `summary.json` copies under `tool/`, BIRD's evaluator outputs under `official/`, and a
  `reproduce.sh` that takes `MEASURE_WORK` and `ATTESTQL_INPUTS` from the environment,
  downloads only what is absent from the inputs, verifies every digest and regenerates all of
  it (copy the earlier pattern).
- Every number in the report comes from one of those JSON files. No BIRD file is committed:
  no question file, no prediction file, no database, no evaluator source.
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
  scores done, CDS done, report committed and gate green, or blocked.

## End your last message with

```text
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Summary: one or two sentences with the headline numbers
Concerns/Blockers: optional
```
