# L4: Spider 1.0 dev on SQLite, the gold-only probes and Spider's own 2020 corrections

<!-- cspell:ignore sqlglot hoangle Bkyl Mohammadreza Pourreza DAIL tvshow RUCKB -->

You are a research worker on AttestQL, a CLI that replays a text-to-SQL gold against a database
and reports where a second statement disagrees with it. This lane is read-only measurement: it
changes no product code, posts nothing upstream, asks no human anything. Decide, state the
assumption in the report, continue.

## Question

Everything the tool has measured so far is BIRD (Mini-Dev and dev). Spider 1.0 dev is the other
SQLite benchmark: 1,034 questions over 20 databases, golds written in another style (double
quoted string literals, `t1`/`t2` aliases, no evidence text). Measure whether the tool reads
Spider at all, what the gold-only probes fire on, and their recall against Spider's own
correction of 2020-06-07 (commit `25fcd85d` of `taoyds/spider`, "corrected some annotation
errors and label mismatches, ~4 % of dev examples"), the way A35 measured recall against BIRD's
2025-11-06 pass.

## Environment

macOS 25.5 (darwin), 18 GB RAM shared with a second lane. Python 3.13 is `python3` (no
`python`), `uv`, `just`, Node 24 via nvm, `gh` authenticated as the owner's personal account
(read-only use). SQLite is the 3.53.4 that Python links. Timezone Asia/Saigon. Never more than three SQLite processes at once in total for this
lane. A timeout is rerun once, alone; one that survives that rerun is final (Spider statements
are fast: `world_1`'s 120 golds take 0.17 s of statement time together).

Your worktree is an Orca child of the main checkout, branched from `main`; work only inside it
and inside `MEASURE_WORK`. Never touch `/Users/hoangle/Desktop/code/attestql` itself.

## Inputs, read-only, never write into this directory

`~/.cache/attestql-measure/inputs/`:

- `spider_data.zip` (sha256 `00636695…`, 206 MB, Google Drive file id
  `1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J` linked from `https://yale-lily.github.io/spider`, file
  dated 2024-09-12, licence CC BY-SA 4.0): `spider_data/dev.json` (1,034 entries with `db_id`,
  `query`, `question`), `spider_data/dev_gold.sql` (one `SQL<tab>db_id` per line, same order),
  `spider_data/database/<db_id>/<db_id>.sqlite` (the dev databases are among them),
  `spider_data/tables.json`. Unpack it into `MEASURE_WORK`, not here.
- `spider-2020/dev.sql.before` (sha256 `6d3ac4f5…`, `evaluation_examples/dev.sql` at the parent
  commit `e0b7bc91`) and `spider-2020/dev.sql.after` (`36e8c72e…`, the same file at `25fcd85d`):
  1,034 blocks of `Question N: <text> ||| <db_id>` and `SQL: <text>`. 49 lines differ, 28 of
  them `SQL:` lines and 21 `Question` lines. Re-fetch both through
  `gh api "repos/taoyds/spider/contents/evaluation_examples/dev.sql?ref=<sha>" --header "Accept: application/vnd.github.raw+json"`
  in `reproduce.sh` and verify the digests. The "~4 % of dev examples updated" wording is the
  Spider site's news line; the commit message itself (2020-06-08) says "corrected annotated
  errors/mismatches"; cite each as what it is.

Set `MEASURE_WORK=~/.cache/attestql-measure/l4` and
`ATTESTQL_INPUTS=~/.cache/attestql-measure/inputs`. The inputs directory is read-only at the filesystem level: BIRD's own evaluator opens a
database read-write, and the permission is what stops it. Do not change its mode. Install the tool once
from your worktree:
`uv venv "$MEASURE_WORK/venv" --python 3.13 && uv pip install --python "$MEASURE_WORK/venv/bin/python" <worktree>`,
then `ATTESTQL="$MEASURE_WORK/venv/bin/attestql"`.

## Read first, in the worktree

- `docs/audit-command.md`: flags, the question file format (BIRD's: `question_id`, `db_id`,
  `question`, `evidence`, `SQL`), the output directory.
- `plans/reports/measurement-260907-1435-bird-dev-sqlite.md`: the recall design this lane
  repeats (sections "Gold-only", "Recall against BIRD's own rewrite", the hand reading of the
  fires); copy its shape.
- `plans/reports/research-260904-sqlite-before-backend.md` and
  `plans/reports/parser-260905-sqlglot-sqlite-reading.md`: how the tool reads SQLite SQL and
  what it refuses; the double-quoted literal is named there as a risk seen once in BIRD.
- `plans/reports/bird-dev-sqlite-260907/`: `run_tool.sh`, `rerun_timeouts.sh`,
  `question_ids.py`, `measure.py`, `classify.py`.
- `docs/claims-register.md` rows A34 to A36 and the non-claim table.

## Method

1. **Question file.** Build a BIRD-shaped question file from `dev.json`: `question_id` the
   0-based index, `evidence` empty, `SQL` the `query`. Assert `dev_gold.sql` line `i` equals
   entry `i`'s `query` and `db_id` (state the normalisation if whitespace differs). Record the
   20 dev `db_id`s and that each has a database file; `inputs.json` with every digest.
2. **The correction set.** Parse `dev.sql.before` and `dev.sql.after` into 1,034 (question,
   db_id, SQL) triples by their `Question N` number. `Question N` is `dev.json` index N-1: align by index, and
   check the alignment by SQL and question text (normalised: case, whitespace, quotes); report
   the match count, and any entry whose 2024 text differs from the 2020 `after` text (later
   edits). The **correction set** is the entries whose `SQL:` line changed (28 lines, so up to 28
   entries; count them); the text-only set the entries whose `Question` line alone changed
   (five blocks change both lines, so expect 16). `corrections.json` with the before and after
   SQL per entry.
3. **Two passes, as shipped and transformed.** The tool does not refuse Spider golds: a
   smoke run at 0.2.2 audited `concert_singer` (45 golds, five with INTERSECT or EXCEPT) and
   `world_1` (120 golds, 86 of them double-quoted) with zero errors, because sqlglot reads
   `"France"` as an identifier and the linked SQLite runs it as a literal. What is unmeasured is
   whether that misreading moves a probe, the replay rule, or the shuffle's table set. So: run
   the tool gold-only, one run per database with `--ids`, `--engine sqlite`, origin and date
   flags stated, the default 30 s budget, over (a) the current golds and (b) the `before` SQL
   substituted in for the 28 corrected ids only; count refusals by reason from the summaries
   (expect about none). Then count the golds carrying a double-quoted token that is no column
   or table name of that database (`tables.json`; expect 213 of 1,034, `world_1` 86 of 120,
   `flight_2` 56 of 80, `tvshow` 26 of 62, `cre_Doc_Template_Mgt` 20 of 84) and run a second
   pass on exactly those golds with a stated transformation, in a script: such a token becomes a
   single-quoted literal. Report both passes, never only the transformed one, and the deltas
   between them per gold (verdict, replay rule, probes fired, tables the shuffle covered) as the
   finding; never change the tool.
4. **Gold-only fires.** Per probe, per pass: how many golds fire, over how many audited;
   `gold-only.json`. The direction probe stays off (`--experimental-s2` not given).
5. **Recall.** Of the correction set, how many `before` golds fire at least one probe, against
   the text-only set and the untouched golds (the base rate); and how many of those stop firing
   with the `after` SQL. Same table as A35. `recall.json`.
6. **Hand reading.** Every fire on a gold Spider did not correct, up to 40 (if more, a stated
   sample, every k-th by id): wrong, harmless, the tool's rule, one sentence each, against the
   question and the data; `classification.json`, the rule in `classify.py`. Also the 28
   corrections themselves: for each, did the `before` and `after` SQL return the same rows on
   the database (replay both through `sqlite3` with the tool's envelope: `mode=ro`,
   `PRAGMA query_only`, a 30 s deadline); `corrections-replayed.json`.
7. **Prediction mode, bounded.** Spend at most one hour looking for one public Spider dev
   prediction file (1,034 statements, dev order) under MIT, Apache-2.0, BSD or CC-BY; CodeS
   (`RUCKBReasoning/codes`, Apache-2.0) ships `results/pred_sqls-codes-{1b,3b,7b,15b}-spider.txt`,
   1,034 lines of one SQL each in dev order, the first lines matching `dev.json`: take one of
   them first (convert to `{"<index>": sql}` and record the commit and sha256); DIN-SQL
   (`MohammadrezaPourreza/Few-shot-NL2SQL-with-prompting`, MIT) and DAIL-SQL
   (`BeachWang/DAIL-SQL`, Apache-2.0) are the next places to look. If one is found: record
   URL, commit, sha256; run prediction mode on both passes; report compared, EQUAL, NOT_EQUAL by
   mechanism, errors by side, and the `bird_ex` and `test_suite_ex` readings. If none is found
   inside the hour, say what was searched and stop this step.
8. **Report** `plans/reports/research-260907-HHMM-spider-dev-sqlite.md` (HHMM the Asia/Saigon
   time you write it), under 150 lines, 100-column wrap: inputs by URL and sha256; what the
   tool refused as shipped and after the transformation, with counts by reason; the fires per
   probe; the recall table; the hand readings; the corrections replayed; the prediction file if
   any; "What the tool did not catch, and gaps found in use" (what AttestQL lacks for Spider,
   with counts); "Unresolved questions"; last section "What changes in AttestQL".

## Artifact and rules

- `plans/reports/research-260907-spider-dev-sqlite/`: every script, `inputs.json`,
  `corrections.json`, `gold-only.json`, `recall.json`, `classification.json`,
  `corrections-replayed.json`, the per-run `summary.json` copies under `tool/`, and a
  `reproduce.sh` that takes `MEASURE_WORK` and `ATTESTQL_INPUTS` from the environment, uses
  the shared `spider_data.zip` and `spider-2020/` when present and otherwise downloads them
  (`uvx gdown <file id>`, `gh api`), verifies every digest and regenerates all of it.
- Every number in the report comes from one of those JSON files. No Spider file is committed:
  no question file, no gold file, no database; the 28 correction pairs may be quoted in
  `corrections.json` as measured data (short SQL strings under CC BY-SA 4.0, attributed).
- Scripts pass `uv run ruff check plans` and `uv run ruff format --check plans` (pre-commit
  lints `plans/**/*.py`; SQL built from strings carries `# noqa: S608` as the earlier scripts
  do). The report passes `just docs` (markdownlint and cspell over `plans/**/*.md`; words cspell
  does not know go in a `<!-- cspell:ignore ... -->` comment at the top, as the existing reports
  do) and `just repocheck`: no em dash, en dash or numero sign anywhere in a `.md` or `.py`
  (write a hyphen or a comma), every link in the report resolves, the ADR index is untouched.
- No change under `src/`, `tests/`, `docs/`, `tools/`. A tool bug or refusal you hit is a
  paragraph and a count in the report, not a fix.
- Commit on your branch with conventional commits and no AI reference; do not push, do not
  merge. Run `just docs`, `just repocheck` and the two ruff commands before the final commit.
- At each checkpoint run
  `orca worktree set --worktree active --comment "<checkpoint>"`: inputs verified, parse pass
  done, recall done, readings done, report committed and gate green, or blocked.

## End your last message with

```text
Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
Summary: one or two sentences with the headline numbers
Concerns/Blockers: optional
```
