"""Download each selected prediction file only when absent, then verify every digest."""

import hashlib
import json
import os
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path(os.environ["MEASURE_WORK"])


def digest(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hashed.update(block)
    return hashed.hexdigest()


def main() -> None:
    sources = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    target = WORK / "data/preds"
    target.mkdir(parents=True, exist_ok=True)
    for record in sources["accepted"]:
        path = target / record["name"]
        if not path.exists():
            urllib.request.urlretrieve(record["url"], path)  # noqa: S310
        found = digest(path)
        if found != record["sha256"]:
            raise SystemExit(f"{record['name']}: sha256 {found}, expected {record['sha256']}")
        print(f"{record['name']}: {found}")


if __name__ == "__main__":
    main()
