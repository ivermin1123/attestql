# Records an earlier release wrote

Four evidence records, one gold and one prediction per engine, written by attestql 0.2.2 under
the record layout `attestql/audit/2`. They are here so that the round trip in
`tests/test_evidence_load_round_trips.py` is asserted over records an earlier release wrote,
which is the only thing that shows a reader still re-hashes a record it did not write: today's
code writes `attestql/audit/4` and cannot produce one of these.

| file | run it is from | recorded |
| --- | --- | --- |
| `sqlite/evidence-gold.json`, `sqlite/evidence-second.json` | `minidev-sqlite/gpt-4-turbo/california_schools` question 82 | 2026-09-08 |
| `postgres/evidence-gold.json`, `postgres/evidence-second.json` | `minidev-pg/gpt-4-turbo` question 358 | 2026-09-08 |

Both engines are here because what the round trip has to survive is every value an audit
produces: the SQLite records state storage classes and no session preconditions, the PostgreSQL
records state eight settings in force.

They were copied on 2026-09-12 out of `tools/site/data/` as it stood at commit `ae854d0`, the
last commit whose published data was made with 0.2.2. The refresh that followed remade all 121
runs with 0.3.1, so no published record states a layout before the current one any more, and the
test that had read them off the published data had nothing left to read.

Do not regenerate these files, reformat them, or edit a byte of them. Each carries the two
hashes the run that wrote it took, and the test recomputes both: a record that was changed here
would either fail the test or, worse, be a record whose hashes were made to agree with an edit.
A record from a later layout is added here as a file of its own, beside these, and never by
writing over one of them.
