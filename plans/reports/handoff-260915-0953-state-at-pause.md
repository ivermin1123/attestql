# AttestQL at the pause of 2026-09-15

On 2026-09-15 the owner paused the project. The three public pieces drafted in
`drafts-260914-1240-public-writeup.md` were not sent, nothing was posted anywhere, and the next
work waits for a free day. This record fixes where everything stood at that moment, so that the day
it resumes starts from a reading rather than a reconstruction. It is a stateful record like every
report in this directory: the plan index and the claims register remain the authority for what
they own.

## Where the project stands

- `main` is `b0151e7`, pushed, with a clean working tree. CI and the site workflow are green on
  it, and the release workflow is green on `b574bdd`, the commit the tag `v0.4.0` points at.
- 0.4.0 is on PyPI since 2026-09-14 (register row N8). The GitHub release `v0.4.0` carries the 21
  run archives and their `SHA256SUMS`, and attestql.com serves the site built from the 121 runs
  made again under 0.4.0 (row A54, `measurement-260914-2010-site-refresh-040.md`).
- The review-findings plan (`../260910-2013-review-findings/plan.md`) has phases 1, 3, 4, 5 and 6
  done and META-01 of phase 2 done. The HYG-01 remainder of phase 2 is its one open item.
- The whole-project review of 2026-09-12 (`review-260912-1237-project-retrospective.md`) and its
  external lane are committed. Row N2 was reworded and ADR-0013 amended for the IBM toolkit, the
  second blind reader is on record as A53, and `CITATION.cff` names 0.4.0.
- Upstream: seven reports are on record (U1 to U7). U5 to U7 have no reply, and the date set for
  reading them again was 2026-09-21.

## What is open, in the order the owner had chosen before the pause

1. The three public pieces in the drafts report, on hold by the owner's word. Before any of them
   is sent, the list at the end of that report is run again: the numbers it quotes are rows A17,
   A25, A35, A36 and A53, and the sentence about U5 to U7 having no reply is re-read against the
   upstream threads on the day. ADR-0013 point 10 asks for one outside user by 2026-11-02, and the
   pause spends that window.
2. The HYG-01 remainder of phase 2. `plans/` holds 42 MB, and the four files above 500 KB are
   `minidev-sqlite-260907/aggregate.json`, `minidev-sqlite-260907/verdicts-hf.json`,
   `minidev-sqlite-260907/verdicts-zip.json` and `research-260907-spider-dev-sqlite/gold-only.json`.
   The owner's rule of 2026-09-10: a file leaves only if it is reproducible from a recorded script
   and digest, or published as a release asset whose digest the report states.
3. The Spider 1.0 dev measurement of 2026-09-07 (1,034 golds, 60 probe fires) is measured but
   published nowhere. It is the cheapest fourth measurement.
4. The three class A rows without a site page were not sampled by the second reader
   (`measurement-260913-2342-second-reader-hand-classification.md`). The renderer would need to
   bound their rows before those pages can exist.
5. `tests/test_report_imports_no_engine.py:184` compares an intersection with the set it was built
   from, which cannot fail. The test needs one assertion that can.
6. The drop zone of the web UI (phase 5 of `../260907-1730-attestql-web-ui/plan.md`) stays
   unbuilt unless it is asked for.

Of the three items the retrospective placed after the code work, `CITATION.cff` and the drafts are
done except for the sending, and the README's first screen shows the two commands under one
paragraph.

## What was closed at the pause

- The Orca run `run_6265d3d1f806`, which carried phases 4 to 6: all five dispatches settled as
  succeeded, the worker terminal was closed, and the worktree
  `~/orca/workspaces/attestql/review-findings-phase-4` was removed.
- The three merged branches `ivermin1123/review-findings-phase-4`, `-5` and `-6` were deleted
  locally. Their commits are in `main` through the merges `57bb352`, `bbbe9fa` and `12f1c29`.
  Dependabot's two branches were already gone from `origin`.
- The raw 0.4.0 and 0.3.1 runs still sit under `/tmp` on the owner's machine, and the 18 GB
  measurement cache of the 2026-09-07 lanes under `~/.cache/attestql-measure/l3`. Every published
  number from them has a release asset (the archives of `v0.3.1` and `v0.4.0`) or a committed
  summary, so they are disposable at the owner's word. The `inputs` directory beside that cache is
  still what the measurements read, so it stays.

## To resume

```text
git pull
uv sync
uv run pre-commit install --hook-type commit-msg
just check
```

Then read, in this order: this record, the plan index of the review-findings plan, the drafts
report, `docs/claims-register.md` from row A53 down, and the proposed order at the end of the
retrospective review. `docs/developer-environment.md` holds the rest of the setup.
