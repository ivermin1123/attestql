# Measurement: the gold-only probes over all of BIRD Mini-Dev PostgreSQL

Date: 2026-09-02. Phase 3 step 2 of ADR-0013. Code: the spike's `sweep.py`, in the private history before publication; artifacts:
`plans/reports/sweep-260902-gold-only-probes/` (`counts.json`, `fired.json`, `rows.json`). Server: a
throwaway PostgreSQL 16 with the Mini-Dev dump, removed after this measurement. Every fired row was
classified by the coordinator from the recorded evidence; eleven tie-at-the-cut rows were re-run by
hand on the server with the LIMIT widened to see whether the tied rows project the same answer.

## Counts

498 distinct gold statements (500 entries; 137 and 138 duplicated). All 498 executed; no timeout at
the baseline; total 269 s, of which the s4 plan variant alone took 240 s.

| Probe | Applicable | Fired | Errored |
|---|---|---|---|
| s1 ordering over numeric-looking text | 12 | 2 | 0 |
| s2 direction against the question | 84 | 12 | 0 |
| s3 bounded by an arbitrary or null-first cut | 87 | 25 | 1 |
| s4 not a function of the data | 493 | 32 | 5 |
| any probe | 498 | 52 | |

## Classification of the 52 fired rows

A: a gold defect a maintainer would fix. B: a real evaluation hazard (the gold's answer is
arbitrary among ties, or changes with row order, so an equivalent prediction can score 0). C: no
action. X: an artifact of the sweep, not of the gold.

| Class | Rows | Which |
|---|---|---|
| A | 11 | q879, q115 (text ordering); q1029, q129 (direction, wrong ordering column); q1144, q906, q1002 (arbitrary LIMIT with differing projections); q847, q37 (NULLS FIRST returns a null); q82 (`ABS(longitude)` for "highest longitude", null returned); q694 (orders comments by the user's creation date) |
| B | 22 | 9 float aggregates whose value changes with summation order (q1473, q1476, q1482, q1529, q1531, q1380, q1390, q1410, q955); 13 ties at the cut or arbitrary cuts that change the answer (q1389, q1168, q1028, q736, q751, q766, q794, q671, q349, q94, q1135, q1011, q31) |
| C | 16 | 10 s2 fires on "oldest" and "youngest" (the birthday inversion is correct in every case) and "top three in alphabetical order"; 6 ties whose tied rows project the same answer or that DISTINCT would collapse (q1238, q1281, q1014, q669, q459, q1003), and 3 R-ORD lists that only reorder (q1040, q1145, q484) |
| X | 3 | q340, q346, q397: the sweep capped results at 10,000 rows before comparing, so a shuffle changed which 10,000 rows were compared |

## Precision

| Probe | Fired | A | A+B | Precision A+B | Note |
|---|---|---|---|---|---|
| s1 | 2 | 2 | 2 | 100 % | |
| s2 | 12 | 2 | 2 | 17 % | every miss is the age inversion or "alphabetical" |
| s3 | 25 | 6 | 16 | 64 % | every miss is a tie with identical projection or DISTINCT dropped |
| s4 (29 valid) | 29 | 5 | 26 | 90 % | 3 artifacts excluded; float order is 9 of the 26 |
| any probe (49 valid) | 49 | 11 | 33 | 67 % | 63 % over all 52 |

## Decision for release 1

- Gold-only mode stays a feature: 67 % of valid fires are actionable, 22 % are gold defects.
- s2 ships behind an experimental flag, off by default; the README does not advertise it. It
  needs the birthday inversion rule and an "alphabetical" exception before it is a feature.
- s3 fires only when the tied rows project different answers; DISTINCT is never dropped. On this
  corpus that removes all nine misses.
- s4 compares full multisets, never a bounded result; the shuffle uses a seeded order so a run
  reproduces; the plan variant leaves the default (240 s for one unique fire, class C).
- Float aggregates get their own smell label, "float aggregate order": 9 of 498 golds (1.8 %)
  produce a value that depends on summation order, and BIRD compares floats exactly.

## Unresolved

- `interval` results have no canonical rendering (one s3 error, q988); `float4` and `float8` were
  loaded as Decimal from the server's text form, which the product executor must decide on.
- Three rows lose the shuffle half of s4 because a `CREATE TABLE AS` copy carries no primary key
  and PostgreSQL then rejects a GROUP BY that relied on functional dependency.

## Addendum, 2026-09-03: the command over the same corpus, and three rows classified

The released command was run over all 498 golds with its defaults (`plans/reports/audit-260902-minidev-gold-only/`):

| | |
|---|---|
| Questions | 498, all audited, 0 errors, exit 0 |
| Smells fired | 39 on 30 golds: s1 2, arbitrary cut 16, not a function of the data 13, float aggregate order 8 |
| Time | 62 s: fixture 0.02 s, questions 51 s, shuffle 11 s; 70 tables copied, 5 over 300,000 rows skipped |

The same run made before the null placement fix fired 40: the set of 30 golds is identical, and
the one label that moved is q94's second smell, a tie at the cut that the shuffled copies showed in
one run and not the other. A tie is decided by the plan's row order, which a parallel scan does not
fix, so that fire is itself not a function of the run; both observations are true. The null
placement default changed no fire on this corpus (16 arbitrary cuts before and after).

Two things separate that run from the sweep above. The direction probe is off by default, so its
12 fires are absent. The command fires an arbitrary cut only when the tied rows project different
answers, never drops DISTINCT, and compares full multisets, which is the release decision above
and removes the sweep's misses; the sweep also read the null placement default the wrong way
round (ASC without a NULLS clause taken as null-first; PostgreSQL puts nulls last), which the
command does not. The precision figures above are the sweep's and are not re-asserted for the
command.

Three rows fired in the command's run and not in the sweep's, or under another label. Classified
by hand from `smells.json`:

| Row | Fired as | Evidence | Class |
|---|---|---|---|
| q1340 (student_club) | `float-aggregate-order` | `SUM(spent)` differences over `float4`: 2086.05 in table order, 2086.0498 over the shuffled copy | B, the tenth float aggregate whose value is its summation order |
| q1361 (student_club) | `float-aggregate-order` | `SUM(cost)` over `float4`: 600.11 against 600.11005 | B, the same |
| q1482 (debit_card_specializing) | `not-a-function-of-the-data` | three `float8` percentages differ in their sixth significant digit (545.40893 against 545.40903, and so on); the gold subtracts two large `SUM`s before dividing, so the summation-order noise of each sum is amplified by the cancellation and exceeds the six-digit agreement the float label requires | B, a float aggregate order hazard that the label's tolerance does not reach; the sweep had it under the float label |

All three are evaluation hazards, none a gold defect. Over the sweep and this run together, eleven
of 498 golds (2.2 %) have shown a float aggregate whose value is its summation order, not nine; two
of the sweep's nine (q1476, q1390) read `yearmonth`, which is over the row limit and is not
shuffled by the command's defaults.
