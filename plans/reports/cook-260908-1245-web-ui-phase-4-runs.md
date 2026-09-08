# Cook: web UI phase 4, the published runs

Date 2026-09-08, branch `ivermin1123/web-ui`, on Opus. Phase file
`plans/260907-1730-attestql-web-ui/phase-4-publish-runs.md`, with the coordinator's decisions D1
to D9. The reconciliation of every count is
`plans/reports/measurement-260908-site-publish-runs.md`; this is what was done and what was
found while doing it.

## What was delivered

- `tools/site-select/`: `audits.sh` makes the five audits again in a work directory outside the
  repository with the same inputs, digests and caps the four measurement reports state;
  `select.py` chooses the questions the site is about, states what they cost against the build's
  three budgets before copying anything, and leaves out whole questions largest first where they
  do not fit; `release.sh` makes one archive per run or group and the manifest each run's
  `published.json` is written from; `question_ids.py` is the two SQLite measurements' helper,
  copied rather than imported across `plans/`.
- `tools/site/data/`: 121 runs, 348 question directories, 15,359,482 bytes. Four benchmarks:
  `bird-dev-sqlite` as one group of eleven runs, `minidev-sqlite` as nine groups of eleven,
  `minidev-pg-gold-only` as two runs and `minidev-pg` as nine.
- The renderer and the build gained a group level, one shared `static/`, and three files a
  publisher may put beside a summary: `questions.json` (the database in the strip),
  `classification.json` with `classification-source.json` (the read-by-hand row, with the date
  read from the note and never from a template), and `published.json` (the release asset on the
  run page). A directory the audit wrote holds none of them and renders as it did.
- The release of `v0.2.2`: 21 archives, 142,047,367 bytes, with `SHA256SUMS`.
- The preview: <https://attestql-ui.pages.dev>, deployment
  <https://b5a78fd6.attestql-ui.pages.dev>.

## The seven commits

| step | commit | what |
| --- | --- | --- |
| 1 | `feat(site): the scripts that make the five published audits…` | `audits.sh`, `select.py`, `question_ids.py` |
| 2 | `feat(report,site): a group level, one shared static directory…` | the renderer and the build, with their tests |
| 3 | `feat(site): publish the five audits, and select what the site shows…` | 1,526 files of data |
| 4 | `docs: the group level, the three files beside a summary…` | NOTICE, `docs/audit-command.md`, the D1 amendments |
| 5 | `feat(site): the release assets of the whole runs…` | `release.sh`, 121 `published.json` |
| 6 | `fix(report): let a fact whose name is a sentence wrap…` | the layout fix the browser pass found, with its evidence |
| 7 | this commit | the reconciliation, the two READMEs, the status lines |

## Four things found while doing it

**A grep for "timeout" now matches every run.** The two measurement scripts' `rerun_timeouts.sh`
find a run to make again by grepping its stdout for `timeout|timed out`. The audit's closing line
now states "0 timed out (0 gold, 0 prediction)" whether anything did or not, so that grep matches
all 110 SQLite runs and the first pass began rerunning every one of them alone. `audits.sh` reads
`timed_out` out of the run's own `summary.json` instead, which names the questions. 24 runs were
actually made again; 23 of them reported the same questions alone.

**Two rerun passes must not walk each other's runs.** The PostgreSQL stage's rerun pass started
while the SQLite one was still going and moved a directory the other had just written. One run,
`bird-dev-sqlite/dev-20251106/card_games`, lost its under-load copy that way; what is published
there is a serial rerun and is sound. The pass now takes a path prefix and each stage reruns only
its own engine's runs.

**121 copies of the fonts is a tenth of the site's weight.** `render_report` copies the
stylesheet, the script and the three woff2 files beside every report, which is right for a
directory a person moves and wrong for a site of 121 runs: 968 files and 11.9 MB of the same
eight files. The renderer now takes a `static_root`, empty for `attestql report` and a path to
the site's own `static/` for the build, and the link each page carries is measured at every depth by
a test rather than assumed.

**The landing's three numbers are the first facts here whose name is a sentence.** Under
`grid-template-columns: max-content` the first name was 409px wide at a 360px viewport and pushed
the whole page sideways. That state could not exist before this phase, because the aggregate the
numbers come from did not. A column that may shrink below its
maximum content differs from one that may not only where the name would not fit.

## What was measured

**The gate.** `just check` green before every commit, exit status read from
`/tmp/attestql-runs/check.log`.

**The build.** 2,218 files, 40,624,541 bytes, 3.5 s, against 8,000 files, 41,943,040 bytes and
2,097,152 a page; the largest page is 1,806,501. `grep -rl /Users/ tools/site/data build/site`
prints nothing.

**In the browser.** Chromium 1228 through Playwright, the landing, the runs index, the
`minidev-pg` benchmark index, a `minidev-sqlite` group page, a question page with a read-by-hand
row, one without, a filter page and the method page, at 360, 768 and 1280 in both themes, 48
renders: none scrolls sideways, the type is `{13, 16, 20, 28}px`, the spacing is the eight-step
scale, the read-by-hand row is on the one page that has one, and no page carries the banner.
`site-measurements.json` and twelve screenshots are in
`cook-260908-1245-web-ui-phase-4-runs/`.

**Four questions read by hand against their JSON on the built pages.**

- **q879**, `minidev-pg-gold-only/zip` and `minidev-pg/gpt-35-turbo`. The gold-only page states
  the one fired probe `ordering-over-numeric-text`, one row in the record, `formula_1` in the
  strip and "recomputed from this JSON: match". The prediction page states EQUAL with BIRD's own
  check 1 and the test-suite check 1, both results one row: this prediction reproduces the gold's
  text ordering, which is the unjust one the aggregate names.
- **q207**, `minidev-pg/gpt-4`: NOT_EQUAL, BIRD 0, the test-suite check 0, mechanism `other`, gold
  13 rows against the prediction's 5, no probe fired, `toxicology` in the strip. Every one of
  those is what `counterexample.json` states.
- **q1029**, `minidev-pg/gpt-4`: NOT_EQUAL, BIRD 0, mechanism `other`, four rows on each side,
  `european_football_2` in the strip.
- **q1473** is on no page, and that is right. It has a directory in one run only,
  `minidev-pg/gpt-35-turbo`, where it is NOT_EQUAL and BIRD scores 0, so it is not a
  credited-but-unequal row; no probe fires on it and no classification holds it. The note of
  2026-09-04 evening predicted exactly this: with every statement running without parallel
  workers the float sum reproduces, so the other eight files agree to sixteen digits.

**The preview**, by `curl`. The landing serves 164, 66 and 23 with the file each was read from in
a `title`, and no banner. (The second number is 69 after the second review below; 66 is how many
of them have a page.) `runs/minidev-pg/gpt-4/q1029/`, its `evidence-gold.json`,
`runs/minidev-sqlite/gpt-4/` (with "The sums of the 11 runs") and the read-by-hand page all
answer 200. A run page's release-asset link resolves: the archive itself answers 200 from
GitHub.

**attestql.com is unchanged.** Its body hashes to
`a2bacd52fdda77714b8d4b3a3f429776912674795f6c545cfea1f60519a38e93`, which is `site/index.html`
byte for byte, and `git status site/` is empty.

## What is not done here

Phase 5, the in-browser drop zone. The switch of attestql.com onto this site, and the GitHub
Actions deployment that goes with it, are the coordinator's step and were not touched: no
workflow was added, the `attestql` Cloudflare project, the domain and the DNS record were not
reached, and `site/index.html` and `README.md` were not edited.

## Second review, 2026-09-08

The coordinator reviewed the published runs on Fable, with its own measurements in stage 1 and a
code review in stage 2. Two findings were about what a page states and seven about the code that
makes it. All are fixed, in four commits, each with tests.

**The landing's second number was the file budget's, not the benchmark's.** `aggregate.json`
stated 66 where the classification joined to the nine runs holds 69, because the three rows on
questions too large to have a page were dropped from the count as well as from the site. Each key
now carries `value` and `published`; the landing shows `value` and, under a number whose
`published` is below it, one line saying how many have a page and how many are whole in the
release assets. Nothing else is computed in the build: the line is one subtraction, and the
proportion bar is still drawn from `value`.

**The read-by-hand row said `A` and stopped.** The note beside each classification now carries
what every class of it means, cut verbatim out of the legend of
`plans/reports/measurement-260904-0046-prediction-mode-on-real-predictions.md` for the
prediction-mode file and out of the BIRD dev file's own `reading` string for the other, with
`classes_source` naming where each was cut from. A class no source defines renders as the value
the row holds, escaped, and nothing beside it.

**A run page said how many questions it showed and never how many the run wrote.**
`release.sh manifest` now counts the question directories inside each archive, through a new
`manifest.py`; each `published.json` carries the one count its page is about; and the run and
group pages state "this site holds N of the M question directories this run wrote". The archives
were not rebuilt: their digests are unchanged and nothing was re-uploaded.

The six from the code review:

| Finding | What was done |
| --- | --- |
| `postgres_up` ran the auditor-role pipeline and the dump load without checking either, under `set -uo pipefail` with no `-e` | both checked; the load is checked by its result, the 75 tables of schema `public` the Mini-Dev fixture holds, because psql exits non-zero on a whole load |
| the container's teardown was registered after `postgres_up` returned, and the health loop had no deadline | `trap postgres_down EXIT` before `docker run`, and the 90 second deadline `tools/audit-sandbox/run.sh` uses, failing with the container's last lines |
| the release asset's address reached an `href` unchecked, where a `javascript:` value would run on a click | refused unless it begins with `https://`, in the renderer and in the selection, each with its own refusal |
| two rows for one question collapsed silently into whichever came last | identical rows collapse; rows that differ are refused and named, and `questions.json` is deduplicated by id, which is what the audit does with BIRD's repeated 137 and 138 |
| a symlinked file inside a run was followed by `shutil.copyfile` | refused in both copies, with the words the build refuses a symlinked directory with |
| the two scripts' three budgets could drift apart, and `release.sh` did not check its tar | a test compares the two files' own source; the tar is checked and the part-written archive removed |

`select.py` is not imported by any test: its own name is the standard library's `select`, and
`tests/test_boundary.py` forbids `importlib` in `src/` and `tests/` for the reason its one
exemption states, that `importlib.metadata` imports no code. What the tests read instead is what
it wrote, over the whole of it: 131 published lines, 22 classifications, 121 runs and the
aggregate, plus the two files' budgets compared as source. The renderer's own copies of the same
rules are tested by calling them.

**Verified on the redeployed preview** (deployment `aa41fc9b`, the fifth): the landing serves 69
with "66 of them have a page here; the other 3 are whole in the release assets";
`/runs/minidev-pg/gpt-4/` serves "This site holds 26 of the 218 question directories this run
wrote"; `/runs/minidev-sqlite/gpt-4/` serves the group's 7 of 269 and links
`minidev-sqlite-gpt-4.tar.gz` on the release; `/runs/minidev-pg/gpt-4/q249/` states class A with
the report's own words for it. `just check` green at 1,085 passed and 33 skipped. attestql.com
was not touched.

## Unresolved

- Three of the 69 questions a maintainer read by hand are on no page, so the site publishes 66
  of them: their evidence records are 4.5 to 8.8 MB, and a page of one would be 5 to 10 MB
  against a 2 MiB budget. They are whole in the release assets, and `left-out.json` names them.
  The landing states 69 and says under it that 66 have a page here. Publishing the three needs a
  renderer that bounds the rows it draws from a record, which changes what a page is.
- `minidev-pg-gold-only/hf` states 38 probe fires where the 2026-09-03 summary states 39. The
  number of golds the shuffle probe fires on is unchanged in both copies; what moved is which of
  them are labelled `float-aggregate-order`, because a float sum that used to differ between two
  orderings no longer does. Whether the golds that stopped firing it should be read again is a
  question for whoever owns that classification.
