# Discovery: real problem candidates (reorientation, Phase 1)

Date: 2026-09-02. HEAD `0e0c546` on `master`. Requested by the owner's reorientation decision of the
same day. Read-only on the code; no decision taken here. The two standing verdicts
(`verification-260902-1839-direction-and-reality-check.md`,
`research-260902-1833-governed-text-to-sql-landscape.md`) are treated as fact unless a line below
overturns one with a cited source.

Method. Five independent evidence passes, one per candidate, each with no access to the repository
and a fixed budget of 5 searches and 10 fetches. Every claim below carries a link. OPENED means the
page was fetched and read; SEARCH-ONLY means a snippet only. Four load-bearing SEARCH-ONLY items
were re-opened by the coordinator and are marked "re-verified". The raw pass notes are in the
session scratchpad, not in the repository, on purpose: five more process documents is the thing
decision 4 forbids.

## 0. Phase 0: freeze state (measured this session)

| Check | Result | Artifact |
|---|---|---|
| T18 merged | yes, `72c2aea`; HEAD `0e0c546` | `git log` |
| M5 sandbox gate, whole suite as the child | exit 0; 2191 passed, 0 failed, 175 skipped, 12.03 s | `tools/m5-sandbox/run.sh` run with its output directory outside the repository; container and volume removed |
| `just check` runs the sandbox | no | `justfile`: lint, typecheck, repocheck, docs, test |
| Untracked under no gate | 4 reports in `plans/reports/`, modified `cspell.json` | `git status` |
| Stale branches and worktrees | 19 branches, 4 extra worktrees (`wp2/*`, `wp3/*`, `feat/spike`, `codex/ui-prototype`) | `git branch`, `git worktree list` |

The six sandbox failures the verification report saw are gone with T18. Engine work is frozen from
here until ADR-0013 is accepted.

## 1. What survives, as measured in the code

| Asset | Where | Lines | Engine-agnostic | Note |
|---|---|---|---|---|
| Evidence record, 29 required fields, no defaults | `src/attestql/evidence/record.py`, `build.py` | 350 | yes | `IncompleteEvidence` on any missing field |
| Deterministic typed serialization and hash | `src/attestql/evidence/serialize.py` | 228 | yes | typed cells, decimal scale, UTC rendering |
| Replay comparator: EQUAL, NOT_EQUAL, NOT_COMPARABLE naming the moved precondition | `src/attestql/evidence/replay.py` | 198 | yes | 7 precondition fields, 3 rule fields, R-ORD and R-SET |
| Evaluation clock, relative windows against a pinned instant | `src/attestql/contract/clock.py` | part of 625 | yes | raises `UnknownWindow`, never guesses |
| AST allowlist validator, fails closed | `src/attestql/kernel/adapters/v29.py` plus vendored `grammar.py` | 1183 plus vendored | no: PostgreSQL 16 via libpg_query | pinned by digest; `pglast==6.16`, GPLv3+ (section 4) |
| Tenant executor that reads its limits back | `src/attestql/security/` | 4016 | PostgreSQL | psycopg behind one adapter module |
| Golden oracle, second derivation of the same contract | `src/attestql/golden/` | 610 | yes | shares the canonical registry and the clock (verification F7) |
| Claims register, negative-claim decay, NO-GO | `docs/claims-register.md` | 97 lines, 33 rows | n/a | 8 days behind the code (verification F6) |

Provider dependency in the product path: none. `src/` imports no model SDK. The only model call is
`tools/m6-generation/generate.py`, off the product path.

## 2. Candidates

Each candidate has the seven fields the owner asked for. Evidence strength is the pass's own grade,
adjusted by the coordinator only where a re-verification changed it.

### C1. Evaluation false positives and wrong gold in text-to-SQL benchmarks

| Field | Finding |
|---|---|
| Who has it today | [bird-bench/mini_dev #24](https://github.com/bird-bench/mini_dev/issues/24) "Wrong gold sql", closed 2025-09-13, gold sorts a text field lexicographically (OPENED). [taoyds/spider #115](https://github.com/taoyds/spider/issues/115) "Erroneous Gold Sql", open since 2025-04-14, no maintainer reply (OPENED). [xlang-ai/Spider2 #203](https://github.com/xlang-ai/Spider2/issues/203) "execution of gold query lead to different results", open 2026-07-22, no reply (re-verified). [AlibabaResearch/DAMO-ConvAI #227](https://github.com/AlibabaResearch/DAMO-ConvAI/issues/227) "Logical Error in BIRD-DEV Ground Truth SQL, question 207", open 2026-03-29, 0 comments (re-verified). [CIDR 2026, Jin et al.](https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf): 52.8 % annotation error in BIRD Mini-Dev, 66.1 % in Spider 2.0-Snow, leaderboard ranks move up to 3 places on corrected gold. [SpotIt, arXiv 2510.26840](https://arxiv.org/abs/2510.26840), ICLR 2026: execution match "often overlooks differences"; no code release on the abstract page (OPENED). |
| What they do now | Issue-by-issue fixes when someone reports; Spider and Spider 2.0 reports sit open unanswered. BIRD's PostgreSQL and MySQL variants were produced with sqlglot plus a GPT-4 pass, which the 52.8 % figure shows did not catch most errors ([mini_dev README](https://github.com/bird-bench/mini_dev), OPENED). No upstream has adopted a corrected gold set (NONE FOUND). |
| Why existing tools fail | [test-suite-sql-eval](https://github.com/taoyds/test-suite-sql-eval) (EMNLP 2020): SQLite only, assumes gold is correct, no package (SEARCH-ONLY). [Cosette](https://github.com/uwdb/Cosette): deprecated in its own README, decidable fragment only (OPENED). QED, SQLSolver: no runnable public code found. [VeriEQL](https://github.com/VeriEQL/VeriEQL): research code, batch JSON input, no PostgreSQL integration (OPENED). SpotIt: paper only. Nothing takes (question, gold, prediction, PostgreSQL database) and says "these agree on the shipped data and disagree on this instance". |
| Disqualifiers | None complete. SpotIt is the closest idea and has no code; it also cannot say gold is wrong, only that two queries differ. |
| Smallest artifact | A CLI that takes gold SQL, predicted SQL and a PostgreSQL DSN, runs both on the shipped data and on N schema-preserving perturbed instances (row shuffles for order nondeterminism, constraint-respecting mutations for value sensitivity), and emits one evidence record per comparison with EQUAL, NOT_EQUAL or NOT_COMPARABLE and the counterexample instance attached. A second mode re-runs gold alone across instances and flags gold that is not a function of the data (LIMIT without a total order, the Spider2 #203 class). Mutation search, not SMT: weaker than SpotIt's bound, buildable by one person, and it reuses the comparator, the serialization and the record as they are. |
| Observable | A gold row on `bird-bench/mini_dev` or `xlang-ai/Spider2` corrected upstream with our counterexample cited; or, without upstream, a public table "N of 500 Mini-Dev gold queries are order-nondeterministic or data-sensitive, evidence record per row" that a third party can re-run. |
| Public dataset | [BIRD Mini-Dev](https://github.com/bird-bench/mini_dev), CC BY-SA 4.0, 500 pairs over 11 databases, ships a PostgreSQL dump loaded with one `psql -f` (OPENED). Known non-zero yield to find. |
| Evidence strength | STRONG on the problem (four trackers, two peer-reviewed papers), STRONG on the tool gap, MODERATE on "who would run it" (benchmark maintainers are unresponsive; researchers and anyone building an eval set are the users). |

### C2. Fail-closed AST allowlist guard for LLM agents and MCP database servers

| Field | Finding |
|---|---|
| Who has it today | [Datadog Security Labs, 2025-08-21](https://securitylabs.datadoghq.com/articles/mcp-vulnerability-case-study-SQL-injection-in-the-postgresql-mcp-server/): the reference PostgreSQL MCP server's "read-only" was a `BEGIN READ ONLY` wrapper, escaped with `COMMIT; DROP SCHEMA public CASCADE;`; patched and archived 2025-05-29, deprecated package still ~20k weekly downloads (OPENED). [crystaldba/postgres-mcp README](https://github.com/crystaldba/postgres-mcp/blob/main/README.md): restricted mode is a pglast blocklist of COMMIT and ROLLBACK plus a timeout; the README admits stored-procedure languages circumvent it (OPENED). [Replit agent deleted a production database, 2025-07-18](https://incidentdatabase.ai/cite/1152/) (OPENED). [vanna-ai/vanna #475](https://github.com/vanna-ai/vanna/issues/475) read-only mode request, open since 2024-06-02 (OPENED). [supabase discussion #34401](https://github.com/orgs/supabase/discussions/34401): read-only semantics differ across MCP forks; maintainer says never point it at production (OPENED). |
| What they do now | Transaction-level READ ONLY; two-keyword blocklists; a read-only role; or a curated tools file instead of free SQL ([genai-toolbox](https://github.com/googleapis/genai-toolbox), which still ships a raw `execute_sql` tool, OPENED). |
| Why existing tools fail | Transaction READ ONLY dies on multi-statement input. Blocklists stop the known trick and nothing else. Role semantics are inconsistent and invisible to the caller. A modifying CTE parses as a top-level SELECT (SEARCH-ONLY, plausible, not primary-sourced). No named reason, no record of what was checked. |
| Disqualifiers | Brutal one: a real role-level REVOKE plus `statement_timeout` would have stopped both documented incidents. The guard's marginal value is side-effecting functions, resource bounds a role cannot express, misconfigured or shared roles, and the named-reason record. No standalone pglast allowlist package exists on PyPI (NONE FOUND, one dedicated search). A vendor blog argues parser defences are an arms race ([faucetdb](https://faucetdb.ai/blog/2026-04-30-postgres-mcp-sql-injection-read-only-bypass/), secondary, conflict of interest, demonstrates no allowlist bypass). |
| Smallest artifact | `pip install`, `check --policy readonly 'SQL'` returning ADMIT or REFUSE with the node path; adversarial corpus including the exact Datadog payload; then a PR replacing the two-keyword blocklist in crystaldba/postgres-mcp (Python, MIT, already depends on pglast). |
| Observable | That PR merged, with CI showing 100 % refuse on the adversarial corpus and a measured refuse rate on legitimate BIRD Mini-Dev PostgreSQL queries. |
| Public dataset | [Pagila](https://github.com/devrimgunduz/pagila) (PostgreSQL licence) for the schema and the adversarial corpus; BIRD Mini-Dev PostgreSQL for the legitimate-query refuse rate. |
| Evidence strength | MODERATE-STRONG on the problem; the disqualifier is honest and large. Cost the pass did not price: the current grammar refused 11 of 15 model statements (verification F2), so a general-purpose guard needs a much wider grammar before anyone keeps it installed, and widening it re-opens the zero-wrong-answer claim. The parser is GPLv3+ (section 4). |

### C3. Portable evidence record format with a conformance suite

| Field | Finding |
|---|---|
| Who has it today | Nobody asks for it by name (NONE FOUND across Wren AI, Dataherald, MindsDB, DB-GPT, LangChain, Superset). Adjacent asks: [langchain #38345](https://github.com/langchain-ai/langchain/issues/38345) multi-statement SQL executed unvalidated, closed not-planned 2026-06-21; [langchain PR #38622](https://github.com/langchain-ai/langchain/pull/38622) merged 2026-07-02, opt-in sqlglot syntax check, records nothing (both OPENED). [apache/superset #43376](https://github.com/apache/superset/pull/43376) chart query inspector, an open PR of 2026-08-21 with maintainer review (re-verified: a PR, not a user ask). [DB-GPT #3163](https://github.com/eosphoros-ai/DB-GPT/issues/3163) wants SLSA provenance for the Docker image, not the answer (OPENED). [arXiv 2606.04990](https://arxiv.org/abs/2606.04990), June 2026 survey: no unified trace schema for agent execution, SQL not mentioned (OPENED). Wren AI sells "answer lineage" as a paid feature ([getwren.ai/security](https://www.getwren.ai/security), SEARCH-ONLY). |
| What they do now | Per-tool, closed, non-portable: Wren's paid audit trail, Superset's in-app inspector, LangChain's syntax check. |
| Why existing tools fail | [OpenLineage](https://github.com/OpenLineage/OpenLineage/blob/main/README.md): pipeline lineage, no answer facet. [OpenTelemetry GenAI semconv](https://github.com/open-telemetry/semantic-conventions-genai): Development status, `db.*` names a RAG source, no generated-SQL, validation or result-hash attributes. [W3C PROV](https://www.w3.org/TR/prov-overview/): vocabulary only. [in-toto attestation](https://github.com/in-toto/attestation): usable envelope and predicate-type mechanism, no SQL predicate exists (all OPENED). Langfuse, LangSmith, MLflow: not checked. |
| Disqualifiers | None on the payload. in-toto is the right envelope if signing is ever wanted; do not invent one. |
| Smallest artifact | A versioned JSON Schema of the 29-field record, a validator CLI, a conformance kit of fixtures, one emitter PR into a foreign tool. |
| Observable | A tool that shares no code with this repository emits a record our validator accepts and our comparator classifies. |
| Public dataset | BIRD Mini-Dev PostgreSQL as the fixture source. |
| Evidence strength | WEAK on demand, MODERATE-STRONG on the gap. The landscape report's own warning stands: a format nobody emits is a format nobody has. It becomes real only as the output of a tool people already run, which is C1. |

### C4. As-of evaluation clock for restatement-sensitive reporting

| Field | Finding |
|---|---|
| Who has it today | [dbt-core #9892](https://github.com/dbt-labs/dbt-core/issues/9892) snapshot backfill and rebase, open since 2024-04-11, 0 reactions (OPENED). [SQLMesh restatement plans](https://sqlmesh.readthedocs.io/en/latest/concepts/plans/): table-level recompute, no comparison against a prior answer (OPENED); [sqlmesh #3062](https://github.com/TobikoData/sqlmesh/issues/3062) closed, adjacent (re-verified). [Uber QueryGPT](https://www.uber.com/en-CA/blog/query-gpt/): ~5 % run-to-run variance attributed entirely to the model, never tested against data movement (OPENED). Cube, Lightdash, Metabase, Evidence, Rill, Malloy, Dagster, Airflow: not checked. |
| What they do now | Table snapshots going forward only; imperative restatement commands; ignoring the noise. |
| Why existing tools fail | All operate on tables and rows ("what did this row say at T"), none on a question ("what did this metric resolve to under this clock, this data version and this definition, and which of those moved"). [Snowflake Time Travel](https://docs.snowflake.com/en/user-guide/data-time-travel) confirmed table-level (OPENED); Iceberg, Delta, BigQuery, XTDB, SQL:2011 tables: background knowledge, not re-verified. |
| Disqualifiers | None at the question level; all of the above at the table level. |
| Smallest artifact | Record (question, as_of, clock, resolved SQL, result hash, versions) on first ask; on re-ask report EQUAL, NOT_EQUAL or NOT_COMPARABLE with the one precondition that moved. |
| Observable | A metric drift diagnosed from the verdict alone instead of manual archaeology. |
| Public dataset | ALFRED vintage series, purpose-built for "same period, different vintage, different value" ([fredapi](https://github.com/mortada/fredapi) confirms the API, OPENED); alfred.stlouisfed.org and sec.gov blocked automated fetch, licence unverified. |
| Evidence strength | MODERATE and adjacent. Nobody has articulated the question-level framing as a request; the demonstration dataset is real but not confirmed reachable. Already inside C1: data_as_of and evaluation_clock are precondition fields of the comparator. |

### C5. The audit and lineage gap inside open-source text-to-SQL tools

| Field | Finding |
|---|---|
| Who has it today | One primary item: [langchain #38345](https://github.com/langchain-ai/langchain/issues/38345) (above). [Vanna archived 2026-03-29](https://github.com/vanna-ai/vanna), its "audit logs" bullet died with it (OPENED). [Dataherald golden SQL](https://dataherald.readthedocs.io/en/latest/api.golden_sql.html) is a few-shot store, not a record (OPENED). Canner/WrenAI issue search for audit, history, lineage, reproducibility: no matches (OPENED via API). Incident post-mortems: NONE FOUND. |
| What they do now | Nothing per answer, or a paid feature. |
| Why existing tools fail | No per-answer record of validation, versions, limits or replay rule in any OSS tool reached. Eight of fourteen named tools not reached. |
| Disqualifiers | Langfuse, LangSmith and OpenTelemetry tracing were not verified; a "yes" there would end this candidate. |
| Smallest artifact | An additive JSON emitter at one tool's execution hook. |
| Observable | Fewer "what query, what params, what version" round trips on that tool's bug reports. |
| Public dataset | Pagila. |
| Evidence strength | WEAK. Below the owner's bar of external evidence: one issue, closed not-planned. Kept because the owner listed it; it folds into C3, which folds into C1. |

## 3. Ranking

| Rank | Candidate | Problem evidence | Tool gap | Fit to surviving assets | Public data | Cost to first release | Main risk |
|---|---|---|---|---|---|---|---|
| 1 | C1 eval false positives, wrong gold | STRONG | real, no runnable tool | comparator, serialization, record, R-ORD/R-SET, oracle pattern, all unchanged | BIRD Mini-Dev PostgreSQL, one command to load | low: no grammar change, no model in the path | mutation search finds less than SMT; "proof" vocabulary must stay out |
| 2 | C2 read-only AST guard | MODERATE-STRONG | partial (blocklists exist) | validator, but grammar too narrow for general use | Pagila plus Mini-Dev | high: grammar widening, GPL parser swap, over-refusal measured before anyone keeps it | a role plus a timeout already covers the documented incidents |
| 3 | C3 portable record format | WEAK demand | real | record, serialization, comparator | Mini-Dev fixtures | medium | formats without an emitter die; should be C1's output, not a product |
| 4 | C4 as-of clock | MODERATE, adjacent | real at question level | clock, comparator | ALFRED, access unverified | medium | nobody has asked in these words |
| 5 | C5 in-tool audit gap | WEAK | unverified | record | Pagila | low | tracing tools may already cover it |

### The pick, in ten lines

1. C1 is the only candidate where real people have written down the problem, unprompted, in four
   issue trackers and two peer-reviewed venues, and where the reports sit open because nobody has
   a tool to answer them.
2. It is the only candidate that needs none of the risky work: no grammar widening, no parser swap,
   no model in the path, no consortium. The comparator, the serialization and the record are used
   as they are; the golden oracle becomes the pattern "a second derivation disagrees, here is the
   evidence".
3. It is provable on public data in one command: BIRD Mini-Dev ships PostgreSQL, has 500 pairs and
   a known non-zero error yield to find.
4. Its evidence record is C3 for free: every finding is a record, so the format gets an emitter and
   users before anyone is asked to adopt it. C4's clock and as_of are already precondition fields.
5. It is provider-agnostic by construction: predicted SQL comes from any system, or from a human.
6. The owner's own daily task fits if that task is grading model SQL, which M6 already is.
7. The falsification is cheap and dated: if, by a date, no benchmark row is corrected or re-run by
   a third party with our record attached, the thesis is wrong and we stop.
8. C2 stays second because its incidents are real but its honest disqualifier is large and its
   first release costs the most; it is the natural expansion once C1's validator is engine-clean.
9. The name holds: an evidence record for whether a SQL answer survives replay is what "attest"
   can honestly mean. The words "governed data agent" and "natural language" do not survive.
10. Ten minutes for a stranger: install, load Mini-Dev, run one comparison, read one record.

## 4. Licence proposal

**Apache-2.0.** The artefact that survives on every candidate is a format plus a reference
implementation plus a conformance kit, and the point of such a thing is that other projects embed
it. Apache-2.0 carries an explicit patent grant (section 3) and a contribution clause (section 5)
that MIT lacks, so a project that vendors the comparator or emits the record needs no separate
patent assurance and no contributor agreement from us. Every named peer and every neighbouring
standard in this space is Apache-2.0 already (Dataherald, Cube core, OpenLineage, OpenTelemetry),
so an Apache-2.0 artefact enters those codebases with no licence review. MIT would be acceptable
and shorter; it loses only the patent clause, and for a format meant for adoption by vendors that
clause is the one that matters.

**Constraint the owner must know before choosing.** The validator's parser, `pglast`, is GPLv3 or
later (PyPI metadata, checked locally; the maintainer has kept GPL since the 2018 thread,
[lelit/pglast #9](https://github.com/lelit/pglast/issues/9)). The underlying libpg_query is BSD-3
([LICENSE](https://github.com/pganalyze/libpg_query/blob/16-latest/LICENSE)). Our own source can be
Apache-2.0 regardless, but anyone who installs the package pulls a GPL runtime dependency, and
whether a Python import makes a derivative work is the argument nobody wants to have. Two
permissive bindings now exist: [pg-query-python](https://pypi.org/project/pg-query-python/)
(BSD-3, 0.1.3 released 2026-03-25, protobuf AST, builds against `16-latest` by environment
variable) and [postgast](https://github.com/eddieland/postgast) (BSD-2, PostgreSQL 18 grammar,
0 stars). The vendored grammar is pinned by digest and imports `pglast` directly, so swapping the
binding is a new validator version, and the zero-wrong-answer claim must be re-earned on the
mutation corpus. Under C1 the validator need not be in the product path for the first release (predicted SQL
would run under a read-only role and a statement timeout, a design point for ADR-0013), so the
dependency can be declared in the README and left alone; under C2 the swap is on the critical
path.

## 5. Disagreements with the decisions

None on substance. One fact the decisions did not account for: the validator the owner lists as
proven cannot ship under Apache-2.0 or MIT without either the parser swap above or a declared
GPLv3 runtime dependency. That cost is priced into the ranking.

## 6. Questions for the owner

1. What is the concrete task you do yourself where LLM-generated SQL gets checked: grading model
   output as in M6, using a database MCP server from an agent, or evaluating a vendor at work? The
   answer decides between C1 and C2 for "my own daily use".
2. For the first release, is a declared GPLv3 runtime dependency acceptable, with the validator kept
   off the product path, or must the parser swap happen before any tag?
3. The observable for C1 is upstream engagement: filing issues and pull requests on
   `bird-bench/mini_dev` and `xlang-ai/Spider2` under your personal GitHub identity. Are you willing
   to do that publicly, and under which identity?
4. What horizon do you accept for the falsification criterion: 30, 60 or 90 days after the tag?
5. Do you have a non-public evaluation set of your own (work or personal) that may be used for your
   daily task only, with public claims restricted to Mini-Dev, or is public data the only data?

## 7. Unresolved questions

- SpotIt+ ([arXiv 2603.04334](https://arxiv.org/abs/2603.04334)), SEARCH-ONLY, may have released
  code; if it did, it changes C1's tool-gap grade and must be checked before ADR-0013.
- Whether [arXiv 2601.08778](https://arxiv.org/abs/2601.08778) is the preprint of the CIDR paper or
  a second paper; cite one.
- Langfuse, LangSmith and MLflow tracing were not checked for C3 and C5. Dropped on 2026-09-02:
  the owner accepted C1, so neither candidate needs the check.
- ALFRED and SEC data licences could not be fetched by an automated client.
- Whether BIRD Mini-Dev's 780-instance V2 also ships PostgreSQL, or only the 500-pair set.
- No LLM-as-judge equivalence tooling was surveyed.
