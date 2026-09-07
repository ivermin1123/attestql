"""Check what the phase assumed about the inputs, and write down what is actually true.

    MEASURE_WORK=<work-directory> python3 check_inputs.py

Three checks, each recorded in ``out/inputs.json`` rather than only asserted:

1. The eleven ``dev_databases/<db>/<db>.sqlite`` of dev.zip against Mini-Dev's eleven, by sha256
   and, where the digests differ, by schema, by row count per table and by the rows themselves.
   The phase was written expecting them to be the same files. They are not, so the run uses
   dev.zip's own, which is what BIRD dev's golds are answered against.
2. ``dev.sql`` against ``dev.json``: 1,534 lines, gold text and db_id matching position for
   position, so that BIRD's own evaluator can be given the gold file it expects.
3. The two copies of the question set hold the same 1,534 ids in the same order, which is what
   lets one position-keyed prediction file be compared against both.

The Mini-Dev copy is read from ``MINIDEV_DATABASES`` if it is set and present, and check 1 is
recorded as not run otherwise: the comparison is a finding about BIRD's publications, not a
precondition of this measurement.
"""

import hashlib
import json
import os
import sqlite3
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
DEV = WORK / "data/dev/dev_databases"
MINIDEV = Path(
    os.environ.get(
        "MINIDEV_DATABASES",
        str(
            Path.home()
            / ".cache/attestql-measure/minidev-sqlite/data/zip/minidev/MINIDEV/dev_databases"
        ),
    )
)
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


def digest(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hashed.update(block)
    return hashed.hexdigest()


def tables(path: Path) -> list[str]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    names = [
        row[0]
        for row in connection.execute(
            "select name from sqlite_master where type='table' order by name"
        )
    ]
    connection.close()
    return names


def counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    # The names come from this file's own sqlite_master and no parameter can carry an
    # identifier, so the count statement is built from them.
    out = {
        name: connection.execute(f'select count(*) from "{name}"').fetchone()[0]  # noqa: S608
        for name in tables(path)
    }
    connection.close()
    return out


def row_digests(path: Path) -> dict[str, str]:
    """One digest per table over its rows as stored, read in table-scan order.

    ``text_factory`` is bytes so that a text cell and the same characters stored otherwise do
    not collapse into one string; the table names are read first, with the default factory,
    because a bytes name cannot be quoted into a statement.
    """
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    names = tables(path)
    connection.text_factory = bytes
    out = {}
    for name in names:
        hashed = hashlib.sha256()
        for row in connection.execute(f'select * from "{name}"'):  # noqa: S608  (as above)
            hashed.update(repr(row).encode())
        out[name] = hashed.hexdigest()
    connection.close()
    return out


def compare_databases() -> dict:
    if not MINIDEV.is_dir():
        return {"run": False, "why": f"{MINIDEV} is not present"}
    same, differ = [], {}
    for db in DATABASES:
        ours, theirs = DEV / db / f"{db}.sqlite", MINIDEV / db / f"{db}.sqlite"
        if digest(ours) == digest(theirs):
            same.append(db)
            continue
        our_counts, their_counts = counts(ours), counts(theirs)
        entry = {
            "sha256_dev": digest(ours),
            "sha256_minidev": digest(theirs),
            "same_tables": tables(ours) == tables(theirs),
            "row_counts_differ": {
                name: {"dev": our_counts.get(name), "minidev": their_counts.get(name)}
                for name in sorted(set(our_counts) | set(their_counts))
                if our_counts.get(name) != their_counts.get(name)
            },
        }
        if not entry["row_counts_differ"]:
            ours_rows, theirs_rows = row_digests(ours), row_digests(theirs)
            entry["tables_whose_rows_differ"] = sorted(
                name for name in ours_rows if ours_rows[name] != theirs_rows.get(name)
            )
        differ[db] = entry
    return {"run": True, "identical": same, "different": differ}


def main() -> None:
    entries = json.loads((WORK / "data/dev/dev_20240627/dev.json").read_text())
    new = json.loads((WORK / "data/hf/dev_20251106-00000-of-00001.json").read_text())
    lines = [
        line.rstrip("\n")
        for line in (WORK / "data/dev/dev_20240627/dev.sql").open()
        if line.strip()
    ]
    gold_file = {"lines": len(lines), "entries": len(entries), "mismatched_positions": []}
    for position, (entry, line) in enumerate(zip(entries, lines, strict=True)):
        sql, _, db_id = line.rpartition("\t")
        if db_id.strip() != entry["db_id"] or " ".join(sql.split()) != " ".join(
            entry["SQL"].split()
        ):
            gold_file["mismatched_positions"].append(position)
    document = {
        "reading": (
            "What the inputs are, checked rather than assumed. databases_against_minidev is a "
            "finding about BIRD's publications: five of the eleven files differ between dev.zip "
            "and minidev.zip, three by row count and two by the rows themselves, so a "
            "measurement of BIRD dev must use dev.zip's own."
        ),
        "dev_json_entries": len(entries),
        "dev_1106_entries": len(new),
        "same_ids_in_the_same_order": [e["question_id"] for e in entries]
        == [e["question_id"] for e in new],
        "dev_sql_against_dev_json": gold_file,
        "database_sha256": {db: digest(DEV / db / f"{db}.sqlite") for db in DATABASES},
        "databases_against_minidev": compare_databases(),
    }
    if gold_file["mismatched_positions"] or not document["same_ids_in_the_same_order"]:
        raise SystemExit(f"an input is not what the report states: {json.dumps(document)[:400]}")
    (WORK / "out" / "inputs.json").write_text(json.dumps(document, indent=1) + "\n")
    compared = document["databases_against_minidev"]
    print(
        "inputs checked:",
        len(entries),
        "questions,",
        (
            f"{len(compared['identical'])} of 11 databases identical to Mini-Dev's"
            if compared["run"]
            else "Mini-Dev's databases not present, not compared"
        ),
    )


if __name__ == "__main__":
    main()
