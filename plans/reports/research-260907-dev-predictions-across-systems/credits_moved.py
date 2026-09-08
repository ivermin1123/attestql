"""Count BIRD credits that move when the 2025-11-06 gold replaces the old one."""

import json
import os
import re
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
OUT = WORK / "out"
NORMALISE = re.compile(r"\s+")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(sql: str) -> str:
    return NORMALISE.sub(" ", sql.strip().rstrip(";")).lower()


def rewritten_ids() -> set[int]:
    old = load(WORK / "data/dev/dev_20240627/dev.json")
    new = {
        entry["question_id"]: entry
        for entry in load(WORK / "data/hf/dev_20251106-00000-of-00001.json")
    }
    return {
        entry["question_id"]
        for entry in old
        if norm(entry["SQL"]) != norm(new[entry["question_id"]]["SQL"])
    }


def main() -> None:
    measured = load(OUT / "prediction-measurement.json")["files"]
    rewritten = rewritten_ids()
    files = {}
    for _name, row in measured.items():
        old = set(row["credited_ids"]) if row["copy"] == "old" else None
        if old is None:
            continue
        new = set(measured[f"dev1106/{row['file']}"]["credited_ids"])
        lost, gained = sorted(old - new), sorted(new - old)
        files[row["file"]] = {
            "old_credited": len(old),
            "dev1106_credited": len(new),
            "lost_old_to_dev1106": lost,
            "gained_dev1106_over_old": gained,
            "moved_both_directions": len(lost) + len(gained),
            "lost_among_399_rewritten": sorted(set(lost) & rewritten),
            "gained_among_399_rewritten": sorted(set(gained) & rewritten),
        }
    lost_total = sum(len(row["lost_old_to_dev1106"]) for row in files.values())
    gained_total = sum(len(row["gained_dev1106_over_old"]) for row in files.values())
    document = {
        "reading": (
            "BIRD-credited predictions per file under each gold copy, with both directions of "
            "movement and their overlap with the 399 ids whose normalised SQL BIRD rewrote."
        ),
        "rewritten_gold_count": len(rewritten),
        "rewritten_gold_ids": sorted(rewritten),
        "files": files,
        "totals": {
            "file_copy_pairs": len(files),
            "lost": lost_total,
            "gained": gained_total,
            "moved": lost_total + gained_total,
        },
    }
    (OUT / "credits-moved.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(
        f"credits moved over {len(files)} files: lost {lost_total}, gained {gained_total}, "
        f"total {lost_total + gained_total}; rewritten golds {len(rewritten)}"
    )


if __name__ == "__main__":
    main()
