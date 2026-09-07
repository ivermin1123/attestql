# Phase 4: regenerate the published runs with per-question evidence

## Context

The runs this repository has reported (`plans/reports/`) were made before the site existed.
The gold-only runs kept only `summary.json` and the printed lines; the prediction-mode and BIRD
dev runs kept aggregates, the hand classification and a few examples. The site needs the
per-question directories, so the runs are made again, with the same inputs and digests, and the
question directories that the site shows are copied into `site/data/`.

## Requirements

- Five runs, in this order, SQLite first because it needs no container:
  1. `bird-dev-sqlite`: BIRD dev, gold-only, the eleven database files.
  2. `minidev-sqlite-predictions`: Mini-Dev SQLite, BIRD's nine prediction files,
     `--predictions-keyed-by position` where the file needs it.
  3. `minidev-pg-gold-only`: the GitHub zip's question file.
  4. `minidev-hf-gold-only`: the Hugging Face file.
  5. `minidev-pg-predictions`: the nine PostgreSQL prediction files, statement timeout 120
     seconds so q707 is compared, as the committed measurement states.
- Every run records `--questions-origin`, `--questions-date`, `--predictions-origin`,
  `--predictions-date`, `--data-file`, `--data-origin` and `--data-date`, so the run page states
  where everything came from.
- Layout: a benchmark holds CLI runs, one per prediction file, because the audit writes one
  second statement per question per run. `tools/site/data/<benchmark>/<run>/` holds that run's
  `summary.json` whole and the question directories the selection names. Benchmarks:
  `bird-dev-sqlite` (one run), `minidev-sqlite` (nine), `minidev-pg-gold-only` (two runs, the
  zip and the Hugging Face file), `minidev-pg` (nine, against the gold copy the selection states).
- Selection, because Pages holds 20,000 files on the Free plan and NOT_EQUAL alone is about
  1,700 predictions per gold copy: the `credited_but_not_equal` questions of each prediction run,
  every fired-probe gold, every hand-classified row, and the unjust-zero and unjust-one cases
  from the aggregate. ERROR questions have no directory and are rows of the run page. The
  selection script writes an aggregate JSON the landing page reads and a dry-run report of file
  count and bytes; the budgets in phase 3 are copied from that report, not written by hand.
- Full runs, every directory, are published as release assets (one archive per run) that each
  run page links to, so nothing is lost by the selection.
- The hand classifications are copied beside the runs they read and joined by their own keys:
  `prediction-mode-260904-real-predictions/classification.json` at
  `per_file[<prediction file>].rows[]` (`question_id`, `class`, `mechanism`, `reason`) and
  `bird-dev-sqlite-260907/classification.json` at `rows[]` (`question_id`, `db`, `probes`,
  `class`, `why`). The "read by hand" row shows `class` and the reason verbatim with the file's
  date; a question with no row shows no such line.
- Reconciliation: the counts on each run page equal the counts in the corresponding measurement
  report in `plans/reports/`; a difference is investigated and written down, not overwritten.
- Size: the two evidence records hold every row of their results, so a question directory
  ranges from kilobytes to megabytes; the dry run measures it. Records are never trimmed or
  re-issued. If the selection is still over budget, whole questions are left out of the site and
  remain in the release asset.

## Files

- `tools/site/data/<benchmark>/<run>/...` as above, plus `tools/site/data/README.md` stating for
  each run the command, the digests and the date.
- `tools/site-select/select.py`: the selection, the aggregate, the dry-run report and the size
  check, so the copy is reproducible.
- `plans/reports/measurement-260907-site-publish-runs.md`: the reconciliation table.

## Steps

1. Run the two SQLite audits; select; build the site locally; check the numbers against the two
   SQLite measurement reports.
2. Start the PostgreSQL 16 container, load the Mini-Dev dump, create the scratch schema (the
   README's ten-minute block, as written).
3. Run the three PostgreSQL audits; select; build; reconcile against the gold-only and
   prediction-mode reports.
4. Wire the classifications; confirm the "read by hand" row appears only where a classification
   exists and states its date.
5. Remove the phase 3 stand-in banner; push; confirm the live site shows the real rows; spot
   check q879, q207, q1029 and q1473 by hand against the JSON.

## Validation

- The reconciliation report has one row per run with the site's count, the report's count and
  the difference (zero, or explained).
- The size check passes in `tools/site/build.py`.

## Risk and rollback

- A rerun on a fresher server or dump gives different digests; the run page states the digests
  it was made from, and the reconciliation report states which measurement it matches.
- Rollback: `tools/site/data/` reverts to the sandbox stand-in; the site keeps working.
