---
title: "Web UI phase 4: the five audits published, reviewed twice, and attestql.com switched onto the site"
date: 2026-09-08
summary: "121 runs regenerated and selected under budget, release v0.2.2 with 21 archives, two-stage review fixed on the same worker terminal, attestql.com now serves the built site with the deployment workflow waiting on one secret"
---

# Web UI phase 4: the five audits published, reviewed twice, and attestql.com switched onto the site

## What happened

Phase 4 of `plans/260907-1730-attestql-web-ui/plan.md` was cooked by an Opus worker through Orca (run `run_17780ac036e0`, task `task_39a7457074d7`) in the worktree on `ivermin1123/web-ui`, from a brief carrying nine coordinator decisions: on SQLite a prediction file is a group of eleven runs; the prediction benchmarks use the GitHub zip copy with `--predictions-keyed-by position`; BIRD dev uses the 2025-11-06 copy the hand classification reads; release assets go on the existing `v0.2.2` tag because the audit engine is unchanged since it; the three budgets stay. The worker delivered seven commits (`e58cfee`..`14b2050`): `tools/site-select/{audits.sh,select.py,release.sh}`, 121 runs and 348 question directories under `tools/site/data/`, a group level and one shared `static/` in the build and the renderer, `questions.json`, `classification.json` with its source note and `published.json` beside each summary, 21 archives on a new GitHub release for `v0.2.2`, and `plans/reports/measurement-260908-site-publish-runs.md` reconciling every count (164 credited-but-NOT_EQUAL on PostgreSQL, the README's number; 237 on SQLite; 35 BIRD dev golds with fired probes).

The coordinator's stage 1 review measured two builds (deterministic outside the demo pages), 4,945 internal references (none broken), 78 renders at three widths in both themes (no overflow, four type steps), two release assets against `SHA256SUMS` and `published.json`, and attestql.com unchanged. It found the landing stating 66 hand-classified rows where the classification joined to the runs holds 69 (three questions have no page because a page of one would be 5 to 10 MB), the class letter A/B/C shown without its meaning, and run pages silent on how much of a run the site holds. Stage 2 (a single code-reviewer) found the auditor-role pipeline unchecked and the teardown trap registered after `docker run` in `audits.sh`, no scheme check on the release-asset URL before it became an `href`, and a silent last-write-wins on a duplicate classification key, plus eight minor items. A fix task on the same terminal (`task_ffc06b3849d4`, five commits `41d5090`..`786f32f`) closed all of it with tests; `just check` exit 0 at 1,085 tests plus both sandboxes, re-verified by the coordinator with the same measurements. The branch was pushed and PR #1 extended to phases 1 to 4.

The owner, mid-turn, asked for the attestql.com switch and the GitHub Actions deployment as well. After phase 4 was reviewed, commit `8b27fa0` added `.github/workflows/site.yml` (push to `main` publishes to the Pages project `attestql`; a manual run publishes the ref to `attestql-ui`) and the wording in the site README, the developer guide and the plan; the site built at that commit was deployed by hand from outside the repository with wrangler to the project that holds the domain, and attestql.com now answers with the landing, the indexes, a question page, its JSON and the stylesheet. The `CLOUDFLARE_ACCOUNT_ID` secret was set; `CLOUDFLARE_API_TOKEN` can only be created in the Cloudflare dashboard, so the workflow's first real run waits on the owner. A manual dispatch of the workflow from the branch was refused by GitHub ("not found on the default branch"), so the workflow is exercised for the first time by the push that merges PR #1.

## Decisions

- A run is one invocation; a merged summary is never written. Group pages state sums and say so.
- The aggregate's numbers are the benchmark's, not the budget's: each key carries `value` and `published`, and the landing puts one line under a number whose pages are fewer than its value.
- Three hand-classified questions stay out of the site (page over 2 MiB) and whole in the release assets; publishing them needs a renderer that bounds the rows it draws, a phase of its own.
- Release assets live on the `v0.2.2` release, created for this purpose; the engine at the branch head is that tag's.

## Next steps

- Owner: create the API token (Cloudflare Pages: Edit on the account) and `pbpaste | gh secret set CLOUDFLARE_API_TOKEN`; merge PR #1 once the main checkout has nothing left to push (`git log origin/main..main` empty), which is also the workflow's first run.
- Phase 5, the in-browser drop zone, after the merge.
- `/tmp/attestql-runs` (the work directory, 2.8 GB of database copies plus every run and archive) can be deleted once the release assets are trusted.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
