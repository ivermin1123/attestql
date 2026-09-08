# GLM research lanes, 2026-09-07

<!-- cspell:ignore minidev -->

Status 2026-09-08 13:10: all four lanes done and merged into main (`49afd57`, `0c41dbe`,
`b926f71`, `ed3da41`; register rows A41 to A44), their worktrees removed. L3 (task
`task_4c1921eaaf8b`, dispatched 19:47) lost the night to a dead background terminal and finished
2026-09-08 12:30; its 50-row hand sample, templated by the worker, was re-read row by row before
merge (`e7c354d`). Four lanes on codex (GLM) workers, one Orca child worktree each, two at a
time (L1 and L2, then L3 and L4). The owner's order of 2026-09-07 18:37: a lane gets its own worktree, a
written brief, a validation pass and a red review before it is dispatched. Read-only research:
every lane writes one report and one artifact directory under `plans/reports/`, touches no
product code, posts nothing upstream.

## Lanes

| Lane | Question | Brief | Report slug |
|---|---|---|---|
| L1 | Of the 399 dev golds BIRD rewrote on 2025-11-06, how many change the answer on the data, how, and what changed in the SQL; which changes a gold-only probe could see | [l1-bird-rewrites.md](l1-bird-rewrites.md) | `research-260907-HHMM-bird-rewrites-what-changed.md` |
| L2 | The eleven dev databases ship in two copies (`dev.zip`, `minidev.zip`) and five differ: how many gold answers and how many of BIRD's own Mini-Dev scores depend on the copy; which copy carries the right CDS codes | [l2-two-database-copies.md](l2-two-database-copies.md) | `research-260907-HHMM-two-database-copies.md` |
| L3 | More public BIRD dev prediction files with a clear licence (CodeS ships eight under Apache-2.0), to widen A37 from two GPT-3.5 files | [l3-more-dev-predictions.md](l3-more-dev-predictions.md) | `research-260907-HHMM-dev-predictions-across-systems.md` |
| L4 | Spider 1.0 dev on SQLite: the gold-only probes, and recall against Spider's own 2020 corrections of `evaluation_examples/dev.sql` | [l4-spider-dev.md](l4-spider-dev.md) | `research-260907-HHMM-spider-dev-sqlite.md` |

## Shared inputs

`~/.cache/attestql-measure/inputs/`, fetched and verified by the coordinator before dispatch
(`fetch.sh`, `unpack.sh`, `SHA256SUMS` with nine digests): `dev.zip` (`cdd6d19f…`),
`minidev.zip` (`cc48ba16…`), `dev_20251106.json` (`ffd80183…`), `mini_dev_sqlite_hf.json`
(`88ceb071…`), both zips unpacked once, `spider_data.zip` (`00636695…`) and the two 2020
`dev.sql` versions for L4. The directory is read-only (`chmod -R a-w`); workers read it and
never write into it, and `unpack.sh` is never rerun while a lane runs.

## Constraints

- Two lanes at a time, three SQLite processes per lane: the machine holds 18 GB and thrashed
  under four agents and Docker on 2026-09-04.
- Codex workers get the whole process in the brief: no skill files, no questions to a human.
- Reports follow `measurement-260907-1435-bird-dev-sqlite.md`: inputs by URL and sha256, every
  number from a JSON a committed script wrote, under 150 lines, the last section "What changes
  in AttestQL".
- The coordinator (Fable) reviews each branch, merges `--no-ff` into main, updates the claims
  register and removes the child worktree.

## Gate before dispatch

1. Validate: every path, digest and command a brief names exists or runs; the counts it asserts
   match the register. Done 2026-09-07 18:30 (one minidev path corrected).
2. Red review: an independent reader on the strongest model reads the brief as the worker
   would and lists what is ambiguous, wrong, or would produce a wrong number; the brief is
   amended before dispatch. Done 2026-09-07 18:54, [red-review.md](red-review.md): all four
   "amend then dispatch", one blocking item in L4 (the tool refuses no Spider gold, so the
   lane measures the delta between an as-shipped and a transformed pass instead of refusals),
   and shared amendments: the exact `MEASURE_WORK` links the earlier scripts read, the inputs
   directory made read-only (`chmod -R a-w`, BIRD's evaluator opens databases read-write), a
   timeout that survives one serial rerun is final, `just repocheck` and the typography rule in
   the gate, the mechanism names the tool writes, `ATTESTQL_INPUTS` for `reproduce.sh`. All
   applied before dispatch; `SHA256SUMS` now holds the nine digests. The Claude Bash hook that
   blocks "venv" in commands does not apply to codex workers.

## Acceptance

- The lane's `reproduce.sh` runs from a clean `MEASURE_WORK` and regenerates the JSON the
  report cites.
- `just docs`, `uv run ruff check plans` and `uv run ruff format --check plans` pass on the
  branch.
- The worker's last message carries the Status Protocol block.
