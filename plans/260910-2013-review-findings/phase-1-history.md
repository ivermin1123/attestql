# Phase 1: the three commits, and the blob that rides along

**Done 2026-09-11 at `c92e234`.** What the validation below came back as: the gate and both
CI workflows green; `v0.2.0`, `v0.2.1` and `v0.2.2` resolve to byte-identical trees;
`v0.3.0`'s tree differs by exactly the one deleted path and nothing else, and the published
wheel and sdist hold no `plans/` path so neither changed; no commit in the graph carries the
trailer; 94 references across 27 files were rewritten from the commit map and a scan of all
3,293 tracked files finds none pointing at a commit the graph no longer holds; every object
that was dangling before the rewrite is still present; and the measurement file round-trips
from the `v0.3.0` release at the two digests the claims register states.

Closes HYG-09, and the single largest item of HYG-01.

## What is wrong

Three commits of 2026-09-07 carry `Co-Authored-By: Claude Opus 5`, against the owner's standing
rule that a commit names no AI. They are `d640be1`, `9c8b38c` and `6a43c01`, all
`docs(measurement)`. The owner decided on 2026-09-10 to rewrite them and repair every consequence
rather than accept them as history.

## What the rewrite touches

`d640be1` is the earliest, and 121 commits follow it. Measured on 2026-09-10:

- four tags become stale: `v0.2.0`, `v0.2.1`, `v0.2.2`, `v0.3.0`;
- two published GitHub releases point at two of those tags, and the `v0.2.2` release holds 21 run
  archives as assets;
- 60 commit references in tracked documents fall out of the graph, 18 of them in
  `docs/claims-register.md`, which is the document this repository designates as the owner of
  every claim it makes;
- `git fsck` shows two dangling objects the repository keeps on purpose. A rewrite that prunes
  unreachable objects would destroy them.

PyPI holds 0.2.x and 0.3.0 immutably. Their contents do not change and cannot; what changes is
which commit a tag of the same name resolves to, so the tag has to be recreated over the rewritten
commit with the same tree.

## Steps

1. Back the repository up whole, `.git` included, outside the working tree, and record the
   `git fsck --dangling` output so the two kept objects can be restored by hash if a prune takes
   them.
2. Record, for each of the four tags, the tree hash it currently resolves to. This is the check
   that the rewrite changed messages and not content.
3. Rewrite with `git filter-repo` in one pass: a message callback that strips the trailer line
   from the three commits, and a path exclusion that drops
   `plans/reports/research-260907-dev-predictions-across-systems/prediction-measurement.json`,
   11.1 MB, added in `43d2a04` after the rewrite point. Doing both in one pass is why this phase
   precedes phase 2.
4. Build the old-to-new commit map filter-repo writes, and rewrite the 60 references in tracked
   documents from it. A reference whose commit was not rewritten stays as it is.
5. Recreate the four tags over the mapped commits, and confirm each resolves to the tree hash
   recorded in step 2.
6. Publish the measurement file that step 3 dropped as a release asset, and make its report name
   the asset and its digest, which is what phase 2 does for the rest.
7. Add a `commit-msg` hook that refuses a message naming an AI co-author, so the rule is held by
   the machine rather than by memory. Test that it refuses and that it passes a clean message.
8. Force-push `main` and the four tags, then re-point the two published releases at the recreated
   tags.

## Validation

- `just check` green, CI green on the pushed head.
- Every tag resolves to the tree hash recorded in step 2.
- `git log --grep="Co-Authored-By: Claude" -i --all` is empty.
- `tools/check_doc_links.py` green, and a scan finds no reference in `docs/` or `plans/` naming a
  commit that is not in the graph.
- The two kept dangling objects are still present.
- The measurement file is reachable from its report through the release asset and its digest.

## Risk and rollback

This is the only irreversible step in the plan. Rollback is a restore from the step 1 backup and a
force-push back, which is possible only while nobody has fetched the rewritten history. The
window should therefore be short: steps 3 to 8 run in one sitting.

The repository has no other clone: `git worktree list` shows one working tree after the web UI
worktree was removed on 2026-09-10, and there are no forks. That is what makes the rewrite
affordable at all, and it should be confirmed again immediately before step 8.
