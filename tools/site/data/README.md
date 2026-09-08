# The published runs the site is built from

What `tools/site/build.py` renders. Everything here was written by `attestql audit` and copied
in by `tools/site-select/select.py`; nothing in it is edited by hand, and remaking it is
`tools/site-select/audits.sh` followed by that script.

The question text, the evidence text and the gold SQL in these directories are BIRD Mini-Dev's
and BIRD dev's, licensed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); `NOTICE` at the repository root
is the precise list.

## What a benchmark, a group and a run are

```text
tools/site/data/<benchmark>/<run>/summary.json                 PostgreSQL
tools/site/data/<benchmark>/<group>/<db_id>/summary.json       SQLite
```

A **benchmark** is a question set and the engine it was audited on: `bird-dev-sqlite`,
`minidev-sqlite`, `minidev-pg-gold-only`, `minidev-pg`. A **run** is one invocation of
`attestql audit`, which writes one second statement per question.

On PostgreSQL one invocation answers a whole question set, so a prediction file is a run and a
benchmark of nine prediction files has nine runs. On SQLite `--dsn` is one database file, so a
question set naming eleven databases is eleven invocations: a prediction file is a **group** of
eleven runs, one per database, and the group is a level in the address. `build.py` reads both
shapes; a directory holding a `summary.json` is a run, and one holding runs and no summary is a
group.

A group is a line and a page stating the **sums** of its runs' counts, by the merge rule
`plans/reports/measurement-260907-1106-minidev-sqlite.md` and
`plans/reports/measurement-260907-1435-bird-dev-sqlite.md` state: no question id is in two of
the eleven, so the counts add. It is never a merged `summary.json`, because a summary no audit
wrote would be this site's own invention.

A run directory is an audit directory. It holds that run's whole `summary.json` and the question
directories the selection names, each with the files the audit wrote for that question
(`counterexample.json`, `evidence-gold.json`, `evidence-second.json`, `smells.json`). The build
hands each run directory to `attestql report`, so a directory here is a directory that command
can render, and nothing about its shape is this site's invention. A question whose statement
could not be run has no directory and is a row of the run page read from the summary.

## The three files beside a summary that no audit writes

- `questions.json`: `question_id`, `db_id` and the question text of every question that run
  audited, read out of the question file the run's own summary names. The database a question
  is about reaches no file the audit writes, and the question page states it in its strip.
- `classification.json` and `classification-source.json`: a copy, byte for byte, of a hand
  classification committed under `plans/reports/`, and a note saying where that copy came from,
  what date the measurement report states for it, and which of its rows are this run's. The
  question page shows one "read by hand" row where the file holds a row for that question, with
  the class and the reason verbatim and that date. The tool's verdict and a person's reading are
  two blocks and never one. The note also carries `classes`, what each class of that
  classification means, cut out of the measurement report's own legend or out of the file's own
  `reading` string and named in `classes_source`, so that the row states a meaning nobody wrote
  for this site. A class the note does not define is shown as the value the row holds, alone.
- `published.json`: the name, the URL, the size and the sha256 of the release asset holding the
  whole of that run or group, and `directories`, how many question directories that archive
  holds, counted out of the archive itself by `tools/site-select/manifest.py`. What is here is a
  selection; that archive is all of it, and the run page states both numbers: how many question
  directories have a page here, counted as the pages were written, and how many the run wrote.
  A run of a group states its own count and the group's own file states the group's sum.

## `aggregate.json`

Beside the benchmarks, one file the landing page reads for its three headline numbers. It is
written by `tools/site-select/select.py` and never by hand. Each key holds an object with three
fields: `value`, the number; `published`, how many of them have a page on this site; and
`source`, the file the number was read out of, which the landing puts in a `title` attribute
beside it so a reader can see what to open.

```json
{
  "credited_but_not_equal": {"value": 0, "published": 0, "source": "minidev-pg/<run>/summary ..."},
  "classified_by_hand": {"value": 0, "published": 0, "source": "minidev-pg/classification.json"},
  "bird_dev_classified_by_hand": {"value": 0, "published": 0, "source": "bird-dev-sqlite/..."}
}
```

`value` and `published` are two questions and the landing shows the number as `value`. What the
runs and the classifications state is a fact about the benchmark; how much of it has a page here
is a fact about this site's file budget, and a site whose own budget changed the number it
reports would be reporting the budget. Where `published` is below `value` the landing puts one
line under the number saying how many have a page and how many are whole in the release assets
only; where they are equal it says nothing, and the proportion bar is drawn from `value`. An
aggregate written before the two were told apart holds no `published`, and the build reads
`value` for both, which is what one number meant.

- `credited_but_not_equal`: the questions BIRD's own check credited and this comparison called
  NOT_EQUAL, totalled over the nine PostgreSQL runs against the gold copy the aggregate names.
- `classified_by_hand`: of those, the ones a maintainer read and classified as a gold that does
  not answer its question. It is the classification joined to those nine runs' own sets, whether
  or not the question has a page: what the budget published is `published`.
- `bird_dev_classified_by_hand`: the BIRD dev golds classified by hand the same way.

The three keys are the ones `tools/site/build.py` names in `HEADLINE`, and the build refuses a
file missing one of them rather than showing two numbers where a reader expects three. While the
file is not here the landing shows no number at all and says why: a number typed onto a page by
hand is the one thing this site is against.

`classified_by_hand` is a part of `credited_but_not_equal`, and the proportion bar under the three
numbers draws exactly that: the first number cut into the part a maintainer classified and the
rest. It does not draw the three side by side, because two of them are not disjoint and the third
counts another benchmark's questions, and a bar over all three would state a proportion nothing
holds. A `classified_by_hand` larger than `credited_but_not_equal` is refused.

## `selection.json` and `left-out.json`

What the selection did, so that the reconciliation report is read out of a file rather than
retyped: one row per run with the counts its summary states, the questions published from it and
their ids; and every question the budget left out, largest first, with its size. A question left
out of the site is in that run's release asset, whole.

## How these were made

```sh
tools/site-select/audits.sh inputs      # verify the cached inputs, fetch the predictions
tools/site-select/audits.sh sqlite      # bird-dev-sqlite, then minidev-sqlite
tools/site-select/audits.sh postgres    # the container, the dump, minidev-pg-gold-only, minidev-pg
uv run python tools/site-select/select.py --dry-run
uv run python tools/site-select/select.py
```

Every flag each run was given, with the origin strings and the dates, is in `audits.sh`; the
digest of every file a run read is in that run's own `summary.json`, measured by the run rather
than stated by the script. The four inputs and their digests:

| Input | sha256 |
| --- | --- |
| `minidev.zip`, members `mini_dev_sqlite.json`, `mini_dev_postgresql.json`, `dev_databases/`, `MINIDEV_postgresql/BIRD_dev.sql` | `cc48ba16…` |
| `dev.zip`, member `dev_20240627/dev_databases.zip` | `cdd6d19f…` |
| `dev_20251106-00000-of-00001.json`, BIRD's 2025-11-06 pass at dataset commit `3c11fb19` | `ffd80183…` |
| `mini_dev_pg-00000-of-00001.json`, the Hugging Face PostgreSQL golds at commit `f65faf4a` | `7fa740ef…` |
| the nine `predict_mini_dev_*_sqlite.json` and nine `_postgresql.json` at `b3d4bcbb` | in `audits.sh` and `plans/reports/minidev-sqlite-260907/SHA256SUMS.predictions` |

The reconciliation of every count against the measurement reports that first made it is
`plans/reports/measurement-260908-site-publish-runs.md`.

## What is not here

Nothing generated by a build. The stand-in the build audits when this directory holds no
benchmark is written to a scratch directory under `/tmp`, which is never copied in here. Full
runs, every question directory of them, are release assets that each run page links to; what
lives here is the selection the site shows.
