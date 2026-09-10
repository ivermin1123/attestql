# Phase 4: the findings the review grouped as low risk

Closes 18 findings. Depends on phase 3 so that the release carries the two High fixes rather than
waiting behind this larger set.

The review's group B table is the execution detail; this is the order and the grouping into
commits.

| Commit | Findings | What changes |
|---|---|---|
| maintainer tools | LOGIC-11, LOGIC-10 | `release.sh` can create a release at all; `audits.sh` reports failure instead of printing `SQLITE_DONE` and exiting 0. |
| report integrity | LOGIC-06, LOGIC-07 | The renderer refuses a gap it cannot explain between the summary's ids and the question directories; a rerun clears the two classification files it currently leaves behind. |
| the CLI's contract | LOGIC-12, LOGIC-13, LOGIC-14 | A malformed question file is refused with exit 2 rather than a traceback, a coerced identity, or a directory a rerun cannot clean. |
| unused predictions | LOGIC-08 | A prediction naming an id the question file does not hold is refused or reported, not dropped in silence. |
| six narrow fixes | LOGIC-05, LOGIC-15, LOGIC-16, LOGIC-18, LOGIC-19, LOGIC-20 | Shuffle coverage, the fixture digest taking the value just measured, atomic writes, rowid error classification, pragma restoration, and the symlink check. |
| the session envelope | LOGIC-04 | The PostgreSQL envelope pins `search_path`. This changes the settings every record states, so records rendered before and after differ by those bytes and the change is stated in the release notes. |
| small corrections | CQ-L1-01, ARCH-01, ARCH-02, CQ-L3-02 | A DSN whose database name contains the word password is accepted, the backend gains `close`, the parser identity is asserted, and the three count readers become one. |
| the summary line | FEAT-04 | The line prints `other`. The README quotes that block verbatim, so the README and its test change with it. |
| the site's own pages | UI-01 to UI-06 | Search metadata, distinguishable titles, a lighter question page, a way back up, an empty state, and mechanism chips that behave with JavaScript off. |
| two measurements | PERF-02, PERF-03 | The digest is computed once; the database role is read once for a run. |
| the landing's links | HYG-03 | The three links move into the landing template, the build stops reading `site/index.html`, and the original page goes. The order matters: the build refuses to run if the page goes first. |

## Validation

Each commit carries a test that fails before it. `just check` green at each. The site changes are
checked against the rendered pages, not only against the templates.
