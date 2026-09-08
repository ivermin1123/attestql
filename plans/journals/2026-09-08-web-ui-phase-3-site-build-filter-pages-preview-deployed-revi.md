---
title: "Web UI phase 3: site build, filter pages, preview deployed, reviewed"
date: 2026-09-08
summary: "Phase 3 cooked on the same Opus worker and reviewed on Fable in two stages; the review caught the builder's home directory on the public preview; eleven commits pushed to PR 1"
---

# Web UI phase 3: site build, filter pages, preview deployed, reviewed

## What happened

- The owner decided at 09:30: start phase 3 on the same branch, move the measure to 55ch, keep the figures fixed, keep the screenshots. The coordinator created the Pages project `attestql-ui` under the personal account and dispatched the worker at 09:45.
- The worker delivered eight commits: the 55ch measure with every phase 2 screenshot taken again, the filter pages inside the package renderer, the site build with the packaged sandbox as a stand-in and a banner that a published run removes, the landing and method pages, the developer docs, and a first-pass review of its own that caught a path traversal (a mechanism class of `../..` wrote a page outside the output directory) and fixed it before the coordinator saw the branch.
- The coordinator's review. Stage 1 with its own acts: the traversal guard held against hostile class and probe names, the gate passed, 152 report renders and 136 site renders showed no horizontal overflow, the strip aligned with the prose on every measured page. Stage 2, one reviewer with a file list, finished in eighteen minutes and found the preview's sandbox pages stating the backend identity with the build machine's absolute path, the owner's home directory included, live on the public address. Smaller: the method page carried an internal decision note out of a docstring; names under the data directory reached links unconstrained and symbolic links there were followed; negative counts were accepted; the install line was matched by substring; the nav parser had untested edge cases; the module name `build` collides with the ignored output directory.
- The fix task on the same worker: three commits and six tests. The demo now runs at a fixed neutral path under the system temporary directory, the preview was deployed a third time, and curl confirmed no home directory on any page while attestql.com stayed byte identical to the committed file. The gate is green at 1,059 tests plus both sandboxes.

## Decision

- The record is not edited to hide a path. The build chooses where the demo runs so that what the record states is a neutral place. The fixed scratch path is shared, so two builds at once on one machine would collide; accepted for a single-owner tool.
- A method page shows a rule's opening paragraph only; the paragraphs under it are written for a maintainer.
- A bad name under the data directory is refused and named rather than skipped, because that directory is the maintainer's.

## Lessons

- A path is not markup. Autoescaping did nothing for a name that became a directory; every place a document's text becomes a path needs its own guard and a test that tries to escape.
- What a record states is what a page publishes. Read every rendered fact for machine-specific values before a deployment, not after.
- The Stage 2 reviewer works when scoped to one agent and a file list; the fan-out form stalled in phase 2 and was not tried again.

## Next steps

- Merge PR 1 when CI is green and the main checkout has nothing left to push, then merge `origin/main` into the worktree.
- Phase 4: the five runs made again, the selection script, `aggregate.json` with the three keys the landing reads, the release assets; the banner goes on its own.
- The switch of attestql.com to the built site, with the Actions deployment, stays the owner's step.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
