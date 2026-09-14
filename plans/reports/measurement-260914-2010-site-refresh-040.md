# The site's 121 runs, made again with 0.4.0

Measured 2026-09-14 in `/tmp/attestql-runs`, from `main` at `89c2459`, the tree that becomes 0.4.0
with the version bump and nothing else still to come, through `tools/site-select/audits.sh`
unchanged in what it asks the tool. The reconciliation is `site-refresh-260914/reconcile.py`, run
from the same work directory, and its output is `site-refresh-260914/reconciliation.json`.

## Why the runs were made again

Every run the site published was made with 0.3.1. Phases 4 to 6 of the review-findings plan moved
three things a published record or summary states, and the site should hold runs made by the
release it names.

**A PostgreSQL record states the `search_path` its statement ran under.** The envelope pins it to
`public` now (phase 5, PERF-01 and LOGIC-21), so a record made from a session that reported
`"$user", public` states `public`, and the key sits where the envelope sets it rather than where
the session reported it. Every PostgreSQL record on the site differs from its 0.3.1 counterpart by
those bytes.

**A SQLite record holds a tenth session setting, `automatic_index`.** The shuffle probe's plan
variant turns that pragma off and gives it back (phase 4), so the value in force over a statement
is stated rather than assumed. Every SQLite record differs by those bytes and by nothing else.

**`summary.json` names the question directories the run wrote.** `question_directories` is the
key `attestql report` reconciles a directory against (phase 4, LOGIC-06), so a selection that lost
a directory is refused rather than rendered short. A summary written by 0.3.1 has no such key and
renders under the count bounds alone; the site should carry summaries the renderer can reconcile
exactly.

Two budgets refuse now rather than cut (phase 5): 200,000 rows fetched per statement and
20,000,000 rows compared per permutation search. Both were set above every published record
(the largest holds 15,429 rows; the widest published search spends 4 units over 3 columns and
1,664 rows), so no verdict should have moved to ERROR under them, and the reconciliation checks
that none did.

## What moved, over every run compared

121 runs compared, and every published run had a fresh counterpart. Every fresh `summary.json`
carries `question_directories`, and in all 121 the ids it states are exactly the directories on
disk. All 4,273 gold records the fresh runs wrote state the layout `attestql/audit/4`.

The whole of what moved, in probes fired, over all of them:

| probe | moved | where |
| --- | --- | --- |
| `not-a-function-of-the-data` | -7 | PostgreSQL only: `gpt-35-turbo` -1, `gpt-4` -2, `gpt-4-32k` -2, the gold-only pair -1 each |
| `float-aggregate-order` | -1 | PostgreSQL only: `gpt-4-32k` |
| `duplicate-full-row` | -1 | `minidev-sqlite/gpt-35-turbo/financial`, question 145, under the row budget below |

The two PostgreSQL probes are the order-dependent ones that A52 measured against the planner's
statistics: this wave loaded the dump once and ran `ANALYZE` once for all eleven PostgreSQL runs,
and a count of these fires is a fact about the run that states it and not a number another load
reproduces. No SQLite probe moved except the one the budget explains.

Five verdicts moved. Four are one question each going from a decided verdict to ERROR because a
statement returned more rows than the tool holds for one result, which is the budget phase 5 set
and the owner's rule that a budget refuses rather than cuts:

| run | question | side | rows returned | was |
| --- | --- | --- | --- | --- |
| `bird-dev-sqlite/dev-20251106/card_games` | 384 | gold | 200,001 | GOLD-ONLY |
| `minidev-pg/meta-llama-3-70b-instruct-2` | 346 | prediction | 239,842 | NOT_EQUAL |
| `minidev-sqlite/gpt-35-turbo/financial` | 145 | prediction | 200,001 | NOT_EQUAL |
| `minidev-sqlite/gpt-4-32k/debit_card_specializing` | 1490 | prediction | 200,001 | NOT_EQUAL |

The default of 200,000 rows was set from the published records, the largest of which holds 15,429
rows, and it reproduces every one of them; what it refuses here are results the site never
published. Three are predictions that return a whole table where the question asks for a value,
which is a wrong answer the benchmark scored 0 in any case; one is a BIRD dev gold, question 384
of `card_games`, whose reference query returns more than 200,000 rows on the shipped data. A
question the budget refuses reports nothing, its gold's probes included: question 145's gold fired
`duplicate-full-row` under 0.3.1 and the fresh run counts no probe over a question it did not
decide, which is the `-1` in the table above.

The fifth is timing: `minidev-sqlite/mistralai-mixtral-8x7b-instru-4/financial` went NOT_EQUAL 8
to 9 and ERROR 19 to 18 as question 116's prediction stopped crossing the wall-clock bound, and the
run kept its crowded copy beside it, which is what says the rerun on a quiet machine happened.
The 22 SQLite runs whose bound stopped a statement under three processes were each run again
alone; 21 stopped at the same questions alone, and `financial` under `mixtral` was the one that
did not. No PostgreSQL run needed a rerun.

Two things the clock recorded that are not the tool's: the machine slept with its lid closed on
battery during the SQLite reruns, which stretched three runs' wall-clock to 2,106, 3,385 and
5,066 seconds while their own `elapsed_seconds`, measured by a clock that stops in sleep, stayed
under 160; and the PostgreSQL wave was started twice, because the first was stopped by the
machine's memory pressure after its two gold-only runs, and those two were deleted so that all
eleven PostgreSQL runs share one dump load and one `ANALYZE`, as A52 requires.

## What the site now holds

The selection is 353 of the 1,431 questions the runs offer, and the build is 2,181 files and
32,728,713 bytes against a budget of 8,000 files and 41,943,040 bytes.

| benchmark | runs | questions published |
| --- | --- | --- |
| `bird-dev-sqlite` | 11 | 63 |
| `minidev-pg` | 9 | 213 |
| `minidev-pg-gold-only` | 2 | 38 |
| `minidev-sqlite` | 99 | 39 |

The whole of every run is on the release as 21 archives holding 4,273 question
directories, 146,078,504 bytes in all, with `SHA256SUMS` beside them; each run's `published.json`
names its archive.

## What a reader of two records of one question sees

The record layout is still `attestql/audit/4`: no field was added to or removed from a record, so
`tests/records-from-earlier-releases/` gains nothing from this refresh. The bytes that differ
between a 0.3.1 record and a 0.4.0 record of the same question are the two session-settings
changes above, and `tools/site-select/notes.py` states both under the release's assets.
