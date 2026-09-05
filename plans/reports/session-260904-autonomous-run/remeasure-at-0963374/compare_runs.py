"""Compare a rerun of the prediction-mode measurement with the committed artifact.

The baseline is what `plans/reports/prediction-mode-260904-real-predictions/` holds: the
per-question verdicts of the run at `41621c0` (`verdicts-{zip,hf}.json`), BIRD's own scoring
of that run (`official/`) and its totals (`aggregate.json`). The rerun is a work directory
`reproduce.sh` filled at another commit. What is written: every question whose verdict or
BIRD reading moved, with both values; every question whose EX under BIRD's own evaluator
differs between the two runs; the totals side by side; and the credited-but-NOT_EQUAL
counts by mechanism the rerun's summaries state, against the baseline's 170 = 138 + 32.

usage: compare_runs.py <artifact-dir> <work-dir> <out-dir>
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

LINE = re.compile(
    r"^q(\d+)\s+(\S+)\s+(\S*)\s+(EQUAL|NOT_EQUAL|NOT_COMPARABLE|ERROR|GOLD-ONLY)\s+smells=(\S+)(?:\s+(.*))?$"
)
MODELS = (
    "gpt-35-turbo-instruct",
    "gpt-35-turbo",
    "gpt-4-32k",
    "gpt-4-turbo",
    "gpt-4",
    "meta-llama-3-70b-instruct-2",
    "meta-llama-3-8b-instruct-2",
    "mistralai-mixtral-8x7b-instru-4",
    "phi-3-medium-128k-instruct-1",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cut(message: str) -> str:
    """The server's message without the statement fragment it quotes."""
    return re.split(r"\s+LINE \d+:", message, maxsplit=1)[0].strip()


def rerun_verdicts(work: Path, gold: str, model: str) -> dict[str, dict[str, Any]]:
    """Per question: the verdict line of the rerun, and its BIRD reading from the counterexample."""
    directory = work / "out" / "tool" / gold / model
    found: dict[str, dict[str, Any]] = {}
    for line in (directory / "stdout.txt").read_text(encoding="utf-8").splitlines():
        match = LINE.match(line)
        if not match:
            continue
        question_id, _, rule, verdict, _, rest = match.groups()
        entry: dict[str, Any] = {"verdict": verdict, "rule": rule}
        if verdict == "ERROR":
            entry["error"] = cut(rest or "")
        counterexample = directory / f"q{question_id}" / "counterexample.json"
        if counterexample.is_file():
            document = read_json(counterexample)
            entry["bird_ex"] = document["bird_ex"]["value"]
            mechanism = document.get("mechanism")
            if mechanism:
                entry["mechanism"] = mechanism["class"]
        elif verdict == "EQUAL":
            entry["bird_ex"] = 1
        found[question_id] = entry
    return found


def main(artifact: Path, work: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    moves: list[dict[str, Any]] = []
    credited: Counter[str] = Counter()
    credited_by_gold: dict[str, Counter[str]] = {"zip": Counter(), "hf": Counter()}
    for gold in ("zip", "hf"):
        baseline = read_json(artifact / f"verdicts-{gold}.json")
        for model in MODELS:
            rerun = rerun_verdicts(work, gold, model)
            summary = read_json(work / "out" / "tool" / gold / model / "summary.json")
            block = summary["credited_but_not_equal"]
            credited_by_gold[gold]["total"] += block["total"]
            for name, count in block["by_mechanism"].items():
                credited_by_gold[gold][name] += count
            for question_id, before in baseline[model].items():
                after = rerun.get(question_id)
                if after is None:
                    continue
                if before["verdict"] != after["verdict"] or before["bird_ex"] != after.get(
                    "bird_ex"
                ):
                    moves.append(
                        {
                            "gold": gold,
                            "model": model,
                            "question_id": int(question_id),
                            "before": {"verdict": before["verdict"], "bird_ex": before["bird_ex"]},
                            "after": {
                                "verdict": after["verdict"],
                                "bird_ex": after.get("bird_ex"),
                                **({"error": after["error"]} if "error" in after else {}),
                            },
                        }
                    )
    credited.update(credited_by_gold["hf"])
    flips: list[dict[str, Any]] = []
    for gold in ("zip", "hf"):
        for model in MODELS:
            before_rows = {
                row["question_id"]: row["res"]
                for row in read_json(artifact / "official" / gold / f"{model}.json")["rows"]
            }
            after_rows = {
                row["question_id"]: row["res"]
                for row in read_json(work / "out" / "official" / gold / f"{model}.json")["rows"]
            }
            for question_id, before in before_rows.items():
                after = after_rows.get(question_id)
                if after is not None and after != before:
                    flips.append(
                        {
                            "gold": gold,
                            "model": model,
                            "question_id": question_id,
                            "ex_before": before,
                            "ex_after": after,
                        }
                    )
    totals = {
        "baseline": read_json(artifact / "aggregate.json"),
        "rerun": read_json(work / "out" / "aggregate.json"),
    }
    moves_by_question: dict[str, int] = dict(Counter(f"q{m['question_id']}" for m in moves))
    document = {
        "what": (
            "The prediction-mode measurement rerun with reproduce.sh at another commit, "
            "against the committed run at 41621c0: verdict or BIRD-reading moves per question, "
            "BIRD's own evaluator's EX flips between the two runs, the totals side by side, and "
            "the credited-but-NOT_EQUAL counts the rerun's summaries state by mechanism."
        ),
        "moves": sorted(moves, key=lambda m: (m["gold"], m["question_id"], m["model"])),
        "moves_by_question": moves_by_question,
        "official_flips": flips,
        "credited_but_not_equal_by_mechanism": {
            gold: dict(counter) for gold, counter in credited_by_gold.items()
        },
        "totals": totals,
    }
    (out / "comparison.json").write_text(
        json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        f"verdict or BIRD-reading moves: {len(moves)} "
        f"({', '.join(f'{k} x{v}' for k, v in sorted(moves_by_question.items()))})",
        f"BIRD's evaluator flips between the two runs: {len(flips)}",
    ]
    for gold, counter in credited_by_gold.items():
        lines.append(f"{gold}: credited by BIRD but NOT_EQUAL {dict(counter)}")
    for gold in ("zip", "hf"):
        before, after = totals["baseline"][gold], totals["rerun"][gold]
        keys = ("ex1", "ex0", "errors", "official_ex", "agree", "disagree", "ex1_not_equal")
        lines.append(f"{gold}: " + ", ".join(f"{k} {before[k]} -> {after[k]}" for k in keys))
    lines.append(f"classes: {totals['baseline']['classes']} -> {totals['rerun']['classes']}")
    (out / "comparison.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
