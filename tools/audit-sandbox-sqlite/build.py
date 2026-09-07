"""Build the SQLite audit sandbox fixture from ``fixture.sql``, outside the repository.

The SQLite half of ``tools/audit-sandbox/run.sh``, and much shorter than it, because there is
nothing to start and nothing to tear down. A SQLite database is a file: this writes it, the
audit opens it read-only, and whoever ran this deletes the directory. There is no container,
no port, no server to wait for, no login to create and no credential anywhere, which is why
the tests that use it are not skipped when Docker is absent.

    python tools/audit-sandbox-sqlite/build.py <output-directory>

The file is rebuilt from scratch every time: an existing one is removed first, so a fixture
edited since the last build cannot be audited without being rebuilt, and a half-written file
from an interrupted build is never read as a fixture.

The output directory must be outside the repository. The built file is not a repository
artifact: it is a few kilobytes of the same rows ``fixture.sql`` writes out, and the file is
what the SQL says it is.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parent.parent

FIXTURE_SQL = HERE / "fixture.sql"
"""The tables and the rows, in SQLite, and the whole of what the built file holds."""

QUESTIONS_FILE = HERE / "questions.json"
PREDICTIONS_FILE = HERE / "predictions.json"
"""The golds and their corrections, beside the fixture. Named here so that a caller reads
them from one place and a change to either file is a change to every run over it."""

FIXTURE_FILE = "fixture.sqlite"
"""What the built database is called under the output directory."""


def build_fixture(directory: Path) -> Path:
    """Write ``fixture.sql`` into a fresh SQLite file under that directory and return it.

    The one builder. The command line below calls it and so do the sandbox tests, so the file
    a person opens by hand and the file the gate audits are built by the same statements.
    """
    directory = directory.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / FIXTURE_FILE
    path.unlink(missing_ok=True)
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.executescript(FIXTURE_SQL.read_text(encoding="utf-8"))
    finally:
        connection.close()
    return path


def main(argv: list[str]) -> int:
    """Build the fixture where the argument says, and print where it went."""
    if len(argv) != 1:
        print(f"usage: {Path(__file__).name} <output-directory>", file=sys.stderr)
        return 2
    directory = Path(argv[0]).expanduser().resolve()
    if directory == REPOSITORY or REPOSITORY in directory.parents:
        print(f"the output directory must be outside the repository: {directory}", file=sys.stderr)
        return 2
    path = build_fixture(directory)
    print(f"fixture built: {path} ({path.stat().st_size} bytes)")
    print(f"audit it with: attestql audit --engine sqlite --dsn {path} \\")
    print(f"    --questions {QUESTIONS_FILE} --out <directory>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
