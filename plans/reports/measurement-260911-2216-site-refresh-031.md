# The site's 121 runs, made again with 0.3.1

Measured 2026-09-11 in `/tmp/attestql-runs`, from the tree that carries the three fixes below and
nothing else, through `tools/site-select/audits.sh` unchanged in what it asks the tool. The
reconciliation is `site-refresh-260911/reconcile.py`, run from the same work directory, and its
output is `site-refresh-260911/reconciliation.json`.

## Why the runs were made again

Every run the site published was made with 0.2.2 and states the record layout
`attestql/audit/2`. Three things moved since.

**`duplicate-full-row` did not exist in 0.2.2.** It shipped in 0.3.0 (register row A45) and the
site has never shown a run that had it, so a probe the claims register owns was invisible on the
page that exists to show the runs.

**`arbitrary-cut` retracted a fire.** On SQLite a DISTINCT statement may order by an expression its
select list does not hold, and reading the rows at the cut meant projecting that key, which widens
the grain the de-duplication runs on and returns rows the statement never returned. One published
page, the one for q392 of `card_games` on the 2025-11-06 copy of BIRD dev, asserted an
`arbitrary-cut` against BIRD's gold on rows the statement did not produce. That is the reason this
refresh happened when it did rather than at the next convenient time.

**A result holding a non-finite number now receives a verdict.** Hashing refused such a value, so a
question the comparison had already decided reported an error instead. No published run was
affected, because neither Mini-Dev nor BIRD dev returns one on these databases, which is why the
defect was found by reading rather than by a run.

## What moved, over every run compared

121 runs compared, and every published run had a fresh counterpart. The whole of what moved, in
probes fired, over all of them:

| probe | moved | where |
| --- | --- | --- |
| `duplicate-full-row` | +613 | 97 on BIRD dev, 211 on Mini-Dev predictions, 69 on the gold-only pair, 236 on Mini-Dev over SQLite |
| `not-a-function-of-the-data` | +15 | PostgreSQL only: 6 runs, none over SQLite |
| `arbitrary-cut` | -1 | BIRD dev, question 392 of `card_games` |
| `float-aggregate-order` | -1 | PostgreSQL only: +1 in one prediction run, -2 across the gold-only pair |

`duplicate-full-row` is the probe that did not exist, and its 613 fires are what the site had
never shown. `arbitrary-cut` is the retraction, and it is the one page this refresh was for.

Two verdicts moved, both in Mini-Dev over SQLite, and both are one question crossing or stopping
crossing the wall-clock bound rather than a comparison deciding differently:
`gpt-35-turbo/financial` went NOT_EQUAL 16 to 17 as question 145's prediction stopped timing out,
and `mistralai-mixtral-8x7b-instru-4/financial` went 9 to 8 as question 116's prediction started.
The second is the run whose crowded copy was kept beside it, which is what says the rerun on a
quiet machine happened. No question changed its verdict for any other reason.

## The planner's statistics decide what an order-dependent probe sees

`not-a-function-of-the-data` and `float-aggregate-order` moved on PostgreSQL and on no SQLite run.
Both read the gold's result against the same query over a shuffled copy of the data, so what they
see depends on the order the rows come back in, and on PostgreSQL that order is a plan the planner
chose from its statistics.

A dump load leaves those statistics absent. Autovacuum then fills them in, at a time nobody
controls, so the first runs of a wave plan one way and the rest plan another. Measured on one
prediction file against one freshly loaded server, with the same code, the same seed and no other
load, the same audit run five times in a row:

| passes | first pass | passes 2 to 5 |
| --- | --- | --- |
| no `ANALYZE` after the load | 59 probes fired | 61 probes fired |
| `ANALYZE` after the load | 61 probes fired | 61 probes fired |

The verdicts were identical in every pass of both: 212 NOT_EQUAL, 17 credited by BIRD and
NOT_EQUAL, 0 stopped by the bound. What the statistics move is what an order-dependent gold probe
sees, and nothing about a comparison of two results.

The tool recorded the cause itself: `last_autoanalyze` and `n_mod_since_analyze`, which every
PostgreSQL record states, named autovacuum as what arrived between the first run and the second.
SQLite is not exposed to this. It has no statistics unless somebody runs `ANALYZE`, no BIRD or
Mini-Dev database carries a `sqlite_stat1` table, and `sqlite.py` states that the tool never runs
one, which is what the measurement above shows from the other side: not one SQLite run moved.

`audits.sh` now runs `ANALYZE` once after the dump load, before the wave, so that every run in a
wave plans the same way. That is what the runs published here were made with.

The fix settles a wave against itself and not two waves against each other. `ANALYZE` samples
rows, so two servers loaded from the same dump and analysed separately do not hold the same
statistics: the wave published here fired 63 of these probes on the `gpt-4` prediction file where
the five-pass experiment above, on its own analysed server, fired 61. An order-dependent gold
probe's count is therefore a fact about the run that states it, not a number another machine will
reproduce. The verdict counts, which are what every claim in the register rests on, were the same
in every one of these measurements.

## What the site now holds, and one thing the refresh moved in the selector

The selection is 353 of the 1,433 questions the runs offer, and the build is 2,177 files and
40,700,238 bytes against a budget of 8,000 files and 41,943,040 bytes.

| benchmark | runs | questions published |
| --- | --- | --- |
| `bird-dev-sqlite` | 11 | 63 |
| `minidev-pg` | 9 | 213 |
| `minidev-pg-gold-only` | 2 | 38 |
| `minidev-sqlite` | 99 | 39 |

`duplicate-full-row` brought 613 question directories with it, which is 362 MB more than the
budget can hold, and the first selection made under the refreshed runs gave `minidev-sqlite` zero
questions: the cut dropped the largest question of the whole selection until the site fit, which
settles one size threshold on every benchmark, and `minidev-sqlite`'s smallest question is 52 KB
where `bird-dev-sqlite`'s is 28 KB. Every one of its 99 runs would have published a run page with
no question page under it. The cut now takes the largest question of whichever benchmark still
holds the most, which leaves the benchmarks as equal as the cut reaches; the budget is unchanged.

## Reproducing this

The fresh runs are in `/tmp/attestql-runs/runs` and are published whole as the release assets of
`v0.3.1`, one archive per run or group, their digests in the release's `SHA256SUMS`.
`reconcile.py` compares a published tree with those runs and defaults to `tools/site/data`, which
now holds the fresh selection: to run it again, extract the tree it was run against with
`git archive ae854d0 tools/site/data` and pass that with `--published`.
