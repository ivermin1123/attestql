<!-- cspell:ignore minidev satscores frpm CDSCode birdenv hoangle Kaggle birdsql -->

# Research: BIRD dev and Mini-Dev, the two copies of the same databases

Date 2026-09-07, tree `c109d46`. Python 3.13.7, SQLite 3.53.4, sqlglot 30.18.0. Artifact:
[research-260907-two-database-copies](research-260907-two-database-copies/). No product code changed.

## Inputs and assumptions

| Input | Source and digest |
|---|---|
| 2024 dev gold and databases | `https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip`, sha256 `cdd6d19f…`; member `dev_20240627/dev.json` is `630272f2…` |
| 2025 dev gold | `https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/resolve/3c11fb19…/data/dev_20251106-00000-of-00001.json`, sha256 `ffd80183…` |
| Mini-Dev gold and databases | `https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip`, sha256 `cc48ba16…`; member `mini_dev_sqlite.json` is `4ba5fa8d…` |
| Mini-Dev HF gold | `https://huggingface.co/datasets/birdsql/bird_mini_dev/resolve/f65faf4a…/data/mini_dev_sqlite-00000-of-00001.json`, sha256 `88ceb071…` |
| Predictions and evaluator | `bird-bench/mini_dev` commit `b3d4bcbb`; nine file digests are in `SHA256SUMS.predictions`, evaluator files are `da1bbcd4…` and `f6943d24…` |

All 22 database digests and every table count are in
[tables.json](research-260907-two-database-copies/tables.json): six pairs identical, five
different. The row-count differences are exactly A38: `formula_1` 420,369/400,524 `lapTimes`,
6,070/5,815 `pitStops`, 7,397/6,967 `qualifying`, 976/954 `races` and 23,657/23,179 `results`;
`thrombosis_prediction` 806/106 `Examination`; and `toxicology` 12,333/9,111 `atom`,
12,379/9,156 `bond` and 24,758/18,312 `connected` (dev first).

BIRD's evaluator opens `card_games` read-write although the publication is read-only. Scoring
therefore used one writable clone of each `card_games` copy; both kept sha256
`c98bdb57fe7474da798b407785544b9af0daaad5d61fd21e2a73309493bc1227`. That clone is the only
filesystem adaptation, and `score-flips.json` records it.

## Gold answers that depend on the downloaded database

Each gold ran on both copies through Python sqlite3, read-only, under `PRAGMA query_only`, with a
30 second progress-handler deadline. BIRD's reading is `set(rows)` equality, the multiset reading
is `Counter(rows)` equality, and the typed reading prefixes each returned cell with its SQLite
storage class. The files are the three `replay/pairs-*.json` members of the artifact.

The table counts golds whose rows differ; the first number is BIRD's set reading and the second is
the multiset reading. The 2025 q1131 rewrite timed out on both copies after its serial rerun and
is outside the scored rows.

| Database | 2024 golds | 2025 golds | Mini-Dev HF golds |
|---|---|---|---|
| `california_schools` | 12 / 12 | 16 / 16 | 5 / 5 |
| `european_football_2` | 5 / 5 | 5 / 5 | 1 / 1 |
| `formula_1` | 30 / 33 | 28 / 28 | 10 / 12 |
| `thrombosis_prediction` | 5 / 5 | 5 / 5 | 1 / 1 |
| `toxicology` | 30 / 30 | 30 / 30 | 6 / 6 |
| **Total of 700, 699 scored and 237** | **82 / 85** | **84 / 84** | **23 / 25** |

The multiset reading is stricter only on q959, q972 and q974 in 2024, and q959 and q972 in
Mini-Dev. q959 returns row `[17]` twice on dev and once on Mini-Dev; q972 returns `[14, COU]` 82
and 77 times; q974 returns `[2004]` 347 and 327 times. No gold is a typed-only difference: every
copy-dependent answer already differs by value or multiplicity, so the typed count adds zero.

Three examples show the scale. 2024 q9 returns dev row `[2]` that Mini-Dev does not. 2025 q6
returns a 14-column Polytechnic High row on dev that Mini-Dev does not. Mini-Dev q1189 returns
dev row `[3]` that Mini-Dev does not.

## Gold-only probes

AttestQL ran at this worktree's version on both copies of all five databases with the 2024 golds,
three processes at a time. No statement timed out. The ten `tool/<copy>/<db>/summary.json` files
and [smells-by-copy.json](research-260907-two-database-copies/smells-by-copy.json) own the counts.

| Copy | Golds with a smell | `arbitrary-cut` | `not-a-function` | `ordering-text` |
|---|---|---|---|---|
| dev | 31 | 24 | 19 | 2 |
| Mini-Dev | 32 | 25 | 19 | 2 |

Exactly one gold differs: q1196 (`thrombosis_prediction`) fires `arbitrary-cut` on Mini-Dev and
not on dev. The 31 dev fires match `gold-only-old.json` from tree `6a43c01` exactly, so this is
the fixture and not a tool-version change.

## BIRD's own Mini-Dev prediction scores

The nine BIRD prediction files were scored by BIRD's unmodified `evaluation_utils.py` and
`evaluation_ex.py` against the HF gold, first on Mini-Dev's shipped pairing and then on dev.zip.
Each file has 500 positions over 498 distinct ids. Direction is Mini-Dev to dev.

| Prediction file | Mini-Dev EX | dev EX | Flips | Gains | Losses |
|---|---|---|---|---|---|
| gpt-35-turbo-instruct | 170 | 170 | 2 | 1 | 1 |
| gpt-35-turbo | 191 | 192 | 3 | 2 | 1 |
| gpt-4-32k | 237 | 236 | 3 | 1 | 2 |
| gpt-4-turbo | 219 | 218 | 1 | 0 | 1 |
| gpt-4 | 244 | 243 | 1 | 0 | 1 |
| llama-3-70b | 206 | 205 | 1 | 0 | 1 |
| llama-3-8b | 124 | 123 | 1 | 0 | 1 |
| mixtral-8x7b | 107 | 107 | 0 | 0 | 0 |
| phi-3-medium | 157 | 155 | 2 | 0 | 2 |
| **Total** | **1,655** | **1,649** | **14 of 4,500** | **4** | **10** |

Only q906, q933, q944 and q1189 move. q1189 loses EX on seven files, q944 loses on three, q906
gains on three and q933 gains on one. The Mini-Dev side matches the earlier `official/hf` scores
position for position and result for result.

## CDS codes and Player heights

The CDS evidence is in [cds.json](research-260907-two-database-copies/cds.json). Dev has 211 of
2,269 `satscores.cds` values at 13 characters and 2,058 join `schools.CDSCode`; Mini-Dev has all
2,269 at 14 characters and all 2,269 join. `frpm.CDSCode` joins all 9,986 `schools` rows on both
copies, but its join through `satscores.cds` is 1,620 on dev and 1,782 on Mini-Dev, the expected
162-row delta. Mini-Dev's `california_schools` is therefore the copy with the correct codes.

The California Department of Education landing page was attempted at
`https://www.cde.ca.gov/ds/si/ds/pubschls.asp`; it answered curl with a Web Application Firewall
redirect loop, so there is no external directory digest. The verdict rests on the internal join.

The golds naming `satscores` plus `schools` or `frpm`, and their differing ids, are in
[column-golds.json](research-260907-two-database-copies/column-golds.json): 2024 names 32 and 12
differ, ids 9, 10, 15, 17, 19, 24, 27, 37, 43, 50, 51 and 57; 2025 names 49 and 16 differ, ids 6,
9, 10, 11, 12, 17, 19, 20, 24, 27, 37, 43, 50, 51, 55 and 57; Mini-Dev names 13 and 5 differ, ids
17, 24, 27, 37 and 50.

The 13 dev golds naming `height` are 1021, 1033, 1040, 1058, 1059, 1068, 1069, 1079, 1087, 1116,
1131, 1132 and 1148. In 2024, ids 1033, 1059, 1068, 1087 and 1131 differ; in 2025, ids 1021, 1033,
1059, 1068 and 1087 differ, while q1131 times out on both. Mini-Dev carries six of these golds and
only q1068 differs; its dev-only row includes aggregate height `68.89975315514602`. All 11,060
`Player.height` values are REAL on dev and INTEGER on Mini-Dev, for example `182.88` against `182`.
No football source was checked because the origin Kaggle dataset requires a login.

## For the owner: a follow-up to `mini_dev` issue 50

BIRD publishes two different `dev_databases` sets: six of eleven database files match and five differ, with all 22 sha256 values recorded in the artifact.

Replay makes the choice material: 85 of 700 2024 dev golds and 84 of 699 scored 2025 dev golds differ by multiset, and 25 of 237 Mini-Dev golds do; the 2025 q1131 rewrite times out on both copies.

BIRD's own evaluator moves 14 of 4,500 Mini-Dev prediction positions when the identical HF gold is scored on dev.zip instead of minidev.zip: 4 positions gain EX and 10 lose it, over only q906, q933, q944 and q1189.

`california_schools` identifies the intended copy: dev lost a leading zero from 211 of 2,269 `satscores.cds` values, so 211 rows stop joining `schools`, while Mini-Dev's 14-digit codes all join.

`european_football_2` is the other same-count divergence: every one of 11,060 Player heights is REAL in dev and truncated INTEGER in Mini-Dev, changing five dev gold answers and one Mini-Dev gold answer.

A digest list per published database, plus one sentence saying which gold set and evaluator pairing each list owns, would make the download choice checkable.

## Unresolved questions

- The California public directory could not be fetched through its WAF, so the 211 zero-padded
  codes have no external check.
- The football origin needs a Kaggle login, so the height truncation has no source check.
- Which publication BIRD intended for the three row-count databases remains a curatorial
  decision; this lane only measures both.

## What changes in AttestQL

Nothing. An audit already records its fixture digest and origin, which is the invariant this
incident needs; the 25 Mini-Dev gold replays and 14 score flips came from feeding the tool
different files, not from a missing comparison. A cross-run warning that the same `db_id` has a
different fixture digest could be useful later, but adding a two-fixture contract is speculative.
