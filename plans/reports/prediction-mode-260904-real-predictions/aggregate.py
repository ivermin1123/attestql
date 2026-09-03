"""The totals the report states, from measurement.json, classification.json and the name counts."""

import json
import os
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])  # the work directory reproduce.sh fills

m = json.loads((WORK / "out/measurement.json").read_text())
c = json.loads((WORK / "out/classification.json").read_text())
out = {}
for gold in ("zip", "hf"):
    t = Counter()
    for r in m["per_file"][gold].values():
        t["audited"] += r["audited"]
        t["compared"] += r["compared"]
        t["ex1"] += r["tool_ex1"]
        t["ex0"] += r["tool_ex0"]
        t["errors"] += r["errors"]
        t["official_ex"] += r["official_ex_sum"]
        t["agree"] += r["crosscheck"]["agree"]
        t["disagree"] += r["crosscheck"]["disagree"]
        t["ex1_not_equal"] += r["ex1_not_equal"]
        for k, v in r["ex1_not_equal_by_class"].items():
            t["class_" + k] += v
        t["not_equal_names_differ"] += r["not_equal_names_differ"]
        for k, v in r["error_steps"].items():
            t["errstep_" + k] += v
    out[gold] = dict(t)
# hand classes
tc = Counter()
for r in c["per_file"].values():
    tc["A"] += r["A"]
    tc["B"] += r["B"]
    tc["C"] += r["C"]
tot = tc["A"] + tc["B"] + tc["C"]
out["classes"] = {
    **tc,
    "total": tot,
    "A_over_all": round(tc["A"] / tot, 3),
    "AB_over_all": round((tc["A"] + tc["B"]) / tot, 3),
    "A_over_AB": round(tc["A"] / (tc["A"] + tc["B"]), 3),
}
qs = Counter()
qclass = {}
for r in c["per_file"].values():
    for row in r["rows"]:
        qs[row["question_id"]] += 1
        qclass[row["question_id"]] = row["class"]
out["distinct_questions"] = len(qs)
out["distinct_questions_by_class"] = dict(Counter(qclass.values()))
# names on EQUAL rows
names = Counter()
for p in (WORK / "out/names/hf").glob("*.json"):
    d = json.loads(p.read_text())
    names["equal"] += d["equal"]
    names["differ"] += d["names_differ"]
out["names_on_equal_rows"] = dict(names)
# unjust zero / unjust one
uz = []
uo = []
for model, rows in m["unjust_zero"].items():
    for row in rows:
        i = row["question_id"]
        for gold in ("zip", "hf"):
            v, ex = row[gold]
            cv, cex = row["corrected"]
            if ex == 0 and cex == 1:  # BIRD's reading against the correction, loose or not
                uz.append((model, i, gold, cv))
            if ex == 1 and cv == "NOT_EQUAL" and cex == 0:
                uo.append((model, i, gold))
out["unjust_zero"] = uz
out["unjust_one"] = uo
out["unjust_table"] = m["unjust_zero"]
# zip against hf
changed = {}
for model, rows in m["zip_against_hf"].items():
    changed[model] = [
        (r["question_id"], r["zip"], r["hf"]) for r in rows if r["question_id"] not in (119, 120)
    ]
out["zip_against_hf"] = changed
out["position_keying_equals_id_keying_on_zip"] = m["position_keying_equals_id_keying_on_zip"]
(WORK / "out/aggregate.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
