# Red review of the four GLM lanes, 2026-09-07 18:54

<!-- cspell:ignore minidev sqlglot satscores frpm CDSCode birdenv psycopg pymysql typeof DQS tvshow Mgt noqa CodeS repocheck docstrings RUCKB misparse dispatchable -->

Independent reader on Fable, read-only, 34 tool calls, 12 minutes. Every claim below was checked
with a command against the repository, the inputs directory, the tool at 0.2.2, or a read-only
`gh api` call. Scratch runs went to the reviewer's scratchpad only. The amendments were applied to
the briefs on 2026-09-07 before dispatch; S2 and S5 by the coordinator on the inputs directory.

## Shared findings (L1, L2, L3, and where noted L4)

- **S1 SHOULD-FIX (L1, L2, L3): the `MEASURE_WORK` layout the briefs prescribe does not match the scripts they tell the worker to reuse.** `run_tool.sh`, `rerun_timeouts.sh`, `run_predictions.sh` read `data/dev/dev_databases/$db/$db.sqlite` and `data/dev/dev_20240627/dev.json`; `measure.py`, `check_inputs.py` and `bird_ex_official.py` read `data/hf/dev_20251106-00000-of-00001.json`. The inputs tree holds `dev/dev_20240627/dev_databases/` and `dev_20251106.json`. One `data/dev` symlink leaves `data/dev/dev_databases` and `data/hf/...` missing, so a copied `run_tool.sh` fails on `--dsn`. Amend to the exact links: `data/dev/dev_20240627` to `inputs/dev/dev_20240627`, `data/dev/dev_databases` to `inputs/dev/dev_20240627/dev_databases`, `data/hf/dev_20251106-00000-of-00001.json` to `inputs/dev_20251106.json`. L2 also needs `data/zip/minidev` to `inputs/minidev/minidev` and `data/hf/mini_dev_sqlite-00000-of-00001.json` to `inputs/mini_dev_sqlite_hf.json` (the minidev scripts read `data/zip/...`; the brief's `data/minidev` is read by nothing), and `MINIDEV_DATABASES=...` for `check_inputs.py`, whose default is the old `minidev-sqlite/` work directory.
- **S2 SHOULD-FIX (safety, L2, L3): BIRD's evaluators open the database read-write.** Both `bird_ex_official.py` docstrings: upstream's path is `sqlite3.connect(db_path)` and it executes whatever the prediction says; through the symlinks above that file is the shared inputs directory the other lane reads. The tool itself is safe (`src/attestql/audit/sqlite.py:25`, `mode=ro` plus `PRAGMA query_only`). Amend: coordinator runs `chmod -R a-w ~/.cache/attestql-measure/inputs` before dispatch (SQLite opens an unwritable file read-only; `mode=ro` is unaffected), and never re-runs `unpack.sh` while a lane runs (it removes `dev` and `minidev` first).
- **S3 SHOULD-FIX (all): three timeouts survive a serial rerun and the briefs' "every timeout rerun alone" has no stop.** `measurement.json` errors: q518 (`card_games`, in the 963), q701 (`codebase_community`, in the 172), and the 2025-11-06 rewrite of q1131 (`european_football_2`, in the 399; 30 s on both copies). Amend: "a timeout that survives one serial rerun is final; expect these three". Consequences per lane below.
- **S4 SHOULD-FIX (all): gate items the briefs omit.** `.pre-commit-config.yaml` `check-typography` refuses an em dash, en dash or numero sign in any `.md` or `.py`, and `just check` runs `repocheck` (justfile:60); `check_doc_links.py` needs every link in the report to resolve; ruff `S` rules fire on SQL built from strings (the earlier scripts carry `# noqa: S608`). GLM output uses em dashes freely. One line in each brief.
- **S5 SHOULD-FIX (all): `SHA256SUMS` holds four digests, the briefs cite nine "beside them".** Verified the other five match the quoted prefixes: `dev.json` 630272f2, `mini_dev_sqlite.json` 4ba5fa8d, `spider_data.zip` 00636695, `dev.sql.before` 6d3ac4f5, `dev.sql.after` 36e8c72e. Append them.
- **S6 NIT (all):** a `reproduce.sh` copied from the earlier pattern re-downloads `dev.zip` (346 MB, stalling OSS) and `minidev.zip` (800 MB) on every "clean MEASURE_WORK" run, the acceptance run included; let it take `ATTESTQL_INPUTS` (default the shared directory) and download only what is absent. Say "three processes in total per lane", not per step.
- **S7 NIT (L1, L3):** the tool's mechanism names are `multiplicity`, `type`, `order`, `truncation`, `other` (`summary.json` `credited_but_not_equal.by_mechanism`, `counterexample.json` `mechanism.class`), not "storage class" and "row order". Per-question `bird_ex.value`, `test_suite_ex.value`, `mechanism.class` and `mechanism.multiset_equal` live in `q<id>/counterexample.json`, written only for NOT_EQUAL or a fired probe; an EQUAL question has no directory and both readings are 1 by construction. Name this so `verdicts.json` is derivable.

## L1 (`l1-bird-rewrites.md`)

- Verified: split 399/172/963 and 31 fires on the 399 (`measurement.json` `recall_on_the_old_copy`); `gold-only-old.json` is `{"<id>": {db, rule, smells}}`; `sqlglot` 30.18.0 is a pinned dependency and `sqlglot.diff` exists (`from sqlglot.diff import diff`; the attribute `sqlglot.diff` is the function). Prediction keying by question id with `--ids` per database and extra keys is the pattern the minidev `hf` lane already ran.
- SHOULD-FIX: step 2 "the 172 ... every one must be EQUAL" is false by design: q701 is in the 172 and its gold times out (192 s alone), so it is an ERROR line. Expect 171 EQUAL and q701 ERROR; and in the 399, q1131's rewrite is a prediction-side timeout that is final.
- SHOULD-FIX: "`--ids` that database's ids" is ambiguous; say the 399 ids (and, for the check, the 172) of that database. Running all of the database's ids audits the rest gold-only for nothing.
- SHOULD-FIX: "same answer under the multiset rule": under R-ORD the verdict is order-sensitive. Define it as verdict EQUAL or `mechanism.multiset_equal` true; `bird_ex.value` for the set reading. Also state that the replay rule is the old gold's, so a rewrite that adds or drops ORDER BY is judged under the old rule.
- NIT: prediction mode reruns the gold-only probes on the 399; assert the fires equal `gold-only-old.json` (seeded shuffle) and report any drift. Step 5's cap is up to 13 classes x 8 = 104 readings; say so.
- Verdict: **AMEND-THEN-DISPATCH**.

## L2 (`l2-two-database-copies.md`)

- Verified: `inputs.json` names the six identical and five differing files; dev copy: 211 of 2,269 `satscores.cds` are 13 characters and 2,058 join `schools`; minidev copy: all 14 characters, 2,269 join. `Player.height` is REAL (182.88) in dev and INTEGER (182) in minidev on all 11,060 rows. Golds on the five databases: 700 (dev.json), 700 (2025-11-06), 237 (HF Mini-Dev), so step 2 is about 3,300 executions, cheap. The CDE URL answers 303 (reachable). `official/hf/*.json` in `minidev-sqlite-260907/` already hold 500 scored rows per file for the shipped pairing.
- SHOULD-FIX: step 6 "golds whose SQL names `Player.height`": zero golds carry that literal; 13 `european_football_2` golds name `height` through an alias. Match `\bheight\b` on that database's golds or the answer is a false zero.
- SHOULD-FIX: step 2's multiset reading through Python `==` makes `182 == 182.0 == True`; the tool's typed reading would not, and the heights differ in storage class on every row. State the equality rule in `replay_pairs.py` and count typed differences (`typeof`) apart from value differences.
- SHOULD-FIX: step 4's `birdenv` needs `psycopg2-binary pymysql func_timeout` (upstream `evaluation_utils.py` imports the first two at the top; minidev `reproduce.sh`), not `func_timeout` alone; and `bird_ex_official.py` hardcodes `DATABASES = .../data/zip/minidev/MINIDEV/dev_databases`, so the dev-copy scoring needs a copy of the script with a database-directory argument. Say so, and say "500 positions, 498 distinct ids".
- SHOULD-FIX: step 3 reuses dev-copy fires from tree `6a43c01` and runs the minidev copy at the worktree's 0.2.2; rerun the dev copy too (five runs, minutes) so a probe delta is the copy and not the version.
- NIT: step 5's frpm join differs by 162 (1,620 vs 1,782), not 211, because frpm has fewer rows; say it so the worker does not treat it as a failed check. Step 2 with the 2025-11-06 golds hits q1131's timeout on both copies (S3).
- Verdict: **AMEND-THEN-DISPATCH**.

## L3 (`l3-more-dev-predictions.md`)

- Verified via `gh api`: `RUCKBReasoning/codes` is Apache-2.0 and `results/` holds exactly the eight `predict_dev-codes-*-bird*.json`; the 1b file has 1,534 string entries keyed "0".."1533", each with the `\t----- bird -----\t<db_id>` suffix, 0 non-strings, and the suffix db_id equals `dev_20240627/dev.json`'s `db_id` at all 1,534 positions. `gh` is logged in as the owner's personal account. Dev `bird_ex_official.py` needs only `func_timeout`.
- SHOULD-FIX: positional pairing is only valid when the file answers this dev.json order. Make the suffix check above a mandatory assertion per hunted file; a file without suffixes needs another witness (the tool's `ERROR` rate by database is one) or is refused. Without this a shifted file yields a wrong number silently.
- NIT: GitHub code search is 10 requests per minute. Runtime is hours, not days: the whole gold-only copy summed to about 300 s of statement time (`measurement.json` `elapsed_seconds`). Per-question readings: S7.
- NIT for L4, found here: `results/pred_sqls-codes-{1b,3b,7b,15b}-spider.txt` are 1,034-line Spider dev predictions (first lines match dev.json order).
- Verdict: **AMEND-THEN-DISPATCH** (S1, S2, S3, S4 plus the pairing assertion).

## L4 (`l4-spider-dev.md`)

- Verified: 1,034 entries over 20 databases, every `database/<db>/<db>.sqlite` present in the zip, `dev_gold.sql` equals dev.json `query` and `db_id` at every position (whitespace-normalised), 49 differing lines (28 `SQL:`, 21 `Question`), five blocks change both lines (so the text-only set is 16), `gh api repos/taoyds/spider/contents/evaluation_examples/dev.sql?ref=<sha>` with `Accept: application/vnd.github.raw+json` re-fetches both files at the stated digests, commit 25fcd85d has parent e0b7bc91. `Question N` is dev.json index N-1 (Q17 equals index 16 in text and SQL).
- **BLOCKING (method premise): the tool does not refuse Spider golds, so step 3 as written measures nothing.** Smoke run at 0.2.2 in the reviewer's scratch area: `concert_singer` 45 golds including five INTERSECT/EXCEPT, 0 errors, 2 `arbitrary-cut`; `world_1` 120 golds of which 86 double-quoted, 0 errors, 6 `arbitrary-cut`, 6 `not-a-function-of-the-data`. sqlglot reads `"Republic"` as an identifier without error (`research-260904-sqlite-before-backend.md:32-35`) and the linked SQLite 3.53.4 runs it as a literal (DQS on: `where a = "France"` matched). So "refusals by reason" is about zero and "if double-quoted literals dominate" never triggers, while the real question, whether the misparse moves a probe, the replay rule, or the shuffle's table set, goes unmeasured. Amend step 3: count golds carrying a double-quoted token that is no column or table of that database (213 of 1,034 carry a double quote; `world_1` 86/120, `flight_2` 56/80, `tvshow` 26/62, `cre_Doc_Template_Mgt` 20/84); run the transformed pass on those unconditionally; report verdict, rule and smell deltas between the passes as the finding; keep the refusal count as well.
- SHOULD-FIX: step 7 should name CodeS `pred_sqls-codes-{1b,3b,7b,15b}-spider.txt` (Apache-2.0, 1,034 lines, one SQL per line, dev order; convert to `{"<index>": sql}`) first; it makes the hour near-certain to succeed.
- NIT: the "~4 %" sentence is the Spider site's news line, not the commit message ("corrected annotated errors/mismatches", 2020-06-08T08:02Z); cite it so. Use index alignment as primary and text as the check. Pass (b) needs only the 28 corrected ids. Spider runs are trivial (world_1: 0.17 s of statements).
- Verdict: **AMEND-THEN-DISPATCH** (one paragraph fixes the blocking item).

## `plan.md`

- Consistent: the model report is 149 lines; `just docs` covers `plans/**/*.md`; `orca worktree set --worktree active --comment` is valid syntax. Working tree is clean at review time. Add S2 (chmod), S5 (SHA256SUMS) and the note that the Claude Bash hook on "venv" does not touch codex workers.

Status: DONE_WITH_CONCERNS. All four briefs are dispatchable after amendments; none needs a
redesign, but L4's step 3 rests on refusals that do not happen (verified by running the tool on
165 Spider golds with zero errors), and L1 to L3 share a work-directory layout that no reused
script reads, a read-write path from BIRD's evaluators into the shared inputs, and three timeouts
the "rerun alone" loop cannot resolve.
