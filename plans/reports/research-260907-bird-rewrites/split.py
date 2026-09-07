"""Split BIRD dev's two gold copies and build the two prediction files replayed here.

    MEASURE_WORK=<work-directory> python3 split.py

The split is R-C's normalisation from the earlier measurement: whitespace collapsed, a trailing
semicolon dropped, case dropped. A count other than 399 / 172 / 963 stops the lane rather than
moving a denominator. The SQL itself stays in the work directory; only id lists are committed.
"""

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
HERE = Path(__file__).resolve().parent
OLD = WORK / "data/dev/dev_20240627/dev.json"
NEW = WORK / "data/hf/dev_20251106-00000-of-00001.json"
DATABASES = [
    "california_schools",
    "card_games",
    "codebase_community",
    "debit_card_specializing",
    "european_football_2",
    "financial",
    "formula_1",
    "student_club",
    "superhero",
    "thrombosis_prediction",
    "toxicology",
]
NORMALISE = re.compile(r"\s+")


def norm(sql: str) -> str:
    return NORMALISE.sub(" ", sql.strip().rstrip(";")).lower()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_predictions(name: str, entries: list[dict]) -> str:
    path = WORK / "data/predictions" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    statements = {str(entry["question_id"]): entry["SQL"] for entry in entries}
    path.write_text(json.dumps(statements, separators=(",", ":")) + "\n", encoding="utf-8")
    return str(path.relative_to(WORK))


def main() -> None:
    old, new = json.loads(OLD.read_text()), json.loads(NEW.read_text())
    if [entry["question_id"] for entry in old] != [entry["question_id"] for entry in new]:
        raise SystemExit("the two question files do not hold the same ids in the same order")

    groups: dict[str, list[dict]] = {"sql_rewritten": [], "text_only": [], "unchanged": []}
    for first, second in zip(old, new, strict=True):
        if norm(first["SQL"]) != norm(second["SQL"]):
            groups["sql_rewritten"].append(second)
        elif (
            first["question"].strip() != second["question"].strip()
            or first.get("evidence", "").strip() != second.get("evidence", "").strip()
        ):
            groups["text_only"].append(second)
        else:
            groups["unchanged"].append(second)

    sizes = {name: len(entries) for name, entries in groups.items()}
    if sizes != {"sql_rewritten": 399, "text_only": 172, "unchanged": 963}:
        raise SystemExit(f"the split moved: {sizes}; stop and report it")
    old_by_id = {entry["question_id"]: entry for entry in old}
    rewrite_prediction = write_predictions("rewrite-399", groups["sql_rewritten"])
    harness_prediction = write_predictions(
        "text-only-172",
        [old_by_id[entry["question_id"]] for entry in groups["text_only"]],
    )

    for name in ("rewrite-399", "text-only-172"):
        ids_dir = WORK / "out/ids" / name
        ids_dir.mkdir(parents=True, exist_ok=True)
        entries = groups["sql_rewritten" if name.startswith("rewrite") else "text_only"]
        by_database = Counter(entry["db_id"] for entry in entries)
        for database in DATABASES:
            ids = [str(entry["question_id"]) for entry in entries if entry["db_id"] == database]
            if not by_database[database]:
                raise SystemExit(f"{name} has no ids on {database}, contrary to the split")
            (ids_dir / f"{database}.txt").write_text(",".join(ids) + "\n", encoding="utf-8")

    document = {
        "reading": (
            "The 2025-11-06 pass split by R-C's SQL normalisation. rewrite-399 is replayed as "
            "the prediction; text-only-172 is replayed as itself as a harness check."
        ),
        "normalisation": "whitespace collapsed, trailing semicolon dropped, case dropped",
        "sizes": sizes,
        "ids": {
            name: [entry["question_id"] for entry in entries] for name, entries in groups.items()
        },
        "input_sha256": {"old_dev_json": digest(OLD), "dev_20251106_json": digest(NEW)},
        "prediction_files": {
            "rewrite-399": {
                "work_path": rewrite_prediction,
                "sha256": digest(WORK / rewrite_prediction),
                "source": "2025-11-06 SQL",
            },
            "text-only-172": {
                "work_path": harness_prediction,
                "sha256": digest(WORK / harness_prediction),
                "source": "2024-06-27 SQL, selected because the two normalised SQL texts match",
            },
        },
    }
    (HERE / "split.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(f"split: {sizes}")


if __name__ == "__main__":
    main()
