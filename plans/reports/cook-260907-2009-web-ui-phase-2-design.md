# Cook report: phase 2, the design applied and verified

Worked 2026-09-07 20:09 to 21:30 (Asia/Saigon) in the worktree `~/orca/workspaces/attestql/web-ui`,
from `8fd4458`. Scope: phase 2 of `plans/260907-1730-attestql-web-ui/plan.md` only, per
`plans/260907-1730-attestql-web-ui/phase-2-design-and-verification.md` and `design-spec.md`.
Nothing of phase 3 was started: no `tools/site/`, no landing or method page, no pre-rendered
filter paths, no deployment. Gate green, committed.

The measurements and the screenshots are the other report,
`plans/reports/design-260907-report-verification.md`. This one is what landed and why.

## What landed

| File | What it is |
| --- | --- |
| `src/attestql/report/static/report.css` | the design: tokens, typography, layout, states, motion, print |
| `src/attestql/report/static/fonts/` | three Latin subsets of IBM Plex, the OFL text, a provenance note |
| `src/attestql/report/static/method.svg` | the method figure, authored by hand, classes and no colours |
| `src/attestql/report/figures.py` | the slope, the two bar figures, the run's two, and the landing bar as a function |
| `src/attestql/report/templates/_figure.html` | one figure and the same numbers under it |
| `src/attestql/report/templates/` | the figures placed, the strip reordered, one row hook |
| `src/attestql/report/render.py` | the counts a figure is drawn from, the figure attached, the static tree copied |
| `src/attestql/report/static/report.js` | every disclosure open before printing, and put back after |
| `tests/test_report_tokens_meet_contrast.py` | 35 assertions: WCAG over the tokens read out of the stylesheet |
| `tests/test_report_figures_are_deterministic.py` | 14 assertions: the same bytes twice, a title, an alternative, one line per row |
| `tests/test_report_copy_never_judges.py` | `figures.py` added to the files the rule is read over |
| `tests/test_report_renders_an_audit_directory.py` | three tests: the run's figures, a question's figure, the fonts beside the pages |
| `tools/report-stress/build.py` | the stress directory: 14 questions, every state, built by the tool itself |
| `pyproject.toml` | `static/fonts/*` in the package data |
| `NOTICE`, `cspell.json` | the OFL paragraph; five words the report needed |

## Decisions, and why

- **The figures read the view model, not the JSON.** `figures.py` imports the standard library
  and, under `TYPE_CHECKING`, the render module's type names. A figure is arithmetic over
  integers that were read out of a document somewhere else, which is what makes it byte
  identical on a second render and what keeps the import boundary the renderer is built on.
- **A figure is a fixed size in its own scroll region, not a fluid one.** The spec puts the
  numbers on a figure at 13px. An SVG with a `viewBox` and no width scales its text with its
  box, so a slope chart in a 328px column would state its axis numbers at seven pixels. It is
  640px wide with `width` and `height` attributes, inside a region that scrolls sideways the way
  a table's does, and the text is 13px at every width.
- **Marks carry classes; the stylesheet gives them colour.** `var()` is not a value an SVG
  presentation attribute reads. This is what lets one committed `method.svg` hold in light, in
  dark and on paper, and it is asserted: the run page's markup holds no `fill=` attribute.
- **The run page's mechanism counts are counted from the directories.** `summary.json` counts a
  mechanism only for the rows another evaluator credited, so a gold-only run states none at
  all. `RunPage` gained `verdict_counts`, `mechanism_counts` and `questions_audited`; the
  mechanisms are counted from the question pages the run wrote, largest first then by name, so
  two renderings draw one bar.
- **The strip states the verdict first and the question set last.** The set is named by its file
  and, when the run was told one, by the origin that file came from, which a benchmark may
  write as a URL of any length. As a chip it was 1,465px wide and the loudest thing on the
  page; it is a line of secondary text under the chips, and the strip drops it when it
  condenses, so a sticky header cannot cover a phone screen while the rows under it are read.
- **`--warn` never sits on `--rule`.** 4.32:1 in light. A chip that marks a state takes the gold
  tint, 4.58:1. The rule and its number are in the stylesheet beside the declaration.
- **Two dark tokens moved.** The spec's dark tints are 1.21:1 and 1.17:1 against the dark paper
  and the light pair is 1.29 and 1.30; a tint a reader cannot see marks nothing. They are the
  same hues lifted to 1.31:1, moved together with the test that holds them there, and reported.
  `design-spec.md` is not this phase's to edit, so its table still states the old pair.
- **The stress directory is built by the tool, not written by hand.** `attestql.demo`'s own
  fixture with tables and rows on top of it, a question file and a prediction file like any
  other pair, and `attestql audit --engine sqlite` over the three. Every JSON in it came from
  the audit's own writers.
- **NOT_COMPARABLE is built from two records against two fixtures.** Both records of a
  comparison come from one session, so one run never writes one. The builder records the same
  statement against two fixtures that differ by one row in the table the statement reads,
  compares them with `compare_r_ord`, and writes the directory with `write_comparison` and
  `smells_json`. Nothing is edited afterwards, and the question is excluded from the run with
  `--ids` so the summary counts what the run actually audited.
- **The Playwright driver is not committed.** Playwright is not a dependency of this project and
  `pyright` strict covers `tools/`. The driver ran from the session scratchpad; its acts are
  named in the verification report so each can be repeated.

## What the rendering found, and what was repaired

Every one of these was found by a measurement or by looking at a screenshot, not by reading the
stylesheet. Each was repaired and re-rendered.

1. **The question set chip pushed every question page 1,137px past the viewport at 360.**
   Repaired as above.
2. **A `.facts` grid blew past its container**: `max-content` on the name column made the list
   634px wide inside a 328px column.
3. **A paragraph holding a URL pushed the page to 634px.** Repaired at the root, with
   `overflow-wrap: break-word` on the body, which breaks a word only where nothing else can
   give and leaves a table's own columns alone.
4. **`.files__list` kept the browser's `1em` margin at 13px text**, which is 13px, and 13 is a
   type step and not a space one.
5. **The reduced-motion rule lost to more specific declarations.** `transition-property: opacity`
   on a universal selector does not beat `.strip { transition: padding ... }`; it is
   `!important` now, and the render confirms every element computes to `opacity`.
6. **The stacked bar read as one mark.** Its parts shared a colour and had no separator; there
   is a pixel of paper between them now, and every part is labelled on the first row below the
   bar that is free, a row being added when none is.
7. **Chips broke mid-word in the question index**, the last letter of NOT_COMPARABLE printing
   on a line of its own: `overflow-wrap: anywhere` let the table size the column down to one
   character. A chip is `white-space: nowrap` now.
8. **The slope chart printed its left axis numbers on top of each other** when twenty-five rows
   of a forty-row result stood closer together than the numbers naming them. Both axes now write
   a number only where there is room, and the text under the figure states them all.
9. **The disclosures did not open in print**, and `method.svg` had no rule for its own classes,
   which is why its notes rendered at the body size and its verdict line was not `--warn`.

## Tests

| File | What it observes |
| --- | --- |
| `tests/test_report_tokens_meet_contrast.py` | every text pair the spec names, in both themes, against 4.5:1 and 3:1, from the values in the stylesheet; each tint against the paper; that no dark colour is inherited from light |
| `tests/test_report_figures_are_deterministic.py` | each of the six figures built twice from one model, byte identical; a `<title>` naming a file; a text alternative holding a number; the SVG pointing at it; the slope chart drawing one line per row of a known ten-row `order` counterexample with nine marked; `type` and `other` drawing none |
| `tests/test_report_renders_an_audit_directory.py` | the run page's two figures with the summary's own counts in their titles and captions and no `fill=` anywhere; a `truncation` question drawn and an `other` question not; every font the stylesheet asks for written beside it, byte identical to the package's, with the licence and the provenance note |
| `tests/test_report_copy_never_judges.py` | the forbidden phrases over `figures.py` as well as every template |

`just check`: green. Lint, `pyright` strict, the three repository checks, markdownlint and
cspell, 1,018 passed and 33 skipped, the Docker sandbox's 33, the SQLite sandbox's 59.
`uv build` produces a wheel carrying the three woff2 files, the licence, the provenance note and
`method.svg`.

## Acceptance

Plan criteria 3, 6 and 7 met, each by the act named in the verification report. The phase's
Validation section: the contrast test is in the gate, and the verification report holds a
screenshot per width and theme with the measured numbers and names the act behind every claim.
Both sandbox audits still render (the gate's own tests). Every file the phase names exists.

## Left for the owner, and for phase 3

1. `66ch` measures 86 characters, and the design reference's band is 45 to 75. `55ch` measures
   72. Not changed: `design-spec.md` is accepted and is not this phase's to edit.
2. `design-spec.md` still states the dark tints this phase moved.
3. A table wider than its column scrolls with a pointer and not with a keyboard. A `tabindex`
   on every `.rows__region` would put ten tab stops on a question page; the fix belongs where a
   region can be given a stop only when its table is wide.
4. Non-Latin text falls to the system font (the subset is Latin), and the gutter does not add
   `env(safe-area-inset-*)`.
5. Three states of the spec's table are not rendered by this phase and are not faked:
   `result.truncated` (no backend writes it), unreadable tables (a file has no grants), and a
   hand classification (phase 4's file, no renderer path).
