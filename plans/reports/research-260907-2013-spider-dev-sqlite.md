<!-- cspell:ignore sqlglot Bkyl Mohammadreza Pourreza DAIL tvshow RUCKB CodeS gdown wta cccf -->
# Research: Spider 1.0 dev on SQLite, gold-only probes and the 2020 correction

Date 2026-09-07 20:13, tree `a376007`, AttestQL 0.2.2, Python 3.13.7, SQLite 3.53.4 and
sqlglot 30.18.0. Artifact: [research-260907-spider-dev-sqlite/](research-260907-spider-dev-sqlite/).

## Inputs and alignment

Spider dev is the Google Drive zip linked from the [Yale Spider page][spider-page],
file `1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J`, sha256 `00636695dabed6b5f4b8328a16b13e069a2f16591d5e
fcce57660669c85b121b`, dated 2024-09-12, CC BY-SA 4.0. The run verifies the zip and the digests
of `dev.json`, `dev_gold.sql`, `tables.json` and each of the 20 dev databases in `inputs.json`.
The 1,034 `dev_gold.sql` lines match their `dev.json` entries: same `db_id`, and SQL equal after
whitespace, punctuation spacing, quotes, trailing semicolon and case are normalised.

Spider's correction is pinned, not inferred. The parent `e0b7bc91` copy of
`evaluation_examples/dev.sql` has sha256 `6d3ac4f5e2657e30ff9418353be9f1360fe6517075809b8c13bc7
a9c3f82a02a`; `25fcd85d` has sha256 `36e8c72ec576cc78a225b1f039d5269239d9c80ded027b748fe28aba679
7cccf`. The commit message is dated 2020-06-08 and says "corrected annotated errors/mismatches";
the site news dated 2020-06-07 says "corrected some annotation errors and label mismatches, ~4% of
dev examples". Raw line comparison gives 28 SQL-changed entries, 21 question-changed entries, five
of them both, 16 question-only and 990 untouched. Under the looser alignment normalisation, the
2024 `dev.json` matches the 2020 after text on all 1,034 SQL and question texts, so no later
semantic edit is present; the parent matches 1,008 SQL and 1,013 question texts.

## Reading Spider and the double-quoted literal

Table columns: selected, audited, errors, `arbitrary-cut`, `not-a-function-of-the-data`,
`ordering-over-numeric-text`, `float-aggregate-order`, and golds firing at least one probe.

The BIRD-shaped conversion uses zero-based `question_id`, empty `evidence` and `query` as `SQL`.
AttestQL selected all 1,034 current golds, audited 1,032, refused no fixture or shuffle, and timed
out no statement. The two misses are q455 and q456 on `wta_1`: SQLite returns text in the
`last_name` column that Python cannot decode as UTF-8. The same two errors and zero refusals
appear with the 28 parent-commit SQL texts substituted.

`tables.json` finds 213 golds with a double-quoted token that is neither a table nor a column of
that database: `world_1` 86, `flight_2` 56, `tvshow` 26, `cre_Doc_Template_Mgt` 20, `network_1`
10, `course_teach` 4, `orchestra` 4, `poker_player` 2, `singer` 2, `real_estate_properties` 2 and
`voter_1` 1. The transformed pass changes exactly those tokens to single-quoted literals. It
audits all 213, refuses nothing and errors on none.

| Pass | Sel | Aud | Err | Cut | Data | Num | Float | Fires |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Current | 1,034 | 1,032 | 2 | 42 | 30 | 0 | 0 | 60 |
| Before SQL | 1,034 | 1,032 | 2 | 42 | 30 | 0 | 0 | 60 |
| Transformed literals | 213 | 213 | 0 | 0 | 0 | 0 | 0 | 0 |

None of the 213 ambiguous-literal golds fires as shipped, so transformation changes no verdict,
replay rule, probe or statement-level shuffle coverage. The merged per-run shuffle table set
differs on 57 only because the transformed run holds a subset of a database's questions; the
per-statement covered table set changes on none. The direction probe stayed off.

## Recall against Spider's own correction

Measured on the before SQL, with the current 2024 gold serving as Spider's after SQL:

| Group | Size | Fired | Share |
|---|---:|---:|---:|
| SQL changed by Spider | 28 | 0 | 0.0% |
| Question text only | 16 | 1 | 6.25% |
| Untouched | 990 | 59 | 5.96% |

Recall against the 28 corrections is therefore zero. The one text-only fire is q134, which
carries both `arbitrary-cut` and `not-a-function-of-the-data`; its SQL was not corrected. No
corrected gold stops or starts firing when after replaces before.

All 28 before/after pairs execute under a fresh `mode=ro`, `PRAGMA query_only` connection with a
30 s deadline. Fifteen return identical ordered rows and 13 differ; none errors. The differing
pairs are q16, q43, q44, q109, q119, q120, q161, q162, q361, q362, q629, q630 and q813 in
`corrections-replayed.json`.

## Hand reading

There are 60 fires on golds whose SQL Spider did not correct. The stated sample is every second
id: 30 rows, each read against its question and data, with one sentence in
`classification.json`. Of those, 24 are wrong and six are harmless. The wrong group is mostly
cuts through ties: q26 returns either 2015 or 2014, both tied for most concerts; q95 has 17
car-name rows at minimum horsepower across seven model names; q804 cuts seven zero-population
countries to three; q816 uses a bare `max` where eight countries tie at 0.0% between two
languages; and q641 groups `tv_channel` by country and returns one arbitrary channel id per
qualifying country. The six harmless fires are equal-key orderings, such as employees tied on age
or episodes tied on rating, where another ordering still answers the question.

## Prediction mode

One public file was found immediately inside the one-hour bound, so the search stopped there:
[CodeS-1B prediction file][codes-repo], path
`results/pred_sqls-codes-1b-spider.txt`, Apache-2.0, commit
`e203386173eecf6fbe8b14cf233611a2fb7c994e` dated 2024-08-21, sha256 `913576f655c6ca9a00762c83acf05234006fae164826e9577cbd1373d07274d2`.
It has 1,034 non-empty lines in dev order; 471 normalise to their gold.

| Pass | Selected | Compared | EQUAL | NOT_EQUAL | ERROR | Bird EX 1 / 0 | Test-suite 1 / 0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Current | 1,034 | 1,006 | 765 | 241 | 28 | 778 / 228 | 792 / 214 |
| Transformed | 213 | 204 | 146 | 58 | 9 | 146 / 58 | 148 / 56 |

Current NOT_EQUAL mechanisms are 104 type, 121 other, 12 multiplicity, three truncation and one
order. Current errors are 26 prediction-side and two gold-side: 25 no-such-column, two invalid
UTF-8 gold text and one ambiguous column. Transformed errors are nine prediction-side
no-such-column rows. Bird's set reading credits 13 current rows the typed comparator calls
NOT_EQUAL, and none on the transformed subset. On the 213 ambiguous literals, verdict, replay
rule, Bird EX and test-suite EX each change on no gold.

## What the tool did not catch, and gaps found in use

- All 28 SQL corrections Spider made in 2020. Most change meaning or row shape, not whether the
  data decides an answer; the probes have no semantic reading of the question.
- Two golds cannot be replayed because Python's SQLite decoder rejects non-UTF-8 text stored in
  `wta_1.last_name`. This is an execution error, not a parser refusal, and prediction mode counts
  both as gold-side errors.
- Spider supplies no evidence field. The conversion leaves it empty, and nothing in this run can
  use schema documentation that BIRD would carry.
- The ambiguous double-quoted literal is pervasive but inert here: no affected gold fires as
  shipped or transformed. A future Spider-like corpus can still expose it in an ordering key or
  table reference.
- The merged run-level shuffle table set shrinks with a per-database subset, so benchmark merges
  must keep statement-level coverage rather than comparing one run's union with another's.
- The sample leaves 30 of 60 uncorrected fires unread by hand; `classification.json` names the
  exact sample rule, so the unread half is visible rather than implied.

## Unresolved questions

- Whether the 13 row-changing Spider corrections were intended to change answers, fix labels, or
  both; this lane replayed but did not judge their wording.
- Whether q455 and q456 are worth reporting upstream, since the shipped SQLite text violates the
  database's declared UTF-8 encoding.
- Whether the unread half of the 60 uncorrected fires changes the 24 wrong / six harmless sample
  balance enough to matter.

## What changes in AttestQL

- Add a SQLite text-decoding policy that records invalid UTF-8 bytes losslessly instead of
  failing the statement, so the two `wta_1` golds and their predictions can be compared.
- Keep the BIRD-to-Spider conversion outside the tool: the BIRD question shape already carries
  Spider once ids, database and SQL are mapped, and empty evidence is valid.
- Do not add a blanket refusal for ambiguous double-quoted tokens. This corpus shows 213 affected
  golds and no probe movement; schema-aware resolution remains the safer future fix.
- Treat these gold-only probes as data-decision checks, not benchmark QC recall. Spider's 2020
  correction set proves the limit: semantic and label fixes need a different signal.

[codes-repo]: https://github.com/RUCKBReasoning/codes

[spider-page]: https://yale-lily.github.io/spider
