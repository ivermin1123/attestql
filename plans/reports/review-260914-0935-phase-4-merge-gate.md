# Merge gate for phase 4 of the review-findings plan

Reviewed 2026-09-14 from 09:35, branch `ivermin1123/review-findings-phase-4` at `28a9291` over base
`eba24a0`, twelve commits, 49 files, 2,853 lines added and 368 removed. The branch is the work of
`plans/reports/cook-260913-2338-review-findings-phase-4.md`. Two independent reviewers read it in
parallel, one over the audit core, the CLI contract and the evidence record (commits `07a2101`,
`ca2076e`, `2077a87`, `157c8a5`, `62c4c81`, `8b62611`, `27838d7`), one over the renderer, the site
build, the maintainer scripts and the test boundary (`c070764`, `f9185d0`, `83f7ad1`, `9f5e7c5`,
`28a9291`). The coordinator ran `just check` on the branch head independently: 1,273 passed and
34 skipped, then 34 in the PostgreSQL sandbox and 125 in the SQLite sandbox, exit 0.

Verdict of both reviewers: **merge after fixes**. The fixes were dispatched to the same worker as
new commits on the same branch and landed as `a53847f` (the LOGIC-06 redesign), `1955fb3` (the
contract text, and the question file read before the backend opens so the claim became true),
`d5e8b11` (the seven small items) and `9287a3c` (the report). The coordinator re-ran the five
LOGIC-06 cases by hand on the branch head: a clean one-question audit renders, the whole demo run
renders, the run with `q879` removed is refused naming it, the run with a stray `q42` is refused
naming it, and a summary without the new key renders. The branch merged into `main` as `57bb352`
on 2026-09-14 with `just check` green on the merged tree: 1,284 passed and 34 skipped, then 34 in
the PostgreSQL sandbox and 130 in the SQLite sandbox.

## What blocked the merge

**LOGIC-06 was implemented on a false premise.** The renderer refused a directory when the
question directories plus the errors numbered fewer than the audited count. A question that agreed
and fired no probe has no directory and is not an error, so `attestql report` exited 2 on any
healthy audit holding one such question. Reproduced by the reviewer and again by the coordinator:
a gold-only audit of q1029 from the packaged sandbox (verdict GOLD-ONLY, no smell, exit 0) could
not be rendered. The gate stayed green because every one of the six demo questions disagrees or
fires a probe. The `published.json` exception, meant for the site's selections, also silenced the
check for exactly the case the finding was written about, a published run that lost a directory.

The cause is upstream of the renderer: `summary.json` holds counts and never the ids of the
directories a run wrote, so no reconciliation from the summary alone can tell a clean question
from a lost directory. The fix decided by the coordinator adds one key to the summary,
`question_directories`, the ids whose directory the run wrote, and reconciles against it exactly:
a whole run must hold that set and no other, a selection must hold a subset and state how much of
the whole it holds, and a summary written before the key existed is rendered under the count
bounds alone rather than refused.

**Three places where the branch's own contract text states the pre-change behaviour.** The CLI
module docstring still said nothing aborts a run after it started, while a failed write now exits
2; the SQLite session settings docstring and the `SessionSettings` record type still enumerated
nine settings after `automatic_index` became the tenth; and the CLI claimed an out-of-range id is
refused before the backend opens, while the SQLite backend copies the database file first.

**Two documents left stale by the branch.** The report command's reference did not list the two
classification files a rerun now removes, and the site README still described the deleted refusal
of an output directory under `site/`.

## Carried into the same fix pass

Filter-page titles were not given their context and 173 of 654 titles exceed 60 characters;
the release-notes sentence about `search_path` says the value moved but not that the key moved
position in the session settings object; `public` is spelled twice in the PostgreSQL backend; a
killed run leaves a `.partial` file that a rerun does not clear; one shell test wrote under the
repository's `build/` directory; a re-raise in the SQLite backend skipped a `query_only` restore.

## Left open, on record

The DSN keyword parser accepts a password carried in forms the old word check refused; one
mid-run write path catches `OSError` alone; the shared count reader shares its message templates
across its three callers where the review asked to keep each caller's wording; the `Backend` and
`Connection` protocols gained a method, which an out-of-tree implementation would have to add.
None changes what a run concludes. Two tests assert markup text rather than behaviour.

## What both reviewers verified clean

Every number the worker stated reproduced: 2,181 files and 32,678,701 bytes built, 653 pages under
`index.html` with 653 distinct titles, the heaviest page down from 1,806 KB to 148 KB, two builds
identical outside the demo pages. Records under the bounded preview are byte-identical to the
site's data and every "recomputed from this JSON: match" line holds. All ten demo records
recompute both hashes through the loader, and the 0.2.2 record layout still round-trips, so the
layout version does not move. LOGIC-08 refuses only under id keying, only for ids absent from the
whole file, bounded at twenty names and a count, exit 2; no cached copy of BIRD dev, Mini-Dev or
their Hugging Face files (1,534, 500, 1,534 and 500 entries) is refused by the new type checks.
LOGIC-04's read-back runs before the shuffle's scratch path and no record is written for a
shuffled rerun. The two-file exemption in `tests/test_boundary.py` is exact and the new assertion
that nothing under `src/` starts a process is a real walk of the tree. No em dash, en dash or
curly quote in any changed file; no AI mention in any commit message; ruff, pyright strict,
cspell, markdownlint and the link check clean.

## Process note

The three High defects of 0.3.0 were found by a review that came after the release. This time
the review came before the merge and found one defect of the same weight, reachable from the
second command a user types. The order held; keep it.
