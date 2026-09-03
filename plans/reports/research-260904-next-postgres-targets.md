# Next PostgreSQL text-to-SQL targets for AttestQL

Survey of public benchmarks beyond BIRD Mini-Dev (already in the README) that ship or claim
PostgreSQL gold. 5 web searches used; all download/parse numbers below were measured against
`attestql.audit.statements.parse_statement` on real files in scratch, not guessed.

| Set | Dialect(s) | Questions | Licence (dataset) |
|---|---|---|---|
| [BIRD-CRITIC-1.0-PostgreSQL](https://huggingface.co/datasets/birdsql/bird-critic-1.0-postgresql) | PostgreSQL 14.12 | 530 | CC-BY-SA-4.0 (card); repo MIT |
| [BIRD-CRITIC-1.0-flash-exp](https://huggingface.co/datasets/birdsql/bird-critic-1.0-flash-exp) | PostgreSQL 14.12 | 200 | CC-BY-SA-4.0 |
| [BIRD-Interact-lite](https://huggingface.co/datasets/birdsql/bird-interact-lite) | PostgreSQL | 300 (card says 270) | CC-BY-SA-4.0; repo MIT |
| [LiveSQLBench-base-lite](https://huggingface.co/datasets/birdsql/livesqlbench-base-lite) | PostgreSQL | 270 | CC-BY-4.0; repo MIT |
| [Spider 2.0](https://github.com/xlang-ai/Spider2) (lite/snow/dbt) | Snowflake, BigQuery, SQLite, DuckDB. No PostgreSQL variant exists. | 547 / 547 / 68 | repo MIT, no per-dataset licence found |
| [BEAVER](https://github.com/peterbaile/beaver-may-2025) | MySQL, Oracle. Not PostgreSQL. | 209 | MIT |

## Gold availability, measured

**BIRD-CRITIC.** The public JSONL (`data/pg-00000-of-00001.jsonl`, `data/flash-00000-of-00001.jsonl`)
carries `issue_sql`, the buggy statement quoted inside the question, not the fix. The fix
(`sol_sql`) and `test_cases` are withheld and released only by emailing
`bird.bench25@gmail.com`; I did not send that email (out of scope for a read-only, no-login
research pass). Categories in the 530 set: Query 291, Management 88, Personalization 151.
Predictions are `{instance_id, pred_sqls}` per line, confirmed from a real example output file
(`example_output/claude-opus-4.6/pg530.jsonl` in the repo), evaluated by Docker test cases, not
by a diff against a single gold string.

**BIRD-Interact-lite and LiveSQLBench-base-lite.** Downloaded both public JSONL files
(`bird_interact_data.jsonl`, `livesqlbench_data.jsonl`). `sol_sql`, `test_cases` and
`external_knowledge` are empty arrays on all 300 and all 270 rows respectively; every gold
statement is withheld behind the same email gate. Nothing gold-shaped is publicly downloadable
for either set at all. Both also use a multi-turn interactive evaluator (a user simulator asks
follow-ups; BIRD-Interact is explicitly agentic), so even a released gold is not one statement
per question the way AttestQL reads a question.

**Spider 2.0.** Confirmed from the repo README: Spider2-Snow is Snowflake only (547), Spider2-Lite
is BigQuery(214)/Snowflake(198)/SQLite(135), Spider2-DBT is DuckDB(68). Gold SQL exists only
partially (256/547 lite, 120/547 snow files present in `evaluation_suite/gold/sql`), and running
anything needs a Snowflake or BigQuery account (gated signup), which the task rules out. No
PostgreSQL gold ships anywhere in this benchmark, so it was listed as a candidate for nothing.

**BEAVER.** MySQL/Oracle dialects, dump gated behind an authenticated Google Drive folder. Not a
PostgreSQL candidate; included only because it turned up as "another set."

## Parse measurement (issue_sql, the only public PostgreSQL SQL text found)

Ran every string in `issue_sql` through `parse_statement`; this is BIRD-CRITIC's buggy input
statement, not its fix, so this is a proxy for statement shape, not a gold-coverage number.

- **bird-critic-1.0-postgresql (530 instances, 556 statements):** 390/556 parsed (70.1 %).
  Top refusals: "the text does not parse" (syntax libpg_query 17 rejects) 74, "N statements in
  one text" (scripts) 17, InsertStmt 17, UpdateStmt 14, CreateFunctionStmt 12.
- **bird-critic-1.0-flash-exp (200 instances, 211 statements):** 144/211 parsed (68.2 %).
  Top refusals: "the text does not parse" 20, InsertStmt 12, UpdateStmt 9, "N statements" 6,
  CreateFunctionStmt 5.

BIRD-Interact and LiveSQLBench have no public SQL text at all to run this measurement on.

## What AttestQL lacks, per set

- **BIRD-CRITIC:** the fix statements themselves (email-gated); and, structurally, AttestQL
  compares one SELECT's replay against another's, while roughly 30 % of the public proxy
  statements are DML/DDL/multi-statement (mostly the Management category) that
  `parse_statement` refuses outright regardless of gating. The remaining ~70 % looks like a real
  fit once gold is obtained.
- **BIRD-Interact, LiveSQLBench:** no public gold at all, and their evaluators are multi-turn
  agentic sessions with a user simulator, not one statement per question; AttestQL's model
  (one gold, one prediction, one replay) does not match the task shape even with gold in hand.
- **Spider 2.0:** wrong engine family entirely (no PostgreSQL); AttestQL runs on PostgreSQL only
  and has no path onto Snowflake/BigQuery/DuckDB SQL without a new executor and dialect layer.

## Recommendation

BIRD-CRITIC-1.0-PostgreSQL (530 instances) next, once the gold email is sent. It is the only
surveyed set with any public, ungated PostgreSQL SQL text (issue_sql, 530/530 instances have it,
zero empty) and a same-shape prediction file format already observed in the wild
(`{instance_id, pred_sqls}`), same licence family (CC-BY-SA-4.0) as the badge on Mini-Dev's README, already handled in
NOTICE. The measured 70.1 % parse rate on issue_sql is a lower bound signal, not the gold number;
expect the true sol_sql rate to be close, since sol_sql is a fix to the same question and shares
its category split (Query 291, Management 88, Personalization 151 of 530). BIRD-Interact and
LiveSQLBench are excluded for now: zero public gold measured, and an agentic multi-turn evaluator
that AttestQL's single-statement replay model cannot consume even once gold arrives.

## Not verified

- True `sol_sql` parse/refusal counts for BIRD-CRITIC: inferred from `issue_sql`'s category
  split, not measured, because obtaining it needs the email gate.
- Database dump sizes for BIRD-CRITIC/BIRD-Interact/LiveSQLBench: stated in their READMEs
  (BIRD-Interact ~207 MB lite / ~272 MB full via Google Drive) but not independently downloaded;
  BIRD-CRITIC's dump size is not stated anywhere I read.
- Whether Spider2-lite's 256/547 and Spider2-snow's 120/547 released gold files include any
  disguised PostgreSQL-compatible SQL: read the directory listing and dialect statement only,
  did not open individual gold files (irrelevant given no PostgreSQL variant exists).
