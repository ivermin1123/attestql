# Phase 2: what plans/ carries, and what main allows

Closes the remainder of HYG-01 and META-01. Depends on phase 1, whose rewrite has to happen
before a ruleset forbids force-push, and which already removes the largest file.

## HYG-01, the rest of the raw output

`plans/` holds 1,491 of the repository's 3,287 tracked files and 52 MB. The owner decided the raw
output moves to release assets while the text reports and the small summaries stay in the
repository, each report naming the asset that holds its raw output and that asset's digest. The
practice already exists: the `v0.2.2` release holds 21 run archives.

The rule for what may leave: a file is moved only if it can be reproduced from a script and a
digest already recorded, or if it is published as an asset whose digest the report states. A file
that is evidence for a claim and is reproducible by neither route stays.

## META-01, the ruleset

`main` has no protection at all today; `gh api repos/ivermin1123/attestql/rulesets` returns an
empty list. The owner chose protection that does not change how they work: block deletion, block
force-push, require the CI check on pull requests, and leave direct pushes to `main` available to
the owner. Dependabot's pull requests must still be mergeable under it.

## Validation

- Every report whose raw output moved names its asset and the asset's digest, and the digest
  matches the published asset.
- `tools/check_doc_links.py` green.
- A force-push to `main` is refused, a branch deletion is refused, and a normal push by the owner
  is not.
- A Dependabot pull request can still be merged.
