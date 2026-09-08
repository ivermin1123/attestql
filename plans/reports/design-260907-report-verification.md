# Design verification: the report pages, rendered and measured

Phase 2 of `plans/260907-1730-attestql-web-ui/plan.md`, verified 2026-09-07 (Asia/Saigon) on the
branch `ivermin1123/web-ui`. Every claim below names the act that produced it. Nothing here is
a reading of the stylesheet: the design reference this plan follows treats an unrendered claim
about layout as an assumption, so what is asserted was rendered in Chromium and measured, or
computed by a formula, and the screenshots are beside this file.

## What was rendered, and what it was rendered from

Two directories, both written by `attestql audit`:

| Directory | What it is | Built by |
| --- | --- | --- |
| the demo | the packaged SQLite sandbox, 6 questions | `uv run attestql demo --out <tmp>` |
| the stress directory | 14 questions chosen for what they make a page do | `uv run python tools/report-stress/build.py <tmp>` |

Both were rendered with `uv run attestql report <audit> --out <dir>`. Every screenshot below is
of the stress directory unless its name says `demo`.

The stress directory holds, measured by the build: a result of 10,000 rows in a record of
863,964 bytes, whose page is 1,976,298 bytes; a 575-character gold and its 575-character
prediction; a 16-column projection; a NULL-heavy result (about a third of the cells); a
timestamp column; a 201-character origin with nowhere to break; and one question of each
state. Rendering its 11 pages takes 0.23 s (`time.perf_counter` around `render_report`, printed
by the build).

The browser is Chromium 1228 (headless shell) through Playwright 1.58.0, driven by a script in
the session scratchpad and not committed: Playwright is not a dependency of this project and
`pyright` covers `tools/`, so the driver lives outside the checked tree. Its acts are named
below so each can be repeated.

## The states of the design spec, and where each is rendered

| State | Rendered on | Screenshot |
| --- | --- | --- |
| EQUAL | q800001 (writes no directory: it is a row of the run page) | `errors-1280-light.png` |
| NOT_EQUAL, multiplicity | q800002 | `multiplicity-1280-light.png` |
| NOT_EQUAL, type | q800005, q800012 | `type-1280-light.png` |
| NOT_EQUAL, order | q800003, q800013 | `order-1280-light.png` |
| NOT_EQUAL, truncation | q800004 | `truncation-1280-light.png` |
| NOT_EQUAL, other | q800006, q800010 | `errors-1280-light.png` |
| ERROR, the parser refused the statement | q800007, step `statement` | `errors-1280-light.png` |
| ERROR, the engine refused it | q800008, step `row_counts` | `errors-1280-light.png` |
| timed out | q800009, gold side, 2 s bound | `errors-1280-light.png` |
| NOT_COMPARABLE | q800014, `mismatched: fixture` | `not-comparable-1280-light.png` |
| projection names differ | q800010 | `errors-1280-light.png` |
| duplicate ids | 800001 twice in the question file | run page, notes block |
| positions unused | position 14 of the prediction file | run page, notes block |
| GOLD-ONLY with a fired probe | q800011, `arbitrary-cut` | `gold-only-1280-light.png` |
| a quiet probe | q800011, `ordering-over-numeric-text` | `gold-only-1280-light.png` |
| a probe not applicable | q800011, `direction-against-question` | `gold-only-1280-light.png` |
| fixture: missing tables | the run's fixture block | run page, notes block |

Three states of the spec's table are not rendered, and were not faked.

- **result truncated.** No backend this tool has writes it: `postgres.py:622` and
  `sqlite.py:531` both construct an `ExecutionResult` with `truncated=False`, and nothing else
  sets it. The renderer's path for it exists and is tested by phase 1; there is no run that
  produces one.
- **unreadable tables.** A SQLite file has no grants, so `existing_tables` never reports one.
  The state arises on PostgreSQL, where the sandbox already exercises it, and it is a run-page
  row there.
- **hand classification present.** Phase 4's file, with no renderer path in phase 1. This is
  the one state of the spec's table that this phase does not render at all.

## The computed numbers

### Contrast

Computed by `tests/test_report_tokens_meet_contrast.py`, which reads the token values out of
`report.css` and applies the WCAG 2.1 formula. 35 assertions, in `just check`. Every text pair
in both themes:

| Pair | Light | Dark |
| --- | --- | --- |
| `--ink` on `--paper` | 16.36 | 15.30 |
| `--ink-2` on `--paper` | 6.85 | 7.49 |
| `--accent` on `--paper` | 6.70 | 8.32 |
| `--warn` on `--paper` | 5.90 | 8.51 |
| `--ink` on `--gold-tint` | 12.71 | 11.66 |
| `--ink-2` on `--gold-tint` | 5.32 | 5.71 |
| `--accent` on `--gold-tint` | 5.21 | 6.34 |
| `--warn` on `--gold-tint` | 4.58 | 6.48 |
| `--ink` on `--second-tint` | 12.56 | 11.72 |
| `--ink-2` on `--second-tint` | 5.25 | 5.74 |
| `--accent` on `--second-tint` | 5.14 | 6.38 |
| `--warn` on `--second-tint` | 4.53 | 6.52 |
| `--ink` on `--rule` | 11.98 | 10.80 |
| `--ink-2` on `--rule` | 5.01 | 5.28 |

The threshold is 4.5:1 for body text and 3:1 for the 20px heads and the 28px title. The lowest
is 4.53:1. The two tints against the paper are 1.29 and 1.30 in light, 1.31 and 1.31 in dark,
which is the perceptibility the spec asks of them and is asserted separately.

`--warn` on `--rule` is 4.32:1 in light and is therefore not used: a chip that marks a state
takes the gold tint as its fill instead, which is 4.58:1. The rule and the reason are in the
stylesheet beside the declaration.

**One spec value moved.** The dark tints the spec first fixed were `#2e2416` and `#16252b`,
which are 1.21:1 and 1.17:1 against the dark paper; the light pair is 1.29 and 1.30, and a tint
under about 1.2:1 marks nothing a reader sees. They are `#352a19` and `#1b2e35` in `report.css`,
the same hues lifted to 1.31:1, with every text pair on them recomputed above 5.7:1. Moved
together with the test that holds them there, per the plan's constraint, and `design-spec.md`
was brought to the same pair in review (2026-09-07), with the reason and the numbers in the
paragraph under its colour table.

### Line length

Measured in the browser by walking a `Range` character by character over the longest paragraph
of each page and counting the characters before the client rect's top changes.

Re-measured on 2026-09-08 at `55ch`, the owner's decision of that day, on the same pages and
by the same act:

| Width | Prose column | Characters on the first line |
| --- | --- | --- |
| 360 | 315 to 328 px | 40 to 44 |
| 768 | 528 px | 56 to 75 |
| 1280 | 528 px | 56 to 75 |

`ch` is the advance of the digit zero, which Plex Sans sets at 0.6em, so `55ch` is 528px at
16px and `66ch` was 634px. At 634px the same walk read 86 to 88 characters, outside the 45 to
75 band the design reference names; at 528px it reads 75 on the run page's longest paragraph
and 56 on a question page's, both inside it. The swing between the two is the paragraphs and
not the measure: the longest paragraph on a question page is the rerun line, which holds a
file path with nowhere to break, so its first line ends where that path does not fit rather
than where the column does. At 360 nothing moved, because below 768 the gutters and not the
measure decide the column.

The 66ch numbers were a review finding of 2026-09-07 and are kept above as the measurement the
decision was made against. The estimate offered to the owner then was 72 characters, scaled
from 86 by the ratio of the two widths; measured, it is 75.

### The type scale

`grep` over `report.css`: every `font-size` declaration is one of the four tokens, 3 at
`--text-body`, 18 at `--text-cell`, 2 at `--text-head`, 1 at `--text-title`, and no literal
`font-size` anywhere. Confirmed against the render: `getComputedStyle(el).fontSize` over every
element carrying text, on all 28 page renders, yields the set `{13px, 16px, 20px, 28px}` and
nothing else.

### The spacing scale

`getComputedStyle` over every element, collecting the eight box properties, on all 28 renders:
`{4, 8, 12, 16, 24, 32, 48, 64}px`, which is the spec's scale exactly. One value off it was
found and repaired: `.files__list` kept the browser's own `1em` margin at 13px text, which is
13px, and 13 is a type step and not a space one.

### Horizontal overflow

`document.documentElement.scrollWidth` against `clientWidth`, on every page of the stress
directory at each width in each theme. **Every page: equal.** The measurement is honest because
nothing on these pages hides overflow: `overflow-x: hidden` appears nowhere in the stylesheet,
so an element pushing the page sideways would show up here rather than be clipped out of the
number.

| Page | 360 | 768 | 1280 |
| --- | --- | --- | --- |
| the run page | 360 = 360 | 768 = 768 | 1280 = 1280 |
| q800003, order | 360 = 360 | 768 = 768 | 1280 = 1280 |
| q800002, q800004, q800005, q800011, q800012, q800013, q800014 | 360 = 360 | not shot | 1280 = 1280 |

Measured again at `55ch` on 2026-09-08, over the whole set: every page equal at every width in
both themes, and the strip's three children still start on the same left edge as the first
heading under them, at 360, 768, 1280 and 1440 (16, 24, 64 and 144 px, `getBoundingClientRect`
on each).

Three defects were found by this measurement and repaired, each re-measured after the fix:

1. **The question set chip was 1,465px wide.** The stress run's origin is 201 characters with
   nowhere to break, and the strip put it in a chip. The set is a line of secondary text under
   the chips now, and the strip condenses it away once the reader has scrolled past the
   question, so a sticky header cannot cover a phone screen while the rows under it are read.
2. **A `.facts` grid blew past its container.** `max-content` on the name column plus a long
   value made the whole list 634px wide inside a 328px column.
3. **A paragraph holding a URL pushed the page to 634px.** Fixed at the root: the body carries
   `overflow-wrap: break-word`, which breaks a word only where nothing else can give and
   leaves a table's own columns alone. Confirmed: on q800012 the 16-column table is 1,673px
   inside a 328px scroll region, and the page is 360px.

### The fonts

Three Latin subsets of IBM Plex, 60,788 bytes together, self-hosted with `font-display: swap`
and the OFL 1.1 text beside them; `fonts/provenance.txt` records the npm release, the URL and
the sha256 of every file and of both tarballs. `uv build` produces a wheel carrying all five
files under `attestql/report/static/fonts/` plus `method.svg`, verified by listing the wheel.

The fallback measure was measured, not assumed: the same sentence of this page's own text at
16px, in Chromium, is 1,245.97px in Plex Sans, 1,243.95px in Helvetica Neue and 1,231.16px in
Arial; Plex Mono is 1,603.20px and Menlo 1,608.69px. The two metric-matched fallback faces
carry `size-adjust: 100.7%` and `99.8%` from those ratios, with Plex's own hhea metrics as
ascent and descent overrides. Rendered with the woff2 files blocked at the network layer
(`page.route("**/*.woff2", abort)`), the prose column measures 591px against 634px with the
fonts, a difference of 6.8 percent, inside the 10 percent the phase asks for
(`fallback-1280-light.png`).

The two triangles that mark the gold and the second side, U+25C0 and U+25B6, are outside the
Latin subset and are drawn by the reader's own system font. That is stated in
`fonts/provenance.txt`.

## The squint test

Each screenshot was looked at and a verdict recorded. The question asked is the design
reference's: does the intended first element win?

| Screenshot | What should win | Verdict |
| --- | --- | --- |
| `run-1280-light.png`, `run-1280-dark.png` | the counts | wins: the counts table is the only dense block above the fold, and the verdict bar under it repeats it |
| `run-768-*.png`, `run-360-*.png` | the counts | wins at both |
| `order-1280-light.png`, `order-1280-dark.png` | the verdict strip, then the statements | wins: `q800003` at 28px and the NOT_EQUAL chip are the only filled marks in the top third |
| `order-768-*.png` | the same | wins |
| `order-360-*.png` | the same | wins, with the set line under the chips reading as secondary |
| `multiplicity-1280-light.png` | strip, then the two statements | wins |
| `truncation-1280-light.png` | strip | wins |
| `type-1280-light.png` | strip | wins |
| `other-long-1280-light.png` | strip, then the two 575-character statements | wins; the marked tokens are where the eye lands second |
| `gold-only-1280-light.png` | the GOLD-ONLY chip and the two fired probes | wins |
| `not-comparable-1280-light.png` | the NOT_COMPARABLE chip and the preconditions line | wins |
| `errors-1280-light.png` | the verdict column | wins: one column of filled chips down the table |
| `errors-360-dark.png` | the same | wins |
| `differing-1280-light.png`, `differing-1280-dark.png` | the differing rows | wins: the tinted label column is the only fill in the region |
| `method-768-light.png`, `method-768-dark.png` | the flow, then the verdict line | wins |
| the 360 dark set (7 pages) | the strip | wins on each |
| `print-q800004.pdf` | the verdict, then the rows | wins |

Two verdicts were failures before they were repairs, and the screenshots are of the repaired
pages: the 201-character set chip won the strip on every question page, and the stacked bar on
the run page read as one mark because its parts shared a colour and had no separator.

## The states walk

Every act below was performed in the browser and its result read back.

- **Tab order.** Tabbing a question page reaches, in document order: the mechanism chip
  (a `button`), each link, each `summary`. Nothing else takes focus; the chips that state
  something are `span`s and are not focusable, which is what the spec asks. The focus ring is
  `2px solid var(--accent)` at 2px offset and is visible on every one of them.
- **The mechanism chip.** Hover changes its fill from the gold tint to `--warn` with the paper
  as its text, over 120ms; focus shows the ring; clicking toggles `aria-pressed` and the token
  marking below. Its visible box is one line high and its hit area is 44px, given by an
  absolutely positioned `::before` at `inset: -10px -4px`, so the chip stays in register and a
  finger still has a target.
- **Disclosures.** Every `details` on the page was opened; each reveals its region with a
  240ms opacity fade and nothing moves.
- **Reduced motion.** Loaded under `prefers-reduced-motion: reduce`: every element's
  `transitionProperty` computes to `opacity`, the differing rows' animation is `fade-in`, and
  their `transform` is `none`. Only opacity changes. (`reduced-motion-1280-light.png`.)
- **The entrance.** At ordinary motion the differing rows run `row-in` once, 240ms, with delays
  `0s, 0.03s, ... 0.3s, 0.3s`: 30ms per row, capped at 300ms, twelve rows. Nothing loops
  (`animationIterationCount: 1` on every row).
- **Print.** Rendered to PDF with print media emulated. The strip's position computes to
  `static`; all 13 closed disclosures have a non-zero content height, so every one is open on
  paper; every differing row is visible at opacity 1 with `animation-name: none`; every
  transition duration is `0s`; a link prints its target, `" <counterexample.json>"`. The two
  tints do not print, because a browser does not print backgrounds by default: the label column
  and the glyph carry which side a row came from, which is what the spec pairs them for, and
  the PDF shows it.

## The slop catalogue and the missed details, item by item

Scanned as a checklist against `~/.claude/skills/ak-fable-thinking/references/design-taste.md`,
not from memory.

| Item | Result |
| --- | --- |
| the default stack: overused font, neutral panel, violet gradient hero, three cards | absent. One family, two weights, no hero, no cards |
| glassmorphism, neon glow, gradient text | absent. No gradient anywhere in the stylesheet |
| emoji as icons or bullets | absent. The two marks are geometric triangles, and they are `aria-hidden` beside a word |
| decoration stacking | absent. No shadow, no gradient; radius is 3px on chips and code blocks and 0 on tables |
| centre-aligned paragraphs, full-width text lines | absent. Prose is left aligned and held to 55ch; measured above |
| grey-on-grey body text failing contrast | absent. Computed: lowest pair 4.53:1 |
| five font sizes where three would do; values off the scale | absent. Four steps, measured in the render |
| animating everything; motion that communicates nothing | one animation on the page, on the rows two results differ in, once |
| placeholder tells | absent. Every number and every string on a page is read out of the JSON beside it |
| uniform card grids | absent |
| focus visibility and tab order | walked above |
| hover-only affordances | none. The one control states its state in `aria-pressed` and its label |
| touch targets under 44px | one control; its hit area is 44px, measured |
| the longest realistic string | the stress directory's business: a 575-character statement, a 201-character origin, a 16-column projection, a 10,000-row record. Three overflow defects found and repaired |
| non-Latin and diacritic text | **not covered.** The subset is Latin, and no question set this tool has read holds another script. A CJK or Vietnamese question would fall to the system font. Recorded as a limit, not a pass |
| dark mode as a re-decision | the spec's own dark values, re-tuned, asserted by a test that fails if any of the eight is inherited from light |
| empty, loading and error states | empty: "no rows" is rendered and screenshotted (`print-q800004.pdf`, page 2). Loading: there is none; a page is a file. Error: three kinds, on the run page |
| tables: numeric right aligned, tabular figures, overflow contained | all three. `cell--int` and `cell--dec` are right aligned on `tabular-nums`; the region scrolls and the page does not |
| optical versus box alignment | the glyphs sit on the text baseline beside their word; no icon in a circle anywhere |
| layout shift while fonts load | measured: 6.8 percent on the fallback, with metric overrides |
| sticky elements covering content | found and repaired: the strip drops the set line when it condenses |
| z-index collisions | one `z-index` in the file, on the strip |
| mobile safe-area insets | **not covered.** The gutter is a fixed 16px at 360 and does not add `env(safe-area-inset-*)`. On a notched phone in landscape the gutter would sit under the inset. Recorded |
| print appearance | rendered to PDF and read |

## The defect this phase's own pass missed, found in review

One defect reached the commits and was found by the coordinator's review rather than by the
pass above, so it is recorded separately: the pass measured whether a page overflowed and
never measured whether two elements on it lined up.

**The sticky strip started one gutter left of the prose under it.** Measured in Chromium on
the stress report, before the repair: `.strip__title` left against the first `.page h2` left,
32 against 64 at 1280, 112 against 144 at 1440, 384 against 416 at 1920. It is visible on the
`order-1280-light.png` and `multiplicity-1280-light.png` of the first pass. The cause is that
`.strip > *` took `width: min(100%, var(--content))` while `.page` takes that same width with
the gutter as padding inside its border box, so once `--content` binds the two content boxes
differ by one gutter on each side; below 1280 nothing binds and the two agree, which is why
the earlier renders at 360 and 768 showed nothing.

The repair is `width: min(100%, calc(var(--content) - 2 * var(--gutter)))` on `.strip > *`.
Applying it moved the title and left the two lines under it where they were, because
`.strip__facts` and `.strip__set` restate `margin` as a shorthand and dropped the auto inline
margins that do the centring; that half was found by measuring all three children rather than
the title alone. Both were repaired: the two rules keep their auto inline margins, and
`.strip__set` no longer clamps itself to the prose measure, which would otherwise have centred
a 634px line inside a 1152px box and started it 319px right of the title at 1280 (the numbers
of the 66ch measure this was repaired under; at 55ch the same clamp would centre a 528px line
and start it 312px right).

Measured again after the repair, on the run page and on the order and multiplicity question
pages, at five widths, reading `getBoundingClientRect().left` off each of the strip's three
children and off the first heading of the page under them:

| Width | Title | Chips | Set line | First `h2` | Page overflow |
| --- | --- | --- | --- | --- | --- |
| 360 | 16 | 16 | 16 | 16 | none |
| 768 | 24 | 24 | 24 | 24 | none |
| 1280 | 64 | 64 | 64 | 64 | none |
| 1440 | 144 | 144 | 144 | 144 | none |
| 1920 | 384 | 384 | 384 | 384 | none |

`--content` also gained the comment it lacked: 1216 is on no scale of the spec, and it is
1280 less the two 32px gutters that breakpoint fixes, which is the width the widest
breakpoint is designed at.

`run-1280-light.png`, `order-1280-light.png`, `multiplicity-1280-light.png`, their dark pairs
and the 768 pair for the order page were re-shot after the repair and are the ones in this
directory. The 768 pair shows no change, and was re-shot for the record.

## Acceptance

- Plan criterion 3, at 360, 768 and 1280 with the stress content: no horizontal page scroll
  (measured, every page, both themes), no clipped text (read on every screenshot), body
  contrast at least 4.5:1 and large text at least 3:1 (computed, 35 assertions in the gate).
- Plan criterion 6: every record on every page still carries "recomputed from this JSON:
  match", asserted by `tests/test_report_renders_an_audit_directory.py` and visible on the
  screenshots.
- Plan criterion 7: `just check` green. Lint, `pyright` strict, the three repository checks,
  markdownlint and cspell, 1,018 passed and 33 skipped, the Docker sandbox's 33 and the SQLite
  sandbox's 59.
- The phase's Validation section: the contrast test is in `just check`; this report holds a
  screenshot per width and theme with the measured numbers, and every claim names the act.
- `uv build` produces a wheel carrying the three woff2 files, the licence, the provenance note
  and `method.svg`.

## The three questions the owner decided, 2026-09-08

The three items this report left open for a decision were answered by the owner on 2026-09-08,
and the first is applied here.

1. **The measure is `55ch`.** 66ch set 86 to 88 characters a line, outside the 45 to 75 band;
   55ch sets 75 and 56, inside it. `--measure` in `report.css` and the Typography and Layout
   entries of `design-spec.md` carry the new value with the decision beside it, and every
   screenshot in this directory was shot again at it: the measure changes the width of the
   prose on every page, so a screenshot taken before it is a screenshot of another design. The
   measurements above are the re-measurement, not the earlier one.
2. **Figures stay a fixed 640px in their own scroll region**, with the caption carrying the
   numbers. On a 360px screen a figure is a region that scrolls sideways, the way a wide table
   is; nothing about it is redrawn for the width, because a figure scaled to a phone column
   would set the numbers on its axes at seven pixels. The text alternative under every figure
   holds the same numbers, so a reader who does not scroll loses none of them.
3. **The committed screenshots stay in the repository.** They are the evidence the design was
   verified against, and a report whose evidence lives outside the tree is a report nobody can
   check later.

## What is left for the owner

1. **A scrollable region has no keyboard stop.** A table wider than its column scrolls with a
   pointer and, in Chromium, not with a keyboard. Giving every `.rows__region` a `tabindex`
   would put ten tab stops on a question page, so it is recorded rather than done: the fix
   belongs with the site, which can give the region a stop only where the table is wide.
2. **Non-Latin text and safe-area insets**, as recorded in the checklist above.
