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
import sqlite3
from collections.abc import Iterator
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.cli import AuditOptions, main, run_audit
from attestql.audit.compare import GOLD_RECORD_FILE, SECOND_RECORD_FILE
from attestql.audit.engines import SQLITE
from attestql.audit.postgres import PostgresBackend
from attestql.evidence.load import UnreadableRecord, load_record
from attestql.evidence.serialize import UndecodedText

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


def _write(path: Path, document: object) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


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


SITE_RECORDS = REPOSITORY / "tools" / "site" / "data" / "bird-dev-sqlite"


def test_a_record_written_under_the_earlier_layout_still_re_hashes() -> None:
    """The layout version moved when a text value that does not decode became recordable.
    A record written before that states the version it was written under and is rendered
    under that one, so its two hashes are still its own: a reader that re-rendered every
    record under today's rules would report every record ever written as a mismatch."""
    written = sorted(SITE_RECORDS.rglob("evidence-gold.json"))
    assert written, "the site data holds records from a real run"
    earlier = [
        path
        for path in written
        if cast("dict[str, str]", document(path)["serialization"])["version"]
        in {"attestql/audit/2", "attestql/audit/3"}
    ]
    assert earlier, "those records were written under a layout before this one"
    for path in earlier[:20]:
        round_trips(path)


def test_a_text_value_that_did_not_decode_round_trips_as_its_bytes(tmp_path: Path) -> None:
    """The cell a benchmark database holds and Python's decoder refuses: it is recorded as
    the bytes it is, read back as the same bytes, and hashes to what the record states."""
    path = tmp_path / "undecodable.sqlite"
    connection = sqlite3.connect(path)
    with connection:
        connection.execute("CREATE TABLE t (a TEXT)")
        connection.execute("INSERT INTO t VALUES (CAST(x'ff' AS TEXT)), ('ff')")
    connection.close()
    _write(
        tmp_path / "questions.json",
        [
            {
                "question_id": 1,
                "db_id": "t",
                "question": "Which ones?",
                "evidence": "",
                "SQL": "SELECT a FROM t ORDER BY a",
                "difficulty": "simple",
            }
        ],
    )
    _write(tmp_path / "predictions.json", {"1": "SELECT a FROM t ORDER BY a DESC"})
    audit = tmp_path / "audit"
    run_audit(
        AuditOptions(
            dsn=str(path),
            questions=tmp_path / "questions.json",
            predictions=tmp_path / "predictions.json",
            out=audit,
            engine=SQLITE,
        ),
        SQLITE.connect(str(path), scratch="temp"),
        Lines(),
    )
    written = list(records(audit))
    assert len(written) == 2, "the gold and the prediction, which order the rows otherwise"
    for record in written:
        round_trips(record)
    stated = document(written[0])
    rows = cast("list[list[dict[str, Any]]]", cast("dict[str, Any]", stated["result"])["rows"])
    assert sorted(cell["type"] for row in rows for cell in row) == ["str", "text-bytes"]
    loaded = [value for row in load_record(stated).result.rows for value in row]
    undecoded = [value for value in loaded if type(value) is UndecodedText]
    assert undecoded == [UndecodedText(b"\xff")], "the bytes come back as those bytes"
    assert "ff" in loaded, "and the text that decoded is still text"


@pytest.mark.sandbox
def test_a_non_finite_float_receives_a_verdict_and_its_record_round_trips(
    sandbox_backend: PostgresBackend, tmp_path: Path
) -> None:
    """The product path the NaN rendering exists for.

    A PostgreSQL ``float8`` reaches a record as the decimal the server printed for it, so
    ``'NaN'::float8`` reaches one as ``Decimal('NaN')``. Until 2026-09-11 the rendering refused
    that value, so hashing the result raised and a question holding a NaN reported an error
    instead of the verdict the comparison had already reached.

    Two questions, because they show different halves of it. The first pair is identical and has
    to be EQUAL, which is the verdict that was being lost. The second pair differs, which is what
    makes the run write the records, so the round trip is taken over records that really hold a
    NaN rather than over constructed ones.
    """
    same = "SELECT v FROM (VALUES ('NaN'::float8), (1.5::float8), ('Infinity'::float8)) AS t(v)"
    gold = "SELECT v FROM (VALUES ('NaN'::float8), (1.5::float8)) AS t(v)"
    predicted = "SELECT v FROM (VALUES ('NaN'::float8)) AS t(v)"
    _write(
        tmp_path / "questions.json",
        [
            {
                "question_id": 1,
                "db_id": "european_football_2",
                "question": "Which values?",
                "evidence": "",
                "SQL": same,
                "difficulty": "simple",
            },
            {
                "question_id": 2,
                "db_id": "european_football_2",
                "question": "Which values, again?",
                "evidence": "",
                "SQL": gold,
                "difficulty": "simple",
            },
        ],
    )
    _write(tmp_path / "predictions.json", {"1": same, "2": predicted})
    audit = tmp_path / "audit"
    run_audit(
        AuditOptions(
            dsn=os.environ[SANDBOX_DSN],
            questions=tmp_path / "questions.json",
            predictions=tmp_path / "predictions.json",
            out=audit,
            data_as_of=DATA_AS_OF,
        ),
        sandbox_backend,
        Lines(),
    )

    summary = document(audit / "summary.json")
    assert summary["errors"] == [], f"a NaN is not an error: {summary['errors']}"
    assert cast("dict[str, int]", summary["verdicts"]) == {"EQUAL": 1, "NOT_EQUAL": 1}, summary[
        "verdicts"
    ]
    assert cast("dict[str, Any]", summary["settings"])["serialization"] == "attestql/audit/4"

    written = list(records(audit))
    for path in written:
        round_trips(path)
    holds_a_nan = [
        path
        for path in written
        if any(
            cell.get("value") == "NaN"
            for row in cast(
                "list[list[dict[str, Any]]]",
                cast("dict[str, Any]", document(path)["result"])["rows"],
            )
            for cell in row
        )
    ]
    assert holds_a_nan, "the records the run wrote hold the NaN the question returned"
