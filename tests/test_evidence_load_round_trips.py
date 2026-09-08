"""Every record of both sandboxes, read back from its own JSON and hashed again.

``record_json`` writes a record out and puts two hashes at the end of it: ``result_hash``
over the canonical rendering of the result, and ``record_hash`` over the document with
``result_hash`` already in it and itself not yet in it. ``attestql.evidence.load`` reads the
document back and takes both again, which is what lets a page state "recomputed from this
JSON: match" beside a hash rather than repeating a number the file gave it.

The reading is exercised over real records rather than constructed ones, on both engines,
because what it has to survive is every value an audit actually produces: a SQLite record
whose columns carry storage classes and states no session preconditions, and a PostgreSQL
record that states seven of them. A round trip that only ever saw one engine's records would
be a round trip nobody had shown to be about the format.
"""

from __future__ import annotations

import io
import json
import os
from collections.abc import Iterator
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.cli import AuditOptions, main, run_audit
from attestql.audit.compare import GOLD_RECORD_FILE, SECOND_RECORD_FILE
from attestql.audit.postgres import PostgresBackend
from attestql.evidence.load import UnreadableRecord, load_record

REPOSITORY = Path(__file__).resolve().parent.parent
SANDBOX = REPOSITORY / "tools" / "audit-sandbox"
SANDBOX_DSN = "ATTESTQL_AUDIT_DSN"

DATA_AS_OF = datetime(2026, 9, 2, tzinfo=UTC)
"""The fixture is loaded from one file and never changes under a run, so one instant
describes the data every record here is about."""

RECORDS = (GOLD_RECORD_FILE, SECOND_RECORD_FILE)


class Lines:
    """A writer that keeps what it was given, which is what a run needs and no test reads."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def line(self, text: str) -> None:
        self.written.append(text)


def records(audit: Path) -> Iterator[Path]:
    """Every evidence record the run wrote, in the order a reader would open them."""
    found = sorted(path for path in audit.rglob("*.json") if path.name in RECORDS)
    assert found, f"{audit} holds no evidence record"
    yield from found


def document(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def round_trips(path: Path) -> None:
    """One record: both hashes taken again from the file, against what the file states."""
    stated = document(path)
    loaded = load_record(stated)

    assert loaded.result_hash.stated == stated["result_hash"]
    assert loaded.result_hash.recomputed == stated["result_hash"], path
    assert loaded.record_hash.recomputed == stated["record_hash"], path
    assert loaded.result_hash.match and loaded.record_hash.match
    assert len(loaded.result.rows) == stated["row_count"]
    assert (
        loaded.serialization.version == cast("dict[str, str]", stated["serialization"])["version"]
    )


@pytest.mark.sandbox_sqlite
def test_every_record_of_the_sqlite_sandbox_re_hashes_to_what_it_states(
    tmp_path: Path,
) -> None:
    """The packaged sandbox, audited by ``attestql demo``: ten records over six questions."""
    sandbox = tmp_path / "sandbox"
    with redirect_stdout(io.StringIO()):
        assert main(["demo", "--out", str(sandbox)]) == 1

    written = list(records(sandbox / "audit"))

    assert len(written) == 10, "two records for each of four comparisons, one for each gold"
    for path in written:
        round_trips(path)


@pytest.mark.sandbox
def test_every_record_of_the_postgresql_sandbox_re_hashes_to_what_it_states(
    sandbox_backend: PostgresBackend, tmp_path: Path
) -> None:
    """The same reading over records that state the seven session preconditions.

    A PostgreSQL record renders numerics and timestamps this engine's own way (an interval
    reaches the record as the text the engine printed, under the ``str`` tag), so it is the
    half of the round trip that exercises the tags the SQLite sandbox has none of.
    """
    audit = tmp_path / "audit"
    run_audit(
        AuditOptions(
            dsn=os.environ[SANDBOX_DSN],
            questions=SANDBOX / "questions.json",
            predictions=SANDBOX / "predictions.json",
            out=audit,
            data_as_of=DATA_AS_OF,
        ),
        sandbox_backend,
        Lines(),
    )

    written = list(records(audit))

    assert written, "the sandbox run wrote records"
    for path in written:
        round_trips(path)
        settings = cast("dict[str, Any]", document(path)["session_settings_in_force"])
        assert settings["time_zone"], "a PostgreSQL record states its session"


@pytest.mark.sandbox_sqlite
def test_a_cell_tagged_with_a_type_the_reading_has_no_rule_for_is_refused(
    tmp_path: Path,
) -> None:
    """No fallback and no best effort: a tag nobody stated a reading for is refused.

    A reading that guessed would produce a hash that differs from the recorded one for a
    reason no reader could find, which is the one thing the recomputed line exists to rule
    out.
    """
    sandbox = tmp_path / "sandbox"
    with redirect_stdout(io.StringIO()):
        assert main(["demo", "--out", str(sandbox)]) == 1
    path = sandbox / "audit" / "q879" / GOLD_RECORD_FILE
    stated = document(path)
    rows = cast("list[list[dict[str, Any]]]", cast("dict[str, Any]", stated["result"])["rows"])
    rows[0][0]["type"] = "money"

    with pytest.raises(UnreadableRecord, match="money"):
        load_record(stated)
