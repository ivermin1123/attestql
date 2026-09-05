# Published gold errata for BIRD dev, Mini-Dev, Spider 1.0, and test-suite accuracy against the shuffle probe

<!-- cspell:ignore Wretblad Riseby Biswas Holmstrom Zhong Klein huybery Arcwise atremante TestSuiteEval niklaswretblad ICSE cidrdb UIUC laptimes misranks aclanthology ruiqi -->

R-C, 2026-09-04. Scripts/ids: `plans/reports/research-260904-published-gold-errata/`
(`build_overlap.py`, `errata-ids.json`, `overlap.json`); raw downloads stay in the scratchpad, cited
by URL, commit, sha256.

## 1. Sources of published gold errata

**Wretblad et al. 2024, BIRD financial domain.** arXiv 2402.12243 (ACL 2024 short). Repo:
[niklaswretblad/the-effects-of-noise-in-text-to-SQL](https://github.com/niklaswretblad/the-effects-of-noise-in-text-to-SQL),
MIT, commit `6930cf6f`. `annotations/financial_annotations.csv` (106 questions, sha256
`88167ff3...`): id, original/suggested question and gold SQL, a comment, an error category (six:
spelling/syntax, vague/ambiguous, incorrect SQL, synonyms, capitalization, no schema mapping).
Measured: 52 of 106 (ids 89-194) carry a category, 27 also a corrected SQL, reproducing the paper's
own "52/106 (49%)". `annotations/sampled_annotations.csv` (80 rows, sha256 `0d1d2601...`, 20 each
from california_schools, superhero, toxicology, thrombosis_prediction, not the full domain):
flagged 9, 3, 7, 8, matching the paper. Three curated `datasets/*.json` files (106 rows each) round
out the repo, kept whole at `$W/wretblad-repo/`.

**SpotIt (ICLR 2026) and SpotIt+ (arXiv 2603.04334).** SpotIt: [OpenReview iMkvR2ICSE](https://openreview.net/forum?id=iMkvR2ICSE),
[arXiv 2510.26840](https://arxiv.org/abs/2510.26840), CC BY 4.0. Reports EX dropping 11.3 to 14.2
points on BIRD under its verifier; the paper (read in full) names no released question-id list and
no code repository. SpotIt+: paper CC BY 4.0; two near-identical repos,
[atremante26/SpotItPlus](https://github.com/atremante26/SpotItPlus) and
[ai-ar-research/SpotIt-plus](https://github.com/ai-ar-research/SpotIt-plus), neither carries a
results or flagged-question file. Licence correction to N3/U4: `LICENSE` (one commit, `fbf5460`,
2026-02-15, unchanged since, read raw from both repos) opens "All rights reserved" but the next
paragraph grants study, modification and redistribution under a reproduced modified-BSD-3-clause
text, a real grant, not "no grant of use" as ADR-0013, N3 and issue U4 state; new evidence against a
claim on record, flagged, not changed here.

**Jin, Choi, Zhu, Kang, CIDR 2026, "Text-to-SQL Benchmarks are Broken".**
[vldb.org/cidrdb/papers/2026/p5-jin.pdf](https://www.vldb.org/cidrdb/papers/2026/p5-jin.pdf), CC BY
4.0, UIUC; read in full (5 pages). Four patterns: E1 semantics-vs-intent, E2 semantics-vs-data,
E3 semantics-vs-domain-knowledge, E4 ambiguity. BIRD Mini-Dev (498): 52.8% error rate, "16.7%
higher than the previously reported rate of 36.1%", a citation to a `mini_dev` issue-39 comment not
loadable this session (see Unresolved). No separate data file; the
per-question record is Table 2 (Mini-Dev, 18 ids, in `errata-ids.json`'s `cidr2026_jin_minidev_table2_18`)
and Table 3 (Spider 2.0-Snow `sf_bq*` ids, 66.1% of 121). Its Figure 2 corrects BIRD Dev question
985 (`laptimes.time` misranks as text), the same defect class as Mini-Dev 879, found independently.

**`bird-bench/mini_dev` issues naming a gold, evidence or question defect.** All 40 issues/PRs read (one API page, cached in `$W/gh_cache/`). Nine name an id (a tenth, issue
31, open 2026-01-18, questions a boundary predicate on question 336, a clarification not a defect):

| # | State | Opened | Ids | What |
|---|---|---|---|---|
| [38](https://github.com/bird-bench/mini_dev/issues/38) | open | 2026-08-09 | 1029 | `ASC` orders "highest"; owner's comment U1 |
| [39](https://github.com/bird-bench/mini_dev/issues/39) | open | 2026-09-03 | 207 | join returns 13 not 5; filed by owner, U2 |
| [24](https://github.com/bird-bench/mini_dev/issues/24) | closed | 2025-09-13 | 879 | text-typed `fastestLapSpeed` misranks |
| [19](https://github.com/bird-bench/mini_dev/issues/19) | closed | 2025-03-17 | 1322 | `EXCEPT` returns names, question asks a count |
| [17](https://github.com/bird-bench/mini_dev/issues/17) | closed | 2025-01-03 | 137, 138 | duplicated rows; still duplicated in our zip (A10) |
| [30](https://github.com/bird-bench/mini_dev/issues/30) | closed | 2025-12-24 | 180 | "their" ambiguous; overlaps Wretblad's own flag |
| [18](https://github.com/bird-bench/mini_dev/issues/18) | closed | 2025-03-12 | 563, 565 | timestamp absent from shipped data |
| [40](https://github.com/bird-bench/mini_dev/issues/40) | open | 2026-09-03 | (set-level) | zip vs Hugging Face id sets differ; owner, U3 |

`AlibabaResearch/DAMO-ConvAI` issue 227 (open, 2026-03-29) restates the 207 defect above under a
new title. Its issue 39 (2023-06-11, `huybery`) is the report-here panel, thread not enumerable
(same quota), no other issue found there. `bird-bench/BIRD-CRITIC-1` (a different, CC BY-SA 4.0
benchmark, gold withheld by email) carries no BIRD dev/Mini-Dev errata.

**BIRD's own change history**, dated entries from the site and the Hugging Face commit APIs:

| Date | What |
|---|---|
| 2023-09-25 | "a cleaner version of dev set... fixed all errors"; ChatGPT/GPT-4 EX rise to 42.24%/49.15% |
| 2024-04-27 | licence to CC BY-SA 4.0 |
| 2024-06-27 | Mini-Dev announced (500, three dialects); our `dev.zip`'s `dev.json` shares the date |
| 2025-07-03 | `birdsql/bird_mini_dev` first published (commit `3f687bcc`, then `30c3c8b2` same morning) |
| 2026-01-18 | `bird_mini_dev` replaced (`f65faf4a`, our pin); `bird_sql_dev_20251106` shows the same last-modified |
| 2025-11-13 (site) | "comprehensive quality control", `bird-sql-dev-20251106` on Hugging Face, CC BY-SA 4.0 |

Measured (`3569beae...` vs our pin): between the two Mini-Dev revisions only 879 changed; 1322 was
already fixed at first publish. Measured (`bird_sql_dev_20251106` sha256 `ffd80183...` vs
`dev.json` sha256 `630272f2...`): of 1,534, 399 (26.0%) have a normalized-different gold SQL, 172
(11.2%) differ only in text; all three tracked defects sit in the 399, unevenly: 1029's `ORDER BY`
is now `DESC` (fixed); 207 is replaced by an unrelated, larger query with a different result shape
(a rewrite, not visibly minimal); 879's SQL is byte-identical modulo newlines, still open here
though Mini-Dev HF fixed it five months earlier. `dev_tied_append.json` (42 rows, same fields,
2023-09-19) ships inside `dev.zip`, unexplained by any changelog found.

**Spider 1.0 errata.** No single errata file; search of `taoyds/spider` found about 30 open-mostly issues reporting a
wrong or ambiguous gold. The "dev-set fixes announced in 2020": the raw README changelog dates
them, `06/07/2020` "corrected some annotation errors and label mismatches... in Spider dev and test
sets (~4% of dev examples updated)", commit
[`25fcd85d`](https://github.com/taoyds/spider/commit/25fcd85d9b6e94acaeb5e9172deadeefeed83f5e), and
`08/03/2020` corrected `column_name` mismatches in two schemas and reparsed SQL. Spider has no
stable numeric id; issues cite `dev_gold.sql` row numbers: issue 67 rows 542-543, issue 68 rows
362-363 (case typo), issue 70 rows 484-485 (wrong `GROUP BY`), issue 95 four questions numbered 17
to 20 in `evaluation_examples/dev.sql`; all four open. Issue 24 is Spider's report-here panel (open
since 2019-02-13, not enumerable, same quota); the test-suite paper corrects no Spider gold of its
own. Spider-DK, Spider-Syn, Spider-Realistic, Dr.Spider: perturbation sets, not errata.

## 2. Overlap by question id

Id verification (`build_overlap.py`): matching `db_id` and question text between
`mini_dev_pg-00000-of-00001.json` (500) and `dev.json` (1,534): 496 match; 4 do not (581, 791, 937,
1135), each a real text edit Mini-Dev carries that `dev.json` lacks (SQL not compared, Mini-Dev's
is a PostgreSQL rewrite by design). Mini-Dev ids are confirmed to be `dev.json` ids.

Sizes and every nonzero pairwise overlap are in `overlap.json`. Largest: Wretblad-financial x
BIRD's 2025-11-06 pass, 25 ids; our 56-question set (behind the 170 EX=1/NOT_EQUAL rows) x the same
pass, 14; our 22 evaluation-hazard ids x the same pass, 13. Questions 1029, 207, 879 sit in the
widest reach (corrected-golds, a `mini_dev` issue, the 2025-11-06 pass); 879 shows the reach's
limit: flagged in three places, fixed in only one (Mini-Dev HF).

## 3. Test-suite accuracy against the shuffle probe

Mechanism (Zhong, Yu, Klein, EMNLP 2020, `aclanthology.org/2020.emnlp-main.29` pages 396-399, read
in full; code per `ruiqi-zhong/TestSuiteEval`, `fuzz/`, `sql_util/`): mutate the gold once per
"neighbor" query (column, operator, constant, string, or drop a non-inert span); sample up to 1,000
random databases per schema under foreign-key/type constraints; greedily keep the smallest subset
that still distinguishes every neighbor from the gold; require the prediction to agree with the
gold on that distilled set. Takes the gold's denotation as ground truth: tightens single-database
match into multi-database match, never checks whether the gold itself is right.

| Test suites catch, shuffle cannot | Shuffle catches, test suites cannot |
|---|---|
| a prediction coincidentally equal to a correct gold on the shipped instance only (F2; no concrete Mini-Dev id found, release-1 does not build this) | a wrong gold itself: 1029's `ASC` and 879's text-typed order are wrong on every database, because the suite is built to match the gold, not question it |
| (none found) | order/float-sum dependence on the one real instance: 1473's `AVG` differs between two runs of the same statement on the same data under parallel workers (A22); separate database instances have no such axis |

Both assume the gold is correct: test suites raise confidence a differing prediction is really
different, the shuffle probe surfaces that the gold's own answer is unstable.

## 4. What changes in AttestQL

- (claim) `docs/claims-register.md` N3, (non-claim) the SpotIt+ licence line: raw `LICENSE` reads
  as a real modified-BSD grant, not "no grant of use"; owner should re-read before revising N3/U4.
- (claim) new candidate row: BIRD's 2025-11-06 pass (`bird-sql-dev-20251106`, 1,534 questions, CC
  BY-SA 4.0) changes 399 golds, fixes 1029, not 879; a row once AttestQL's target is decided.
- (no change: release 1 is Mini-Dev only, ADR-0013) Wretblad, CIDR and `mini_dev`-issue ids do not
  enter `smells.py`; (no change: F2 remains release 2) no source gave a concrete F2 id; (no change:
  NOTICE already lists the excerpted material) none of today's ids are reproduced here.
- (claim) `docs/adr/0014-sqlite-backend-behind-the-same-evidence-record.md`: adds weight to its
  premise (BIRD dev, Spider 1.0 dev are SQLite-only; dev has a second gold, 26% rewritten).

## Unresolved questions

- Two threads unreadable (pagination, quota): CIDR's 36.1% citation (`mini_dev` issue 39, comment
  `2303283506`, `Arcwise`) and the DAMO-ConvAI 39 panel.
- `dev_tied_append.json`'s purpose, and whether the 2025-11-06 pass's rewrite of 207 is a fix or a
  new defect: neither judged here.

Status: DONE_WITH_CONCERNS
Summary: every requested source found and measured with a script or a direct read; the SpotIt+
licence finding and the 2025-11-06 BIRD dev pass are most likely to change a decision on record.
Concerns/Blockers: two comment threads unreadable under the exhausted GitHub API quota; the SpotIt+
licence contradicts ADR-0013/N3/U4, needs the owner's own read before anything changes.
