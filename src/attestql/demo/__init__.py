"""The SQLite sandbox the tool audits itself on, carried inside the package.

These three files lived under ``tools/audit-sandbox-sqlite/`` and a person who installed the
wheel from PyPI had none of them: the command the README opens with names a fixture, a
question file and a prediction file, and nothing on that machine held any of the three. They
are package data now, so ``attestql demo`` writes all three wherever it is told and audits
them, and the gate audits the same bytes the wheel ships rather than a second copy of them
that a release could leave behind.

A SQLite database is a file, which is why the whole sandbox is this and why the tests over it
are never skipped: there is nothing to start, no port to hold, no login to create and no
credential anywhere. The builder below writes the file, the audit opens it read-only, and
whoever ran it deletes the directory.

The golds for 1029, 879 and 207 are BIRD Mini-Dev's own, reproduced because the defect being
replayed is in that shipped gold; ``questions.json`` states the attribution and NOTICE records
the licence. The rows those statements run against are this repository's own synthetic fixture
and hold nothing of BIRD's.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

FIXTURE_SQL = Path(__file__).with_name("fixture.sql")
"""The tables and the rows, in SQLite, and the whole of what the built file holds."""

QUESTIONS_FILE = Path(__file__).with_name("questions.json")
PREDICTIONS_FILE = Path(__file__).with_name("predictions.json")
"""The golds and their corrections, beside the fixture. Named here so that a caller reads
them from one place and a change to either file is a change to every run over it."""

FIXTURE_FILE = "fixture.sqlite"
"""What the built database is called under the output directory."""


def build_fixture(directory: Path) -> Path:
    """Write ``fixture.sql`` into a fresh SQLite file under that directory and return it.

    The one builder. ``attestql demo`` calls it, the command line under
    ``tools/audit-sandbox-sqlite/`` calls it and so do the sandbox tests, so the file a person
    opens by hand and the file the gate audits are built by the same statements.

    The file is rebuilt from scratch every time: an existing one is removed first, so a fixture
    edited since the last build cannot be audited without being rebuilt, and a half-written
    file from an interrupted build is never read as a fixture.
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


def write_inputs(directory: Path) -> tuple[Path, Path]:
    """Copy the questions and the predictions into that directory and return the two paths.

    A run is given files and never this package's own paths, so that the command a reader is
    told to rerun names files they can open, edit and hand to another tool, and so that the
    installed package is read and not written to. Both are overwritten every time: they are
    the demo's own copies, and a demo that audited an edited one would not be the demo.
    """
    directory.mkdir(parents=True, exist_ok=True)
    questions = directory / QUESTIONS_FILE.name
    predictions = directory / PREDICTIONS_FILE.name
    shutil.copyfile(QUESTIONS_FILE, questions)
    shutil.copyfile(PREDICTIONS_FILE, predictions)
    return questions, predictions


__all__ = [
    "FIXTURE_FILE",
    "FIXTURE_SQL",
    "PREDICTIONS_FILE",
    "QUESTIONS_FILE",
    "build_fixture",
    "write_inputs",
]
