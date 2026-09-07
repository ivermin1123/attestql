# Phase 2: design applied and verified

## Context

Phase 1 produced correct, unstyled pages with token class hooks. This phase applies
`design-spec.md` and proves the result by rendering, not by reading the CSS. The design reference
this repository follows treats an unrendered claim about layout as an assumption.

## Requirements

- Every colour, size, spacing and duration in `report.css` is a custom property from the spec.
- Light and dark themes via `prefers-color-scheme`, dark re-tuned per the spec, no inversion.
- Fonts self-hosted, subset to Latin, licence file shipped; `font-display: swap`; a system fallback
  stack that keeps the measure within 10 percent so nothing jumps on load.
- Every state in the spec's table has its designed appearance, verified by a page that exercises
  it.
- Print stylesheet: the sticky strip becomes static, disclosures open, links show their URLs.

## Files

- `src/attestql/report/static/report.css`, `report.js`, `fonts/` (woff2 and licence).
- `tests/test_report_tokens_meet_contrast.py`: computes WCAG contrast for every text-on-background
  pair the spec names, in both themes, and for `--warn` and `--accent` on both tints.
- `tools/report-stress/build.py`: builds a stress audit directory from the packaged sandbox
  (`attestql.demo`) with a result of 10,000 rows (the record holds all of them; the page shows
  the counterexample's 25 first and the record's table below, and the build measures both the
  record's size and the page's render time), a 600-character statement, a 16-column projection,
  a timestamp column, an origin URL of 200 unbroken characters, a NULL-heavy result, and one
  question of each state in the spec's table, NOT_COMPARABLE and a refused statement included.
- `plans/reports/design-260907-report-verification.md`: the screenshots and measurements.

## Steps

1. Apply tokens and typography; subset and place the fonts.
2. Build the stress directory and render it.
3. Render at 360, 768 and 1280 px with Playwright (the `ak-agent-browser` or Playwright skill
   is available in this environment): screenshot the run page, one comparison page of each
   mechanism, one gold-only page with a fired probe, the ERROR listing, in light and dark, and
   the print rendering to PDF.
4. Squint test on each screenshot: the verdict strip and the differing rows must win on the
   question page; the counts on the run page. Record the verdict per screenshot.
5. Compute: contrast (the test), line length of the prose column at each width, the type scale
   in use (a grep of `font-size` values against the four steps), the spacing values against the
   scale, the presence of horizontal page overflow (`document.documentElement.scrollWidth`
   against `clientWidth` at each width).
6. Walk the states: tab through a question page, open every disclosure, hover and focus the
   mechanism chip, load with `prefers-reduced-motion` and confirm only opacity changes.
7. Scan the slop catalogue and the missed-details list from the design reference as a checklist
   and record each item's result.
8. Repair and re-render until one full pass is clean; commit the report.

## Validation

- The contrast test is in `just check`.
- The verification report holds a screenshot per width and theme with the measured numbers, and
  every claim in it names the act that produced it.

## Risk and rollback

- The fonts add about 100 KB; if the size budget of phase 3 is threatened, drop the 600 weight
  before dropping the family.
- Rollback: the stylesheet and fonts revert to phase 1's unstyled state; nothing else depends on
  them.
