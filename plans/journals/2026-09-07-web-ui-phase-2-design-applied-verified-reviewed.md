---
title: "Web UI phase 2: design applied, verified, reviewed"
date: 2026-09-07
summary: Phase 2 cooked on an Opus worker through Orca and reviewed on Fable with independent Playwright measurements; ten findings fixed on the same worker; branch pushed to PR 1
---

# Web UI phase 2: design applied, verified, reviewed

## What happened

- Session resumed from memory and the plan. PR 1 stayed open: CI green, but the main checkout held 7 and later 10 commits not yet pushed, so the merge rule was not met.
- Phase 2 dispatched as one Orca task on claude-opus-5 in the web-ui worktree. Done in about 95 minutes: six commits, gate green, stress directory of 14 questions, screenshots at three widths in both themes.
- Review in two stages. Stage 1 was spec compliance plus a Playwright pass of my own over the stress report: 88 renders, no horizontal overflow, type in use exactly the four steps, all three Plex faces loaded. Stage 2 was a code-reviewer subagent; the first attempt stalled after fanning out its own sub-reviewers, and a narrowed single-agent retry completed with reproduced findings.
- Findings: a Claude co-author trailer on all six commits (repository rule); the sticky strip one gutter left of the prose at 1280 and wider (32 against 64, 112 against 144, 384 against 416); the slope chart's caption contradicting the drawing when gold rows are absent from the prediction; an unclamped probe bar; titles escaped twice; stand-in zero digests in the stress builder's NOT_COMPARABLE record; a docs sentence missing its verb; a docstring claiming 18 is on the spacing scale; the spec's dark tints out of sync with the tested values.
- Fix task on the same worker terminal: two commits, the six earlier ones rewritten in place with identical trees. The worker found the second half of the alignment defect on its own: the chip row and the set line had dropped their auto inline margins, so my one-line patch had moved the title alone.
- Verified after the fix: all three strip children on the prose's left edge at 360, 768, 1280, 1440 and 1920 on three pages; 88 renders with no overflow; caption and escaping probes pass; `just check` green at 1,020 tests plus both sandboxes.
- Pushed the eight commits; PR 1's title and body now cover phases 1 and 2; CI running at the time of writing.

## Decision

- Fixes went to the same worker terminal so its context carried; the commit-message rewrite was allowed because none of the six commits had been pushed.
- The spec's dark tints were synced to the tested values, which the spec's own rule permits. The 66ch measure was left as accepted: it is the owner's decision.
- The Playwright driver stays uncommitted; the screenshots (about 3 MB) are committed beside the verification report.

## Lessons

- Alignment is not overflow. Measure the left edge of every child of the strip against the prose, not only the page's scroll width.
- A code-reviewer subagent that spawns sub-reviewers stalls. Scope it to one agent with an explicit file list.
- An Opus worker appends the harness's co-author trailer unless the brief forbids it by name. Read `git log --format=%B` before accepting a commit.
- The credential hook that flags `rt_` fires on identifiers containing `report_`. A false positive.

## Next steps

- Merge PR 1 when CI is green and the main checkout has nothing left to push, then merge `origin/main` into the worktree.
- Owner questions: the measure (66ch sets 86 characters a line; 55ch would set 72), the fixed 640 px figures cut at 328 px on a phone, and whether the committed screenshots stay in the repository.
- Phase 3: the site build, the landing and method pages, and the preview deployment.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
