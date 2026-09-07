"""Compare each Mini-Dev prediction score on the two database copies."""

import json
import os
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
MODELS = [
    line.split()[0]
    for line in (Path(__file__).parent / "SHA256SUMS.predictions").read_text().splitlines()
]


def load(copy: str, model: str) -> dict:
    return json.loads((WORK / "out" / "official" / copy / f"{model}.json").read_text())


def main() -> None:
    files = []
    all_changed = []
    for model in MODELS:
        minidev, dev = load("minidev", model), load("dev", model)
        changed = []
        for left, right in zip(minidev["rows"], dev["rows"], strict=True):
            if left["res"] == right["res"]:
                continue
            row = {
                "position": left["position"],
                "question_id": left["question_id"],
                "db_id": left["db_id"],
                "minidev_res": left["res"],
                "dev_res": right["res"],
                "direction": ("minidev-1-dev-0" if left["res"] == 1 else "minidev-0-dev-1"),
            }
            changed.append(row)
            all_changed.append({"model": model, **row})
        files.append(
            {
                "model": model,
                "positions": minidev["positions"],
                "ex_sum_minidev": minidev["ex_sum"],
                "ex_sum_dev": dev["ex_sum"],
                "changed_positions": len(changed),
                "changed_question_ids": sorted({row["question_id"] for row in changed}),
                "minidev_to_dev_gain": sum(
                    row["direction"] == "minidev-0-dev-1" for row in changed
                ),
                "minidev_to_dev_loss": sum(
                    row["direction"] == "minidev-1-dev-0" for row in changed
                ),
                "rows": changed,
            }
        )

    previous_root = Path(__file__).parent.parent / "minidev-sqlite-260907" / "official" / "hf"
    crosscheck = []
    for model in MODELS:
        previous = json.loads((previous_root / f"{model}.json").read_text())
        current = load("minidev", model)
        if current["ex_sum"] != previous["ex_sum"]:
            crosscheck.append(
                {
                    "model": model,
                    "current_ex_sum": current["ex_sum"],
                    "previous_ex_sum": previous["ex_sum"],
                }
            )
        current_rows = {
            (row["position"], row["question_id"], row["res"]) for row in current["rows"]
        }
        previous_rows = {
            (row["position"], row["question_id"], row["res"]) for row in previous["rows"]
        }
        if current_rows != previous_rows:
            crosscheck.append({"model": model, "row_differences": True})
    if crosscheck:
        raise SystemExit(f"shipped-pairing crosscheck failed: {crosscheck}")

    document = {
        "gold": "mini_dev_sqlite_hf.json, sha256 88ceb071...",
        "card_games_preparation": (
            "BIRD's evaluator opens card_games read-write; each copy is a writable clone with "
            "sha256 c98bdb57fe7474da798b407785544b9af0daaad5d61fd21e2a73309493bc1227"
        ),
        "prediction_positions": 500,
        "distinct_question_ids": 498,
        "files": files,
        "total_changed_positions": sum(file["changed_positions"] for file in files),
        "total_minidev_to_dev_gain": sum(file["minidev_to_dev_gain"] for file in files),
        "total_minidev_to_dev_loss": sum(file["minidev_to_dev_loss"] for file in files),
        "all_changed_question_ids": sorted({row["question_id"] for row in all_changed}),
        "crosscheck_against_minidev_measurement": {
            "source": "plans/reports/minidev-sqlite-260907/official/hf",
            "differences": crosscheck,
        },
    }
    target = WORK / "out" / "score-flips.json"
    target.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(
        f"score flips: {document['total_changed_positions']} of "
        f"{len(MODELS) * 500} positions, "
        f"gain {document['total_minidev_to_dev_gain']}, "
        f"loss {document['total_minidev_to_dev_loss']}"
    )


if __name__ == "__main__":
    main()
