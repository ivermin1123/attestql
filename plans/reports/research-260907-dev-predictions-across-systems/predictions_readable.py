"""Write the measurement form of each prediction file, preserving its shipped statements.

    predictions_readable.py

JSON files are copied value for value, with only upstream's single-space substitution for a
non-string. Plain-line files are wrapped in the JSON object AttestQL reads; DAIL-SQL's wrapper
also applies upstream ``to_bird_output.py``'s ``split('/*')[0]`` cut. The target key is a
question id where upstream's converter uses one and a position otherwise. Every changed or
no-statement position is recorded.
"""

import json
import os
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
SUFFIX = "\t----- bird -----\t"
UPSTREAM_SUBSTITUTE = " "

JSON_FILES = {
    "alpha-sql-dev.json": "id",
    "predict_dev-codes-1b-bird.json": "position",
    "predict_dev-codes-1b-bird-with-evidence.json": "position",
    "predict_dev-codes-3b-bird.json": "position",
    "predict_dev-codes-3b-bird-with-evidence.json": "position",
    "predict_dev-codes-7b-bird.json": "position",
    "predict_dev-codes-7b-bird-with-evidence.json": "position",
    "predict_dev-codes-15b-bird.json": "position",
    "predict_dev-codes-15b-bird-with-evidence.json": "position",
}
LINE_FILES = {
    "csc-sql-7b.sql": "position",
    "csc-sql-32b.sql": "position",
    "gsr-gpt-4o.sql": "position",
    "rsl-sql-deepseek.txt": "position",
    "rsl-sql-gpt-4o.txt": "position",
}
DAIL_FILES = {
    "dail-sql-gpt-4-7shot-mask-thr-0.8.txt": "id",
    "dail-sql-gpt-4-7shot-mask-thr-0.85.txt": "id",
    "dail-sql-gpt-4-7shot-questionmask.txt": "id",
    "dail-sql-gpt-4-9shot-mask-thr.txt": "id",
    "dail-sql-gpt-4-9shot-questionmask.txt": "id",
}
ATLAS_FILES = {"atlas-core-20260301.sql", "atlas-core-20260324.sql"}


def write_changed(document: dict) -> None:
    target = WORK / "out/predictions-readable.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


def read_json(source: Path, name: str, keying: str) -> dict:
    shipped = json.loads(source.read_text(encoding="utf-8"))
    changed = sorted((key for key, value in shipped.items() if not isinstance(value, str)), key=int)
    readable = {
        key: (value if isinstance(value, str) else UPSTREAM_SUBSTITUTE)
        for key, value in shipped.items()
    }
    no_statement = sorted(
        (
            key
            for key, value in readable.items()
            if not value.split(SUFFIX, 1)[0].strip()
            or value.split(SUFFIX, 1)[0].strip() in {"0", "SELECT"}
        ),
        key=int,
    )
    return {
        "file": name,
        "source": f"data/preds/{name}",
        "target": f"data/preds-run/{name}.json",
        "source_shape": "JSON object",
        "keyed_by": keying,
        "entries": len(readable),
        "non_string_entries_replaced": changed,
        "entries_with_no_statement": no_statement,
        "statement_text_changed_positions": [],
    }, readable


def read_lines(source: Path, name: str, keying: str, dail: bool, atlas: bool) -> tuple[dict, dict]:
    lines = source.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1534:
        raise SystemExit(f"{name}: expected 1,534 lines, found {len(lines)}")
    old_entries = json.loads((WORK / "data/dev/dev_20240627/dev.json").read_text(encoding="utf-8"))
    database_matches = 0
    raw_statements = []
    if atlas:
        for position, line in enumerate(lines):
            sql, separator, database = line.rpartition("\t")
            if not separator or database != old_entries[position]["db_id"]:
                raise SystemExit(f"{name}: line {position} does not name its dev database")
            raw_statements.append(sql)
            database_matches += 1
    else:
        raw_statements = lines
    statements = [raw.split("/*", 1)[0] if dail else raw for raw in raw_statements]
    keys = (
        [
            str(entry["question_id"])
            for entry in json.loads(
                (WORK / "data/dev/dev_20240627/dev.json").read_text(encoding="utf-8")
            )
        ]
        if keying == "id"
        else [str(position) for position in range(len(lines))]
    )
    readable = dict(zip(keys, statements, strict=True))
    changed = [
        key
        for key, before, after in zip(keys, raw_statements, statements, strict=True)
        if before != after
    ]
    no_statement = sorted(
        (
            key
            for key, value in readable.items()
            if not value.strip() or value.strip() in {"0", "SELECT"}
        ),
        key=int,
    )
    return {
        "file": name,
        "source": f"data/preds/{name}",
        "target": f"data/preds-run/{name}.json",
        "source_shape": "one SQL per line",
        "keyed_by": keying,
        "entries": len(readable),
        "non_string_entries_replaced": [],
        "entries_with_no_statement": no_statement,
        "statement_text_changed_positions": changed,
        "dail_upstream_comment_cut": dail,
        "atlas_database_suffix_matches": database_matches if atlas else None,
    }, readable


def main() -> None:
    source_dir = WORK / "data/preds"
    target_dir = WORK / "data/preds-run"
    target_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for name, keying in JSON_FILES.items():
        record, readable = read_json(source_dir / name, name, keying)
        (target_dir / f"{name}.json").write_text(
            json.dumps(readable, indent=1) + "\n", encoding="utf-8"
        )
        records.append(record)
    for name, keying in {**LINE_FILES, **DAIL_FILES}.items():
        record, readable = read_lines(
            source_dir / name, name, keying, dail=name in DAIL_FILES, atlas=False
        )
        (target_dir / f"{name}.json").write_text(
            json.dumps(readable, indent=1) + "\n", encoding="utf-8"
        )
        records.append(record)
    for name in ATLAS_FILES:
        record, readable = read_lines(source_dir / name, name, "position", dail=False, atlas=True)
        (target_dir / f"{name}.json").write_text(
            json.dumps(readable, indent=1) + "\n", encoding="utf-8"
        )
        records.append(record)
    write_changed({"reading": "Prediction files in the form the runs read.", "files": records})
    for record in records:
        changed = record.get(
            "statement_text_changed_positions", record.get("statement_text_changed", [])
        )
        print(
            f"{record['file']}: {record['entries']} entries, keyed {record['keyed_by']}, "
            f"no statement {len(record['entries_with_no_statement'])}, "
            f"text changed {len(changed)}"
        )


if __name__ == "__main__":
    main()
