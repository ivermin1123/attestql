# BIRD Mini-Dev PostgreSQL: the GitHub zip against the Hugging Face file

Checked 2026-09-03. `diff.json` beside this file holds every difference and both sources' digests;
`compare` is a plain field-by-field comparison of the two JSON files keyed by `question_id`.

| Source | File | Digest | Date |
|---|---|---|---|
| GitHub zip | `minidev.zip` from the README of [bird-bench/mini_dev](https://github.com/bird-bench/mini_dev), member `minidev/MINIDEV/mini_dev_postgresql.json` | zip sha256 `cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f`; member sha256 `d2731292f20b8d8569cd956dd747ffe1df13cd625076263e38ae9ebcef50b1ab` | downloaded 2026-09-02 |
| Hugging Face | [birdsql/bird_mini_dev](https://huggingface.co/datasets/birdsql/bird_mini_dev), `data/mini_dev_pg-00000-of-00001.json` | sha256 `7fa740ef9225389cff6c34432120e8325d0ca3008d73db1ae38731234bc10da7`; commit `f65faf4a` | last modified 2026-01-18T08:44:25Z, downloaded 2026-09-03 |

| | GitHub zip | Hugging Face |
|---|---|---|
| Entries | 500 | 500 |
| Distinct ids | 498 | 500 |
| Duplicated ids | 137, 138 (byte-identical copies at positions 484 to 488) | none |
| Ids absent | 119, 120 (both `financial`) | none |
| Golds whose SQL differs | 2 | |
| Golds whose question, evidence, `db_id` or difficulty differs | 0 | |

The two statements that differ:

| Id | GitHub zip | Hugging Face |
|---|---|---|
| q879 (`formula_1`) | `ORDER BY T2.fastestLapSpeed DESC NULLS LAST LIMIT 1`, a text column ordered as text; the defect [mini_dev #24](https://github.com/bird-bench/mini_dev/issues/24) reported | `ORDER BY CAST(T2.fastestLapSpeed AS DOUBLE PRECISION) DESC NULLS LAST LIMIT 1`: corrected |
| q1322 (`student_club`) | `SELECT T1.event_name ... GROUP BY T1.event_id HAVING COUNT(T2.link_to_event) > 10 EXCEPT SELECT T1.event_name FROM event AS T1 WHERE T1.type = 'Meeting'`: the events attended by more than ten that are not meetings, by name | `SELECT COUNT(DISTINCT T1.event_id) ... WHERE T1.type = 'Meeting' GROUP BY T1.event_id HAVING COUNT(T2.link_to_event) > 10`: one row per qualifying meeting, each counting one event |

The question of q1322 asks "among the events attended by more than 10 members, how many of them
are meetings"; neither statement returns that count as one number, which is stated here as an
observation, not a finding.
