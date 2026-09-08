"""Verify the two database publications and count every differing table.

    MEASURE_WORK=<work> ATTESTQL_INPUTS=<inputs> python3 verify_inputs.py

The digests and the five differing databases are stated in the sibling dev measurement's
``inputs.json`` and checked again here. This lane owns only ``tables.json``, which adds the
row count of every table in each differing database and records the three gold sets used below.
"""

import hashlib
import json
import os
import sqlite3
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
INPUTS = Path(os.environ["ATTESTQL_INPUTS"])
DEV = WORK / "data/dev/dev_databases"
MINIDEV = WORK / "data/zip/minidev/MINIDEV/dev_databases"
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
EXPECTED = {
    "california_schools": (
        "986817d793479801ed55133e55aa27e335422c0cd3866b54a3d6317b7c5f09c1",
        "c0903eec662e63068fd1d14403d3d6c1d473287fc10c4356333ea58f878db983",
    ),
    "card_games": (
        "c98bdb57fe7474da798b407785544b9af0daaad5d61fd21e2a73309493bc1227",
        "c98bdb57fe7474da798b407785544b9af0daaad5d61fd21e2a73309493bc1227",
    ),
    "codebase_community": (
        "92101be6d2a9f6adceea59d38f6d1c556087f9eea1432432a21268cb1348036d",
        "92101be6d2a9f6adceea59d38f6d1c556087f9eea1432432a21268cb1348036d",
    ),
    "debit_card_specializing": (
        "b3d149ad05746dbbe5116e229e17e18f09c39db43cf117d9ef3441753608b691",
        "b3d149ad05746dbbe5116e229e17e18f09c39db43cf117d9ef3441753608b691",
    ),
    "european_football_2": (
        "e4d361dbeec6591a4b315877c0c481da05c8ff5a3d389b34d6e17b6f15bee4e0",
        "f72f5c9b990371417288a67b27a02e601ef904d45525c2c9f7931fb01001c536",
    ),
    "financial": (
        "d15d89cdb068a202b6f2b99342af44dffc1d52545b39ceaf62efdc0ba570101e",
        "d15d89cdb068a202b6f2b99342af44dffc1d52545b39ceaf62efdc0ba570101e",
    ),
    "formula_1": (
        "17185981cd747f6cdc374cb02a6096db3130e6ec2ddc582fe1686a28fb4c4c8a",
        "79770caf966707e35516fa566e24b40ae515c74ec1ec4631235245645b87b24d",
    ),
    "student_club": (
        "eb89bcfe97eefa386a27904ec5aa15159811a7eac894ec659a36e48fa9f76b77",
        "eb89bcfe97eefa386a27904ec5aa15159811a7eac894ec659a36e48fa9f76b77",
    ),
    "superhero": (
        "75e94a2c3236ee3bb2c01fb97a1c4b4c1c269bcefd4eab1d04be323d2d0825b1",
        "75e94a2c3236ee3bb2c01fb97a1c4b4c1c269bcefd4eab1d04be323d2d0825b1",
    ),
    "thrombosis_prediction": (
        "e7e16d74b4731b4b8d33fdbe8c29cd5622620788ce8d1f335631f65fc7cf1db9",
        "87583183c3dc472fba04de702965560a9d7c0a548836613f242317e0eeb83f00",
    ),
    "toxicology": (
        "f5fa7f21af1ad878ff8fef1b0582b8cb2d7ed63dbac65ff16d2ba05667650c5b",
        "35ef27ae6bdfda530e125ed369666ac0abb8bc8c0bcc0ad09407f547ecb61a93",
    ),
}
GOLD_SETS = {
    "dev-20240627": (WORK / "data/dev/dev_20240627/dev.json", 700),
    "dev-20251106": (
        WORK / "data/hf/dev_20251106-00000-of-00001.json",
        700,
    ),
    "minidev-hf": (WORK / "data/hf/mini_dev_sqlite-00000-of-00001.json", 237),
}
DIFFERING = [
    "california_schools",
    "european_football_2",
    "formula_1",
    "thrombosis_prediction",
    "toxicology",
]


def digest(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hashed.update(block)
    return hashed.hexdigest()


def table_counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    names = [
        row[0]
        for row in connection.execute(
            "select name from sqlite_master where type='table' order by name"
        )
    ]
    # Identifiers come from this database's own sqlite_master and cannot be bound parameters.
    counts = {
        name: connection.execute(f'select count(*) from "{name}"').fetchone()[0]  # noqa: S608
        for name in names
    }
    connection.close()
    return counts


def main() -> None:
    databases: dict[str, dict] = {}
    for db in DATABASES:
        dev = DEV / db / f"{db}.sqlite"
        minidev = MINIDEV / db / f"{db}.sqlite"
        found = (digest(dev), digest(minidev))
        if found != EXPECTED[db]:
            raise SystemExit(f"database digest mismatch: {db} {found}")
        entry = {
            "sha256_dev": found[0],
            "sha256_minidev": found[1],
            "identical": found[0] == found[1],
        }
        if db in DIFFERING:
            dev_counts, minidev_counts = table_counts(dev), table_counts(minidev)
            if list(dev_counts) != list(minidev_counts):
                raise SystemExit(f"table list differs: {db}")
            entry["tables"] = {
                name: {"dev": dev_counts[name], "minidev": minidev_counts[name]}
                for name in dev_counts
            }
        databases[db] = entry

    gold_sets = {}
    for name, (path, expected) in GOLD_SETS.items():
        entries = json.loads(path.read_text())
        on_differing = sum(entry["db_id"] in DIFFERING for entry in entries)
        if on_differing != expected:
            raise SystemExit(f"{name}: expected {expected} golds, found {on_differing}")
        gold_sets[name] = {
            "path": str(path),
            "sha256": digest(path),
            "entries": len(entries),
            "on_differing_databases": on_differing,
        }

    document = {
        "reading": (
            "All 22 database files were digested. Six pairs are byte-identical and the five "
            "named pairs differ; every table of each differing pair is counted on both copies."
        ),
        "databases": databases,
        "identical": [db for db in DATABASES if databases[db]["identical"]],
        "different": [db for db in DATABASES if not databases[db]["identical"]],
        "gold_sets": gold_sets,
    }
    output = WORK / "out" / "tables.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(
        f"inputs verified: {len(document['identical'])} identical, "
        f"{len(document['different'])} differing"
    )


if __name__ == "__main__":
    main()
