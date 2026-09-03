"""Diff the re-measurement at HEAD (out/) against the run at 41621c0 (out-41621c0/)."""

import json
import os
import sys
from collections import Counter
from pathlib import Path

S = Path(__file__).resolve().parent
os.environ.setdefault("MEASURE_WORK", str(S))
REPO = Path(
    "/Users/hoangle/Desktop/code/attestql/plans/reports/prediction-mode-260904-real-predictions"
)
sys.path.insert(0, str(REPO))
import measure  # noqa: E402

OLD, NEW = S / "out-41621c0", S / "out"


def questions(directory: Path) -> dict:
    out = {}
    for line in (directory / "stdout.txt").read_text().splitlines():
        found = measure.LINE.match(line)
        if not found:
            continue
        qid, _db, rule, verdict, smells, rest = found.groups()
        entry = {
            "rule": rule,
            "verdict": verdict,
            "smells": smells,
            "bird_ex": None,
            "message": rest if verdict == "ERROR" else "",
        }
        if verdict == "EQUAL":
            entry["bird_ex"] = 1
        elif verdict in ("NOT_EQUAL", "NOT_COMPARABLE"):
            ce = json.loads((directory / f"q{qid}" / "counterexample.json").read_text())
            entry["bird_ex"] = ce["bird_ex"]["value"]
        out[int(qid)] = entry
    return out


if (NEW / "aggregate.json").is_file():
    old_agg = json.loads((REPO / "aggregate.json").read_text())
    new_agg = json.loads((NEW / "aggregate.json").read_text())
    for gold in ("zip", "hf"):
        o, n = old_agg[gold], new_agg[gold]
        diffs = {k: (o.get(k), n.get(k)) for k in sorted(set(o) | set(n)) if o.get(k) != n.get(k)}
        print(gold, "totals differ:" if diffs else "totals identical", diffs)
    for k in (
        "classes",
        "distinct_questions",
        "unjust_zero",
        "unjust_one",
        "names_on_equal_rows",
        "zip_against_hf",
    ):
        print(
            k,
            "same"
            if old_agg.get(k) == new_agg.get(k)
            else f"DIFF\n  old={old_agg.get(k)}\n  new={new_agg.get(k)}",
        )
else:
    print("no aggregate.json at HEAD yet")

verdict_changes, smell_changes = Counter(), Counter()
examples = []
for new_stdout in sorted(NEW.glob("tool/*/*/stdout.txt")):
    gold, model = new_stdout.parent.parent.name, new_stdout.parent.name
    old_dir = OLD / "tool" / gold / model
    if (
        " questions: " not in new_stdout.read_text().splitlines()[-1:][0]
        if new_stdout.read_text().strip()
        else True
    ):
        print("unfinished:", gold, model)
        continue
    if not (old_dir / "stdout.txt").is_file():
        print("no old run for", gold, model)
        continue
    o, n = questions(old_dir), questions(new_stdout.parent)
    for qid in sorted(set(o) | set(n)):
        a, b = o.get(qid, {}), n.get(qid, {})
        if (a.get("verdict"), a.get("bird_ex")) != (b.get("verdict"), b.get("bird_ex")):
            verdict_changes[
                (gold, a.get("verdict"), a.get("bird_ex"), b.get("verdict"), b.get("bird_ex"))
            ] += 1
            examples.append(
                (
                    "verdict",
                    gold,
                    model,
                    qid,
                    a.get("verdict"),
                    b.get("verdict"),
                    (b.get("message") or a.get("message") or "")[:100],
                )
            )
        if a.get("smells") != b.get("smells"):
            smell_changes[(gold, a.get("smells"), b.get("smells"))] += 1
            if len(examples) < 60:
                examples.append(("smells", gold, model, qid, a.get("smells"), b.get("smells"), ""))
print("verdict/bird_ex changes:", sum(verdict_changes.values()))
for k, v in sorted(verdict_changes.items(), key=lambda kv: -kv[1]):
    print(" ", k, v)
print("smell-string changes:", sum(smell_changes.values()))
for k, v in sorted(smell_changes.items(), key=lambda kv: -kv[1])[:15]:
    print(" ", k, v)
print("examples:")
for e in examples[:60]:
    print(" ", e)
