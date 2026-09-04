"""Cross-tab every reading against the hand classes (A/B/C) over the 170 rows.

Reads results.json (this directory), writes aggregate.json (counts) and
cells.json (question ids per reading x verdict, keyed "<reading>:forgiven"/"refused").
"""

import json
from collections import defaultdict
from pathlib import Path

HERE = __file__.rsplit("/", 1)[0]
results = json.loads(Path(f"{HERE}/results.json").read_text())

READING_NAMES = ["bird_ex", "test_suite", "bird_critic", "livesqlbench", "defog", "spider2"]

agg = {
    name: {
        "A": {"forgiven": 0, "refused": 0},
        "B": {"forgiven": 0, "refused": 0},
        "C": {"forgiven": 0, "refused": 0},
    }
    for name in READING_NAMES
}
cells = {name: defaultdict(list) for name in READING_NAMES}

for row in results:
    klass = row["class"]
    for name in READING_NAMES:
        v = row.get(name)
        if v is True:
            agg[name][klass]["forgiven"] += 1
            cells[name]["forgiven"].append(f"{row['model']}:q{row['question_id']}")
        elif v is False:
            agg[name][klass]["refused"] += 1
            cells[name]["refused"].append(f"{row['model']}:q{row['question_id']}")
        else:
            cells[name]["error"].append(f"{row['model']}:q{row['question_id']}")

totals = {}
for name in READING_NAMES:
    f = sum(agg[name][k]["forgiven"] for k in "ABC")
    r = sum(agg[name][k]["refused"] for k in "ABC")
    totals[name] = {"forgiven": f, "refused": r}

Path(f"{HERE}/aggregate.json").write_text(json.dumps(agg, indent=1))
Path(f"{HERE}/cells.json").write_text(json.dumps({k: dict(v) for k, v in cells.items()}, indent=1))

print(
    "reading | A forgiven/refused | B forgiven/refused | C forgiven/refused | total forgiven/refused"
)
for name in READING_NAMES:
    a, b, c = agg[name]["A"], agg[name]["B"], agg[name]["C"]
    t = totals[name]
    print(
        f"{name} | {a['forgiven']}/{a['refused']} | {b['forgiven']}/{b['refused']} | {c['forgiven']}/{c['refused']} | {t['forgiven']}/{t['refused']}"
    )
