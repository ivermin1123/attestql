# Architecture decision records

An ADR here records a decision that is load-bearing, non-obvious, and likely to be challenged.
Decisions that are obvious or reversible in an afternoon are not recorded.

Format: Status, Date, Context, Decision, Alternatives considered, Consequences, Open questions.

| ADR | Decision | Status |
|---|---|---|
| [0003](0003-fixed-evaluation-clock.md) | All relative time windows resolve against a fixed evaluation clock | Accepted |
| [0004](0004-replay-equality-r-ord-r-set.md) | Replay equality is R-ORD or R-SET, declared per result; "byte-identical" is rejected as ambiguous | Accepted |
| [0013](0013-audit-text-to-sql-gold-with-typed-replay-evidence.md) | AttestQL audits text-to-SQL gold and predictions with typed replay evidence, and the Slice 1 product path is retired | Accepted |
| [0014](0014-sqlite-backend-behind-the-same-evidence-record.md) | A SQLite backend behind the same evidence record: one record and one comparator, one backend and one parser per engine | Accepted |
| [0015](0015-a-text-value-that-does-not-decode-is-recorded-as-its-bytes.md) | A text value that does not decode is recorded as its bytes, under a tag of its own | Accepted |

## The numbers that are missing

ADR-0001, 0002 and 0005 to 0012 recorded the decisions of the product direction this repository
followed privately from 2026-08-25 until ADR-0013 retired it on 2026-09-02: a governed data agent
over a synthetic schema, its security kernel, its metric contract and its milestones. They, the code
they governed and the reports that verified it stay in the private history before publication, which
the owner can provide on request. The three accepted ones kept here are the ones the audit tool
still rests on; 0014, accepted on 2026-09-04, is the engine it reaches next.
