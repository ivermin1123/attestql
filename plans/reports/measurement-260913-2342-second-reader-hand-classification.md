# A second reader for the class A hand classification of Mini-Dev on PostgreSQL

Measured 2026-09-13 at `eba24a0`, over the published runs under `tools/site/data/minidev-pg/`
(made with 0.3.1 on 2026-09-11). Artifact: [measurement-260913-second-reader/](measurement-260913-second-reader/).

## Why

The README's headline is that 69 of the 164 Mini-Dev predictions BIRD credits and the tool calls
NOT_EQUAL are wrong answers the benchmark credited (class A of the hand classification in
`prediction-mode-260904-real-predictions/classify.py`). That number rested on one reader. The
whole-project review of 2026-09-12 named it the single point of trust in the evidence chain, and
the owner chose a second, blind reading by a session on another model as the check.

## Method

- **Population.** The 69 class A rows of `tools/site/data/minidev-pg/classification.json`, of
  which 66 have a question directory on the site; the other three (q1124 under two prediction
  files, q207 under one) are whole only in the release assets and were left out.
- **Sample.** 30 of the 66, drawn by `sample.py` with the seed `20260913` from the rows sorted by
  file and question id. The 30 cover 16 distinct questions and all 9 prediction files; 27 are
  `multiplicity` rows and 3 are `type` rows, the same proportion as the population (64 and 5).
- **What the reader saw.** For each item: the question, BIRD's evidence hint, the gold and the
  prediction as executed, both results (columns, row count, up to 25 rows a side), BIRD's own
  score, the typed verdict and its mechanism, and the differing rows, up to 25 a side. No label,
  no reason, no file name, no question id. The packet has sha256
  `2dc0a3564bc475fabe9140ffc4e304883824f701574e714669afd3a7d12047fd` and is made again by the
  script from the site data.
- **Reader.** A fresh Claude Opus 5 session with the three class definitions quoted from
  `classify.py` verbatim, told not to open any classification file, key, report or README, and
  asked for one class per item with a confidence and a one-sentence reason. It read the packet
  only; its transcript shows nine tool calls, all on the packet and its own output file.
- **Comparison.** `comparison.json` joins the first reader's class and reason with the second's,
  item by item.

## Result

| | Count |
|---|---:|
| Items | 30 |
| Second reader also says A | 27 |
| Second reader says B | 1 |
| Second reader says C | 2 |
| Agreement on class A | 90.0 % (Wilson 95 % interval 74.4 % to 96.5 %) |
| Second reader low confidence | 8 items, 5 of them agreements |

Cohen's kappa is not reported: the first reader's class is A on every item by construction, so
there is no chance-corrected statistic to compute. The number that matters for the headline is
the first row: of the rows the first reader called wrong answers, a second reader who did not know
that called nine in ten the same.

## The three departures

| Item | Row | First reader (A) | Second reader |
|---|---|---|---|
| 9 | `gpt-4-32k`, q173 | the prediction reads `trans` instead of `order` and matches the gold's one row 13 times by coincidence of the data | B, low: one distinct pair repeated 13 times, the answer a reader takes away is unambiguous, though the prediction reads `trans.amount` instead of the gold's `SUM` over `order` |
| 16 | `gpt-4-turbo`, q565 | both results are empty on this data; the prediction projects a bool, not the well-finished label the question asks for | C, low: both results empty, the only difference is the declared type, text against bool, and the bool is the yes or no the question asks for |
| 19 | `meta-llama-3-70b-instruct-2`, q565 | as item 16 | C, low: as item 16 |

Item 9 is a real disagreement about what "wrong answer" means: both readers see that the
prediction reads another table and lands on the gold's value by coincidence; the first reader
calls a right value from the wrong computation a wrong answer, the second calls the value
unambiguous. Items 16 and 19 are the same question under two models, and both readers agree the
results are empty and differ only in declared type; the first reader classed them A because the
prediction does not project what the question asks for, the second stretched class C, which
`classify.py` defines for numeric types only, to a text against bool case. Neither departure says
the row is a correct answer the benchmark should credit; they say the class boundary between A
and B, and the coverage of C, are the two places the rubric is soft.

## The five low-confidence agreements

Items 11, 13, 21 and 27 are q249 and q268 under four models: an `OR` join over `atom_id` and
`atom_id2` returns each of two elements twice, exactly twice the answer. Both readers called them
A, the second noting they sit on the rubric's "at least twice" threshold. Item 22 is q565 under
`meta-llama-3-8b-instruct-2`, where the prediction projects `(title, closeddate)`; both readers
called it A, the second with low confidence because both results are empty.

## What follows

- The headline "69 of 164 are wrong answers the benchmark credited" now has a measured second
  reading: 90 % agreement on a sample of 30, interval 74 % to 97 %. It is recorded as register
  row A53.
- The rubric's soft edges are the "at least twice" threshold of class A and the numeric-only
  definition of class C. Neither changes a published number; a future classification should
  state a rule for a right value reached by the wrong computation, and widen C to any declared
  type difference with equal values, or say why not.
- The three rows without a site page were not sampled. A reading of those three needs the release
  assets and is a small separate step.
