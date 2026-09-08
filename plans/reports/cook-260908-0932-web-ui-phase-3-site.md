# Cook: phase 3, the site build, the landing and method pages, a preview deployment

Phase 3 of `plans/260907-1730-attestql-web-ui/plan.md`, on the branch `ivermin1123/web-ui` in the
worktree `~/orca/workspaces/attestql/web-ui`, 2026-09-08 (Asia/Saigon), on Opus per the owner's
model rule. Four commits on top of `ab4a99f`. The screenshots and the browser measurements are in
`cook-260908-0932-web-ui-phase-3-site/` beside this file.

| Commit | What it is |
| --- | --- |
| `6e0a896` | step 0: the measure moves to `55ch`, the owner's decision of 2026-09-08 |
| `dbf3f6a` | the pre-rendered filter pages in the package renderer |
| `0b770ef` | `tools/site/build.py`, the four site templates, the two READMEs, the tests |
| `daaf66f` | one paragraph in `docs/developer-environment.md` |

## Step 0: the three owner decisions of 2026-09-08

**The measure is `55ch`.** `--measure` in `report.css`, and the Typography and Layout entries of
`design-spec.md`, with the decision, its date and the two measurements beside the value.

Because the measure changes the width of the prose on every page, a screenshot taken before it is
a screenshot of another design, so the whole verification directory was made again from the same
acts phase 2 used: `uv run python tools/report-stress/build.py <tmp>`, then
`uv run attestql report <tmp>/stress --out <tmp>/report`, then the phase 2 driver in the session
scratchpad, in Chromium 1228 through Playwright 1.58.0. Every screenshot in
`plans/reports/design-260907-report-verification/` is the new render under its existing name, at
the same width and theme.

Measured again, by the same act (a `Range` walked character by character over the longest
paragraph of each page):

| Width | Prose column | Characters on the first line | Before, at 66ch |
| --- | --- | --- | --- |
| 360 | 315 to 328 px | 40 to 44 | 40 to 44 |
| 768 | 528 px | 56 to 75 | 86 to 88 |
| 1280 | 528 px | 56 to 75 | 86 to 88 |

The estimate offered to the owner was 72, scaled from 86 by the ratio of the two widths; measured
it is 75 on the run page's longest paragraph and 56 on a question page's. The swing between the
two is a property of the paragraphs and not of the measure: the longest paragraph on a question
page is the rerun line, which holds a file path with nowhere to break, so its first line ends
where that path does not fit. At 360 nothing moved, because below 768 the gutters and not the
measure decide the column. Nine screenshots at 360 and the two of the method figure are byte
identical to the ones before, which is the same fact from the other side.

Overflow was measured again on every page of the stress directory at every width in both themes:
`document.documentElement.scrollWidth == clientWidth` on all of them. The strip's three children
still start on the same left edge as the first heading under them, at 360, 768, 1280 and 1440
(16, 24, 64 and 144 px).

**Figures stay a fixed 640 px in their own scroll region** and **the committed screenshots stay.**
Both were already the state of the tree, so both are recorded in the verification report rather
than applied; its "What is left for the owner" now holds only the three items still open, and the
one it listed about the dark tints was dropped because `design-spec.md` had already been synced to
the tested values in the phase 2 review.

## The filter pages

The design spec puts the run page's filters at their own paths, because a static host reads no
query string and this project ships no script that filters. Every render of `attestql report` now
writes, beside the run page and the question directories:

```text
not-equal/index.html
by-mechanism/<class>/index.html      one per class the run's counterexamples hold
by-probe/<name>/index.html           one per probe that fired
```

Each is the run page's own index with the rows its rule drops removed, a line saying what it kept,
and a link back to the whole. A filter no row satisfies is not written, and the run page links to
exactly the ones that exist. The markup of the index moved into `templates/_index.html`, a macro
both `run.html` and the new `filter.html` call, so the index exists once; the `root` the macro is
given is what makes a question's path reachable from one directory down or two.

The marker rule follows: `.attestql-report` now names the three directories, and a rerun clears
them the way it clears `q<id>/`. On the packaged sandbox that is six filter pages
(`not-equal`, two classes, three probes), and `by-mechanism/multiplicity` and the two quiet probes
get nothing.

`docs/audit-command.md` gained one paragraph naming the three paths and the clear.

## The site build

`tools/site/build.py` renders every run under `tools/site/data/<benchmark>/<run>/` with the phase 1
renderer into `build/site/runs/<benchmark>/<run>/`, writes one index per benchmark and one over all
of them, then the landing and the method page from `tools/site/templates/`. The two templates
extend the package's `base.html` and take its stylesheet, its script, its fonts and `method.svg`,
copied once to `build/site/static/`, so there is one design and not two.

**Nothing on the landing is typed by hand that an artifact states.** In the phase's order:

| On the page | Read from |
| --- | --- |
| the one sentence | `description` in `pyproject.toml` |
| the command and its unedited output | `attestql demo` run at build time, inside the scratch directory and told `--out demo`, so the paths it prints are the relative ones a reader would see |
| the run id and the time | that run's `summary.json`, named on the page as this build's |
| the differing rows of q879 | that run's `counterexample.json`, through `attestql.report.render.question_page`, rendered by the same `rows_table` macro the question page uses |
| the principle sentence | a named value in `build.py`, which the design spec allows verbatim |
| the three headline numbers | `tools/site/data/aggregate.json`, each with its source in a `title` attribute; absent, the landing says so in the banner's voice and shows no number, and the proportion bar is not drawn |
| the install line | the line of `README.md` that holds `pip install attestql` |
| the run table | each run's `summary.json`: date, engine, question set origin, question set digest |
| the three links at the foot | the `nav` of `site/index.html`, read and never edited |

The method page is generated from the strings the package holds: R-ORD and R-SET from
`compare_r_ord` and `compare_r_set`'s own docstrings, the descriptor from the `SERIALIZATION` every
result is rendered under, the seven settings from `session_preconditions()`, every probe and its
meaning from `probe_meanings()`, the five classes and the two `reading` strings from `compare.py`,
and the two benchmark readings from `BIRD_EX_METHOD` and `TEST_SUITE_EX_METHOD` with their sources.
The two readings' names are now constants in `render.py` (`BIRD_READING`, `TEST_SUITE_READING`), so
the question page and this page cannot call them two things. `method.svg` is inlined and carries
its own `title` and `desc`; the visible caption is the same words for a reader who has the picture
and cannot read it, and is `aria-hidden` so it is not read twice. The flags link out to the
repository's rendered `docs/audit-command.md`, because the site does not serve `docs/`.

**The stand-in.** `tools/site/data/` holds only a `README.md`, which states what a benchmark and a
run directory are and the shape of `aggregate.json` (three keys, each with `value` and `source`).
The build audits the packaged sandbox into a scratch directory under `build/` and renders it as the
benchmark `sandbox`, run `demo`; nothing from it is written into `tools/site/data/`. Every page of
the built site carries one banner line, from the `banner` variable `base.html` gained, saying the
runs shown are the packaged sandbox and the published ones arrive with phase 4. **A benchmark
directory appearing under `data/` is what removes it**, not an edit, which is asserted by building
with a benchmark directory present and reading every page back.

**Budgets.** The build fails over 8,000 files, over 40 MB in total, or with any page over 2 MB, and
names the offenders worst first. Each of the three was failed on purpose in a test, because a
checker never seen to fail is not known to work. It prints the file count, the total bytes and the
wall time.

**Refusals.** An `--out` inside `site/` is refused with nothing written, resolved first so a
relative path, a symlink and a `..` are the same answer. An `aggregate.json` missing one of the
three keys is refused rather than showing two numbers where a reader expects three. A `README.md`
with no `pip install attestql` line is refused rather than a line being typed.

## What was measured

**The build**, on the sandbox stand-in: **55 files, 524,181 bytes, 0.1 to 0.6 s.** Against the
budget: 0.7 % of the 8,000 files, 1.3 % of the 40 MB, and the largest page is 31 KB against the
2 MB bound. Plan criterion 4's two minutes is not close.

**Determinism.** Two builds into the same output directory: 25 of 55 files byte identical; 14
differ only in the demo run's id and its timestamps; 16 differ also in a hash those two feed
(`record_hash` is taken over a document that holds the run id and the executed-at) or in the
audit's own `elapsed_seconds`. **Nothing else differs**, measured by masking the run id and the
timestamps and diffing what was left. Two builds into two *different* output directories differ
additionally in the recorded backend identity, which is `SQLite <version> | file=<absolute path> |
size=<bytes>` and therefore carries the scratch directory's own path; the build's own `--out` is
fixed at `build/site`, so on one machine the path is fixed too. It is the audit's recorded value
and this phase does not change what a record states.

**In the browser.** Chromium 1228 through Playwright 1.58.0, five pages (the landing, the method
page, a run page, a question page, a filter page) at 360, 768 and 1280 in both themes, thirty
renders:

- **no page scrolls sideways**: `scrollWidth == clientWidth` on all thirty. What sits past the
  viewport edge is inside its own `overflow-x: auto` region, which is the design: the run table on
  the landing at 360 and 768, the index table on a filter page at 360, and the 640 px figures on
  the method and run pages at 360.
- **the type scale is the four tokens** and nothing else: `{13px, 16px, 20px, 28px}`.
- **the spacing is the eight-step scale** and nothing else: `{4, 8, 12, 16, 24, 32, 48, 64}px`.
- **the banner shares a left edge with the prose** at every width: 16 at 360, 24 at 768, 64 at 1280.

Twelve screenshots, the landing and the method page at the three widths in both themes, are beside
this file with `site-measurements.json`, which holds every number above.

**The preview.** Deployed from `$TMPDIR`, outside the repository, with
`npx --yes wrangler@4.129.0 pages deploy <repo>/build/site --project-name attestql-ui --branch
web-ui`, after confirming the project with `pages project list`. 55 files uploaded in 2.16 s.

- <https://attestql-ui.pages.dev> and the deployment's own address
  <https://843f9699.attestql-ui.pages.dev> both answer 200. The first request answered 522 and the
  second, fifteen seconds later, 200; a fresh Pages deployment takes a moment to be routable.
- The landing serves the one sentence (`grep` for the `pyproject.toml` description: found).
- `/runs/sandbox/demo/q879/index.html`, `/runs/sandbox/demo/not-equal/index.html`, `/method/`,
  `/runs/sandbox/demo/`, `/runs/`, `/runs/sandbox/` each answer 200 through one 308 that Pages adds
  to drop `index.html` from the address. `/runs/sandbox/demo/q879/counterexample.json` answers 200
  as `application/json`, 5,488 bytes. `static/report.css` and the woff2 answer 200.
- The question page carries "recomputed from this JSON: match" four times, the filter page carries
  its restriction line, the method page names the probes, and the landing carries the banner.

**attestql.com is unchanged.** `curl https://attestql.com/` returns 200, 5,284 bytes, and the
sha256 of the body is `a2bacd52fdda77714b8d4b3a3f429776912674795f6c545cfea1f60519a38e93`, which is
the sha256 of `site/index.html` in this checkout; `cmp` reports the two identical. `pages project
list` still shows `attestql.com` on the `attestql` project. Nothing in this phase touched that
project, the domain or the DNS record.

**The one network.** The phase asks for a second network to check the preview from. This session
has one, the machine's own, so the verification above is from one network and is stated as such.
What a second network would add is a check that the address is not resolving through something
local; nothing in this deployment is local, and the `pages.dev` address is Cloudflare's own.

## The gate

`just check` green after each of the four commits. At the last: ruff, `pyright` strict over `src`,
`tests` and `tools`, the three repository checks, markdownlint and cspell over 44 documents,
**1,045 passed and 33 skipped**, the Docker PostgreSQL sandbox's 33 and the SQLite sandbox's 78.
Phase 2 ended at 1,018; the 27 new are the filter pages, the site build and the copy rule extended
to the site's templates.

New tests:

- `tests/test_site_builds_from_the_sandbox.py`, ten tests: the site is built and every page is
  where it should be; the landing states nothing it did not read out of `pyproject.toml`,
  `README.md` or `site/index.html`; it shows the rows of the question it names, read back out of
  that run's own `counterexample.json`; it shows no number and no bar without the aggregate and
  three numbers with their sources with it; the method page holds every probe, every meaning and
  all seven preconditions; the banner is on every page without data and on none with it; an `--out`
  inside `site/` is refused; and each of the three budgets fails the build when crossed.
- `tests/test_report_renders_an_audit_directory.py` gained three: the filter pages hold the rows
  the run page and the summary state, an empty filter is not written and is not linked, and a rerun
  clears a filter the run before it wrote. Its byte-identical test now covers the filter pages too.
- `tests/test_report_copy_never_judges.py` reads `tools/site/templates/*.html` under the same rule,
  and refuses to pass if that directory is empty.

## Decisions taken, and the ones a reviewer should look at

1. **The demo is always run and always rendered**, as the benchmark `sandbox`, whether or not
   `data/` holds published runs. The landing opens with the demo command, its output and one of its
   questions' rows, and those rows have to be a page on this site rather than a quotation of one.
   Phase 4 adds its benchmarks beside the sandbox and the banner goes.
2. **`base.html` gained a `banner` variable and `render_report` a keyword-only `banner=""`.** The
   phase asks for the banner to come from a template variable and to be on every page of the site,
   and the run and question pages are the pages the banner is most about. The default keeps
   `attestql report` writing what it wrote.
3. **`question_page()` is public in `render.py`**, the second accessor this plan adds for the
   pages of phase 3 after the two of phase 1. The landing shows one question's differing rows
   through the same macro the question page shows them through, and a second reader of
   `counterexample.json` written in `tools/` would be a second answer to what those rows are.
4. **`pyproject.toml` gained `tools/site` to the pytest `pythonpath` and the pyright
   `extraPaths`.** The phase fixes the file at `tools/site/build.py`, `tools` is already on both,
   and without the entry `pyright` cannot resolve the test's import of it. It touches no package
   data and adds no dependency.
5. **`build/site/index.html` is a landing, and `build/site/runs/index.html` is an index over the
   benchmarks.** The phase names the benchmark index and the runs index separately; both exist.
6. **The three keys of `aggregate.json` are `credited_but_not_equal`, `classified_by_hand` and
   `bird_dev_classified_by_hand`**, defined in `HEADLINE` in `build.py` and stated in
   `tools/site/data/README.md` with the file each is expected to be read out of. Phase 4 fills
   them; the build refuses a file missing one.

## What is left

- **Phase 4 fills `tools/site/data/`** and the banner goes by itself. Nothing in this phase's code
  has to change for that; the budgets the build enforces are the ones phase 4's dry run is
  measured against.
- **A wide table still has no keyboard stop.** Carried from the phase 2 verification report, where
  it was recorded as belonging to the site. The site's own tables (the run table on the landing,
  the index on a filter page) scroll sideways at 360 and 768 and, in Chromium, do so with a pointer
  and not with a keyboard. It is not repaired here: giving every `.rows__region` a `tabindex` puts
  ten stops on a question page, and doing it only where the table is actually wider than its column
  needs a measurement at render time that the renderer does not make.
- **The owner's switch.** Replacing what attestql.com serves is an owner step, recorded in the
  phase file and in `tools/site/README.md` and not performed: deploy `build/site` to the project
  `attestql` with the same command, and retire `site/index.html` in a commit on `main`. The GitHub
  Actions deployment belongs to that switch and is not added.
- **A second network.** Stated above.
