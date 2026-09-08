"""Verify the question, gold and database digests this measurement reads."""

import hashlib
import json
import os
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
DIGESTS = {
    "data/dev/dev_20240627/dev.json": "630272f2b1c44d8cef2c3b246f623355cf0bbc1e832c81061df895530dfc2f06",
    "data/dev/dev_20240627/dev.sql": "42087d70ed96496b2746a7453e530155076564df127acd1e87d5fa710b6a3805",
    "data/hf/dev_20251106-00000-of-00001.json": "ffd8018378ddb1a8794753e0a31cfc81862ff7318a5184c22f3dc4ce03a03feb",
}
DATABASES = {
    "california_schools": "986817d793479801ed55133e55aa27e335422c0cd3866b54a3d6317b7c5f09c1",
    "card_games": "c98bdb57fe7474da798b407785544b9af0daaad5d61fd21e2a73309493bc1227",
    "codebase_community": "92101be6d2a9f6adceea59d38f6d1c556087f9eea1432432a21268cb1348036d",
    "debit_card_specializing": "b3d149ad05746dbbe5116e229e17e18f09c39db43cf117d9ef3441753608b691",
    "european_football_2": "e4d361dbeec6591a4b315877c0c481da05c8ff5a3d389b34d6e17b6f15bee4e0",
    "financial": "d15d89cdb068a202b6f2b99342af44dffc1d52545b39ceaf62efdc0ba570101e",
    "formula_1": "17185981cd747f6cdc374cb02a6096db3130e6ec2ddc582fe1686a28fb4c4c8a",
    "student_club": "eb89bcfe97eefa386a27904ec5aa15159811a7eac894ec659a36e48fa9f76b77",
    "superhero": "75e94a2c3236ee3bb2c01fb97a1c4b4c1c269bcefd4eab1d04be323d2d0825b1",
    "thrombosis_prediction": "e7e16d74b4731b4b8d33fdbe8c29cd5622620788ce8d1f335631f65fc7cf1db9",
    "toxicology": "f5fa7f21af1ad878ff8fef1b0582b8cb2d7ed63dbac65ff16d2ba05667650c5b",
}


def digest(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hashed.update(block)
    return hashed.hexdigest()


def main() -> None:
    paths = dict(DIGESTS)
    for db, expected in DATABASES.items():
        paths[f"data/dev/dev_databases/{db}/{db}.sqlite"] = expected
    checked = {}
    for relative, expected in paths.items():
        path = WORK / relative
        found = digest(path)
        if found != expected:
            raise SystemExit(f"{relative}: sha256 {found}, expected {expected}")
        checked[relative] = found
    old = json.loads((WORK / "data/dev/dev_20240627/dev.json").read_text())
    new = json.loads((WORK / "data/hf/dev_20251106-00000-of-00001.json").read_text())
    if len(old) != 1534 or len(new) != 1534:
        raise SystemExit("a question copy does not hold 1,534 entries")
    print(f"verified {len(checked)} input digests and 1,534 entries in each question copy")


if __name__ == "__main__":
    main()
