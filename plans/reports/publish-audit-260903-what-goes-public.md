# Publish audit: what goes public

Date 2026-09-03, at `master` `59c27da` (tag `v0.1.0`), read-only. Every row names the command or
path it rests on. Not repeated here, because the owner already checked them: all 530 author and
committer entries are the personal identity; the Mini-Dev run artifact holds no BIRD SQL or
question text; no cache is tracked. Tree: 169 tracked files, 96 Markdown files, 34,781 Markdown
lines. History: 265 commits on `master`, 271 over all refs.

## The table

Proposal values: **public** as is; **archive** into `docs/archive/` with one index line; **drop**
from the tree at HEAD (stays in history); **rewrite** means it must leave history too; **owner**
means the owner decides.

| Path or group | Kind | Proposal | Reason |
|---|---|---|---|
| `src/attestql/kernel/adapters/v29_vendored/grammar.py` (191 lines), `PROVENANCE.json` | vendored V2.9 validator, no licence header, bundle "packaged by the owner" per `PROVENANCE.json` | **owner** (default drop) | Only `kernel/adapters/v29.py` and four tests import it; the product path imports `kernel/types.py` and `kernel/ports.py` only. Owner-authored: public. Not: drop, history keeps it unless a third party wrote it |
| `src/attestql/kernel/adapters/v29.py`, `v29_widths.py`, `widths.py` (1,507 lines) | adapter over the vendored grammar, off the product path | drop with the grammar, else public | Dead weight for a stranger; four tests go with it |
| `src/attestql/kernel/ports.py`, `types.py` | product types (`ExecutionResult`, `ColumnType`) | public | Imported by `audit/` and `evidence/` |
| `tools/audit-sandbox/fixture.sql` | synthetic rows, own names and ids | public after two edits | Two `fastestlapspeed` literals, `257.320` and `91.610`, are BIRD's real extreme values (one hit each in the dump); replace them. Nothing else matches the dump (team names, drivers, molecules: 0 hits) |
| `tools/audit-sandbox/questions.json`, `predictions.json` | three BIRD questions, evidence and gold verbatim, attributed CC BY-SA 4.0 in the file | public, plus a `NOTICE` line | Attribution is inside the JSON only; a stranger reading LICENSE sees Apache-2.0 alone |
| `plans/reports/audit-260902-minidev-gold-only/` | run output: ids, verdicts, smells, digests | public | No SQL, no question text, no rows |
| Spike artifacts at `5c044a3`, sweep at `924817a` (history only) | BIRD gold SQL and small result rows inside evidence records; a scratchpad path in `index.json`; no licence note | owner | Fine under CC BY-SA with attribution; none is written there. Only option 3 below removes them |
| SpotIt+ | nothing | public | `git grep -i SpotIt` outside Markdown: 0 hits; `z3`, `VeriEQL`: only a cspell word |
| `docs/v29-review.md` (300 lines, Vietnamese, "verbatim third-party review", exempted from lint, cspell and typography) | text by a party other than the owner, received 2026-08-25 | **owner**: archive if the author agreed to publication, else rewrite | Only file whose right to redistribute is not the owner's to assume. A stranger does not need it |
| `docs/claude-v29-response.md`, `claude-v29-execution-report.md`, `claude-execution-report.md` (1,496 lines) | session-written responses to that review; 15 `/Users/<owner>` paths | drop | Owner's own sessions; they answer a document that leaves. ADR-0001 stands without them |
| `docs/codex-security-execution-boundary-acceptance.md`, `codex-wire-streaming-decision-evidence.md` (1,160 lines) | session-written WP2 spike records; 2 paths | archive | ADR-0006 links both; retarget the links or keep them under `docs/archive/` |
| `docs/slice1-scaffolding-prompt.md`, `slice1-tooling-prompt.md`, `slice1-m1-fixture-prompt.md` (734 lines) | the prompts milestones were built from; 4 paths | drop | Process, retired code, nothing a user needs |
| `docs/v29-report-corrected.md`, `verification-log.md`, `external-review-brief.md`, `slice1-product-decision-brief.md`, `slice1-implementation-plan.md`, `slice0-wp2-authorization-design.md`, `wp2-cross-reference.md`, `wp2-postgresql-authority-evidence.md`, two `wp2-milestone-verification*` (6,134 lines) | records of retired Slice 0/1 and WP2 | archive the four an ADR links (`verification-log`, `slice1-implementation-plan`, `slice0-wp2-authorization-design`, `wp2-milestone-verification-addendum`), drop the rest | `check_doc_links` covers README and `docs/`; every ADR link must resolve |
| `docs/developer-environment.md` | gates and why | public after a pass | Still says Slice 1 in places |
| `docs/adr/` (14 files, 1,870 lines) | decisions; 7 superseded, 6 accepted | public | The index gate needs the set whole; superseded ones say so |
| `plans/reports/discovery-260902-1856-*`, `mechanism-260902-2055-*`, `measurement-260902-2226-*` | the evidence chain README cites | public | README links the measurement report; ADR-0013 names the other two |
| `plans/reports/research-260902-1833-*`, `verification-260902-1839-*` | reorientation inputs | archive | Cited by the discovery report; internal tone |
| `plans/reports/brainstorm-260901-1055-glm-*`, `brainstorm-260901-1116-blind-session-*` | a GLM session's verdict and a verbatim paste from an outside AI session | drop | Second opinions on a premise ADR-0013 retired; the blind paste is not the owner's text |
| `plans/reports/2026-08-30-showcase-strategy.md` | recruiter and portfolio framing | drop | Internal, and it argues a goal the owner overruled on 2026-09-02 |
| `plans/orca-handover.md`, `plans/journals/` (10 files), 12 milestone plans, 30 `t*`, `measure-*`, `research-2608*` reports (about 21,000 lines) | coordination state, journals, implementation reports of retired code; 24 files carry `/Users/<owner>` paths, one an Orca run id | drop | History keeps them under options 1 and 2; nobody outside needs them |
| `src/attestql/kernel/adapters/v29_vendored/PROVENANCE.json` | `/Users/<owner>/Downloads/...` bundle path | drop with the grammar, else edit to the file name | Machine path in `src/` |
| `cspell.json` | three personal names as words; two of them no longer occur in any Markdown | public after removing the three | Names as dictionary entries |
| `orca.yaml` | Orca worktree hook, comments in Vietnamese | drop | Tool of one machine; a contributor without Orca gains nothing |
| `.vscode/` (3 files) | editor settings, no machine path | owner (default keep) | Harmless; `developer-environment.md` documents it |
| `.github/workflows/ci.yml` | never run; pinned image is a multi-arch index with `linux/amd64` | public | Runs on `ubuntu-latest`: Docker is present there, `just check` takes 14 s locally, so a cold CI run is a few minutes of installs plus that. Nothing in it points at this machine |
| `.gitignore`, `.python-version` (3.13), `uv.lock` (`uv lock --check` clean) | tree hygiene | public | `.gitignore` lacks `.claude/` beyond worktrees and `node_modules/`; harmless |
| `pyproject.toml` | version `0.0.0`, description still "Slice 1 sandbox", no `license`, `readme`, `classifiers`, `urls` | listed for B1 | Not changed here |
| `LICENSE` | absent | listed for B1 | README says Apache-2.0 |

## Evidence per group

1. **Redistribution.** The vendored grammar is the bundle `eda-v29-bundle.tar.gz`, whose outer hash
   `PROVENANCE.json` records as confirmed by the owner "as the bundle they packaged"; no file in the
   repository states its licence. Fixture literals against the dump: `grep -c -F` per value over
   `MINIDEV_postgresql/BIRD_dev.sql`, 12 values, 2 hits (the two speeds), 10 zero. Markdown quoting
   a gold `SELECT`: 0 files (the SQL found is the retired synthetic slice's). SpotIt+: 0 hits.
2. **Third-party text.** Headers read for 17 files; the dates and authors are in the table. Only
   `v29-review.md` and the blind-session paste (`brainstorm-260901-1116`) are text the owner did not
   write in a session of their own.
3. **Personal data.** `git grep -c /Users/<owner>`: 29 files, 66 lines (list above by group). Emails
   in tracked files: 0. Orca run id: 1 (`t12b` report). Session UUIDs: 2 files, both run ids the tool
   made. Host name: 0 hits. Company name: 0 hits.
4. **Secrets.** `gitleaks` and `trufflehog` are not installed. `git log -p --all`, added lines only,
   138,188 lines, grepped for `PGPASSWORD=`, `POSTGRES_PASSWORD=`, `PRIVATE KEY`, `password=`,
   `secret=`, `token=`, `api_key`, `sk-`, `ghp_`, the AWS access key prefix, and 60-plus-character base64 runs.
   Every password hit is a shell variable, an `openssl rand -hex 24` call, or a psql `:'variable'`;
   the base64 hits are `sha512` integrity fields of `ui/package-lock.json` on the `codex/ui-prototype`
   branch; `api_key` hits are the string `api_keys` in a schema list. WP2 and M5 sandboxes, by the
   history of their `run.sh`: three credentials generated per run by `openssl rand`, handed to psql
   over a `printf` pipe, no redirection of a credential to a file in any revision.
5. **Noise.** Keep set: README, the 14 ADRs, claims register, developer environment, discovery,
   mechanism, measurement: 20 files, 2,620 lines. Archive set (the six an ADR links plus the two
   reorientation reports): about 5,000 lines. Everything else leaves HEAD. Remaining Markdown after
   the proposal: about 7,700 lines, from 34,781.
6. **Git.** 19 local branches; only `codex/ui-prototype-2026-08-27` (30 files under `ui/`) and
   `feat/spike` are unmerged. Push `master`, `v0.1.0`, `slice1-final` and the coming `v0.1.1`; push
   no branch. Delete the 16 merged `wp2/*`, `wp3*` branches; keep the two unmerged ones local or
   drop them with their four worktrees (`attestql-ui-prototype`, `worktrees/attestql-a`, `-b`,
   `-spike`); nothing is cleaned in this pass. 21 commits carry `Co-Authored-By: Claude Opus 5`,
   all on `master`, 2026-08-26 to 2026-09-01, 19 of them `docs(security)` or `docs(plans)`; the
   list is `git log master --grep=Co-Authored-By`. Default branch is `master`; GitHub's default is
   `main`, so either rename before the first push or set the repository default to `master`.
7. **Tree at HEAD.** Largest tracked file is `docs/slice0-wp2-authorization-design.md` at 204 KB;
   nothing binary. `uv.lock` is in sync. `.python-version` says 3.13 while `requires-python` says
   3.11 and pyright checks 3.11.

## History: one recommendation

**Option 2: push the whole history, clean the tree at HEAD.** No secret and no company identity is in
the history (group 4 and the owner's check); what the history carries beyond that is prose, paths
of the form `/Users/<owner>/...`, 21 AI trailers, and the vendored grammar, none of which a rewrite is
worth. The project's own rule is that every claim has an artifact, and the artifacts for A5, A7 and
A8 of the claims register live only at `5c044a3` and `924817a`; option 2 keeps them checkable by a
stranger with `git show`.

- **Option 1** (push as is): same pointers, but 34,781 lines of process prose and 29 files of machine
  paths land on the first page a stranger opens. Rejected on noise alone.
- **Option 3** (new history from v0.1.1, private archive): the cleanest public log, and the only
  option that removes `v29-review.md`, the blind paste and the trailers from what is published.
  Cost: `5c044a3`, `924817a` and `slice1-final` stop resolving for anyone but the owner, so A5, A7
  and A8 fall to "artifact not public", and the measurement report's evidence with them. Partial
  rewrites (`filter-repo` on one file) cost the same, because every SHA after 2026-08-25 changes.

Pointer changes under each option:

| Pointer | Options 1 and 2 | Option 3 |
|---|---|---|
| README line 112: "history at commit `5c044a3`" | unchanged; becomes a GitHub commit link after push | rewrite to name the private archive, and say the artifact is not public |
| Register A5, A7 (`5c044a3`), A8 (`924817a`), section 4 (`slice1-final`) | unchanged; `slice1-final` must be pushed with `master` | verified-by column changes to "artifact not public"; or re-commit the three counterexamples and the sweep `rows.json` under `plans/reports/` with a BIRD attribution, and point there |
| ADR-0013 lines 27 and 103 (`5c044a3`, `slice1-final`) | unchanged | add one sentence: the commits named here are in the private archive |
| ADR-0006 links to `codex-*` and `wp2-*` documents | retarget to `docs/archive/` or to a commit | same, or drop the links |

**Owner decision, 2026-09-03 10:10:** reset the history to one commit (option 3 in its simplest
form). Consequences this pass records, so that B points once:

- The current repository, history and all, becomes the private archive; the public repository
  starts from one commit made after B on the cleaned tree of this table.
- `5c044a3`, `924817a` and `slice1-final` resolve only in the archive. The three counterexamples
  (`counterexample.json`, `evidence-gold.json`, `evidence-second.json` of q1029, q879, q207, about
  700 lines together) and the sweep's `counts.json`, `fired.json`, `rows.json` are re-committed under
  `plans/reports/` beside the Mini-Dev run artifact, with a BIRD attribution file, and A5, A7, A8
  point there; README line 112 and ADR-0013 lines 27 and 103 say "in this repository's archive
  history" without a SHA. The scratchpad path inside the spike's `index.json` is not carried over.
- The 21 trailers, `v29-review.md`, the blind paste and every `/Users/<owner>` path leave with the
  history; questions 1 and 3 below are answered by the reset.
- B7 (replace `pglast`) decides the vendored grammar: `grammar.py` imports `pglast` itself, so
  either the V2.9 adapter tree and its four tests leave the public tree, or `pglast` stays as a
  dependency and the GPL paragraph stays with it. The clean cut is to drop the adapter tree.
- This report and the other process records stay in the archive, not in the public tree.

## Unresolved, for the owner

1. Who wrote `docs/v29-review.md`, and did they agree to publication? Decides archive versus rewrite.
2. Is the V2.9 bundle the owner's own work, so that `grammar.py` may carry Apache-2.0? Decides keep
   versus drop; drop needs no rewrite.
3. Keep or drop the 21 `Co-Authored-By` trailers: only option 3 removes them.
4. `master` or `main` for the public default branch.
5. `.vscode/`: keep as documented editor setup, or drop with `orca.yaml`.
