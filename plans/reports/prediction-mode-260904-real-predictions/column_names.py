"""For every question the tool called EQUAL, do the gold and the prediction name their columns
the same? The tool writes no artifact for an EQUAL verdict, so the names are read here by
running both statements once more and comparing cursor descriptions
nothing else is compared.

usage: column_names.py <gold: zip|hf> <model> <out.json>
"""

import json
import os
import re
import sys
from pathlib import Path

import psycopg2

WORK = Path(os.environ["MEASURE_WORK"])  # the work directory reproduce.sh fills
gold, model, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
questions = {
    e["question_id"]: e
    for e in json.loads(
        (
            WORK
            / (
                "data/hf/mini_dev_pg-00000-of-00001.json"
                if gold == "hf"
                else "data/zip/minidev/MINIDEV/mini_dev_postgresql.json"
            )
        ).read_text()
    )
}
preds = json.loads(
    (WORK / f"data/preds-by-id/predict_mini_dev_{model}_postgresql.json").read_text()
)
equal_ids = [
    int(m.group(1))
    for line in (WORK / f"out/tool/{gold}/{model}/stdout.txt").read_text().splitlines()
    if (m := re.match(r"^q(\d+)\s+\S+\s+\S+\s+EQUAL\b", line))
]
conn = psycopg2.connect(
    "host=127.0.0.1 port=5498 dbname=bird user=auditor", password=os.environ["PGPASSWORD"]
)
rows = []
for i in equal_ids:
    cur = conn.cursor()
    cur.execute(questions[i]["SQL"])
    g = [d.name for d in cur.description]
    cur.execute(preds[str(i)].split("\t----- bird -----\t")[0])
    p = [d.name for d in cur.description]
    rows.append({"question_id": i, "gold_names": g, "second_names": p, "differ": g != p})
    conn.rollback()
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(
    json.dumps(
        {
            "gold": gold,
            "model": model,
            "equal": len(rows),
            "names_differ": sum(r["differ"] for r in rows),
            "rows": rows,
        },
        indent=1,
    )
)
print(gold, model, "EQUAL", len(rows), "names differ", sum(r["differ"] for r in rows))
