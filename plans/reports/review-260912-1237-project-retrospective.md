<!-- cspell:ignore PVLDB uiuc UIUC replayable -->
# AttestQL, reviewed across every dimension, and what to do next

Written 2026-09-12 at `ba12f36`, the day 0.3.1 reached PyPI. This is a retrospective of the whole
public project, 2026-09-02 to today, read against what ADR-0013 promised, and it ends with a
proposal. It restates nothing the seven-lane review of 2026-09-08 already holds: that report and
the plan acting on it (`plans/260910-2013-review-findings/`) own the code-level findings and are
pointed at, not copied. What this review adds is the dimensions that report did not have: outcome
against the contract, evidence quality, adoption, upstream effect, process, and cost.

Everything below was measured today unless a date says otherwise. The external landscape lane,
`research-260912-1237-external-landscape.md`, was run beside this review and is summarised in
section 6.

## 1. What was promised, and what exists

ADR-0013 (2026-09-02) promised one artifact, `attestql audit` on PostgreSQL, about 900 source lines
and 600 test lines, a merge gate reproducing three shipped-gold defects, a README written only after
the gold-only probes were measured over all of Mini-Dev, and a falsification date 60 days after the
first public push.

What exists at `ba12f36`:

| Promised | Delivered | Beyond the promise |
|---|---|---|
| `attestql audit` on PostgreSQL | yes, with the session envelope read back and refused on drift | a SQLite backend behind the same record (ADR-0014); `attestql demo`; `attestql report` |
| about 900 source lines | 13,754 source lines, 15,513 test lines, 3,439 lines of tools | nine smell names in the code where the mechanism page named four probes |
| a gate reproducing three defects | `just check`: ruff, pyright strict, three repository checks, markdownlint, cspell, 1,190 tests, 34 PostgreSQL sandbox tests, 107 SQLite sandbox tests, green today | the demo output quoted in the README is checked byte for byte |
| a README after the Mini-Dev measurement | three measurements, each with the benchmark's own evaluator run beside the tool | a public site with 121 runs and 353 question directories, rebuilt on every push |
| upstream reports under the owner's identity | seven filed, one withdrawn, three acknowledged, one upstream document changed | six of the seven carry a counterexample the maintainer can run |
| a package a stranger can install | PyPI 0.2.1, 0.2.2, 0.3.0, 0.3.1 in five days, trusted publishing, no stored token | release assets hold every run whole, 21 archives, digests listed |

The scope grew by an order of magnitude in eleven days of commits (197 commits on nine active days,
88 of them docs, 41 fixes, 32 features). The growth was directed: every addition is either a second
engine the original ADR named as the first expansion, a probe with a measured precision, or the
publication of runs that already existed. Nothing in the tree is speculative.

The falsification criterion of ADR-0013 point 10 has two halves. The first, an upstream gold
acknowledged as wrong with our counterexample cited, was met on 2026-09-05. The second, a person
outside this repository using the tool and leaving an issue or a pull request, is not met, and
the window closes on 2026-11-02, 51 days from today. The ADR says neither outcome means
reconsider, so no decision is forced, but the project's own opening sentence, "built to be used
and not sold", is what the second half measures.

## 2. Evidence quality

This is the dimension the project is best at, and it has one soft spot.

**What holds.** Every number in the README has an owning artifact in `docs/claims-register.md`
with the tree it was measured at, the input digests, and who verified it. The benchmark's own
evaluator was run beside the tool on every measurement, unmodified, and the two readings of EX
agree on 4,476 of 4,482 and 4,481 of 4,482 predictions, with every disagreement explained by a
float sum's addition order. Negative claims carry a date and a decay rule. The site's runs were
made again under 0.3.1 and reconciled against the published counts before the release notes said
so. The run that retracted a false fire (q392 of `card_games`) is named on the release and the
page is gone. This is more rigour than the benchmarks being audited apply to themselves.

**The soft spot is the hand classification.** The headline the README leads with is that 69 of the
164 Mini-Dev predictions BIRD credits and the tool calls NOT_EQUAL are wrong answers the benchmark
credited, and that 23 BIRD dev golds do not answer their question. Both numbers rest on one reader.
On SQLite the reading was a sample of 50 of 237. The GLM research lanes of 2026-09-07 showed how a
hand label can go wrong at scale: lane L3 returned 49 of 50 labels from one template and had to be
re-read row by row (memory of that run; its corrected split was A 18, B 31, C 1). A second,
independent reading of even 30 of the 69 rows, agreement stated as a number, would turn the
headline from one person's judgement into a measured one. Nothing else in the evidence chain has a
single point of trust like this.

**One negative claim is wrong.** Register row N2 says no installable tool takes a gold, a
prediction and a database and reports where they differ. Section 6 shows one did, on PyPI since
March. The register's own rule is that negative claims decay and are re-measured, not inherited;
this one was not re-measured at the 0.3.x releases, and the correction is the first item of
section 9.

**Two smaller points.** The order-dependent probes on PostgreSQL (`not-a-function-of-the-data`,
`float-aggregate-order`) move with the planner's statistics, as the 0.3.1 refresh report measured;
the run records `last_analyze` per table, so a reader can see it, but a stranger's rerun on a
fresh load will not reproduce those two probes' fire counts exactly, and the README does not yet
say so in the sentence that quotes them. And no measurement has been reproduced by anyone outside
the repository, which is the same gap as section 4.

## 3. Engineering state

The seven-lane review of 2026-09-08 found 95 standing findings, 0 Critical, 7 High. Since then:
group A (22 safe items) was done by 2026-09-10; the three High logic defects shipped as 0.3.1
today; the history carrying an AI trailer was rewritten on the owner's order and a commit-message
hook now refuses the trailer. `just check` is green at `ba12f36` in the run made for this review.

Open, from that plan, in dependency order:

| Phase | Holds | Why it matters now |
|---|---|---|
| 2 | `main` has no ruleset (confirmed today: the rulesets list is empty, branch protection 404); raw output in `plans/reports` still 1,434 files that are not text reports | a public repo with releases and a deploying workflow, and nothing refuses a force-push or a deletion |
| 4 | 18 low-risk findings, among them LOGIC-08 (a prediction naming an unknown id is dropped in silence), LOGIC-12 to 14 (malformed question files reach a traceback or a wrong identity), LOGIC-04 (`search_path` not pinned) | these are the first things an outside user with their own files will hit; the demo cannot reach them |
| 5 | seven decided behaviours: the two budgets that refuse, ADR-0004 wording, kernel port removal, wrangler lockfile, semver statement, relative paths | PERF-01 is the only open item that can take a machine down on a bad prediction |
| 6 | the three refactors: `cli.py` at 1,999 lines, `render.py` at 1,865, `dict[str, Any]` with 31 casts | no open defect; it is where a contributor gives up, and there are no contributors yet |

The architecture holds its boundaries under test: the report package imports no engine, the two
backends sit behind one protocol, the record and comparator are one for both engines. The
dependency choices are argued in `pyproject.toml` itself, the two parsers are pinned exactly for a
stated reason, actions are SHA-pinned, Dependabot runs, private vulnerability reporting is on,
`SECURITY.md` exists. The public surface is the CLI alone and the README says so.

## 4. Adoption, measured

| Signal | Value | Read as |
|---|---|---|
| GitHub stars, forks, watchers | 0, 0, 0 | nobody has bookmarked it |
| Issues or pull requests from outside | 0 (four PRs: one the owner's, three Dependabot) | nobody has used it and spoken |
| Unique visitors, 14 days | 9 (62 views); referrers: github.com 2 uniques, attestql.com 1 | the owner and the review lanes |
| Unique cloners, 14 days | 168 (668 clones) | mirrors and CI runners, not people |
| PyPI downloads, last week | 315, last day 2 | the mirror baseline a new package gets |
| Mentions of the name outside the repo, PyPI and the site | one: a PyPI index crawler | none |

Nothing about the tool has been said anywhere except in the six upstream issues and one Hugging
Face discussion, all addressed to maintainers. Those are the right first audience, and they
answered. But a maintainer fixing a gold is not a user running the tool, and the people who would
run it (anyone who evaluates a text-to-SQL system on BIRD or Spider and wants to know what the
score is made of) have not been told it exists. The project has built the whole of the supply and
none of the demand.

## 5. Upstream effect

| Report | State today | Since |
|---|---|---|
| U1 q1029, U2 q207 | closed 2026-09-05, "we will review and correct this issue in the next patch"; no patch | 7 days |
| U3 zip versus Hugging Face | closed, README changed the same day (`abd11b6`, the only commit on the repository since) | done |
| U4 SpotIt licence | withdrawn by the owner, correction recorded | done |
| U5 q1473 float order, U6 23 BIRD dev golds, U7 five databases differ | open, zero comments each | 5 days |

The repository `bird-bench/mini_dev` has had one commit since 2026-09-05 and the Hugging Face
dataset is unchanged. The first batch got a reply within a day; the second has none after five.
Two of the three open reports (U6, U7) are the ones that ask for the most work, and U6 offers to
send corrected SQL per question. A follow-up that does that work for them, one pull request or one
corrected file, is the most likely way a gold row actually changes, which is the outcome the
criterion names.

## 6. The outside, as measured by the external lane

The sources are in `research-260912-1237-external-landscape.md`; the four facts below were
checked again by the coordinator on 2026-09-12 before being written here.

**A neighbour exists, and the register's N2 is out of date.** IBM's `text2sql-eval-toolkit`
(<https://github.com/IBM/text2sql-eval-toolkit>, PyPI since 2026-03-11, 1.5.0 on 2026-09-01, a
VLDB 2026 demo) runs a gold and a prediction on SQLite or PostgreSQL and scores them under several
comparisons, one of which reproduces BIRD's set reading; it decides ordered against unordered
comparison by the presence of ORDER BY in the gold. It predates the register row N2 of 2026-09-04,
so that row was wrong on the day it was written, not only decayed since. What the toolkit does
not do, by reading its code: no gold-only probes, no counterexample rows, no evidence record with
session settings, digests and a replay recipe, and nothing about nondeterminism. Its own survey
note asks for exactly that auditable output. N2 has to be reworded to the claim that still holds,
and the toolkit cited where neighbours are named.

**The audience has names.** The group that measured the 52.8 % annotation error rate (Jin, Choi,
Zhu, Kang, PVLDB 19(5) and CIDR 2026) released an LLM auditing agent and corrected labels
(<https://github.com/uiuc-kang-lab/text_to_sql_benchmarks>, pushed 2026-08-27) and a verified
BIRD training set (`uiuc-kang-lab/bird-platinum` on Hugging Face, 2026-08-27, 61 % of instances
corrected). A deterministic, model-free detector of a subclass of the errors they correct by hand
is directly useful to them, and they are the most likely first outside user. Beside them: the IBM
toolkit's authors, the BenchPress curation work (CIDR 2026), one vendor post of 2026-08-07 that
leads with gold quality, and a community pull request on Spider 2.0
(<https://github.com/xlang-ai/Spider2/pull/211>, 2026-08-13, a read-only gold audit, zero
maintainer comments) that is the closest peer effort found.

**Upstream has not moved.** One commit on `bird-bench/mini_dev` since 2026-09-05, the README
change; both Hugging Face datasets last modified 2026-01-18; the three open reports have zero
comments.

**Nobody outside knows the tool exists.** Web, GitHub, Hacker News and Hugging Face searches for
the name return the owner's own surfaces and two automated package mirrors. X, Bluesky and Reddit
could not be searched from the lane's environment, so a mention there would not have been seen.

**A second target is already half done.** Of the benchmarks that ship both databases and golds in
public, Spider 1.0 dev (SQLite, CC BY-SA 4.0) was already audited by the L4 research lane on
2026-09-07: 1,034 golds, 1,032 audited, 60 firing a probe (42 arbitrary cuts, 30 results that are
not a function of the data), report `research-260907-2013-spider-dev-sqlite.md`. It is measured
and not published: no README paragraph, no site benchmark, no upstream report. The Spider 2.0-lite
local SQLite subset (135 instances, 256 public gold files, MIT) is the next one that needs little
code. BIRD-Critic, LiveSQLBench and BIRD-Interact withhold their golds.

## 7. Product surface and documentation

The README opens with a 75-word sentence before the reader learns what to type. The two commands
and the verbatim demo output that follow are the strongest part of the page; they should be what a
reader meets first, with the sentence after them. The landing page has the same order problem in
a milder form: the one-line description from PyPI, then the ten-minute block, then the three
headline numbers. A reader who scrolls sees the right thing; one who does not sees a description.

Present and good: a flag-by-flag reference (`docs/audit-command.md`, 364 lines), the developer
environment document, six ADRs with a maintained index, the claims register, the site's own
method page. Absent: `CONTRIBUTING.md` (the developer document does the job, but a stranger looks
for the file), `CITATION.cff` (the audience is researchers; a citation file is how a tool gets
named in a paper), and a one-paragraph statement of what a first user should try on their own
files, which today is spread across the README's install section and the reference.

The site's open UI findings (UI-01 to UI-06: search metadata, distinguishable titles, a lighter
question page, a way back up, an empty state, chips with JavaScript off) are in phase 4. Three
hand-classified questions have no page because a page of one would be 5 to 10 MB; a renderer that
bounds the rows it draws is the fix and is not planned anywhere. Phase 5 of the web UI plan, the
Pyodide drop zone, is accepted and unbuilt; nobody has asked for it.

## 8. Process and cost

The work ran as a coordinator on Fable with implementation on Opus workers through Orca, research
and one review on Codex/GLM lanes, and the owner deciding at every gate. What it produced is above.
What it cost that is worth writing down:

- Three High defects shipped in 0.3.0 and were found by the independent review the same night.
  The review came after the release rather than before it. For the next feature release the
  order should be reversed: review, then tag.
- The GLM lanes were cheap and productive for read-only research and for the seven-lane review,
  and unreliable for hand labels, which had to be re-read. Polling them cost about 300k tokens a
  turn; batches in one blocking script did not.
- One history rewrite was made, on the owner's order, to remove three AI trailers and an 11.1 MB
  blob. It was done once, with a backup, and a hook now prevents the cause. It should stay the only
  one.
- Twelve owner decisions of 2026-09-10 are recorded with their reasons in the plan; nothing was
  decided by a session alone. This is the practice to keep.
- The machine holds 24 GB under `~/.cache/attestql-measure` (18 GB of it the L3 lane's, deletable;
  6.3 GB of inputs still used), 9.2 GB in `/tmp/attestql-runs` (the refresh's work directory, now
  reconciled and archived on the `v0.3.1` release), and a 247 MB pre-rewrite backup.

A note on a flag this session's tooling raised: a scanner flagged strings shaped like a run token
in file names. They are the substring `rt_` inside `test_report_renders` and `concert_singer`,
not credentials. Nothing needs rotating.

## 9. What to do next, in order

The order follows one judgement: the project has proven its claim and has no users, so the next
unit of work should buy a user, and the code work that helps a first user most comes before the
code work that helps a contributor.

**First, this week.**

1. Reword register row N2 to what still holds (no tool runs gold-only probes or writes a
   replayable evidence record with counterexample rows), date it, and name the IBM toolkit and
   SpotIt+ as the neighbours in the register and in ADR-0013's context. The project's brand is
   that its negatives are measured; this one is a week overdue.
2. Say it once, in public, under the owner's identity. One write-up built from the q879 example
   and the 5.6 % number, with the two commands. Two addressees come before any forum: the UIUC
   group behind the 52.8 % measurement, and the author of the Spider 2.0 audit pull request,
   each with the one number their own work would want checked. Sessions draft; the owner sends
   (ADR-0013 point 9). Add `CITATION.cff` the same day.
3. Move the two commands and the demo output to the top of the README and the landing, and put
   the long sentence after them. Two files, no behaviour change.
4. Phase 2 of the review plan: the ruleset on `main` (block deletion and force-push, CI required on
   pull requests) before anyone outside sends a pull request.
5. Set 2026-09-21 as the date to re-read U5 to U7, and prepare the corrected SQL U6 offered, so
   that if the maintainer answers, the fix is ready to hand over.

**Second, the fortnight after.**

1. Phase 4 of the review plan, with LOGIC-08 and LOGIC-12 to 14 first: they are the failure modes
   of a stranger's own question and prediction files.
2. Phase 5: the two budgets that refuse (PERF-01 is the one open item that can exhaust a machine),
   the ADR-0004 wording, and the kernel port removal.
3. A second independent reading of a sample of the 69 hand-classified rows, agreement reported as a
   number in the register, before the headline is repeated anywhere new.
4. One sentence in the README's measurement section saying the two order-dependent PostgreSQL
   probes move with the planner's statistics and where the run records it.

**Third, when the above is done.**

1. Phase 6, the refactors, when there is a contributor to benefit or a quiet week.
2. A renderer that bounds the rows it draws, so the three unpublished hand-classified questions
   get a page.
3. Publish the Spider 1.0 dev measurement that already exists: a README paragraph, a site
   benchmark built the way the three others were, and a register row. It is the cheapest fourth
   measurement the project will ever get, and it reaches a second maintainer community. The
   Spider 2.0-lite local subset is the one after it.
4. Phase 5 of the web UI plan, the drop zone, only when a user asks for it.

**Housekeeping, any time.** Delete the 18 GB L3 cache and the 9.2 GB work directory; delete the
pre-rewrite backup once the owner is satisfied with the rewritten history.

## Unresolved questions

- Whether the owner wants a target for the second half of the criterion by 2026-11-02 (a number of
  outside users or one outside issue), or is content with the acknowledgement half alone. The
  order above assumes the former.
- Who the second reader of the hand classification is. It can be a session on a different model
  with the rows and no labels, or a person; the register should say which.
- Whether the write-up goes out before or after phase 4. Before is faster; after means the first
  outside user meets fewer rough edges. The order above says before, because the demo path is
  clean and the rough edges are on paths a first user reaches only with their own files.
- Whether the IBM toolkit is a neighbour to cite, or a place to offer the probes as a
  contribution. Its survey note asks for what this tool emits; contributing there trades
  ownership for reach, and only the owner can weigh that.
