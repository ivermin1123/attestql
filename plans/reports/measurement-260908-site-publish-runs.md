# Measurement: the five published audits, and what the site shows of them

Date 2026-09-08, tree at the branch `ivermin1123/web-ui`. The tool is `attestql` installed from
this branch, whose audit and evidence code is the code tag `v0.2.2` carries: `git diff --stat
v0.2.2 HEAD -- src/attestql/audit src/attestql/evidence` is the `report` subcommand's two public
accessors and the evidence loader, and no behaviour of the audit. The runs were made by
`tools/site-select/audits.sh` in `/tmp/attestql-runs`, outside the repository; the selection into
`tools/site/data/` by `tools/site-select/select.py`; the release assets by
`tools/site-select/release.sh`.

Every count below is read out of a `summary.json` the audit wrote, through
`tools/site/data/selection.json`, and compared with the measurement report that first made it.

## The runs

121 runs. On PostgreSQL one invocation answers a whole question set, so a prediction file is a
run; on SQLite `--dsn` is one database file, so a question set naming eleven databases is eleven
runs and a prediction file is a group of them.

| benchmark | run or group | runs | audited | compared | ERROR | GOLD-ONLY | probe fires | credited and NOT_EQUAL | timed out | published | here | the report | difference |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bird-dev-sqlite` | `dev-20251106` | 11 | 1,534 | 0 | 3 | 1,531 | 47 |  | 3 | 31 | probe fires 47 | 47 | 0 |
| `minidev-pg` | `gpt-35-turbo` | 1 | 498 | 313 | 185 | 0 | 27 | 23 | 0 | 26 | compared 313 | 313 | 0 |
| `minidev-pg` | `gpt-35-turbo-instruct` | 1 | 498 | 309 | 189 | 0 | 31 | 18 | 0 | 23 | compared 309 | 309 | 0 |
| `minidev-pg` | `gpt-4` | 1 | 498 | 376 | 122 | 0 | 32 | 17 | 0 | 26 | compared 376 | 376 | 0 |
| `minidev-pg` | `gpt-4-32k` | 1 | 498 | 364 | 134 | 0 | 32 | 23 | 0 | 31 | compared 364 | 364 | 0 |
| `minidev-pg` | `gpt-4-turbo` | 1 | 498 | 370 | 128 | 0 | 30 | 27 | 0 | 33 | compared 370 | 370 | 0 |
| `minidev-pg` | `meta-llama-3-70b-instruct-2` | 1 | 498 | 340 | 158 | 0 | 28 | 19 | 0 | 23 | compared 340 | 340 | 0 |
| `minidev-pg` | `meta-llama-3-8b-instruct-2` | 1 | 498 | 240 | 258 | 0 | 15 | 12 | 1 | 15 | compared 240 | 240 | 0 |
| `minidev-pg` | `mistralai-mixtral-8x7b-instru-4` | 1 | 498 | 170 | 328 | 0 | 8 | 14 | 0 | 16 | compared 170 | 170 | 0 |
| `minidev-pg` | `phi-3-medium-128k-instruct-1` | 1 | 498 | 279 | 219 | 0 | 27 | 11 | 0 | 15 | compared 279 | 279 | 0 |
| `minidev-pg-gold-only` | `hf` | 1 | 500 | 0 | 0 | 500 | 38 |  | 0 | 24 | probe fires 38 | 39 | -1 |
| `minidev-pg-gold-only` | `zip` | 1 | 498 | 0 | 0 | 498 | 39 |  | 0 | 25 | probe fires 39 | 39 | 0 |
| `minidev-sqlite` | `gpt-35-turbo` | 11 | 498 | 409 | 89 | 0 | 24 | 27 | 4 | 7 | compared 409 | 410 | -1 |
| `minidev-sqlite` | `gpt-35-turbo-instruct` | 11 | 498 | 372 | 126 | 0 | 23 | 26 | 2 | 8 | compared 372 | 372 | 0 |
| `minidev-sqlite` | `gpt-4` | 11 | 498 | 472 | 26 | 0 | 26 | 32 | 2 | 7 | compared 472 | 472 | 0 |
| `minidev-sqlite` | `gpt-4-32k` | 11 | 498 | 460 | 38 | 0 | 25 | 32 | 2 | 8 | compared 460 | 460 | 0 |
| `minidev-sqlite` | `gpt-4-turbo` | 11 | 498 | 422 | 76 | 0 | 24 | 29 | 2 | 8 | compared 422 | 422 | 0 |
| `minidev-sqlite` | `meta-llama-3-70b-instruct-2` | 11 | 498 | 440 | 58 | 0 | 23 | 29 | 2 | 7 | compared 440 | 440 | 0 |
| `minidev-sqlite` | `meta-llama-3-8b-instruct-2` | 11 | 498 | 311 | 187 | 0 | 16 | 21 | 3 | 5 | compared 311 | 311 | 0 |
| `minidev-sqlite` | `mistralai-mixtral-8x7b-instru-4` | 11 | 498 | 248 | 250 | 0 | 14 | 16 | 1 | 5 | compared 248 | 248 | 0 |
| `minidev-sqlite` | `phi-3-medium-128k-instruct-1` | 11 | 498 | 366 | 132 | 0 | 20 | 25 | 2 | 5 | compared 366 | 366 | 0 |

The two reports the last three columns are read against: for the prediction runs, the "Per file"
table of `measurement-260904-0046-prediction-mode-on-real-predictions.md` and of
`measurement-260907-1106-minidev-sqlite.md`, whose `Compared` column is the number here; for the
gold-only runs, `measurement-260902-2226-gold-only-probes-mini-dev.md` through the two committed
summaries in `audit-260902-minidev-gold-only/` and `audit-260903-minidev-hf-gold-only/`; for BIRD
dev, the per-probe table of `measurement-260907-1435-bird-dev-sqlite.md`.

**Nineteen of the twenty-one rows are zero.** The two that are not:

- `minidev-pg-gold-only/hf`, 38 fires against 39. The committed summary of 2026-09-03 states
  `float-aggregate-order` 8 and `not-a-function-of-the-data` 14; this run states 7 and 14, and the
  zip run states 7 against the committed 8 with `not-a-function-of-the-data` 14 against 13, so the
  zip's total is unchanged at 39 and the Hugging Face copy's falls by one. `float-aggregate-order`
  is not a probe of its own: it is what the shuffle probe's fire is called when every differing
  cell is a float agreeing to six significant digits. The golds it fires on here are q955, q1340,
  q1361, q1380, q1410, q1529 and q1531, where the 2026-09-02 sweep named q1473, q1476, q1482,
  q1529, q1531, q1380, q1390, q1410 and q955. What moved is which sums differ at all: the note of
  2026-09-04 evening in the prediction-mode report records that every statement now runs without
  parallel workers, which is what makes a float sum reproducible, and `cf0b033` is where the
  planner statistics the shuffle's plan is chosen from began to be recorded. The count of golds
  the shuffle probe fires on is 21 in both runs and in both committed summaries.
- `minidev-sqlite/gpt-35-turbo`, 409 compared against 410. One prediction, q145 of `financial`,
  reached the 30 second bound here and did not in the measurement of 2026-09-07; it survived the
  serial rerun. Its statement is one the report does not list among its six timeouts, so this is
  one more, not one moved.

**The totals.** `minidev-pg`: 2,761 compared, 1,721 errors and **164** credited by BIRD's own check
and called NOT_EQUAL here, over 4,482 slots. 164 is the number the README states and the number
the rerun at `cf0b033` measured; the first measurement at `41621c0` said 170, before the tool's
BIRD reading loaded float columns as psycopg2 does. The errors are 1,721 rather than that rerun's
1,722 because these runs are at `--statement-timeout 120`, so q707 of `meta-llama-3-70b` is
compared; one other prediction, q694 of `meta-llama-3-8b`, reached the 120 second bound instead and
survived its serial rerun. `minidev-sqlite`: **237** credited and NOT_EQUAL, which is exactly the
number that measurement states for the zip copy. `bird-dev-sqlite`: 1,531 golds audited of 1,534,
47 probe fires split `arbitrary-cut` 24, `not-a-function-of-the-data` 20,
`ordering-over-numeric-text` 3, `float-aggregate-order` 0, over **35** golds, every number the same
as the report's.

## The copy and the timeout each benchmark was made with

| benchmark | question file | keying | statement bound | data |
| --- | --- | --- | --- | --- |
| `bird-dev-sqlite` | BIRD's 2025-11-06 pass, `ffd80183…` | gold-only | 30 s, the default | `dev.zip`'s own eleven databases |
| `minidev-sqlite` | the GitHub zip's `mini_dev_sqlite.json`, `4ba5fa8d…` | `position` | 30 s, the default | `minidev.zip`'s eleven databases |
| `minidev-pg-gold-only` | the zip's `mini_dev_postgresql.json` (`d2731292…`) and the Hugging Face `mini_dev_pg-00000-of-00001.json` (`7fa740ef…`) | gold-only | 30 s, what the two committed summaries record | the Mini-Dev dump |
| `minidev-pg` | the zip's `mini_dev_postgresql.json`, `d2731292…` | `position` | 120 s, so q707 is compared | the Mini-Dev dump |

`position` keying is BIRD's own pairing, the one its evaluator credits with, so it needs no derived
file. The 2025-11-06 copy is the one
`plans/reports/bird-dev-sqlite-260907/classification.json` reads.

Every input was verified against the digest the report scripts state before any run. The dump the
two PostgreSQL benchmarks were loaded from is `minidev.zip`'s member
`minidev/MINIDEV_postgresql/BIRD_dev.sql`, sha256
`31b1da211849d24a57c9af7636da46a5b82fc8a3ca1542bb3ebd8775e9a31cec`, which the earlier PostgreSQL
measurements did not record because they passed no `--data-file`. The eighteen prediction files
were downloaded again at `b3d4bcbb` and verified against
`plans/reports/minidev-sqlite-260907/SHA256SUMS.predictions` and the digests in
`plans/reports/prediction-mode-260904-real-predictions/reproduce.sh`. The digest of every file a
run read is in that run's own `summary.json`, measured by the run.

## The reruns

A statement's budget is wall clock, so a starved process reports a bound its statement did not
earn. The SQLite runs were three at a time and the PostgreSQL runs two lanes, each lane with its
own scratch schema; then every run whose `summary.json` names a question the bound stopped was run
again alone, and the rerun's directory is what is published.

**24 runs were made again**: 23 on SQLite and one on PostgreSQL. In 23 of the 24 the bound stopped
the same questions alone; in one, `minidev-sqlite/mistralai-mixtral-8x7b-instru-4/financial`, where
q116 was stopped under load, nothing reached the bound alone, and it is the serial run that is
published. The crowded answer is kept beside each as `<name>.under-load` in the work directory and
is in no release asset. One of the 23 has no such copy: the PostgreSQL stage's own rerun pass began
on the SQLite runs before it was stopped and moved `bird-dev-sqlite/dev-20251106/card_games` aside
a second time, overwriting the first copy; what is published there is a serial rerun and the
under-load answer of that one run is gone. The rerun pass now takes a path prefix, so the two
stages never walk each other's runs.

`float-aggregate-order` and the two SQLite golds q518 and q701 reach the 30 second bound in every
run that reads them, alone as under load, which is what the two SQLite measurements state.

## The selection, and what it left out

Four rules, from the phase: every question BIRD's own check credited and this comparison called
NOT_EQUAL, in each prediction run; every gold a probe fired on, in every run; every question a
maintainer read by hand; and the unjust zeros and unjust ones the prediction-mode aggregate names
for the zip copy. 825 question directories satisfy one of them.

The dry run, before anything was copied:

| benchmark | runs | questions | files | bytes in `data/` | predicted in the built site |
| --- | ---: | ---: | ---: | ---: | ---: |
| `bird-dev-sqlite` | 11 | 31 | 62 | 416,364 | 1,174,168 |
| `minidev-pg` | 9 | 208 | 832 | 13,120,237 | 30,080,404 |
| `minidev-pg-gold-only` | 2 | 49 | 98 | 610,061 | 1,752,609 |
| `minidev-sqlite` | 99 | 60 | 240 | 1,212,820 | 3,147,535 |
| all | 121 | 348 | 1,232 | 15,359,482 | 41,894,716 |

**348 questions published, 477 left out**, 176,928,667 bytes of them. The build's three budgets are
8,000 files, 40 MiB and 2 MiB a page; the answer to a site over one of them is a narrower selection
and never a larger budget, so whole questions were left out, largest first, and nothing inside a
record was trimmed. Every question left out is whole in that run's release asset, and
`tools/site/data/left-out.json` names every one with its size. The twelve largest:

| run or group | question | bytes in `data/` | why |
| --- | --- | ---: | --- |
| `minidev-sqlite/meta-llama-3-8b-instruct-2/european_football_2` | q1144 | 55,536,413 | over-page, probe |
| `minidev-sqlite/gpt-35-turbo-instruct/card_games` | q346 | 10,499,385 | credited, over-page |
| `minidev-sqlite/phi-3-medium-128k-instruct-1/card_games` | q346 | 10,499,315 | credited, over-page |
| `minidev-pg/gpt-35-turbo` | q207 | 8,848,846 | credited, hand, over-page, unjust |
| `bird-dev-sqlite/dev-20251106/california_schools` | q11 | 4,572,612 | over-page, probe |
| `minidev-sqlite/mistralai-mixtral-8x7b-instru-4/european_football_2` | q1124 | 4,535,243 | credited, over-page |
| `minidev-sqlite/phi-3-medium-128k-instruct-1/european_football_2` | q1124 | 4,535,185 | credited, over-page |
| `minidev-sqlite/meta-llama-3-70b-instruct-2/european_football_2` | q1124 | 4,535,163 | credited, over-page |
| `minidev-sqlite/gpt-4-32k/european_football_2` | q1124 | 4,535,153 | credited, over-page |
| `minidev-sqlite/meta-llama-3-8b-instruct-2/european_football_2` | q1124 | 4,535,153 | credited, over-page |
| `minidev-sqlite/gpt-35-turbo/european_football_2` | q1124 | 4,535,147 | credited, over-page |
| `minidev-sqlite/gpt-4/european_football_2` | q1124 | 4,535,137 | credited, over-page |

**Three of the 477 are questions a maintainer read by hand**, which the phase's rule protects from
the budget. They are left out for the other reason: their page alone would be over the 2 MiB a page
is allowed, so they cannot be published at any total budget.

| run | question | bytes in `data/` | page would be | why |
| --- | --- | ---: | ---: | --- |
| `minidev-pg/gpt-35-turbo` | q207 | 8,848,846 | 10,185,172 | credited, hand, over-page, unjust |
| `minidev-pg/gpt-35-turbo-instruct` | q1124 | 4,533,888 | 5,222,971 | credited, hand, over-page |
| `minidev-pg/gpt-4-turbo` | q1124 | 4,533,755 | 5,222,818 | credited, hand, over-page |

q207 of `gpt-35-turbo` is also an unjust one. The same question is published from
`minidev-pg/gpt-4` and `minidev-pg/gpt-4-turbo`, whose records are smaller, so the question itself
is on the site; what is missing is those two models' own rows for it, and both are in
`minidev-pg-gpt-35-turbo.tar.gz` and `minidev-pg-gpt-35-turbo-instruct.tar.gz`.

The three headline numbers `tools/site/data/aggregate.json` states, each the join of a
classification to the nine runs' own credited-and-NOT_EQUAL sets, with what this site publishes of
it beside it: `credited_but_not_equal` **164**, of which 161 have a page; `classified_by_hand`
**69**, of which 66; and `bird_dev_classified_by_hand` **23**, of which 23. The three without a
page are the three questions above, whose records the page budget could not fit. The number is the
join, not the published part of it: whether a question has a page is a fact about this site's file
budget and not about the benchmark, and a site whose budget changed the number it reports would be
reporting the budget. The landing shows 69 with one line under it saying that 66 have a page here
and the other 3 are whole in the release assets, and the proportion bar is drawn from the join.
23 is every `wrong` row of the BIRD dev classification.

## The built site

`uv run python tools/site/build.py`: **2,218 files, 40,624,541 bytes, 3.5 seconds**, against 8,000
files and 41,943,040 bytes. The largest page is
`runs/minidev-pg/gpt-35-turbo-instruct/q1088/index.html` at 1,806,501 bytes, against 2,097,152.
673 pages. Beyond the published questions the site cost 612 files and 5,179,098 bytes, against the
1,048 files and 5,740,000 bytes `select.py` reserved for them.

`grep -rl /Users/ tools/site/data build/site` prints nothing: every audit was run from inside the
work directory with relative paths, and the SQLite backend's recorded identity is
`/private/tmp/attestql-runs/data/...`, which names no user, no repository and no build location.

Chromium 1228 through Playwright, eight pages at 360, 768 and 1280 in both themes, 48 renders:
none scrolls sideways, the type is the four tokens `{13, 16, 20, 28}px`, the spacing is the
eight-step scale, and no page carries the stand-in banner. The measurements and twelve screenshots
are in `cook-260908-1245-web-ui-phase-4-runs/`. One layout defect was found and fixed there: the
landing's three headline numbers are the first facts on this site whose name is a sentence, and
under `grid-template-columns: max-content` the first name was 409px wide at a 360px viewport.

## The release assets

One archive per run and per group on the release of `v0.2.2`, each holding every question directory
that run or group wrote with its `stdout.txt` and `stderr.txt`; 142,047,367 bytes in 21 archives,
the largest 14,509,006. Built with `COPYFILE_DISABLE=1 tar` from the work directory, so no `._*`
member and no absolute path is inside one; the `.under-load` copies are excluded. `SHA256SUMS` is
uploaded beside them. <https://github.com/ivermin1123/attestql/releases/tag/v0.2.2>

| asset | bytes | sha256 |
| --- | ---: | --- |
| `bird-dev-sqlite-dev-20251106.tar.gz` | 375,933 | `4f83fa6296273278933f9f1b7d726f813ac35f73a03e4aa15dce6ec7db0700bc` |
| `minidev-pg-gold-only-hf.tar.gz` | 59,916 | `a15aa56fb0c278816bc42e7ef70e7f206295cfa1b7f2608a7cdbe12edd38cc2e` |
| `minidev-pg-gold-only-zip.tar.gz` | 60,837 | `7c1439ae6b1d562694c76c47aa84cbd5edd26d34d83df538c417621114a8120a` |
| `minidev-pg-gpt-35-turbo-instruct.tar.gz` | 12,218,848 | `c5e459dd3bfda9c6e56ea755afb3c894c63a7d26c215b374d93a9e44b9ec3adf` |
| `minidev-pg-gpt-35-turbo.tar.gz` | 1,680,811 | `415c9f9dbf7b77ee76b4669bf38edeecf6097ed16c0a4bac2b73b3cff192fdff` |
| `minidev-pg-gpt-4-32k.tar.gz` | 1,542,041 | `d93c11c8118a10e0e848e1c279a6605e5c5ee9617b9c4c6cf18c6b1fdc566fb1` |
| `minidev-pg-gpt-4-turbo.tar.gz` | 12,340,022 | `645e9137a81fad4d02664b8042944910c7df0e57830cc344f3ae21b5f1c16533` |
| `minidev-pg-gpt-4.tar.gz` | 12,052,081 | `f81324fb9a1a6c538a2f76035917be0ea93c2f4033a4af191adb91d7786995b9` |
| `minidev-pg-meta-llama-3-70b-instruct-2.tar.gz` | 1,589,058 | `f554f953678de01a49c8d5e58a83c10788850269a41e96686c676d83c2abbfc7` |
| `minidev-pg-meta-llama-3-8b-instruct-2.tar.gz` | 11,791,203 | `0d6e5bbec913c07edab6f3b02f2fee9433b1d091d0ccd965ff5bf00c5706e751` |
| `minidev-pg-mistralai-mixtral-8x7b-instru-4.tar.gz` | 3,707,260 | `af5a6786203547aa70c6524e464e24d94c366a698a76da669b616c5107952ce1` |
| `minidev-pg-phi-3-medium-128k-instruct-1.tar.gz` | 1,439,407 | `597b69fd187cd4405c908c8568b65da5ccea0f1affb0d0ec53d501c662baae95` |
| `minidev-sqlite-gpt-35-turbo-instruct.tar.gz` | 12,866,649 | `8b8a96d259e6eef7d6afe164ced25e6bff5200abe354c2e08dd23f28f39a0e7e` |
| `minidev-sqlite-gpt-35-turbo.tar.gz` | 14,509,006 | `9d4896fac6b15174fed5246787416a05af46c9eaf45fb215dfcc558093fd18f8` |
| `minidev-sqlite-gpt-4-32k.tar.gz` | 2,338,557 | `39bd31d2b9ec4c2b2c7092ddd578f395bb304a14a9cc5e4f7f50f01eb47932c4` |
| `minidev-sqlite-gpt-4-turbo.tar.gz` | 12,234,405 | `4f44c336f425afe237d3fc1cb12c528c960d4f4a373a5f55d8c580eb73af4c63` |
| `minidev-sqlite-gpt-4.tar.gz` | 12,384,631 | `98b2e6ccc58e79221e0d18d0f55374a335256f85ff6a92f0f92793ebe8d39bd0` |
| `minidev-sqlite-meta-llama-3-70b-instruct-2.tar.gz` | 12,446,219 | `7ce19ef9fc5138ea2f75c123aa3bc7acdc2c5c45ca5f9fb82b0c6e521ebcf764` |
| `minidev-sqlite-meta-llama-3-8b-instruct-2.tar.gz` | 13,154,426 | `606473169f3dbe0d3f73dd20ddb40ee7085c571d289f2fe20ecd0878a5b7eb29` |
| `minidev-sqlite-mistralai-mixtral-8x7b-instru-4.tar.gz` | 1,075,349 | `7f34c38f4a2fbc7c9cfd7720ee1dcc8af8c27748e47e2bdd6ebe556f7e3703ea` |
| `minidev-sqlite-phi-3-medium-128k-instruct-1.tar.gz` | 2,180,708 | `cfed02286a542624870170d3a8e8db52a8d16040c78937a5db5f9a2a02d00770` |

Each is at
`https://github.com/ivermin1123/attestql/releases/download/v0.2.2/<name>`, which is what the
`published.json` beside each summary states and what each run page links to.

## Second review, 2026-09-08

The coordinator reviewed the published runs and the code that made them. Three of the findings
change a number on this page.

**The second headline number is 69, not 66.** What the classification holds, joined to the nine
runs' credited-and-NOT_EQUAL sets, is 69; 66 was that join minus the three questions the page
budget left out. `aggregate.json` now states both per key, `value` and `published`:
`credited_but_not_equal` 164 with 161 published, `classified_by_hand` 69 with 66,
`bird_dev_classified_by_hand` 23 with 23. The landing shows `value` and puts one line under a
number whose `published` is below it; the proportion bar is still drawn from `value`.

**Every archive was counted.** `release.sh manifest` reads each `.tar.gz` and counts the question
directories in it, in all and per run, and `select.py --published` copies into each
`published.json` the one number its page is about: 3,957 question directories over the 21
archives, of which this site holds 1,232. A run of a group states its own count and the group's
own file states the archive's total, so no page states another page's number. The archives
themselves were not rebuilt and not re-uploaded: every sha256 in the table above is unchanged,
and the manifest is the only file that was made again.

**19 `questions.json` files named a question twice.** BIRD's Mini-Dev question file repeats 137
and 138, which the audit deduplicates before it runs anything and the selection did not: 5,288
entries became 5,250, and no question id is now in one of those files twice.

The site was built again over the regenerated data: **2,218 files, 40,673,308 bytes, 4.2 seconds**,
against 8,000 files and 41,943,040 bytes. `grep -rl /Users/ tools/site/data build/site` still
prints nothing.

**Verified on the redeployed preview** (deployment `aa41fc9b`, the fifth):
`https://attestql-ui.pages.dev/` serves 69 with "66 of them have a page here; the other 3 are
whole in the release assets"; `/runs/minidev-pg/gpt-4/` serves "This site holds 26 of the 218
question directories this run wrote"; `/runs/minidev-sqlite/gpt-4/` serves the same sentence for
its 7 of 269 and links `minidev-sqlite-gpt-4.tar.gz` on the release; and
`/runs/minidev-pg/gpt-4/q249/` states class A with the words the measurement report's own legend
gives it. `just check` green at 1,085 passed and 33 skipped.

## Unresolved

- The three hand-classified questions above are on no page. Publishing them needs either a larger
  per-page budget, which the plan forbids, or a renderer that bounds the rows it draws from a
  record, which is a change to what a page is and belongs to a phase of its own.
- `minidev-pg-gold-only/hf` states 38 fires where the 2026-09-03 summary states 39. The count of
  golds the shuffle probe fires on is unchanged; what moved is the label. Whether the golds that
  stopped firing `float-aggregate-order` should now be read again by hand is a question for
  whoever owns that classification.
