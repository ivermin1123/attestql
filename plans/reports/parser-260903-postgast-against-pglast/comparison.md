# The parser swap, checked over every Mini-Dev gold

Date 2026-09-03. Acceptance check of ADR-0013 point 8 (amended 2026-09-03): the audit's parser
moved from `pglast` 6.16 (GPLv3 or later) to `postgast` 0.1.0 (BSD-2-Clause), both bindings to
`libpg_query`. What the audit reads off a statement must not change with the binding.

Method: `compare_parsers.py dump` parsed the 498 distinct golds of `mini_dev_postgresql.json`
(500 entries, ids 137 and 138 duplicated) once with the current parser (`current-parser.json`) and
once with the previous `statements.py` module, taken from the private history before publication
and run in an environment holding `pglast==6.16` (`previous-parser.json`). `compare_parsers.py diff`
compared the replay rule, the tables, the ordering keys (expression, direction, null placement),
the bound (`limit_count`, `limit_stated`, `offset_count`) and `distinct` per gold, and checked the
replay rule of every gold against the sweep's `rows.json`
(`plans/reports/sweep-260902-gold-only-probes/`).

Result: 498 golds; 494 agree on every field; 4 field disagreements. Replay rule against the sweep's rows.json: 498 of 498 match. Every disagreement is the
spelling of a cast in an ordering expression as the parser writes it back, `x::type` for `CAST(x AS type)`, with the
same direction, null placement, tables and bound:

<!-- cspell:disable -->
| id | field | previous parser | current parser |
|---|---|---|---|
| q37 | ordering | `[{"expression": "CAST(t1.numge1500 AS real) / (NULLIF(t1.numtsttakr, 0))", "descending": false, "nulls": "first"}]` | `[{"expression": "t1.numge1500::real / (NULLIF(t1.numtsttakr, 0))", "descending": false, "nulls": "first"}]` |
| q988 | ordering | `[{"expression": "avg(CAST(t1.duration AS interval))", "descending": false, "nulls": "default"}]` | `[{"expression": "avg(t1.duration::interval)", "descending": false, "nulls": "default"}]` |
| q1001 | ordering | `[{"expression": "((CAST(split_part(q3, ':', 1) AS integer) * 60) + CAST(split_part(split_part(q3, ':', 2), '.', 1) AS real)) + (CAST(split_part(q3, '.', 2) AS real) / 1000)", "descending": false, "nulls": "default"}]` | `[{"expression": "((split_part(q3, ':', 1)::int * 60) + split_part(split_part(q3, ':', 2), '.', 1)::real) + (split_part(q3, '.', 2)::real / 1000)", "descending": false, "nulls": "default"}]` |
| q1040 | ordering | `[{"expression": "CAST(sum(t2.heading_accuracy) AS real) / (NULLIF(count(t2.player_fifa_api_id), 0))", "descending": true, "nulls": "last"}]` | `[{"expression": "sum(t2.heading_accuracy)::real / (NULLIF(count(t2.player_fifa_api_id), 0))", "descending": true, "nulls": "last"}]` |
<!-- cspell:enable -->

The ordering expression is recorded in the evidence record's sort key, so a record written by the
current parser spells these four keys differently from one written before; the verdict, the rule
and the smells do not read the spelling.
