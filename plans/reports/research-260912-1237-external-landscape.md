<!-- cspell:ignore abedini Bouattour charliefrantowski DBQA Demiralp EHRSQL Fleiss Giovannini Hassanzadeh Hochman Hsuan Kaple Klimovic Klopfenstein linhongyu Lyzr Narodytska Neur nlqdb NOASSERTION Perlitz Pham pinren Pourreza PVLDB pydigger Rafiei replayable sepideh spotit sqlbench szabgab Tatbul Tengjun Tremante uiuc UIUC Wenz Yoojin Yuxuan Zanoli Zrobek -->
# External landscape: neighbours, upstream, discourse, visibility

Read-only research lane. Every source below was read on 2026-09-12 unless a different read date is
stated. Dates attached to artifacts are the artifact's own dates (commit, release, submission),
not the read date.

## Bottom line

1. The register claim of 2026-09-04 ("no installable tool takes a gold, a prediction and a
   database and reports where they differ") is no longer defensible as written. IBM's
   [text2sql-eval-toolkit](https://github.com/IBM/text2sql-eval-toolkit) is on PyPI, executes gold
   and prediction against the same SQLite file or PostgreSQL server, and reports three comparisons
   per record including a reproduction of BIRD's own set equality. It is a VLDB 2026 demo paper.
2. What no other tool does is the gold-only part: probing a gold for tie-at-LIMIT, NULL ordering,
   text-sorted numbers, duplicate rows and non-determinism, and emitting a replayable evidence
   record. Searching the IBM repository for determinism or nondeterminism machinery returns
   nothing in code.
3. Upstream BIRD acknowledged the reports on 2026-09-05 and promised a fix "in the next patch".
   Nothing has shipped since: last mini_dev commit is 2026-09-05 and touches only the README, and
   both Hugging Face datasets were last modified 2026-01-18.
4. The conversation about benchmark gold quality in 2026 is almost entirely academic (VLDB, CIDR,
   ACL) plus a thin blog and Hacker News layer. The people who would care are identifiable and
   few.
5. AttestQL has no third-party mention anywhere I could reach: only the owner's repository, the
   PyPI page, the site, the upstream issue threads he filed, and two automated package mirrors.
6. The only benchmarks with both public databases and public gold are Spider 1.0, the Spider
   2.0-lite local SQLite subset, Archer and BIRD dev/train. The BIRD-Critic, LiveSQLBench and
   BIRD-Interact family still withholds gold.

## 1. Neighbours, re-measured

| Tool | Date | Installable | What it does | Difference from AttestQL |
| --- | --- | --- | --- | --- |
| [IBM text2sql-eval-toolkit](https://github.com/IBM/text2sql-eval-toolkit) | PyPI 1.5.0, 2026-09-01 | yes, PyPI | Runs gold and prediction on SQLite or PostgreSQL, 12+ metrics, LLM judge, dashboard | Scores predictions against a gold assumed correct; no gold-only probes, no evidence record |
| [SpotIt+](https://github.com/ai-ar-research/SpotIt-plus) | repo pushed 2026-07-02, paper 2026-03-04 | no, clone only | Bounded equivalence via Z3, searches for a differentiating database | Synthesises databases; does not run on the shipped data or judge the gold |
| [uiuc-kang-lab/text_to_sql_benchmarks](https://github.com/uiuc-kang-lab/text_to_sql_benchmarks) | pushed 2026-08-27 | no, clone only | SAR-Agent, an LLM agent that detects annotation errors, plus corrected labels | LLM agent plus human validation; AttestQL is deterministic replay |
| [sfu-db/ParSEval](https://github.com/sfu-db/ParSEval) | pushed 2026-07-23, Apache-2.0 | no, clone only | Plan-aware test database generation for SQL equivalence evaluation | Generates test databases, counterexample driven, not shipped-data replay |
| [sepideh-abedini/SQLyzr](https://github.com/sepideh-abedini/SQLyzr) | pushed 2026-06-01, no licence | no | Fine-grained evaluation platform, workload scaling, error classification | Evaluation and analysis of models, not gold auditing |
| [th3nolo/sqlbench-harness](https://github.com/th3nolo/sqlbench-harness) | pushed 2026-07-05, MIT | no | Runs prediction and gold on the same local SQLite DB, reports accuracy and cost | Scoring harness with input provenance; gold is the reference, not the subject |

### The one that matters: IBM text2sql-eval-toolkit

Evidence, all read 2026-09-12:

- On PyPI as version 1.5.0, uploaded 2026-09-01; first release 1.0.0 on 2026-03-11, so it predates
  the register entry of 2026-09-04. See <https://pypi.org/pypi/text2sql-eval-toolkit/json>.
- VLDB 2026 demo paper, presented 2026-08-31, authors Hassanzadeh, Perlitz, Pham, Kaple, Zrobek,
  Vu, Glass, Subramanian, Pourreza and Rafiei, PVLDB 19(12):4582-4585.
  See <https://research.ibm.com/publications/text-to-sql-evaluation-toolkit>.
- It reproduces BIRD's scorer beside its own comparisons. The function
  compare_dfs_bird_eval_logic in src/text2sql_eval_toolkit/metrics/text2sql_utils.py documents
  exactly the three consequences AttestQL's typed comparison is built against: row order ignored,
  duplicate rows collapse, values compared as text. compare_result_dfs decides ordered versus
  unordered comparison by looking for ORDER BY in the gold, with string literals blanked first.
- PostgreSQL execution is real, not transpiled: data/benchmarks/dbs/README.md documents importing
  BIRD_dev.sql into a Postgres container and setting POSTGRES_CONNECTION_STRING. Packaged
  benchmarks include bird_mini_dev_postgres, bird_mini_dev_sqlite, spider_dev, spider_realistic,
  archer_en_dev and beaver (MySQL).
- Licence is inconsistent between surfaces: Apache-2.0 in the GitHub repository metadata, MIT in
  the PyPI metadata. Worth noting before citing it.
- Adoption is small: 14 stars, 409 downloads in the last month
  (<https://pypistats.org/api/packages/text2sql-eval-toolkit/recent>). This is a research demo
  with an institutional name on it, not an established dependency.

What it does not do, checked by code search over the repository on 2026-09-12: zero hits for
"nondeterministic", one hit for "determinism" and that is in a prose survey note, not code. There
is no gold-only probe suite, no tie-at-a-LIMIT-cut check, no NULL-ordering check, no evidence
record with session settings, result hash and a replay recipe. Its own survey note
(docs/notes/text-to-sql-evaluation-survey.md) argues for exactly that direction: "The final score
should be accompanied, where feasible, by raw and canonical SQL, parse trees, predicted/reference
result tables, execution exceptions, runtime ... This makes disagreements auditable rather than
collapsing all evidence into an opaque Boolean." That is a neighbour describing the gap, not
filling it.

### SpotIt+ has code now

The register cited SpotIt+ as a symbolic neighbour with unknown code status. Code exists:
<https://github.com/ai-ar-research/SpotIt-plus>, created 2026-02-02, last push 2026-07-02, 2
stars, licence NOASSERTION, no release, not on PyPI (a request for the name spotit or spotit-plus
on PyPI returns 404). Setup requires a VeriEQL git submodule, an OpenAI API key for constraint
mining, and a local BIRD dev download. The arXiv entry 2603.04334 is at v3, 2026-05-11, authors
Tremante, He, Klopfenstein, Wang, Narodytska and Wu. It proves or disproves equivalence on
synthesised databases; it never claims the shipped gold answers the shipped question.

### Explicitly found nothing

- No package on PyPI, found by direct name probe, for SpotIt, SpotIt+ or SAR-Agent.
- No quality-pass tooling of BIRD's own beyond evaluation_ex.py. The bird-bench account has 13
  repositories (listed 2026-09-12); none is an auditing or correction tool. The newest are
  bird-bench.github.io (2026-09-09, leaderboard entries) and mini_dev (2026-09-05).
- No Spider 2.0 maintainer tooling for gold verification. The one audit that exists there is a
  community pull request, [Spider2 #211](https://github.com/xlang-ai/Spider2/pull/211) by
  linhongyu510, opened 2026-08-13: a dependency-free read-only audit CLI for Spider2-Snow that
  validates external-knowledge references and released gold execution results over 547 instances.
  Zero comments from maintainers as of 2026-09-12. This is the closest thing to a peer effort
  found anywhere.

## 2. Upstream state

Nothing has shipped. Checked 2026-09-12:

- [bird-bench/mini_dev](https://github.com/bird-bench/mini_dev) latest commit abd11b6d,
  2026-09-05T21:32:50Z, "Revise download instructions for BIRD Mini-Dev". The diff touches only
  README.md and names Hugging Face as the canonical download. That is the direct answer to the
  owner's issue 40 and is the only upstream change of any kind.
- Maintainer BlackSoi1 replied on 2026-09-05 to issues 37, 38, 39 and 40 with "We will review and
  correct this issue in the next patch". Issues 41 to 50, filed 2026-09-05 and 2026-09-07, still
  have zero comments.
- Hugging Face birdsql/bird_mini_dev lastModified 2026-01-18T08:44:25Z; birdsql/
  bird_sql_dev_20251106 lastModified 2026-01-18T08:51:02Z. Neither has moved.
- The newest dataset under the birdsql account is birdsql/mini-interact, 2026-09-01. Nothing after
  2026-09-05.
- Hugging Face discussion 3 on bird_sql_dev_20251106 (opened 2026-09-07) has no maintainer reply.
  The only prior community quality report there is discussion 2, "Add boundary-case for Q336" by
  pinren, 2026-01-25, closed.
- AlibabaResearch/DAMO-ConvAI latest commit 2026-06-10, unrelated to BIRD gold.
- The BIRD site news page carries leaderboard submissions through 2026-09-07 and no data patch or
  correction announcement (<https://bird-bench.github.io/>).
- One curiosity: [mini_dev issue 51](https://github.com/bird-bench/mini_dev/issues/51), opened and
  closed within 35 seconds on 2026-09-11 by charliefrantowski, titled "Mini-Dev SQLite leaderboard
  entry (withdrawn pending revision)", body "Withdrawn by the author pending a revised
  submission." A leaderboard submitter pulling an entry back is a weak signal, not evidence of
  anything.

## 3. Discourse and audience

Venues and people, ranked by how plausibly they would care that 5.6 % of Mini-Dev's credits are
wrong answers.

1. **Tengjun Jin, Yoojin Choi, Yuxuan Zhu, Daniel Kang (UIUC Kang lab).** "Pervasive Annotation
   Errors Break Text-to-SQL Benchmarks and Leaderboards", PVLDB 19(5):931-944, 2026, arXiv
   2601.08778 v1 2026-01-13 and v3 2026-01-19, also the CIDR 2026 paper
   <https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf>. They built the audit agent and released
   corrected labels; they are the single most likely audience.
2. **The same group's follow-on work.** "Human-Level Text-to-SQL via Reinforcement Learning on
   Verified Data", arXiv 2603.20004, v1 2026-03-20 and updated 2026-08-21, which produced
   BIRD-Platinum: 2.5k verified BIRD Train instances with errors corrected in 61 % of them,
   published at <https://huggingface.co/datasets/uiuc-kang-lab/bird-platinum> on 2026-08-27. A
   deterministic, LLM-free detector of a subclass of those errors is directly relevant to them.
3. **ELT-Bench-Verified**, arXiv 2603.29399, 2026-03-31, Zanoli, Giovannini, Jin, Klimovic,
   Perlitz. Same audit-the-benchmark argument applied to data engineering, with an
   Auditor-Corrector methodology and Fleiss kappa 0.85. Shares an author with the BIRD audit and
   an author with the IBM toolkit.
4. **The IBM toolkit team** (Hassanzadeh and colleagues, VLDB 2026 demo, 2026-08-31). Their own
   survey note names benchmark audits as one of the directions the field is moving in and cites
   Jin et al. as a warning. They ship the closest competing artifact and are the most likely to
   either adopt or duplicate the probe idea.
5. **BenchPress (CIDR 2026)**, Wenz, Bouattour, Yang, Choi, Gregg, Tatbul, Demiralp, a
   human-in-the-loop annotation system for rapid text-to-SQL benchmark curation
   (<https://www.vldb.org/cidrdb/2026/benchpress-a-human-in-the-loop-annotation-system-for-rapid-text-to-sql-benchmark-curation.html>).
   Curation upstream of the defect, same problem statement.
6. **BLOG@CACM, "If You Think You Can Do Real-World Text-to-SQL", July 2026**, and its Hacker News
   thread <https://news.ycombinator.com/item?id=49013995> (2026-07-22, 62 points, 13 comments).
   The highest-engagement general-audience thread on text-to-SQL benchmark validity I found in
   2026. The post itself returned HTTP 403 to my fetch; the framing comes from the HN title and
   search snippets, which attribute it to the BEAVER line of work.
7. **Omer Hochman, "Your text-to-SQL model isn't as wrong as your benchmark says. The gold SQL
   is."**, DEV Community, 2026-08-07
   (<https://dev.to/omer_hochman/your-text-to-sql-model-isnt-as-wrong-as-your-benchmark-says-the-gold-sql-is-p16>).
   Reports 46 of 238 BIRD-dev mismatches (19 %) differing only by an omitted DISTINCT, and cites
   the UIUC 52.8 %. Promotes a product (nlqdb), one visible comment. This is the only vendor-side
   post found that leads with gold quality.
8. **The upstream issue trackers themselves.** bird-bench/mini_dev, where BlackSoi1 answers within
   days, and xlang-ai/Spider2, where the live gold complaints are
   [#195](https://github.com/xlang-ai/Spider2/issues/195) (2026-05-25, external knowledge
   inconsistent with gold) and [#216](https://github.com/xlang-ai/Spider2/issues/216)
   (2026-09-07, Spider2-lite local029 gold join inflates a count). Spider2's tracker in 2026 is
   dominated by Snowflake access failures (issues 202 to 218), which suppresses attention to gold
   defects there.

Published gold error rates, for citation hygiene:

| Source | Dataset | Rate | Note |
| --- | --- | --- | --- |
| Jin et al., arXiv 2601.08778 (2026-01) | BIRD Mini-Dev | 52.8 % | Same number in both versions |
| Jin et al., arXiv 2601.08778 (2026-01) | Spider 2.0-Snow | 62.8 % | CIDR version states 66.1 % over the 121 open-gold problems; cite the version you read |
| Jin et al., re-evaluating 16 BIRD agents | BIRD dev subset | -7 % to +31 % relative, rank changes -9 to +9 | Leaderboard impact |
| Zhu et al., arXiv 2603.20004 | BIRD Train sample (2.5k) | 61 % of instances corrected | BIRD-Platinum |

## 4. Visibility of AttestQL

Nothing outside the owner's own surfaces. Searched on 2026-09-12: web search for the bare term and
for the term with attestql.com and with text-to-SQL qualifiers; GitHub repository, code and issue
search; Hacker News full-text via Algolia (stories and comments); Hugging Face discussions; PyPI.

- Web search returns the [PyPI page](https://pypi.org/project/attestql/) and nothing else that is
  about this project. Every other hit is about attestation, the survey company Attest, or
  unrelated SQL auditing products.
- GitHub repository search: exactly one result, the owner's own. Issue search: five results, all
  the owner's own pull request and the mini_dev issues he filed or commented on.
- GitHub code search outside the owner's repository: one hit, szabgab/pydigger-data, an automated
  PyPI metadata mirror.
- Automated package mirrors carry the release with no human content:
  <https://libraries.io/pypi/attestql> and <https://www.piwheels.org/project/attestql/> both
  resolve; pydigger.com returns 404.
- Hacker News: no story and no comment mentions the name. The Algolia query matches only
  attestation-related text.
- PyPI downloads as of 2026-09-12: 315 in the last month, 315 in the last week, 2 in the last day
  (<https://pypistats.org/api/packages/attestql/recent>). A week-equals-month figure with this
  shape is consistent with mirrors and CI, not with users.

Not checked, because all three are blocked from here with HTTP 403: X/Twitter, Bluesky and
Reddit. A mention on those would not have been seen.

## 5. Adjacent audit targets

| Benchmark | Engine | Databases public | Gold public | Licence | Size or count |
| --- | --- | --- | --- | --- | --- |
| Spider 1.0 | SQLite | yes | yes | CC BY-SA 4.0 | 1,034 dev pairs, 166 DBs |
| Spider 2.0-lite, local subset | SQLite | yes, separate download | yes, evaluation_suite/gold/sql, 256 files | MIT (repo) | 135 SQLite instances of 547 total |
| Spider 2.0-snow, dbt | Snowflake, DuckDB | Snowflake access broken in 2026 | partial (121 open golds) | MIT (repo) | not a practical target now |
| Archer (English) | SQLite | yes, packaged by the IBM toolkit | yes | not verified | dev and train JSON |
| BIRD dev and train | SQLite, PostgreSQL, MySQL | yes | yes | CC BY-SA 4.0 | current target |
| BIRD-Critic 1.0 SQLite | SQLite | yes, 15 template .sqlite files | no, public rows carry only issue_sql | CC BY-SA 4.0 | 500 issues |
| BIRD-Critic 1.0 PostgreSQL | PostgreSQL | via repo setup | no, same gate | CC BY-SA 4.0 | 530 issues |
| LiveSQLBench base lite | PostgreSQL, SQLite variant | yes | no, sol_sql empty in public rows | CC BY-SA 4.0 | 270 tasks |
| BIRD-Interact lite, mini-interact | SQLite | yes | no, sol_sql empty arrays | CC BY-SA 4.0 | 300 rows |
| BEAVER | MySQL, Oracle | gated Google Drive | yes in repo | MIT (code) | enterprise warehouse |
| EHRSQL | SQLite | requires PhysioNet credentialing, not verified here | yes | CC BY 4.0 | NeurIPS 2022 |
| KaggleDBQA | SQLite | yes, Chia-Hsuan-Lee/KaggleDBQA | yes | NOASSERTION | 272 examples, last push 2023 |

The pattern is unchanged from the 2026-09-04 check: BIRD's newer families ship databases but not
gold. The only fresh near-zero-code target is the Spider 2.0-lite local SQLite subset, where both
the databases and 256 gold files are public under the repository's MIT licence, and where a
community audit attempt already exists in pull request 211.

## Limitations

- X/Twitter, Bluesky and Reddit were not searched: all three are blocked from this environment
  (HTTP 403). Discord and Slack of BIRD and Spider have no public archive I could read; the BIRD
  site lists only two Gmail contacts.
- The CACM blog post returned HTTP 403, so its author list and exact claims are second hand.
- Licence for Archer, and database availability for EHRSQL, were not verified at source.
- I did not verify which version of the IBM toolkit first shipped the PostgreSQL execution path;
  the capability set described is what version 1.5.0 contains.
- Paper claims are taken from abstracts and repository files, not from full-text reading of the
  PDFs, except where a specific file is quoted.

## Open questions for the coordinator

1. The register claim needs rewording rather than deletion. Which narrower claim do you want to
   stand behind: the gold-only probes, the evidence record and replay, or both?
2. Is the IBM toolkit a competitor to differentiate from, a citation to add, or a place to
   contribute the probes? Its own survey note asks for what AttestQL already emits.
3. BIRD said "next patch" a week ago and has shipped nothing. Do you want a dated follow-up on the
   open issues, or silence until they move?
4. Spider 2.0-lite has public SQLite databases, 256 public golds, and an unanswered community
   audit pull request. Worth checking whether that maintainer wants collaboration before any work
   starts there?
