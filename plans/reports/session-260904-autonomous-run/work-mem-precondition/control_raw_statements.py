"""The nine golds without the tool's envelope, so that the role's work_mem reaches them.

The control for the demonstration beside it: the same comparison the research report made
(`plans/reports/research-260904-postgres-result-preconditions/gen_hashagg_workmem_demo.py`),
but with the 64 kB coming from `ALTER ROLE auditor SET work_mem` rather than from a
`SET LOCAL`, because that is the difference between the two audit runs. Only the parallel
gather is turned off here, as the research script did in both of its arms, so what is left
between two runs of this script is the memory bound and nothing else.

Run once per role state; `run.sh` does that and passes the file to write.
"""

import json
import sys
from pathlib import Path

import psycopg

DSN = "host=127.0.0.1 port=5499 dbname=bird user=auditor"
HERE = Path(__file__).resolve().parent
IDS = [1473, 1476, 1482, 1529, 1531, 1380, 1390, 1410, 955]


def main(destination: Path) -> None:
    golds = {
        row["question_id"]: row["SQL"] for row in json.loads((HERE / "nine-golds.json").read_text())
    }
    answers: dict[str, object] = {}
    with psycopg.connect(DSN, autocommit=True) as connection, connection.cursor() as cursor:
        cursor.execute("SHOW work_mem")
        row = cursor.fetchone()
        answers["work_mem_the_role_gave_this_session"] = None if row is None else row[0]
        for question_id in IDS:
            cursor.execute("BEGIN READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '60000'")
            cursor.execute("SET LOCAL max_parallel_workers_per_gather = 0")
            cursor.execute(golds[question_id])
            answers[str(question_id)] = [
                [str(value) for value in fetched] for fetched in cursor.fetchall()
            ]
            cursor.execute("ROLLBACK")
    destination.write_text(json.dumps(answers, indent=1) + "\n")
    print(f"{destination.name}: work_mem={answers['work_mem_the_role_gave_this_session']}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
