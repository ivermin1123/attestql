<!-- cspell:ignore uiuc PVLDB -->
<!-- markdownlint-disable MD034 -->
# Drafts for the first public word about AttestQL, 2026-09-14

Drafts the owner sends by hand after release 0.4.0, under their own identity, as ADR-0013 point 9
requires. Nothing here is posted by a session. Each paragraph of a body is one line, because the
places these go render a line break wherever a file wraps, so a body is pasted as it stands.
Every number below has an owning row in `docs/claims-register.md`; the version number and the
release date are filled in when 0.4.0 exists. Three pieces, in the order the review of
2026-09-12 proposed: two direct notes to the people whose own work the numbers touch, then one
public post.

## 1. To the group behind the 52.8 % measurement

Where: a new issue on `uiuc-kang-lab/text_to_sql_benchmarks`, the repository of "Pervasive
Annotation Errors Break Text-to-SQL Benchmarks and Leaderboards" (Jin, Choi, Zhu, Kang, PVLDB
19(5), 2026) and of the SAR-Agent audit. They released corrected labels and, on 2026-08-27, the
verified BIRD-Platinum training set. Evidence: register rows A16 to A25 (Mini-Dev on PostgreSQL),
A34 to A36 (BIRD dev), A53 (the second reader), U1 to U7 (upstream).

Title: A deterministic detector for one subclass of the annotation errors you correct by hand

Body:

Your PVLDB paper measured a 52.8 % annotation error rate in BIRD Mini-Dev with an LLM audit agent and human validation. I built something narrower and mechanical that lands on the same golds from the other side, and I think the two are complementary enough that you may want to run it over the rows you corrected.

AttestQL runs a gold and a prediction on the shipped database and compares the two results with duplicates, row order and declared types kept, beside BIRD's own set(pred) == set(gold) reading. Without a prediction it runs five probes over the gold alone: does a LIMIT cut through rows the data leaves tied, does an ORDER BY key hold NULLs that sort first, is a numeric-looking ORDER BY key stored as text, does the result change when the referenced tables are copied in another row order, and are whole rows duplicated. No model, no key, one command, an evidence record and the differing rows for every disagreement.

What it found on BIRD's own published files: of the 1,239 Mini-Dev predictions BIRD's evaluator credits across the nine PostgreSQL prediction files, 164 differ from the gold once duplicates, order and types count, and 69 of those (5.6 % of everything credited) are wrong answers the benchmark scored 1, by a hand reading that a second blind reader agreed with on 27 of 30 sampled rows. On BIRD dev, of the 963 golds the 2025-11-06 quality pass left unchanged, the probes fire on 25, and 23 of those do not answer their question on the shipped data (16 cut through a tie, 2 sort NULL first, 2 sort numbers as text, 3 other). Every row has a page with both statements, both results, the rows that differ and the JSON it was rendered from: https://attestql.com

Three things you might do with it, in increasing order of effort. Run the gold-only probes over BIRD-Platinum's 2.5k instances and see whether any of the 61 % you corrected still fire, or whether any you did not correct do. Compare the 69 rows above with your corrected Mini-Dev labels; where we disagree, one of us is wrong and the evidence record says which. Or ignore the tool and take the 23 BIRD dev golds, which I reported upstream on 2026-09-07 (bird-bench/mini_dev issue 49, Hugging Face discussion 3 on bird_sql_dev_20251106) and which have had no reply.

Install: `uv tool install attestql` (or pip), then `attestql demo --out demo` runs the packaged sandbox; on your own files it is `attestql audit --engine sqlite --dsn <db> --questions <json> --predictions <json> --out audit`. Every claim above has an owning artifact in the repository's claims register, with the commit it was measured at. Apache-2.0. I would be glad to be told where it is wrong.

## 2. To the author of the Spider 2.0 read-only audit

Where: a comment on `xlang-ai/Spider2` pull request 211 ("Add a read-only consistency audit for
Spider2-Snow", opened 2026-08-13, no maintainer reply), the closest peer effort found. Kept short:
it is their pull request. Evidence: register N2 (re-measured 2026-09-13), the external landscape
report of 2026-09-12.

Body:

I am doing the same thing for BIRD from the other end, and your PR is the only other read-only gold audit I have found, so a pointer in case it is useful: https://github.com/ivermin1123/attestql runs each gold on the shipped SQLite or PostgreSQL data and probes it mechanically (tie at a LIMIT cut, NULL-first ordering, numbers sorted as text, result not a function of the row order, duplicate rows), and compares a prediction with the gold keeping duplicates, order and types, beside the benchmark's own set reading. On BIRD dev it flags 23 of the 963 golds the 2025-11-06 pass left alone, each with a page showing the rows.

Spider 2.0-lite's local SQLite subset has public databases and 256 public gold files, so the same audit should run there with little change. If you have already read those golds against the data, I would rather compare notes than duplicate the work.

## 3. The public post

Where: a Show HN on Hacker News, which is where the one general-audience thread on text-to-SQL
benchmark validity of 2026 ran (the CACM post's thread of 2026-07-22), with the same text as a
post on the owner's own site. Title under 80 characters, no dash. Evidence: as in piece 1, plus
A5 (the three shipped golds the demo reproduces) and the release notes of 0.4.0 for the version.

Title: Show HN: AttestQL, a tool that audits text-to-SQL benchmark golds by replaying them

Body:

Text-to-SQL benchmarks score a model by running its SQL and the reference SQL on one shipped database and comparing the two result sets. BIRD's evaluator is set(predicted) == set(gold), so duplicated rows, row order and column types never count, and the reference SQL is assumed right. It often is not: a paper at PVLDB this year measured a 52.8 % annotation error rate in BIRD Mini-Dev.

AttestQL is a command-line tool that takes a gold, a prediction and the database, runs both, and tells you where they differ: the typed comparison beside BIRD's own reading, the rows in one result and not the other, and an evidence record for each execution with the statement, the session settings, the result and its hash, so a stranger can rerun it. Without a prediction it probes the gold alone for five mechanical ways a reference query can fail to answer its question on the data it ships with: a LIMIT that cuts through tied rows, an ordering key whose NULLs sort first, numbers ordered as text, a result that changes when the referenced tables are copied in another row order, and whole rows returned twice without a DISTINCT to say so.

Two commands, no server, no account, no model:

    uv tool install attestql
    attestql demo --out demo

The demo audits the three BIRD Mini-Dev golds that upstream reports found wrong, each against a corrected statement, on a fixture of a few rows, plus three synthetic questions. One of them, q879, asks for the nationality of the driver who set the fastest lap speed. The speed column is text, so the gold's ORDER BY puts '93.175' above '259.870' and answers Norwegian where the data says Peruvian; the corrected statement casts the key and gets Peruvian, and the tool shows the two rows side by side.

On BIRD's own published files: of the 1,239 Mini-Dev predictions BIRD's evaluator credits, 164 disagree with the gold once duplicates, order and types count, and 69 of those (5.6 % of everything credited) are wrong answers that scored 1, read by hand and checked by a second blind reader who agreed on 27 of 30 sampled rows. On BIRD dev, 23 of the 963 golds the 2025-11-06 quality pass left unchanged do not answer their question on the shipped data. Every one of those rows has a page at https://attestql.com with both statements, the rows that differ and the JSON behind the page; the runs are also release assets.

I filed six upstream reports with counterexamples (a seventh I withdrew as my own misreading). BIRD replied to three on 2026-09-05: two got "we will review and correct this issue in the next patch", and no patch has shipped; the third changed BIRD's README to name the Hugging Face copy as canonical. The other three have had no reply.

What it does not do: it never decides which statement is right. NOT_EQUAL means two statements disagree on this data under this rule, here are the rows, a person decides. The probes are heuristics and their evidence says so. PostgreSQL and SQLite only. There is a scoring toolkit from IBM that also runs both statements on either engine; this one adds the gold-only probes and the evidence record, and does not score.

Python 3.11+, Apache-2.0, every number in the README has an owning artifact and the commit it was measured at. I am one person and the code was written with AI assistance under my review; the gate, not the author, vouches for it, and the gate is `just check`. I would like to hear where it is wrong: https://github.com/ivermin1123/attestql

## Before sending, on the day

- Release 0.4.0 exists on PyPI and the site's 121 runs are made again with it: done 2026-09-14
  (register rows A54 and N8). The numbers above are measurement rows, A17, A25, A35, A36 and A53,
  which the refresh did not touch, and they were re-read against the register the same day.
- `CITATION.cff` names 0.4.0 and 2026-09-14: done in the release commit `b574bdd`.
- The README's first screen leads with the two commands (the review's step 3), so a reader from
  the post meets what the post promised.
- Re-read U5 to U7 for replies (the date set was 2026-09-21); if a maintainer answered, the note in
  piece 1 says so instead of "no reply".
