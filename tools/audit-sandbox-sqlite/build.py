"""Build the SQLite audit sandbox fixture into a file a person can open with ``sqlite3``.

``attestql demo --out <directory>`` builds the same file and audits it in one command, and it
is what a reader who wants the run itself should type. This stays for the other half of the
sandbox: opening the database by hand, reading the few rows the three defects turn on, and
auditing it with flags of one's own.

    python tools/audit-sandbox-sqlite/build.py <output-directory>

The fixture, the questions and the builder live in ``attestql.demo``, where an installed wheel
carries them too, so the file this writes and the file the gate audits are the same statements
over the same bytes.

The output directory must be outside the repository. The built file is not a repository
artifact: it is a few kilobytes of the same rows ``fixture.sql`` writes out, and the file is
what the SQL says it is.
"""

from __future__ import annotations

import sys
from pathlib import Path

from attestql.demo import QUESTIONS_FILE, build_fixture

REPOSITORY = Path(__file__).resolve().parents[2]


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
