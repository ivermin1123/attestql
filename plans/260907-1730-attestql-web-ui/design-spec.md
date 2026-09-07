# Design spec: tokens, layout, states, motion, copy

Fixed before any markup is written. Every value in the templates and the stylesheet comes from
this page; a value not on a scale here is a finding in review.

## Register

A lab notebook, a court exhibit. Calm, dense, exact. The reader is a maintainer or a researcher
who is going to check what they read. Nothing on the page is there to impress; everything is there
to be checked.

## Colour

Light theme first; dark theme is a re-decision, not an inversion. Contrast is computed in a test
against these values, so the values may move, but only together with the test.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--paper` | `#FAF9F6` | `#151412` | page background |
| `--ink` | `#1C1B18` | `#ECEAE4` | body text |
| `--ink-2` | `#5A5750` | `#A9A59B` | secondary text, labels |
| `--rule` | `#DAD7CF` | `#33312C` | borders, table rules |
| `--accent` | `#1F5F7A` | `#7FB6CF` | links, focus ring, the one emphasis |
| `--warn` | `#9A4B00` | `#E8A24C` | NOT_EQUAL, a fired probe, a timed-out or errored side |
| `--gold-tint` | `#F3DBA6` | `#2E2416` | rows in gold, not in second |
| `--second-tint` | `#CCDFEA` | `#16252B` | rows in second, not in gold |
| `--null` | `--ink-2` on a dotted underline | same | a NULL cell, a state not a string |

Rules: `--accent` is the only colour that says "look here". `--warn` marks a state, never a
judgement, and is always paired with a word. No green anywhere. The two tints never appear
without their label column ("gold" or "second") and their glyph (a left-pointing and a
right-pointing triangle), so the difference survives grayscale and colour blindness. The light
tints sit at 1.29:1 and 1.30:1 against the paper, perceptible; every text colour on them stays
above 4.5:1, the tightest being `--warn` at 4.58:1 and 4.53:1 (computed 2026-09-07). Chips
carry a fill, not only a `--rule` border.

## Typography

- Text and controls: IBM Plex Sans, weights 400 and 600, self-hosted woff2, OFL licence file
  beside the fonts.
- SQL, cells, hashes, commands, digests: IBM Plex Mono, weight 400, with `font-variant-numeric:
  tabular-nums` on numeric cells.
- Scale, in px: 13 (table cells, labels), 16 (body), 20 (section heads), 28 (page title). Four
  steps, no fifth.
- Line height 1.5 for body, 1.35 for cells, 1.6 for SQL blocks.
- Measure: prose column 66ch maximum. Tables and SQL blocks escape it inside their own
  `overflow-x: auto` region; the page body never scrolls horizontally.

## Spacing, radius, elevation

- Spacing scale in px: 4, 8, 12, 16, 24, 32, 48, 64.
- Radius: 3px on chips and code blocks, 0 on tables. No larger radius anywhere.
- Elevation: none. Borders from `--rule` do the separation. The sticky verdict strip gets a
  1px bottom rule and the paper colour, no shadow.

## Layout

- Single column, 66ch prose, full-width content regions for tables and SQL, gutters 16px at 360,
  24px at 768, 32px at 1280.
- Question page order, fixed (the martini glass stem): title line (q id, database, rule,
  verdict) as the sticky strip; question text and hint; the two statements side by side at 1280
  and stacked below, differing tokens marked; the differing rows; "what the benchmark would have
  said" (BIRD's reading, the test-suite reading, the mechanism); then the exploration: full
  results (collapsed, with counts), the probes, both records, the rerun block, the JSON links.
- Run page: the counts as a short table, then what the run was made of (question set digest and
  origin, prediction file digest and origin, data file, server, parser, session settings,
  shuffle state), then the question index with filters by verdict, mechanism and probe.
- Landing: one sentence; the headline finding as three numbers with their run links under
  them; the ten-minute block as one code block; the run index. No hero image, no cards.

## Tables

- Header cell: column name on the first line, declared type on the second in `--ink-2` mono.
- A per-cell type tag appears only where a cell's type differs from its column's declared type
  (SQLite storage classes make this real).
- Numeric cells right-aligned, tabular figures; text left; NULL as the serializer's rendering
  in the `--null` style.
- A leading count column appears when any row in either result repeats; otherwise it is absent.
- Differing rows table: label column, glyph, then the row, with `rows_shown_per_side` stated
  against the counts. Full results are read from the evidence records, which hold every row;
  the table names its source ("from evidence-gold.json, 1,022 rows"), and the counterexample's
  25-row preview is what the page opens with. The `truncated` flag is stated when a record
  states it. Beside every record's hash: "recomputed from this JSON: match" (phase 1).

## States

Each state has its own copy, taken from the JSON's `reading` strings where they exist:

| State | Mark | Copy source |
| --- | --- | --- |
| EQUAL | none | verdict block |
| NOT_EQUAL by mechanism | `--warn` word chip: multiplicity, type, order, truncation, other | `mechanism` |
| ERROR on a side | `--warn` chip naming the side and the step, then the engine's message in mono; a `statement` step is "refused before execution" | summary `errors` |
| timed out | as ERROR, with the bound: `result.statement_timeout_ms` on the record of the side that ran, the summary's `settings.statement_timeout_seconds` for the side that did not | summary `timed_out`, record |
| NOT_COMPARABLE | chip, then the mismatched preconditions listed by name | `verdict.mismatched` |
| projection names differ | one line, the `reading` verbatim, beside the two column lists | counterexample `projection_names` |
| duplicate ids, positions unused, fixture refused | rows on the run page | summary `question_set.duplicate_ids`, `predictions.positions_unused`, `fixture.refused` |
| GOLD-ONLY | plain chip | run line |
| probe fired | `--warn` chip with the probe name, its evidence, its rows | `smells.json` |
| probe quiet | listed in `--ink-2`, no chip | `smells.json` |
| probe not applicable | listed with the reason (not covered, shuffle not run) | `smells.json`, summary |
| result truncated | line under the table | record `result.truncated` |
| fixture missing or unreadable tables | block on the run page and on each affected question | summary `fixture` |
| hand classification present | a labelled row "read by hand: ..." with its date and file | classification JSON |

Focus is visible on every interactive element (2px `--accent` outline, 2px offset). Chips that
do something (the mechanism chip's token highlight) are buttons; chips that state something are
not focusable. Filters on the run page are pre-rendered pages under their own paths
(`not-equal/`, `by-mechanism/<class>/`, `by-probe/<name>/`), so every filtered view has a URL
and works with no JavaScript; nothing filters by query string on a static host.

## Motion

Personality: Corporate. Signature easing `cubic-bezier(0.2, 0, 0, 1)`. Durations: 120 ms
(hover, token highlight), 240 ms (strip condense, disclosure), 400 ms (reserved). Entrance:
opacity 0 to 1 with an 8px rise, once, on the differing rows only, staggered 30 ms per row and
capped at 300 ms in total. Under `prefers-reduced-motion: reduce` every transition is opacity
only; in print every animation is off and every row is visible. Nothing loops. Nothing moves on
the landing page.

## Copy

- Vocabulary is the tool's: EQUAL, NOT_EQUAL, R-ORD, R-SET, GOLD-ONLY, ERROR, probe names as
  written in `smells.json`.
- The `reading` strings from the JSON appear verbatim where they exist.
- Forbidden in template literals, tested: "is correct", "is wrong", "incorrect", "accuracy",
  "passes", "fails", and "score" as a label. The test reads the templates and the site's own
  templates, not the JSON-sourced text: the tool's `reading` strings say "does not state which
  of them is wrong", and the principle sentence says "NOT_EQUAL never means the gold is wrong";
  both appear verbatim and are allowed by name.
- Every number on the landing page is rendered from a JSON value with its file named in a title
  attribute; no number is typed by hand.
