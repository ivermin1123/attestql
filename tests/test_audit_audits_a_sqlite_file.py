"""The SQLite backend against real files, and one whole audit over one of them.

Every other backend test in this suite either scripts a connection or needs the container
the PostgreSQL sandbox starts. This one needs neither: a SQLite file is built in
``tmp_path``, audited through the real backend, and thrown away with the directory, so what
is observed here is the engine's own answers and not a fake's.

What the file cannot state is what most of this is about. A column has no declared result
type, so the type a record carries is the storage class the cells came back at; there is no
session to precondition, so the seven settings are absent and nine readings are recorded
instead; there is no role and no grant, so read-only is the file and the envelope over it;
and there is no scratch schema to be given, so the shuffled copies are TEMP tables on a
second connection that the audited one cannot see.
"""

from __future__ import annotations

import gc
import json
import sqlite3
import tempfile
import time
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.backend import (
    READ_THROUGH_PRIVATE_COPY,
    BackendRefused,
    ReadBackDrift,
    StatementTimedOut,
    TableName,
)
from attestql.audit.cli import SUMMARY_FILE, AuditOptions, connect_and_audit
from attestql.audit.compare import ORDERING_KEY_NAMES_NO_COLUMN, bird_ex, record_statement
from attestql.audit.engines import SQLITE
from attestql.audit.parse import StatementRefused
from attestql.audit.smells import NUMERIC_TEXT, SmellSettings, ordering_over_numeric_text
from attestql.audit.sqlite import (
    NOT_IN_THIS_FILE,
    QUALIFIED_NAME_IS_NOT_REACHED,
    UNOBSERVED,
    WITHOUT_A_ROW_IDENTITY,
    SqliteBackend,
)
from attestql.audit.sqlite_statements import PARSER as SQLITE_PARSER
from attestql.audit.sqlite_statements import parse_statement
from attestql.evidence.serialize import (
    SerializationDescriptor,
    UnsupportedValue,
    canonical_type_tag,
    typed_row,
)
from attestql.evidence.types import ENGINE_SQLITE, QuestionMetadata, StatementSource
from attestql.kernel.types import ColumnType, ExecutionLimits, ExecutionResult

TIMEOUT_SECONDS = 10

FIXTURE = """
CREATE TABLE drivers (driverid INTEGER PRIMARY KEY, nationality TEXT);
INSERT INTO drivers VALUES (1, 'Norwegian'), (2, 'Peruvian'), (3, 'Kenyan');

CREATE TABLE results (
    resultid INTEGER PRIMARY KEY,
    driverid INTEGER,
    fastestlapspeed TEXT,
    points REAL,
    untyped
);
INSERT INTO results VALUES
    (1, 2, '259.870', 1.5, 'a'),
    (2, 1, '93.175', 0.5, 'b'),
    (3, 3, NULL, 2.0, 'c');

CREATE TABLE mixed (value);
INSERT INTO mixed VALUES (1), (1.0), ('1'), (NULL);

CREATE TABLE keyed (code TEXT PRIMARY KEY, label TEXT) WITHOUT ROWID;
INSERT INTO keyed VALUES ('a', 'Alpha'), ('b', 'Beta');

CREATE VIEW fast AS SELECT driverid, fastestlapspeed FROM results;
"""
"""One file with everything the readings below need: a text column of numerals, a REAL
column, a column declared with no type at all, a column holding four storage classes, a
relation with no rowid and a view."""


def _build(path: Path, statements: str = FIXTURE) -> Path:
    connection = sqlite3.connect(path)
    with connection:
        connection.executescript(statements)
    connection.close()
    return path


@pytest.fixture
def audited_file(tmp_path: Path) -> Path:
    return _build(tmp_path / "audit.sqlite")


@pytest.fixture
def backend(audited_file: Path) -> SqliteBackend:
    return SqliteBackend.connect(str(audited_file))


def _rows(backend: SqliteBackend, sql: str) -> tuple[tuple[object, ...], ...]:
    return backend.execute(sql, statement_timeout_seconds=TIMEOUT_SECONDS).rows


def _types(backend: SqliteBackend, sql: str) -> list[str]:
    result = backend.execute(sql, statement_timeout_seconds=TIMEOUT_SECONDS)
    return [column.declared_type for column in result.columns]


def _result(columns: Sequence[ColumnType], rows: Sequence[tuple[object, ...]]) -> ExecutionResult:
    """One result as the SQLite backend would have built it, for a reading asked directly."""
    return ExecutionResult(
        columns=tuple(columns),
        rows=tuple(rows),
        backend_identity="SQLite | file=nowhere | size=0",
        limits_in_force=ExecutionLimits(statement_timeout_ms=1000),
        truncated=False,
    )


def test_a_file_that_is_not_there_is_a_refusal_and_not_an_empty_database(tmp_path: Path) -> None:
    """SQLite would create the file rather than refuse, and an audit over a database it just
    made would measure nothing and say every table is missing."""
    with pytest.raises(BackendRefused, match="there is no SQLite file"):
        SqliteBackend.connect(str(tmp_path / "absent.sqlite"))


@pytest.mark.parametrize("directory", ["a?directory", "a#directory"])
def test_a_path_that_would_end_the_uri_early_opens_the_file_that_was_named(
    tmp_path: Path, directory: str
) -> None:
    """A URI filename ends at the first ``?`` or ``#``. Unescaped, a path holding one would
    end there and leave the rest of it in front of ``mode=ro`` in the query, which SQLite
    ignores as a parameter it does not know: the connection would then be read-write over the
    shorter name, and SQLite creates that file when it is not there. So the file that was
    named is the file that is read, the write is still refused, and nothing is created."""
    home = tmp_path / directory
    home.mkdir()
    backend = SqliteBackend.connect(str(_build(home / "audit.sqlite")))

    assert _rows(backend, "SELECT count(*) FROM drivers") == ((3,),)
    with pytest.raises(BackendRefused, match="readonly database"):
        backend.execute(
            "INSERT INTO drivers VALUES (9, 'Probe')", statement_timeout_seconds=TIMEOUT_SECONDS
        )

    assert sorted(entry.name for entry in tmp_path.iterdir()) == [directory]
    assert sorted(entry.name for entry in home.iterdir()) == ["audit.sqlite"]


def test_the_identity_names_the_version_the_file_and_its_size(
    backend: SqliteBackend, audited_file: Path
) -> None:
    identity = backend.identity()

    assert identity.startswith("SQLite ")
    assert f"file={audited_file.resolve()}" in identity
    assert f"size={audited_file.stat().st_size}" in identity
    assert backend.effective_database_role() == "file"


def test_the_session_states_the_nine_readings_and_none_of_the_seven_preconditions(
    backend: SqliteBackend,
) -> None:
    """A SQLite record states no session setting that decides comparability, so the seven are
    absent rather than filled with a value the engine does not hold, and what the file can be
    asked about itself is recorded instead (ADR-0014 point 2)."""
    settings = backend.session_settings()

    assert settings.engine == ENGINE_SQLITE
    assert settings.database_collation is None
    assert (settings.time_zone, settings.date_style, settings.interval_style) == (None, None, None)
    assert (settings.extra_float_digits, settings.work_mem, settings.hash_mem_multiplier) == (
        None,
        None,
        None,
    )
    assert set(settings.recorded) == {
        "sqlite_version",
        "encoding",
        "compile_options",
        "collation_list",
        "case_sensitive_like",
        "reverse_unordered_selects",
        "query_only",
        "journal_mode",
        "data_version",
    }
    assert settings.recorded["query_only"] == "1", "the envelope is what the run held"
    assert "BINARY" in settings.recorded["collation_list"]
    assert settings.recorded["case_sensitive_like"] == "0", (
        "LIKE is case insensitive by default, and the pragma can be set and never read, so "
        "what is recorded is what the file was observed doing"
    )
    assert backend.session_settings() is settings, "read once for a whole run"


def test_each_storage_class_comes_back_as_the_python_type_a_record_can_render(
    backend: SqliteBackend,
) -> None:
    """A REAL becomes the shortest decimal that round-trips it, because the canonical
    serialization states no rendering for a float and because R-SET has to keep a REAL and an
    INTEGER apart."""
    rows = _rows(
        backend,
        "SELECT d.driverid, d.nationality, r.points, r.fastestlapspeed FROM results r "
        "JOIN drivers d ON d.driverid = r.driverid WHERE r.resultid = 3",
    )

    assert rows == ((3, "Kenyan", Decimal("2.0"), None),)
    assert [canonical_type_tag(value) for value in rows[0]] == ["int", "str", "dec", "null"]


def test_a_real_and_an_integer_holding_one_amount_stay_two_values(backend: SqliteBackend) -> None:
    """ADR-0004's storage-class rule, read off the engine rather than asserted about it: the
    file holds ``1`` and ``1.0`` in one column and the comparator keys them apart."""
    rows = _rows(backend, "SELECT value FROM mixed ORDER BY rowid")

    assert rows == ((1,), (Decimal("1.0"),), ("1",), (None,))
    assert len({typed_row(row) for row in rows}) == 4


def test_a_real_keeps_the_digits_the_double_holds_and_no_more(tmp_path: Path) -> None:
    """``repr`` of a Python float is the shortest text that round-trips the double, so the
    decimal built from it is the number the file holds: no digit invented, none lost."""
    path = _build(tmp_path / "reals.sqlite", "CREATE TABLE r (x REAL); INSERT INTO r VALUES (0.1);")
    backend = SqliteBackend.connect(str(path))

    assert _rows(backend, "SELECT x FROM r") == ((Decimal("0.1"),),)
    assert float(Decimal("0.1")) == 0.1


def test_a_blob_is_refused_at_the_value_rather_than_carried_into_a_record(
    tmp_path: Path,
) -> None:
    """The canonical serialization states no rendering for bytes, so a result holding one is
    refused where the value is read, the way the PostgreSQL backend refuses a float its
    server printed unreadably."""
    path = _build(
        tmp_path / "blob.sqlite", "CREATE TABLE b (x BLOB); INSERT INTO b VALUES (x'00');"
    )
    backend = SqliteBackend.connect(str(path))

    with pytest.raises(BackendRefused, match="no rendering"):
        backend.execute("SELECT x FROM b", statement_timeout_seconds=TIMEOUT_SECONDS)
    with pytest.raises(UnsupportedValue):
        canonical_type_tag(b"\x00")


def test_a_column_is_typed_by_the_storage_classes_its_cells_came_back_at(
    backend: SqliteBackend,
) -> None:
    """SQLite types values and not columns, so what a record states about a result column is
    what its cells were observed at: one class name when they agree, the sorted classes
    joined when they do not, and never nothing."""
    assert _types(backend, "SELECT driverid, nationality FROM drivers") == ["INTEGER", "TEXT"]
    assert _types(backend, "SELECT value FROM mixed") == ["INTEGER|NULL|REAL|TEXT"]
    assert _types(backend, "SELECT fastestlapspeed FROM results WHERE resultid = 3") == ["NULL"]


def test_a_result_with_no_rows_says_its_column_was_observed_at_no_class(
    backend: SqliteBackend,
) -> None:
    """A storage class is a property of a value, so a column that returned none was observed
    at none. The field is never empty: a reader has to be told this was measured and came
    back with nothing rather than left out."""
    assert _types(backend, "SELECT nationality FROM drivers WHERE 0") == [UNOBSERVED]


def test_a_write_is_refused_by_the_file_and_by_the_envelope_over_it(
    backend: SqliteBackend,
) -> None:
    """Read-only twice over: ``mode=ro`` is the file-level guarantee and ``query_only`` is the
    envelope, and both refuse with SQLite's own words."""
    for sql in (
        "INSERT INTO drivers VALUES (9, 'Probe')",
        "UPDATE drivers SET nationality = 'Probe'",
        "CREATE TABLE probe (x INTEGER)",
    ):
        with pytest.raises(BackendRefused, match="readonly database"):
            backend.execute(sql, statement_timeout_seconds=TIMEOUT_SECONDS)


def test_loading_an_extension_is_refused_at_the_moment_the_statement_runs(
    backend: SqliteBackend,
) -> None:
    """Nothing here enables extension loading and the driver leaves it off, so a statement
    that calls for one is refused by the engine and loads nothing. The parse admits the call:
    an allowlist reads a grammar, and what this connection will actually do is the engine's
    answer, so it is read here rather than assumed there."""
    sql = "SELECT load_extension('sqlite_probe')"

    assert parse_statement(sql).sql == sql, "the parse admits it; the execution is what refuses"
    with pytest.raises(BackendRefused, match="not authorized"):
        backend.execute(sql, statement_timeout_seconds=TIMEOUT_SECONDS)


def test_a_connection_that_lost_the_envelope_is_refused_rather_than_read(
    audited_file: Path,
) -> None:
    """Rows returned by a session that is not the session the record would describe are not
    evidence. The envelope is read back before every statement, as the PostgreSQL backend
    reads its SET LOCALs back, and drift is refused the same way."""
    connection = sqlite3.connect(f"file:{audited_file}?mode=ro", uri=True, isolation_level=None)
    backend = SqliteBackend(connection, path=audited_file)
    connection.execute("PRAGMA query_only = 0")

    with pytest.raises(ReadBackDrift, match="query_only was set to 1"):
        backend.execute("SELECT 1", statement_timeout_seconds=TIMEOUT_SECONDS)


def test_a_statement_that_runs_past_its_bound_is_stopped_and_named(
    backend: SqliteBackend,
) -> None:
    """SQLite has no statement timeout to set and read back, so the bound is enforced by this
    process and what the record states as in force is what was enforced.

    It is refused under its own type, because a summary counts the questions the bound stopped
    apart from the ones the file refused: the same statement under a longer bound would have
    been recorded, and one naming a table this file does not hold would not."""
    with pytest.raises(StatementTimedOut, match="past its 1s timeout") as stopped:
        backend.execute(
            "WITH RECURSIVE forever(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM forever) "
            "SELECT count(*) FROM forever",
            statement_timeout_seconds=1,
        )

    assert stopped.value.seconds == 1
    assert stopped.value.step == "execute"


def _a_clock_past(deadline_seconds: float) -> Callable[[], float]:
    """A monotonic clock that starts at zero and is past that many seconds from then on.

    The deadline is moved rather than the statement made slow, because a statement really
    made to run that long is aborted by the progress handler and comes back as the interrupt,
    which is the other branch. What is being read here is the branch a slow machine reaches:
    an error the file raised, arriving when the deadline has already passed.
    """
    ticks = iter([0.0])

    def reading() -> float:
        return next(ticks, deadline_seconds + 1.0)

    return reading


def test_an_error_that_is_not_the_interrupt_keeps_its_message_past_the_deadline(
    backend: SqliteBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SQLite aborts a statement that runs past its bound with ``interrupted``, and that is
    the one error this backend reports as the timeout. A missing table is the file's answer
    about the statement, so it keeps the file's own words even when the deadline has passed
    in the meantime: a reader is sent to the table the gold names and not to a slow query."""
    monkeypatch.setattr(time, "monotonic", _a_clock_past(TIMEOUT_SECONDS))

    with pytest.raises(BackendRefused, match="no such table: seasons") as refused:
        backend.execute("SELECT year FROM seasons", statement_timeout_seconds=TIMEOUT_SECONDS)

    assert "timeout" not in refused.value.detail


def test_the_bound_the_result_states_is_the_one_the_statement_ran_under(
    backend: SqliteBackend,
) -> None:
    result = backend.execute("SELECT 1", statement_timeout_seconds=7)

    assert result.limits_in_force == ExecutionLimits(statement_timeout_ms=7000)
    assert not result.truncated


def test_the_lookup_answers_for_tables_and_views_and_never_for_a_grant(
    backend: SqliteBackend,
) -> None:
    """A file has no grants: whoever opens it reads everything in it, so the second of the two
    ways a name can fail to be measurable does not arise here and the caller is told so rather
    than given a word that means something else on this engine."""
    lookup = backend.existing_tables(
        (
            TableName("", "drivers"),
            TableName("main", "results"),
            TableName("", "fast"),
            TableName("", "seasons"),
            TableName("other", "drivers"),
        )
    )

    assert lookup.present == (
        TableName("", "drivers"),
        TableName("main", "results"),
        TableName("", "fast"),
    )
    assert lookup.unreadable == ()


def test_the_counts_and_the_schema_digest_are_read_under_the_one_schema_a_file_has(
    backend: SqliteBackend,
) -> None:
    """``main.drivers`` and ``drivers`` are one table, so the two spellings are counted once
    and the digest covers the relation once."""
    counts = backend.row_counts((TableName("", "drivers"), TableName("main", "drivers")))

    assert dict(counts) == {"main.drivers": 3}
    assert backend.schema_digest((TableName("", "drivers"),)).startswith("sha256:")
    assert backend.schema_digest((TableName("", "drivers"),)) != backend.schema_digest(
        (TableName("", "results"),)
    )


def test_the_content_digest_is_the_rows_and_not_the_order_they_are_stored_in(
    tmp_path: Path,
) -> None:
    """Taken Python-side and over the rows sorted by what they render to, because SQLite has
    no ``md5`` and no ordered ``string_agg``, and because a shuffled copy of a table holds the
    same rows in another physical order and has to digest the same."""
    one = SqliteBackend.connect(
        str(
            _build(
                tmp_path / "one.sqlite",
                "CREATE TABLE t (a INTEGER, b TEXT); INSERT INTO t VALUES (1,'x'),(2,'y');",
            )
        )
    )
    other = SqliteBackend.connect(
        str(
            _build(
                tmp_path / "other.sqlite",
                "CREATE TABLE t (a INTEGER, b TEXT); INSERT INTO t VALUES (2,'y'),(1,'x');",
            )
        )
    )
    changed = SqliteBackend.connect(
        str(
            _build(
                tmp_path / "changed.sqlite",
                "CREATE TABLE t (a INTEGER, b TEXT); INSERT INTO t VALUES (1,'x'),(2,'z');",
            )
        )
    )
    asked = (TableName("", "t"),)

    assert dict(one.content_digests(asked)) == dict(other.content_digests(asked))
    assert dict(one.content_digests(asked)) != dict(changed.content_digests(asked))
    assert one.content_digests(asked)["main.t"].startswith("sha256:")


def test_a_text_one_and_an_integer_one_are_two_rows_to_the_content_digest(
    tmp_path: Path,
) -> None:
    """The digest is typed for the reason the canonical serialization is: a digest that
    rendered both as ``1`` would call two tables one."""
    integers = SqliteBackend.connect(
        str(_build(tmp_path / "i.sqlite", "CREATE TABLE t (v); INSERT INTO t VALUES (1);"))
    )
    strings = SqliteBackend.connect(
        str(_build(tmp_path / "s.sqlite", "CREATE TABLE t (v); INSERT INTO t VALUES ('1');"))
    )
    asked = (TableName("", "t"),)

    assert dict(integers.content_digests(asked)) != dict(strings.content_digests(asked))


def test_the_content_signal_moves_when_the_file_does_and_is_the_file_s_own(
    backend: SqliteBackend, audited_file: Path
) -> None:
    """The signal is the file's size, its modification time and its two version counters, so
    every table of one file carries the same one. That is stated rather than worked around: it
    is not a digest, it never reaches a record, and it still tells a cached measurement of this
    file from one taken before it changed."""
    asked = (TableName("", "drivers"), TableName("", "results"))
    before = dict(backend.content_signal(asked))

    assert set(before) == {"main.drivers", "main.results"}
    assert len(set(before.values())) == 1

    writing = sqlite3.connect(audited_file)
    with writing:
        writing.execute("INSERT INTO drivers VALUES (4, 'Icelandic')")
    writing.close()

    assert dict(SqliteBackend.connect(str(audited_file)).content_signal(asked)) != before


def test_the_planner_keeps_nothing_an_audit_could_record(backend: SqliteBackend) -> None:
    """SQLite's planner reads ``sqlite_stat1``, which exists only after an ANALYZE, and an
    audit reads. An engine that counts nothing of the kind answers with nothing at all rather
    than with an invented zero."""
    assert backend.planner_statistics((TableName("", "drivers"),)) == {}


def test_the_declared_types_are_the_catalogue_s_own_text_empty_one_included(
    backend: SqliteBackend,
) -> None:
    """SQLite lets a column be declared with no type at all, and an empty declaration IS what
    the catalogue holds for one, so it is kept rather than filled in."""
    types = backend.column_types((TableName("", "results"), TableName("other", "results")))

    assert types[TableName("", "results")] == {
        "resultid": "INTEGER",
        "driverid": "INTEGER",
        "fastestlapspeed": "TEXT",
        "points": "REAL",
        "untyped": "",
    }
    assert TableName("other", "results") not in types


def test_the_census_counts_a_text_column_through_a_regexp_the_file_does_not_define(
    backend: SqliteBackend,
) -> None:
    """SQLite defines the ``REGEXP`` operator and no function behind it, so one is registered
    from Python and the census asks the same question here that it asks of PostgreSQL's
    ``!~``."""
    numeric = backend.numeric_text_census(TableName("", "results"), "fastestlapspeed", NUMERIC_TEXT)
    words = backend.numeric_text_census(TableName("", "drivers"), "nationality", NUMERIC_TEXT)

    assert (numeric.rows, numeric.nulls, numeric.empty_strings, numeric.non_numeric) == (3, 1, 0, 0)
    assert numeric.pattern == NUMERIC_TEXT
    assert (words.rows, words.non_numeric) == (3, 3)


AFFINITY_FIXTURE = """
CREATE TABLE speeds (driver TEXT, fastestlapspeed VARCHAR(50));
INSERT INTO speeds VALUES ('Alder', '259.870'), ('Birch', '93.175'), ('Cedar', '117.5');
"""
"""The shape BIRD's SQLite files are written in: a column of numerals declared with a length,
which no list of type names holds and which SQLite reads as text all the same."""


def test_a_column_declared_with_a_length_is_still_text_to_the_ordering_smell(
    tmp_path: Path,
) -> None:
    """SQLite gives TEXT affinity to any declaration containing CHAR, CLOB or TEXT, so
    ``VARCHAR(50)`` is a text column here and a gold ordering it sorts its numbers as
    strings. The reading is the engine's, which is why the smell asks the backend: matching
    the declaration against a list of names passed over this column and stayed quiet."""
    backend = SqliteBackend.connect(str(_build(tmp_path / "affinity.sqlite", AFFINITY_FIXTURE)))
    sql = "SELECT driver FROM speeds ORDER BY fastestlapspeed DESC"
    baseline = backend.execute(sql, statement_timeout_seconds=TIMEOUT_SECONDS)

    found = ordering_over_numeric_text(
        parse_statement(sql),
        backend,
        baseline,
        settings=SmellSettings(serialization=DESCRIPTOR, statement_timeout_seconds=TIMEOUT_SECONDS),
    )

    assert backend.declared_type_is_text("VARCHAR(50)")
    assert (found.fired, found.applicable) == (True, True)
    key = cast("list[dict[str, Any]]", found.evidence["keys"])[0]
    assert key["declared_type"] == "VARCHAR(50)"
    assert (
        key["cast_sql"] == "SELECT driver FROM speeds ORDER BY CAST(fastestlapspeed AS REAL) DESC"
    )
    assert baseline.rows == (("Birch",), ("Alder",), ("Cedar",)), "'93.175' is the largest string"


def test_a_rerun_over_the_copies_reads_the_copies_and_the_audited_one_never_does(
    backend: SqliteBackend,
) -> None:
    """SQLite resolves an unqualified name in ``temp`` before ``main``, which is what the
    PostgreSQL scratch schema on the search path achieves. The copies are on a second
    connection, so the audited one goes on reading the file: a statement sent to ``execute``
    after the copies exist is answered by the table and not by a copy of it."""
    unordered = "SELECT driverid FROM drivers"
    before = _rows(backend, unordered)
    prepared = backend.prepare_shuffled_copies(
        (TableName("", "drivers"),), seed="a-seed", row_limit=1000
    )
    try:
        shuffled = backend.execute_shuffled(unordered, statement_timeout_seconds=TIMEOUT_SECONDS)

        assert prepared.copied == (TableName("", "drivers"),)
        assert set(shuffled.rows) == set(before), "a copy holds the same rows"
        assert _rows(backend, unordered) == before, "the audited connection sees no copy"
        assert _rows(backend, "SELECT driverid FROM main.drivers") == before
    finally:
        backend.drop_shuffled_copies()

    with pytest.raises(BackendRefused, match="no shuffled copies"):
        backend.execute_shuffled(unordered, statement_timeout_seconds=TIMEOUT_SECONDS)


def test_the_copies_are_written_in_the_order_the_seed_fixes(backend: SqliteBackend) -> None:
    """Seeded rather than random, so a run reproduces; over the source row's rowid rather than
    over its values, so two identical rows still land in two places."""
    order = "SELECT driverid FROM drivers"
    first = backend.prepare_shuffled_copies(
        (TableName("", "drivers"),), seed="a-seed", row_limit=1000
    )
    once = backend.execute_shuffled(order, statement_timeout_seconds=TIMEOUT_SECONDS).rows
    backend.drop_shuffled_copies()
    backend.prepare_shuffled_copies((TableName("", "drivers"),), seed="a-seed", row_limit=1000)
    twice = backend.execute_shuffled(order, statement_timeout_seconds=TIMEOUT_SECONDS).rows
    backend.drop_shuffled_copies()

    assert first.seed == "a-seed"
    assert once == twice


def test_the_copies_name_what_they_did_not_cover_and_why(backend: SqliteBackend) -> None:
    """A smell that reruns a statement says which part of the data it did not shuffle: a
    qualified name a rerun would read in place whatever was copied, a relation with no rowid
    to order a copy by, and a table with more rows than the limit."""
    prepared = backend.prepare_shuffled_copies(
        (
            TableName("", "drivers"),
            TableName("main", "results"),
            TableName("", "keyed"),
            TableName("", "fast"),
        ),
        seed="a-seed",
        row_limit=2,
    )
    try:
        assert prepared.copied == (), "nothing here was both small enough and copyable"
        assert prepared.skipped == {TableName("", "drivers"): 3}
        assert prepared.unreachable[TableName("main", "results")] == QUALIFIED_NAME_IS_NOT_REACHED
        assert prepared.unreachable[TableName("", "keyed")] == WITHOUT_A_ROW_IDENTITY
        assert prepared.unreachable[TableName("", "fast")] == WITHOUT_A_ROW_IDENTITY
    finally:
        backend.drop_shuffled_copies()


def test_a_name_the_file_does_not_hold_is_reported_and_the_rest_is_still_copied(
    backend: SqliteBackend,
) -> None:
    """A gold that names a table nobody loaded is one question's error and never the end of
    the shuffle. Which names the file holds is therefore asked before anything is counted:
    counting one that is not there is the engine's own error, and this answer has a word for
    it already."""
    prepared = backend.prepare_shuffled_copies(
        (TableName("", "drivers"), TableName("", "seasons")), seed="a-seed", row_limit=1000
    )
    try:
        assert prepared.copied == (TableName("", "drivers"),)
        assert prepared.unreachable == {TableName("", "seasons"): NOT_IN_THIS_FILE}
    finally:
        backend.drop_shuffled_copies()


def test_dropping_the_copies_is_safe_when_the_run_made_none(backend: SqliteBackend) -> None:
    backend.drop_shuffled_copies()
    backend.drop_shuffled_copies()


def test_the_plan_variant_reads_the_same_rows_and_gives_the_control_back(
    backend: SqliteBackend,
) -> None:
    """SQLite exposes one plan control to a reader: the transient index it builds for a join
    it has no index for. It is a connection setting, so it is turned back on whatever the
    statement did, and a later execution of the run is not left reading its tables another
    way."""
    join = (
        "SELECT d.nationality FROM drivers d JOIN results r ON r.driverid = d.driverid "
        "ORDER BY r.resultid"
    )
    variant = backend.execute_plan_variant(join, statement_timeout_seconds=TIMEOUT_SECONDS)

    assert variant.rows == _rows(backend, join)
    assert _rows(backend, "SELECT 1") == ((1,),), "the connection still answers"


def test_the_benchmark_s_own_reading_of_a_sqlite_result_is_its_own_driver_s(
    backend: SqliteBackend,
) -> None:
    """BIRD's SQLite scorer sets over the rows ``sqlite3`` returns, where a REAL is a Python
    float and Python equality holds ``1 == 1.0 == True``. This backend loads a REAL as the
    decimal that round-trips it, which typed replay needs and which the reading has to undo
    before it answers for the benchmark: under it the two are one value, and under the typed
    comparison they are two."""
    integers = _result((ColumnType("v", "INTEGER"),), ((1,),))
    reals = _result((ColumnType("v", "REAL"),), ((Decimal("1.0"),),))

    reading = bird_ex(integers, reals, engine=ENGINE_SQLITE)

    assert reading.value == 1
    assert "sqlite3" in reading.method
    assert typed_row((1,)) != typed_row((Decimal("1.0"),)), "the typed rule keeps them apart"
    assert bird_ex(integers, reals, engine=ENGINE_SQLITE).equal
    assert not bird_ex(
        reals, _result((ColumnType("v", "REAL"),), ((Decimal("2.0"),),)), engine=ENGINE_SQLITE
    ).equal


WIDE_COLUMN_FIXTURE = """
CREATE TABLE schools (id INTEGER PRIMARY KEY, name TEXT, "Free Meal Count (K-12)" INTEGER);
INSERT INTO schools VALUES (1, 'Alder', 30), (2, 'Birch', 200), (3, 'Cedar', 7);
"""
"""A real column whose name holds spaces and punctuation, which only double quotes can name.
The shape a BIRD SQLite gold writes, and the one the ambiguous sort key is about."""

DESCRIPTOR = SerializationDescriptor(
    version="sqlite-backend-test/1",
    numeric_scale=6,
    timestamp_format="%Y-%m-%dT%H:%M:%SZ",
    timezone="UTC",
    null_rendering="NULL",
    encoding="utf-8",
)


def _record(backend: SqliteBackend, directory: Path, sql: str) -> tuple[object, ...]:
    """One statement recorded through the path the command takes, and the rows it recorded."""
    recorded = record_statement(
        question=QuestionMetadata(
            question_id="1",
            question_set="a-test",
            question_text="which school?",
            evidence_text="",
        ),
        question_set_version="sha256:test",
        statement_source=StatementSource(
            path="questions.json", digest="sha256:test", origin=None, date=None
        ),
        parsed=parse_statement(sql),
        backend=backend,
        serialization=DESCRIPTOR,
        session_settings=backend.session_settings(),
        run_id="a-test-run",
        directory=directory,
        data_as_of=datetime(2026, 9, 5, tzinfo=UTC),
    )
    return recorded.record.result.rows


def test_a_double_quoted_sort_key_that_names_a_column_is_read_as_that_column(
    tmp_path: Path,
) -> None:
    """BIRD's own shape. The parse names the key without deciding it, the catalogue says it is
    a column of the statement's table, and the statement is recorded and run as written."""
    backend = SqliteBackend.connect(str(_build(tmp_path / "wide.sqlite", WIDE_COLUMN_FIXTURE)))
    sql = 'SELECT name FROM schools ORDER BY "Free Meal Count (K-12)" DESC LIMIT 1'

    assert parse_statement(sql).unresolved_ordering_keys == ("Free Meal Count (K-12)",)
    assert _record(backend, tmp_path / "recorded", sql) == (("Birch",),)


def test_a_double_quoted_sort_key_that_names_a_projected_column_is_read_as_that_one(
    tmp_path: Path,
) -> None:
    """A key may name a column of the result rather than one of the data. An aliased
    expression is what a select list makes available to an ORDER BY, and such a key is as
    much a column as any other, so the output names are in the set the key is resolved
    against."""
    backend = SqliteBackend.connect(str(_build(tmp_path / "wide.sqlite", WIDE_COLUMN_FIXTURE)))
    sql = 'SELECT name, count(*) AS "how many" FROM schools GROUP BY name ORDER BY "how many", name'

    assert parse_statement(sql).unresolved_ordering_keys == ("how many",)
    assert _record(backend, tmp_path / "recorded", sql) == (
        ("Alder", 1),
        ("Birch", 1),
        ("Cedar", 1),
    )


def test_a_double_quoted_sort_key_that_names_no_column_is_refused_before_it_runs(
    tmp_path: Path,
) -> None:
    """SQLite would run this happily and sort every row by the constant string, which is an
    ordering the record cannot state and the parse cannot tell from a column. The catalogue is
    what settles it, so the refusal is the audit's own and names the token and the rule."""
    path = _build(tmp_path / "wide.sqlite", WIDE_COLUMN_FIXTURE)
    backend = SqliteBackend.connect(str(path))
    sql = 'SELECT name FROM schools ORDER BY "a name no column has" DESC LIMIT 1'

    with pytest.raises(StatementRefused, match='"a name no column has" names no column'):
        _record(backend, tmp_path / "recorded", sql)

    assert _rows(backend, sql) == (("Alder",),), (
        "the engine runs it; what is refused is the audit's reading of it as an ordering"
    )
    assert "string literal" in ORDERING_KEY_NAMES_NO_COLUMN


ASCII_FOLD_FIXTURE = """
CREATE TABLE "straße" (name TEXT, "straße" TEXT);
INSERT INTO "straße" VALUES ('Alder', '1'), ('Birch', '2');
"""
"""A table and a column whose name holds the one character the two folding rules disagree
about. Nothing else in the file is unusual: what is being read is how a name is matched."""


def test_a_name_is_matched_over_the_ascii_letters_and_no_further(tmp_path: Path) -> None:
    """SQLite folds A to Z and leaves every other character as it is, so ``STRASSE`` is not
    the column ``straße`` to it and a sort key naming it names no column. Python's
    ``casefold`` is the Unicode rule and folds ``ß`` to ``ss``: under it this tool would
    read a key the engine sorts by a string literal as an ordering over a column, and would
    measure a table the file does not hold under the name of one it does."""
    backend = SqliteBackend.connect(str(_build(tmp_path / "folding.sqlite", ASCII_FOLD_FIXTURE)))
    sql = 'SELECT name FROM "straße" ORDER BY "STRASSE"'

    assert parse_statement(sql).unresolved_ordering_keys == ("STRASSE",)
    with pytest.raises(StatementRefused, match='"STRASSE" names no column'):
        _record(backend, tmp_path / "recorded", sql)

    held = TableName("", "straße")
    folded_case = TableName("", "STRAßE")
    assert backend.existing_tables((held,)).present == (held,), "its own spelling is the table"
    assert backend.existing_tables((TableName("", "STRASSE"),)).present == ()
    assert backend.existing_tables((folded_case,)).present == (folded_case,), (
        "the ASCII letters are folded, which is what the engine does with them"
    )


class Lines:
    """A writer that keeps what was written instead of printing it."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def line(self, text: str) -> None:
        self.written.append(text)


def _question_files(tmp_path: Path) -> tuple[Path, Path]:
    """One gold that orders a numeric-looking text column as text, and its correction."""
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "question_id": 879,
                        "db_id": "formula_1",
                        "question": "For the driver who set the fastest lap speed, "
                        "what is his nationality?",
                        "evidence": "the fastest lap speed refers to (MAX) fastestLapSpeed",
                        "SQL": "SELECT d.nationality FROM drivers AS d "
                        "JOIN results AS r ON r.driverid = d.driverid "
                        "ORDER BY r.fastestlapspeed DESC LIMIT 1",
                        "difficulty": "moderate",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    predictions = tmp_path / "predictions.json"
    predictions.write_text(
        json.dumps(
            {
                "879": "SELECT d.nationality FROM drivers AS d "
                "JOIN results AS r ON r.driverid = d.driverid "
                "ORDER BY CAST(r.fastestlapspeed AS REAL) DESC LIMIT 1"
            }
        ),
        encoding="utf-8",
    )
    return questions, predictions


def test_a_whole_audit_runs_on_a_sqlite_file_and_the_summary_says_which_engine(
    tmp_path: Path, audited_file: Path
) -> None:
    """The command's own path, end to end and without a container: connect to the file, read
    the gold with sqlglot, run both statements read-only, compare under the gold's own rule,
    and write the summary a maintainer reads.

    The disagreement is the shape of BIRD Mini-Dev's q879: '93.175' is the largest string and
    259.870 the largest number, so the two statements land on two drivers.
    """
    questions, predictions = _question_files(tmp_path)
    options = AuditOptions(
        dsn=str(audited_file),
        questions=questions,
        predictions=predictions,
        out=tmp_path / "audit",
        engine=SQLITE,
        data_as_of=datetime(2026, 9, 5, tzinfo=UTC),
    )
    writer = Lines()

    assert connect_and_audit(options, writer) == 1, "a disagreement is exit status one"
    assert writer.written[-1].startswith("1 questions: 1 NOT_EQUAL")

    document = cast(
        "dict[str, Any]",
        json.loads((tmp_path / "audit" / SUMMARY_FILE).read_text(encoding="utf-8")),
    )
    assert document["session_settings"]["engine"] == ENGINE_SQLITE
    assert document["parser"] == SQLITE_PARSER.json()
    assert document["planner_statistics"] == {}
    assert document["fixture"]["row_counts"] == {"main.drivers": 3, "main.results": 3}
    assert document["backend_identity"].startswith("SQLite ")
    assert document["effective_database_role"] == "file"


def test_the_summary_states_where_the_copies_were_made_and_not_what_was_asked_for(
    tmp_path: Path, audited_file: Path
) -> None:
    """``--scratch-schema`` is PostgreSQL's. This engine accepts the name, makes its copies
    in TEMP whatever it says, and the summary reads the place off the backend, so a reader of
    a SQLite run is told where a rerun's rows came from rather than what was asked for."""
    questions, _ = _question_files(tmp_path)
    options = AuditOptions(
        dsn=str(audited_file),
        questions=questions,
        out=tmp_path / "audit",
        engine=SQLITE,
        scratch_schema="a_schema_no_file_has",
        data_as_of=datetime(2026, 9, 5, tzinfo=UTC),
    )

    assert connect_and_audit(options, Lines()) == 0

    document = cast(
        "dict[str, Any]",
        json.loads((tmp_path / "audit" / SUMMARY_FILE).read_text(encoding="utf-8")),
    )
    assert document["shuffle"]["scratch_schema"] == "temp"
    assert document["shuffle"]["copied"] == ["drivers", "results"]


def test_the_gold_and_its_correction_land_on_two_drivers_over_this_file(
    backend: SqliteBackend,
) -> None:
    """What the audit above compared, read directly so the disagreement is visible without
    opening the counterexample: ordering the speeds as text is not ordering them as numbers.
    """
    gold = "SELECT d.nationality FROM drivers AS d JOIN results AS r ON r.driverid = d.driverid ORDER BY r.fastestlapspeed DESC LIMIT 1"
    corrected = parse_statement(gold).with_ordering_key_cast_to_numeric(0)

    assert _rows(backend, gold) == (("Norwegian",),), "'93.175' is the largest string"
    assert _rows(backend, corrected) == (("Peruvian",),), "259.870 is the largest number"


# a file in WAL mode on read-only media


WAL_ROWS = "CREATE TABLE t (a INTEGER); INSERT INTO t VALUES (1), (2);"


def _wal_file(path: Path) -> Path:
    """A database whose own header says WAL, with no sidecar left beside it.

    Which is what BIRD's `card_games` ships as: closing the last connection checkpoints the
    log and removes the two sidecars, and the mode stays in the header, so the next reader
    has to create them again before it can read a row.
    """
    connection = sqlite3.connect(path)
    with connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(WAL_ROWS)
    connection.close()
    assert path.read_bytes()[18:20] == b"\x02\x02", "the header should say WAL"
    return path


@contextmanager
def _read_only(directory: Path) -> Generator[Path]:
    """That directory with nothing writable in it, put back so the test can clean up."""
    modes = {entry: entry.stat().st_mode for entry in directory.iterdir()}
    for entry in modes:
        entry.chmod(0o444)
    directory.chmod(0o555)
    try:
        yield directory
    finally:
        directory.chmod(0o755)
        for entry, mode in modes.items():
            entry.chmod(mode)


def test_a_wal_file_on_read_only_media_is_read_through_a_private_copy(tmp_path: Path) -> None:
    home = tmp_path / "read-only"
    home.mkdir()
    path = _wal_file(home / "wal.sqlite")
    with _read_only(home):
        backend = SqliteBackend.connect(str(path))
        recorded = backend.session_settings().recorded
        copy = Path(recorded[READ_THROUGH_PRIVATE_COPY])

        assert _rows(backend, "SELECT a FROM t ORDER BY a") == ((1,), (2,))
        assert copy.is_file() and copy != path
        assert copy.read_bytes() == path.read_bytes(), "the copy is the file, byte for byte"
        assert str(path) in backend.identity(), "the identity names what was audited"
        assert str(copy) not in backend.identity()

        del backend
        gc.collect()
        assert not copy.exists() and not copy.parent.exists(), "the copy goes with the run"


def test_a_file_that_needs_no_copy_is_read_where_it_is(tmp_path: Path) -> None:
    home = tmp_path / "read-only-rollback"
    home.mkdir()
    path = _build(home / "rollback.sqlite", WAL_ROWS)
    with _read_only(home):
        backend = SqliteBackend.connect(str(path))
        assert _rows(backend, "SELECT a FROM t ORDER BY a") == ((1,), (2,))
        assert READ_THROUGH_PRIVATE_COPY not in backend.session_settings().recorded


def test_a_file_that_is_not_a_database_is_refused_and_never_copied(tmp_path: Path) -> None:
    """The copy answers one refusal and not every one: a file SQLite cannot read at all is
    a run that cannot start, and copying it would only fail again somewhere else."""
    path = tmp_path / "prose.sqlite"
    path.write_text("this is not a database", encoding="utf-8")
    with pytest.raises(BackendRefused, match="not a database"):
        SqliteBackend.connect(str(path))
    assert not list(Path(tempfile.gettempdir()).glob("attestql-sqlite-*/prose.sqlite"))
