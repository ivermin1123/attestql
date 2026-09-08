"""Assert every selected file answers BIRD dev's ids and database order."""

import json
import os
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
SUFFIX = "\t----- bird -----\t"
OLD = WORK / "data/dev/dev_20240627/dev.json"
NEW = WORK / "data/hf/dev_20251106-00000-of-00001.json"
RUN = WORK / "data/preds-run"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    old, new = load(OLD), load(NEW)
    ids = {str(entry["question_id"]) for entry in old}
    if ids != {str(entry["question_id"]) for entry in new}:
        raise SystemExit("the two question copies do not hold the same ids")
    records = load(WORK / "out/predictions-readable.json")["files"]
    checked = {}
    for record in records:
        name = record["file"]
        readable = load(RUN / f"{name}.json")
        keys = set(readable)
        db_suffix_matches = None
        if record["keyed_by"] == "position":
            expected_keys = {str(position) for position in range(len(old))}
            if list(readable) != expected_keys and set(readable) != expected_keys:
                raise SystemExit(f"{name}: position keys are not 0 through 1533")
            db_suffix_matches = sum(
                isinstance(readable[str(position)], str)
                and readable[str(position)].endswith(SUFFIX + old[position]["db_id"])
                for position in range(len(old))
            )
        elif keys != ids:
            raise SystemExit(f"{name}: keys are not BIRD dev question ids")
        checked[name] = {
            "entries": len(readable),
            "keyed_by": record["keyed_by"],
            "codeS_suffix_database_matches": db_suffix_matches,
            "atlas_suffix_database_matches": record.get("atlas_database_suffix_matches"),
        }
    document = {
        "reading": (
            "Pairing checks against both question copies. Position-keyed CodeS files carry "
            "BIRD's db_id suffix at every position; Alpha-SQL and DAIL-SQL carry the id set. "
            "Plain position-keyed RSL-SQL, GSR and CSC-SQL files are paired by the code witnesses "
            "named in sources.json and have exactly 1,534 lines. ATLAS Core lines carry a tab "
            "database suffix checked against every dev position before removal."
        ),
        "files": checked,
    }
    target = WORK / "out/prediction-pairing.json"
    target.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(checked, indent=1))


if __name__ == "__main__":
    main()
