<!-- cspell:ignore crosstab FRPM -->

# BIRD's 399 dev rewrites: what changed in the answer and in the SQL

Date 2026-09-07, tree `a376007`, SQLite 3.53.4 as Python 3.13.7 links it, AttestQL 0.2.2
from this tree, sqlglot 30.18.0. Artifact: `research-260907-bird-rewrites/`.

## Inputs

All data comes from `dev.zip`,
`https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip`, sha256
`cdd6d19faeb45a23970b98d3ef6c40a87987c95459c2cf12076897a60cf5a630`. The two question files
are pinned independently:

Old questions, zip member `dev_20240627/dev.json`, sha256
`630272f2b1c44d8cef2c3b246f623355cf0bbc1e832c81061df895530dfc2f06`.

Rewritten SQL, Hugging Face dataset `birdsql/bird_sql_dev_20251106` at commit `3c11fb19`,
member `data/dev_20251106-00000-of-00001.json`,
`https://huggingface.co/datasets/birdsql/bird_sql_dev_20251106/tree/3c11fb19`; the exact
resolve URL is pinned in `reproduce.sh`, sha256
`ffd8018378ddb1a8794753e0a31cfc81862ff7318a5184c22f3dc4ce03a03feb`.

Each of the eleven `dev_databases/<db>/<db>.sqlite` files is verified by `reproduce.sh`; its
full digest is also in the copied `summary.json` under `tool/`. The split is recomputed under
the earlier normalisation and stops unless it is 399 rewritten, 172 text-only and 963 unchanged.

## Method

The old `dev.json` is the question file. The 2025-11-06 SQL for the 399 rewritten ids is the
prediction file. One SQLite run covers each database, three processes at a time, with the
default 30 second statement budget. The replay rule is deliberately the old gold's: R-ORD when
the old statement orders, R-SET otherwise. A rewrite that adds or drops ORDER BY is therefore
judged by the old rule.

The gold-only probes fired on exactly the same 31 of 399 as `gold-only-old.json`, with no smell
drift. As a harness check, the 172 text-only ids replay their own old SQL: 171 are EQUAL and
q701 is a gold-side execution timeout. In the rewrites, q1131 is a prediction-side execution
timeout. Both timeouts survived a serial rerun. The expected q518 belongs to the 963 unchanged
ids and is outside both `--ids` sets, so this lane did not replay it; A34 remains its evidence.

`card_games.sqlite` is published with a WAL header. SQLite refuses its first identity pragma
beside no writeable sidecar directory, so AttestQL reports `attempt to write a readonly
database` on the read-only inputs. `prepare_database.py` therefore makes a byte-identical work
copy (digest asserted) only for that database and lets SQLite create sidecars there. The first
rerun script also mistook summary text saying `0 timed out` for a timeout and reran some
no-timeout databases alone; every answer stayed the same, and the committed selector requires
an ERROR timeout line or a nonzero timeout count.

## What changed in the answer

- **130 of 399 give the same answer under the old multiset rule**: 129 EQUAL, plus one
  NOT_EQUAL whose multiset is equal and only row order differs.
- **269 differ**: 129 by type, 115 other, 16 multiplicity, 8 truncation and 1 order.
- **1 is an error**: q1131, prediction side, execute timeout.
- The one order mechanism is the same id the multiset bullet calls same; the two readings
  intentionally overlap.
- BIRD's own set reading calls 146 of 399 equal, so it credits 16 of the 269 typed differences.
  The test-suite reading calls 130 equal, the same count as the old multiset reading here.

## Crosstab

Every cell is `count^fires`; `fires` is how many of those ids the old gold-only probes flagged.
The `same` column combines EQUAL with the one same-multiset-other-order result.

| Primary SQL class | total | same | multiplicity | type | other | truncation | error |
|---|---:|---:|---:|---:|---:|---:|---:|
| aggregate function | 1^0 | 1^0 | 0 | 0 | 0 | 0 | 0 |
| DISTINCT | 25^1 | 5^0 | 15^0 | 2^0 | 3^1 | 0 | 0 |
| GROUP BY | 6^0 | 4^0 | 0 | 0 | 2^0 | 0 | 0 |
| JOIN condition | 5^1 | 1^0 | 0 | 0 | 4^1 | 0 | 0 |
| LIMIT or OFFSET | 2^0 | 1^0 | 0 | 0 | 0 | 1^0 | 0 |
| ORDER BY direction only | 3^1 | 1^0 | 0 | 0 | 2^1 | 0 | 0 |
| ORDER BY key | 43^10 | 37^8 | 0 | 0 | 5^2 | 1^0 | 0 |
| projection | 79^0 | 26^0 | 0 | 15^0 | 37^0 | 1^0 | 0 |
| WHERE | 32^0 | 17^0 | 0 | 1^0 | 14^0 | 0 | 0 |
| whole rewrite | 203^18 | 37^1 | 1^0 | 111^4 | 48^9 | 5^4 | 1^0 |

Sqlglot parsed all 399 pairs. All touched clauses remain in `ast-diff.json`; the primary class
is the first match in its recorded precedence. Whole rewrite means different tables or more
than three touched clauses. No HAVING-only, CAST-only or subquery-only rewrite survived that
precedence, although those clauses appear in the full touched sets.

## Hand readings

The fixed sample rule selects sorted ids, every `ceil(size / 8)`-th from the first, at most
eight per class. The ten populated SQL classes give 56 readings, not 104, because seven classes
have fewer than eight ids.

| SQL class | read | semantic | structural | cosmetic | gold-only share |
|---|---:|---:|---:|---:|---:|
| aggregate function | 1 | 0 | 0 | 1 | 0.00 |
| DISTINCT | 7 | 0 | 6 | 1 | 0.71 |
| GROUP BY | 6 | 2 | 0 | 4 | 0.00 |
| JOIN condition | 5 | 5 | 0 | 0 | 0.20 |
| LIMIT or OFFSET | 2 | 0 | 1 | 1 | 0.00 |
| ORDER BY direction only | 3 | 3 | 0 | 0 | 0.33 |
| ORDER BY key | 8 | 2 | 0 | 6 | 0.13 |
| projection | 8 | 8 | 0 | 0 | 0.13 |
| WHERE | 8 | 4 | 0 | 4 | 0.00 |
| whole rewrite | 8 | 7 | 0 | 1 | 0.13 |
| **total** | **56** | **31** | **7** | **18** |  |

The estimate is the sampled share a check reading only the old gold and the data could catch.
It is not a defect census: `semantic` means the rewrite changes what is asked or fixes the SQL
to the question, `structural` means a defect is visible without the question, and `cosmetic`
means the same rows. DISTINCT dominates the structural readings. The whole-rewrite and
projection samples are mostly changed questions and richer requested output.

## Candidate checks

| Candidate | rewrites caught | needs the question |
|---|---:|---|
| current three gold-only probes | 31 | no |
| old result repeats whole rows and rewrite adds DISTINCT | 23 | no |
| bare aggregate beside an ungrouped projection | 1 | no |
| direction against the question | 2 | yes |
| projection contract (requested columns and entity grain) | 53 | yes |

The three gold-only candidates overlap on one id, q580, and together cover 54 of 399: the
current probes 31, a duplicate-row smell adds 22, and the bare-aggregate rule adds one. The
question-aware candidates are not gold-only and are counted only to bound what a question
reader could recover.

## Unresolved questions

- Whether BIRD intended the 2025-11-06 whole rewrites as richer new questions or as repairs to
  the old questions; the sample supports both readings depending on the id.
- Whether a duplicate-row smell should be actionable when a question explicitly asks for one
  row per occurrence; this lane counts catchable rewrites, not confirmed defects.
- What to do about a WAL database on read-only media: a private copy is safe but costs 262 MB
  for `card_games`, while SQLite immutable mode assumes the file cannot change under the run.

## What changes in AttestQL

A35's "miss 368 of 399" should stop implying that the probes missed 368 semantic defects. On
dev.zip, 269 rewrites change the answer, 130 do not under the old multiset rule and one times
out. In the fixed sample, 31 of 56 are semantic, 7 structural and 18 cosmetic. The existing
probes catch 31 rewrites, but a duplicate-full-row smell is the one worth building next: it
catches 23 answer-changing rewrites and 22 beyond the current probes. The bare-aggregate check
catches only one here and is not worth its own lane. A question-aware direction check catches
two answer-changing direction rewrites and must stay outside gold-only mode. AttestQL should
also handle a WAL SQLite file on read-only media, most simply by making a private byte-identical
copy beside which SQLite may create its sidecars, and report that copy in the evidence.
