"""Give SQLite a writable directory for a WAL database without changing its bytes.

    MEASURE_WORK=<work-directory> python3 prepare_database.py

``card_games.sqlite`` is published with WAL as its header's read and write versions. SQLite
cannot open a WAL file read-only beside no ``-shm`` sidecar, so AttestQL's identity read fails
with ``attempt to write a readonly database`` when the published inputs are read-only. The work
copy is byte-identical and SQLite makes its temporary sidecars beside it.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
DATABASES = WORK / "data/dev/dev_databases"
OUT = WORK / "out"


def digest(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hashed.update(block)
    return hashed.hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    copied = {}
    for source in sorted(DATABASES.glob("*/*.sqlite")):
        database = source.parent.name
        with source.open("rb") as handle:
            handle.seek(18)
            versions = handle.read(2)
        if versions != b"\x02\x02":
            continue
        target = WORK / "data/dev/copies" / database / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(source, target)
            target.chmod(0o444)
        source_digest, target_digest = digest(source), digest(target)
        if source_digest != target_digest:
            raise SystemExit(f"{database}: the work copy is not byte-identical")
        copied[database] = {
            "source": str(source.relative_to(WORK)),
            "copy": str(target.relative_to(WORK)),
            "sha256": target_digest,
            "reason": "WAL header; SQLite needs a writable directory for its sidecars",
        }
    document = {
        "reading": (
            "Byte-identical work copies of WAL databases, made only so SQLite can create its "
            "temporary sidecars outside the read-only inputs. Every digest is asserted."
        ),
        "copies": copied,
    }
    (OUT / "database-copies.json").write_text(
        json.dumps(document, indent=1) + "\n", encoding="utf-8"
    )
    print(f"work copies: {sorted(copied)}")


if __name__ == "__main__":
    main()
