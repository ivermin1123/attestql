"""The read-only envelope, driven by a connection that answers what a test tells it to.

No server and no driver import here: the executor takes a connection, so a fake one can
say that the session is not read only, or that its timeout is not the timeout that was
set, and the executor has to refuse rather than return rows. That refusal is the one
property ADR-0013 point 7 carried over from the deleted product executor, and it is the
reason a record can state the session its result came from.

The same fake connection is what says which loaders the backend registers on it. A
float and an interval are loaded as the text the server printed, so the two are tested
here in the two halves a fake can state: the registration the backend makes, and what
each loader turns the server's bytes into.

A connection can also be told to fail the way a driver fails: ``DRIVER_ERROR`` is the name
the backend gives the one failure it translates, and raising it here states a lost
connection without importing the driver, which no file but that one may do. No test lets
one out. Every call this backend makes turns a driver error into a refusal naming its own
step, because the audit above reports that as one question's error, and a driver exception
crossing this seam would end a run with the questions after it unanswered.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

import pytest

from attestql.audit.backend import Backend, BackendRefused, ReadBackDrift, TableLookup
from attestql.audit.postgres import (
    DEFAULT_SCRATCH_SCHEMA,
    DRIVER_ERROR,
    LOCK_WAIT_SECONDS,
    NO_PARALLEL_AGGREGATION,
    NumericFromFloatText,
    PostgresBackend,
    TextFromInterval,
    _lock_key,  # pyright: ignore[reportPrivateUsage]  # the key the backend locks on, so the test cannot name another
)

VERSION = "PostgreSQL 16.4 on aarch64"
STATEMENT = "SELECT nationality, laps FROM results"
COLUMNS: tuple[tuple[str, int], ...] = (("nationality", 25), ("laps", 20))
ROWS: tuple[tuple[object, ...], ...] = (("Italian", 91), ("Brazilian", 257))
TYPES: Mapping[int, str] = {25: "text", 20: "int8", 701: "float8", 1186: "interval"}

FLOAT_STATEMENT = "SELECT avg(fastestlapspeed), sum(duration) FROM results"
FLOAT_COLUMNS: tuple[tuple[str, int], ...] = (("avg", 701), ("sum", 1186))
FLOAT_ROWS: tuple[tuple[object, ...], ...] = ((Decimal("257.32"), "1 day 02:00:00"),)

HEALTHY_SETTINGS: Mapping[str, str] = {
    "statement_timeout": "30000",
    "transaction_read_only": "on",
    "TimeZone": "UTC",
    "DateStyle": "ISO, MDY",
    "IntervalStyle": "postgres",
    "extra_float_digits": "1",
    "search_path": '"$user", public',
    "server_version": "16.4 (Debian 16.4-1.pgdg120+1)",
    "server_version_num": "160004",
    "max_parallel_workers_per_gather": "2",
}
"""What the session holds outside any transaction, which is what a run records. The gather
is on here, as it is on a server nobody configured, so that the value each execution sets
inside its own transaction is visibly not the value the session was found with."""


@dataclass(frozen=True)
class FakeColumn:
    name: str
    type_code: int


class FakeCursor:
    """One cursor over a scripted connection. Every query it is given is recorded."""

    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection
        self._rows: Sequence[tuple[object, ...]] = ()
        self._description: Sequence[FakeColumn] | None = None
        self.closed = False

    @property
    def description(self) -> Sequence[FakeColumn] | None:
        return self._description

    def execute(self, query: object, params: Sequence[object] | None = None) -> object:
        text = str(query)
        self._connection.log.append(text)
        if "pg_advisory" in text:
            # The key is a parameter, so a log of statement text alone cannot say which
            # schema a lock was keyed on. Kept beside the log rather than in it.
            self._connection.lock_keys.append(params[0] if params else None)
        self._rows, self._description = self._connection.answer(text)
        return self

    def fetchall(self) -> Sequence[tuple[object, ...]]:
        return self._rows

    def fetchone(self) -> tuple[object, ...] | None:
        return self._rows[0] if self._rows else None

    def close(self) -> None:
        self.closed = True


class FakeAdapters:
    """What the backend registered on the connection, in the order it registered it."""

    def __init__(self) -> None:
        self.registered: list[tuple[str, type[object]]] = []

    def register_loader(self, type_name: str, loader: type[object], /) -> None:
        self.registered.append((type_name, loader))


class FakeConnection:
    """A connection that answers the questions this backend asks and nothing else.

    ``SET LOCAL`` is answered the way a server answers one: what a transaction set is what
    the session reports until the rollback takes it off again, so a read-back reads back
    something the executor really did. ``keeps_its_gather`` is the other case, a session
    that reports its own value whatever was set on it, which is the drift the read-back is
    there to catch.
    """

    def __init__(
        self,
        *,
        settings: Mapping[str, str] = HEALTHY_SETTINGS,
        rows: Sequence[tuple[object, ...]] = ROWS,
        columns: tuple[tuple[str, int], ...] = COLUMNS,
        collation: str = "en_US.UTF-8",
        schema: Sequence[tuple[str, ...]] = (),
        tables: Sequence[str] = (),
        unreadable_tables: Sequence[str] = (),
        counts: Mapping[str, int] | None = None,
        signals: Mapping[str, Sequence[int]] | None = None,
        census: tuple[int, ...] = (0, 0, 0, 0),
        scratch_exists: bool = True,
        scratch_writable: bool = True,
        keeps_its_gather: bool = False,
        refuses_the_lock: bool = False,
    ) -> None:
        self.settings = dict(settings)
        self.local: dict[str, str] = {}
        """What ``SET LOCAL`` put on the open transaction, which the rollback takes off."""
        self.keeps_its_gather = keeps_its_gather
        """A session that reports its own value however the transaction set it, which is the
        drift the read-back is there to catch."""
        self.scratch_exists = scratch_exists
        self.scratch_writable = scratch_writable
        self.refuses_the_lock = refuses_the_lock
        """A server that would not grant the advisory lock inside the wait it was given,
        which is what a second run told a schema another run holds meets."""
        self.refuses_drops = False
        """Set after the copies are made, so that a drop can fail where the create did
        not: what a role whose grant was taken away mid-run meets."""
        self.lock_keys: list[object] = []
        """The key of every advisory lock and unlock the backend asked for, in order."""
        self.census = census
        self.rows = rows
        self.columns = columns
        self.collation = collation
        self.schema = schema
        self.tables = tuple(tables)
        self.unreadable_tables = tuple(unreadable_tables)
        self.counts = dict(counts or {})
        self.signals = {name: tuple(values) for name, values in (signals or {}).items()}
        """Per qualified table, the file node and the four tuple counters the catalogue holds."""
        self.log: list[str] = []
        self.adapters = FakeAdapters()

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def answer(self, text: str) -> tuple[Sequence[tuple[object, ...]], Sequence[FakeColumn] | None]:
        if text in {"BEGIN READ ONLY", "BEGIN", "SET TRANSACTION READ WRITE", "COMMIT", "ROLLBACK"}:
            self.local.clear()
            return (), None
        if text.startswith("SET LOCAL max_parallel_workers_per_gather"):
            if not self.keeps_its_gather:
                self.local["max_parallel_workers_per_gather"] = text.rsplit("=", 1)[1].strip()
            return (), None
        if "pg_advisory_unlock" in text:
            return ((True,),), None
        if "pg_advisory_lock" in text:
            if self.refuses_the_lock:
                raise DRIVER_ERROR("canceling statement due to lock timeout")
            return ((None,),), None
        if self.refuses_drops and "DROP TABLE" in text:
            raise DRIVER_ERROR("permission denied for schema attestql_scratch")
        if "pg_stat_user_tables" in text:
            # Answered before the branch below because both questions join pg_class: this is
            # the one that reads the counters and that one is the one that reads the grants.
            return tuple((name, *values) for name, values in self.signals.items()), None
        if "pg_class" in text:
            # The catalogue lists what is there whatever the grants are, and says of each
            # whether this role may read it. Asked before the scratch schema's question
            # below, which names pg_namespace too.
            return (
                tuple((name, True) for name in self.tables)
                + tuple((name, False) for name in self.unreadable_tables),
                None,
            )
        if "pg_namespace" in text:
            return ((1 if self.scratch_exists else 0,),), None
        if "has_schema_privilege" in text:
            return (("auditor", self.scratch_writable),), None
        if "set_config" in text:
            return ((self.settings.get("statement_timeout", ""),),), None
        if "pg_settings" in text:
            held = {**self.settings, **self.local}
            return tuple((name, value) for name, value in held.items()), None
        if "version()" in text:
            return ((VERSION, "local", 0, "bird"),), None
        if "current_user" in text:
            return (("bird_reader",),), None
        if "datcollate" in text:
            return ((self.collation,),), None
        if "pg_type" in text:
            return tuple((oid, name) for oid, name in TYPES.items()), None
        if "information_schema.columns" in text:
            return tuple(self.schema), None
        if "FILTER (WHERE" in text:
            return (self.census,), None
        if "count(*)" in text:
            for table, rows in self.counts.items():
                if f"'{table}'" in text:
                    return ((rows,),), None
            return ((next(iter(self.counts.values()), 0),),), None
        if text.startswith(("Composed([SQL('CREATE", "Composed([SQL('DROP", "SET LOCAL")):
            return (), None
        if "md5(" in text:
            return (("d41d8cd98f00b204e9800998ecf8427e",),), None
        return self.rows, tuple(FakeColumn(name, oid) for name, oid in self.columns)


class DeadConnection(FakeConnection):
    """A connection that answers a few statements and is then gone.

    ``kill_after`` is how many it answers first, which is how a test says that the
    envelope, the read-back and the statement each name their own step when the driver
    fails under them. ``kill_the_cursor`` is the state after that: a driver that knows the
    connection is closed refuses to hand out a cursor at all, which is what every call made
    after a lost connection meets. Unwinding fails too, and that failure may not replace
    the refusal being raised through it, so ``ROLLBACK`` is refused from the first moment.
    """

    def __init__(
        self,
        *,
        kill_after: int = 0,
        kill_the_cursor: bool = False,
        counts: Mapping[str, int] | None = None,
    ) -> None:
        super().__init__(counts=counts)
        self.kill_after = kill_after
        self.kill_the_cursor = kill_the_cursor
        self.answered = 0

    def cursor(self) -> FakeCursor:
        if self.kill_the_cursor:
            raise DRIVER_ERROR("the connection is closed")
        return super().cursor()

    def answer(self, text: str) -> tuple[Sequence[tuple[object, ...]], Sequence[FakeColumn] | None]:
        if text == "ROLLBACK":
            raise DRIVER_ERROR("the connection is closed")
        self.answered += 1
        if self.answered > self.kill_after:
            raise DRIVER_ERROR("server closed the connection unexpectedly")
        return super().answer(text)


def _backend(connection: FakeConnection) -> PostgresBackend:
    return PostgresBackend(connection)


def test_the_backend_satisfies_the_engine_neutral_interface() -> None:
    backend: Backend = _backend(FakeConnection())
    assert backend.identity().startswith(VERSION)


def test_a_statement_runs_inside_a_read_only_transaction_that_is_rolled_back() -> None:
    connection = FakeConnection()
    result = _backend(connection).execute(STATEMENT, statement_timeout_seconds=30)
    assert connection.log[0] == "BEGIN READ ONLY"
    assert STATEMENT in connection.log
    assert connection.log[connection.log.index(STATEMENT) + 1] == "ROLLBACK"
    assert result.rows == ROWS
    assert [(c.name, c.pg_type) for c in result.columns] == [
        ("nationality", "text"),
        ("laps", "int8"),
    ]
    assert result.limits_in_force.statement_timeout_ms == 30_000
    assert result.truncated is False
    assert result.backend_identity.startswith(VERSION)


def test_a_transaction_that_is_not_read_only_stops_the_execution() -> None:
    connection = FakeConnection(settings={**HEALTHY_SETTINGS, "transaction_read_only": "off"})
    with pytest.raises(ReadBackDrift, match="not read only"):
        _backend(connection).execute(STATEMENT, statement_timeout_seconds=30)
    assert STATEMENT not in connection.log, "the statement ran anyway"
    assert connection.log[-1] == "ROLLBACK"


def test_a_timeout_the_session_did_not_hold_stops_the_execution() -> None:
    connection = FakeConnection(settings={**HEALTHY_SETTINGS, "statement_timeout": "1000"})
    with pytest.raises(ReadBackDrift, match="statement_timeout was set to 30000"):
        _backend(connection).execute(STATEMENT, statement_timeout_seconds=30)
    assert STATEMENT not in connection.log
    assert connection.log[-1] == "ROLLBACK"


def test_every_execution_adds_a_float_sum_in_one_worker() -> None:
    """Partial sums a gather collected are added in whatever order they came back, so the
    same statement over the same rows can differ in its last digits between two executions.
    Every way in turns the gather off inside its own transaction, after the envelope is set
    and before the read-back that has to see it, so what a reader is shown differing is the
    statement and not the plan the server happened to choose."""
    connection = FakeConnection(counts={"drivers": 100})
    backend = _backend(connection)
    backend.prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)

    for run in (backend.execute, backend.execute_shuffled, backend.execute_plan_variant):
        connection.log.clear()
        run(STATEMENT, statement_timeout_seconds=30)
        read_back = next(i for i, line in enumerate(connection.log) if "pg_settings" in line)
        turned_off = connection.log.index(NO_PARALLEL_AGGREGATION)
        assert connection.log.index("BEGIN READ ONLY") < turned_off < read_back
        assert read_back < connection.log.index(STATEMENT)


def test_a_session_that_kept_its_gather_stops_the_execution() -> None:
    """The same refusal the timeout gets: a session that does not hold what was set on it
    is not the session a record would describe, and rows from it are not evidence."""
    connection = FakeConnection(keeps_its_gather=True)
    with pytest.raises(ReadBackDrift, match="max_parallel_workers_per_gather was set to 0"):
        _backend(connection).execute(STATEMENT, statement_timeout_seconds=30)
    assert STATEMENT not in connection.log
    assert connection.log[-1] == "ROLLBACK"


def test_a_session_that_reports_nothing_at_all_stops_the_execution() -> None:
    connection = FakeConnection(settings={})
    with pytest.raises(ReadBackDrift, match="reports nothing"):
        _backend(connection).execute(STATEMENT, statement_timeout_seconds=30)


def test_a_timeout_that_is_not_a_whole_second_is_refused_before_a_transaction_opens() -> None:
    connection = FakeConnection()
    with pytest.raises(BackendRefused, match="whole number of seconds"):
        _backend(connection).execute(STATEMENT, statement_timeout_seconds=0)
    assert connection.log == []


def test_the_session_settings_name_the_five_and_record_the_rest() -> None:
    """The recorded gather is the session's own, read before any transaction set it to 0:
    the two are different scopes, and a summary stating 0 here would say the server runs no
    parallel plan at all. ``server_version`` is beside the number because a reader of a
    summary sees the build the rows came from and not only its integer."""
    settings = _backend(FakeConnection()).session_settings()
    assert settings.time_zone == "UTC"
    assert settings.date_style == "ISO, MDY"
    assert settings.interval_style == "postgres"
    assert settings.extra_float_digits == "1"
    assert settings.database_collation == "en_US.UTF-8"
    assert dict(settings.recorded) == {
        "statement_timeout": "30000",
        "search_path": '"$user", public',
        "server_version": "16.4 (Debian 16.4-1.pgdg120+1)",
        "server_version_num": "160004",
        "transaction_read_only": "on",
        "max_parallel_workers_per_gather": "2",
    }


def test_a_session_that_cannot_report_a_precondition_setting_is_refused() -> None:
    connection = FakeConnection(settings={"statement_timeout": "30000"})
    with pytest.raises(BackendRefused, match="reported no value for"):
        _backend(connection).session_settings()


def test_a_connection_that_died_in_the_envelope_is_a_refusal_naming_that_step() -> None:
    """``BEGIN READ ONLY`` is the first thing a connection that went away fails on, and it
    is one question's error above rather than a driver exception ending the run."""
    with pytest.raises(BackendRefused, match="server closed the connection") as refused:
        _backend(DeadConnection()).execute(STATEMENT, statement_timeout_seconds=30)
    assert refused.value.step == "begin"


def test_a_connection_that_died_before_the_read_back_is_a_refusal_naming_that_step() -> None:
    """The envelope was set and the session cannot be asked what it holds. Three statements
    make that envelope: the read-only begin, the timeout, and the gather turned off."""
    with pytest.raises(BackendRefused) as refused:
        _backend(DeadConnection(kill_after=3)).execute(STATEMENT, statement_timeout_seconds=30)
    assert refused.value.step == "read_back"


def test_a_connection_that_died_at_the_statement_is_a_refusal_naming_that_step() -> None:
    with pytest.raises(BackendRefused) as refused:
        _backend(DeadConnection(kill_after=4)).execute(STATEMENT, statement_timeout_seconds=30)
    assert refused.value.step == "execute"


def test_every_call_over_a_connection_that_is_gone_refuses_and_names_where_it_was() -> None:
    """Each of these is a call the audit makes for one question, and each of them starts at
    a cursor the driver will not give. None of them may reach a caller as a driver error."""
    backend = _backend(DeadConnection(kill_the_cursor=True))
    calls: tuple[tuple[str, Callable[[], object]], ...] = (
        ("begin", lambda: backend.execute(STATEMENT, statement_timeout_seconds=30)),
        (
            "begin",
            lambda: backend.execute_plan_variant(STATEMENT, statement_timeout_seconds=30),
        ),
        ("existing_tables", lambda: backend.existing_tables(("results",))),
        ("schema_digest", lambda: backend.schema_digest(("results",))),
        ("row_counts", lambda: backend.row_counts(("results",))),
        ("content_digests", lambda: backend.content_digests(("results",))),
        ("content_signal", lambda: backend.content_signal(("results",))),
        ("column_types", lambda: backend.column_types(("results",))),
        ("session_settings", lambda: backend.session_settings()),
        (
            "numeric_text_census",
            lambda: backend.numeric_text_census("results", "fastestlapspeed", "^[0-9]+$"),
        ),
    )

    for step, call in calls:
        with pytest.raises(BackendRefused, match="the connection is closed") as refused:
            call()
        assert refused.value.step == step, step


def test_dropping_the_copies_over_a_connection_that_died_is_a_refusal_and_not_a_crash() -> None:
    """The copies are stranded and the caller says so; a driver error raised out of the
    finally that drops them would take the run's summary with it."""
    connection = DeadConnection(kill_after=100, counts={"drivers": 100})
    backend = _backend(connection)
    backend.prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)
    connection.kill_the_cursor = True

    with pytest.raises(BackendRefused, match="the connection is closed") as refused:
        backend.drop_shuffled_copies()
    assert refused.value.step == "drop_shuffled_copies"


def test_the_tables_the_database_holds_are_the_ones_the_catalogue_names() -> None:
    """A gold that names a table nobody loaded is answered here, before anything is counted."""
    connection = FakeConnection(tables=("public.results", "public.drivers"))
    found = _backend(connection).existing_tables(
        ("results", "public.drivers", "seasons", "results")
    )
    assert found.present == ("results", "public.drivers")
    assert found.unreadable == ()
    assert not any("count(*)" in line for line in connection.log), "a missing table was counted"


def test_a_table_this_role_may_not_read_is_not_a_table_that_is_not_there() -> None:
    """Two states one word used to cover: a grant nobody made, and a table nobody loaded.
    The first is repaired with GRANT and the second in the question file, so a summary that
    spells them the same way sends the operator to fix the wrong one."""
    connection = FakeConnection(tables=("public.results",), unreadable_tables=("public.sealed",))
    found = _backend(connection).existing_tables(("results", "sealed", "seasons"))

    assert found.present == ("results",)
    assert found.unreadable == ("sealed",)
    assert len(connection.log) == 1, "what exists and what may be read were two round trips"


def test_asking_which_of_no_tables_exist_asks_the_server_nothing() -> None:
    connection = FakeConnection()
    assert _backend(connection).existing_tables(()) == TableLookup((), ())
    assert connection.log == []


def test_the_schema_digest_covers_the_columns_and_changes_when_they_do() -> None:
    one = _backend(
        FakeConnection(schema=(("public", "results", "laps", "bigint", "YES"),))
    ).schema_digest(("results",))
    again = _backend(
        FakeConnection(schema=(("public", "results", "laps", "bigint", "YES"),))
    ).schema_digest(("results",))
    nullability = _backend(
        FakeConnection(schema=(("public", "results", "laps", "bigint", "NO"),))
    ).schema_digest(("results",))
    assert one == again
    assert one != nullability
    assert one.startswith("sha256:")


def test_the_counts_and_the_content_digests_are_keyed_by_the_qualified_table_name() -> None:
    backend = _backend(FakeConnection(counts={"results": 23_179}))
    assert dict(backend.row_counts(("results",))) == {"public.results": 23_179}
    assert dict(backend.content_digests(("public.results",))) == {
        "public.results": "md5:d41d8cd98f00b204e9800998ecf8427e"
    }


def test_the_content_signal_is_one_question_and_moves_when_the_rows_do() -> None:
    """What tells a cached measurement of yesterday's data from one of today's. One round
    trip, and a name the catalogue answers nothing for gets no invented counter."""
    connection = FakeConnection(signals={"public.results": (16_384, 23_179, 0, 0, 23_179)})
    signal = _backend(connection).content_signal(("results", "seasons"))

    assert signal == {"public.results": "16384/23179/0/0/23179", "public.seasons": ""}
    assert len(connection.log) == 1, "the signal cost more than the one question it is worth"

    updated = FakeConnection(signals={"public.results": (16_384, 23_179, 12, 0, 23_179)})
    moved = _backend(updated).content_signal(("results",))
    assert moved["public.results"] != signal["public.results"]


def test_asking_for_the_signal_of_no_tables_asks_the_server_nothing() -> None:
    connection = FakeConnection()
    assert _backend(connection).content_signal(()) == {}
    assert connection.log == []


def test_the_backend_registers_the_two_result_types_it_loads_as_the_server_renders_them() -> None:
    """A Python float has no canonical rendering and an interval has none either.

    Both are loaded from the server's own text, so the registration is what makes 107 of
    Mini-Dev's 498 golds measurable instead of refused, and it happens on whatever
    connection the backend is given rather than only on one it opened itself."""
    connection = FakeConnection()
    _backend(connection)
    assert connection.adapters.registered == [
        ("float4", NumericFromFloatText),
        ("float8", NumericFromFloatText),
        ("interval", TextFromInterval),
    ]


def test_a_float_is_loaded_as_the_exact_decimal_the_server_printed() -> None:
    loader = NumericFromFloatText(701)
    assert loader.load(b"257.32") == Decimal("257.32")
    assert loader.load(b"1e-07") == Decimal("1e-07")
    assert str(loader.load(b"0.1")) == "0.1", "a float would have printed 0.1000000000000000055"


def test_an_interval_is_loaded_as_the_text_the_server_rendered_it_in() -> None:
    loader = TextFromInterval(1186)
    assert loader.load(b"1 day 02:00:00") == "1 day 02:00:00"


def test_a_float_that_the_server_printed_unreadably_is_refused_by_name() -> None:
    with pytest.raises(BackendRefused, match="for a float"):
        NumericFromFloatText(701).load(b"not a number")


def test_a_loaded_float_and_interval_keep_the_type_the_server_named_on_the_column() -> None:
    """The value is a decimal and a string; the column still says float8 and interval,
    which is what a reader of the record needs to see beside a cell tagged ``dec``."""
    connection = FakeConnection(rows=FLOAT_ROWS, columns=FLOAT_COLUMNS)
    result = _backend(connection).execute(FLOAT_STATEMENT, statement_timeout_seconds=30)
    assert [(c.name, c.pg_type) for c in result.columns] == [("avg", "float8"), ("sum", "interval")]
    assert result.rows == FLOAT_ROWS


SHUFFLE_TABLES: tuple[str, ...] = ("results", "drivers")


def test_the_shuffled_copies_are_made_in_the_scratch_schema_in_the_seeded_order() -> None:
    """The one write this tool makes, and the shape of it: the audited tables are read."""
    connection = FakeConnection(counts={"results": 23_179, "drivers": 100})
    prepared = _backend(connection).prepare_shuffled_copies(
        SHUFFLE_TABLES, seed="7", row_limit=1_000
    )
    assert prepared.copied == ("public.drivers",)
    assert dict(prepared.skipped) == {"public.results": 23_179}
    assert prepared.seed == "7"
    created = [line for line in connection.log if "CREATE TABLE" in line]
    assert len(created) == 1, "a table over the row limit was copied anyway"
    assert "md5(" in created[0] and "Literal('7')" in created[0]
    assert "attestql_scratch" in created[0]
    # The copy a run that died left behind is cleared, and nothing else in the schema is.
    dropped = [line for line in connection.log if "DROP TABLE IF EXISTS" in line]
    assert len(dropped) == 1
    assert connection.log.index(dropped[0]) < connection.log.index(created[0])
    assert not any("CREATE SCHEMA" in line or "DROP SCHEMA" in line for line in connection.log)
    assert not any("DELETE" in line or "UPDATE" in line for line in connection.log)


def test_the_copies_are_made_in_one_read_write_transaction_under_the_advisory_lock() -> None:
    """A role whose transactions default to read only writes only where it says so."""
    connection = FakeConnection(counts={"drivers": 100})
    _backend(connection).prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)
    writing = connection.log.index("SET TRANSACTION READ WRITE")
    assert connection.log[writing - 1] == "BEGIN"
    lock = next(index for index, line in enumerate(connection.log) if "advisory" in line)
    created = next(index for index, line in enumerate(connection.log) if "CREATE TABLE" in line)
    assert lock < writing < created
    assert connection.log[-1] == "COMMIT"


def test_the_scratch_schema_is_locked_for_the_run_and_not_for_one_transaction() -> None:
    """The lock the copies are made under is the lock the reruns read them under.

    A lock the commit gives back covers the create and the drop and nothing between them,
    so a second run told the same schema takes it while the first is still rerunning
    against its copies, and recreates or drops the tables the first is reading. The lock
    is the session's: taken before anything is created, in its own transaction and under a
    bounded wait, keyed on the scratch schema name, and still held after that transaction
    commits.
    """
    connection = FakeConnection(counts={"drivers": 100})
    _backend(connection).prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)

    taken = next(index for index, line in enumerate(connection.log) if "pg_advisory_lock" in line)
    created = next(index for index, line in enumerate(connection.log) if "CREATE TABLE" in line)
    assert taken < created
    assert connection.log[taken - 2] == "BEGIN"
    assert "lock_timeout" in connection.log[taken - 1]
    assert connection.log[taken + 1] == "COMMIT"
    assert connection.lock_keys == [_lock_key(DEFAULT_SCRATCH_SCHEMA)]
    assert not any("pg_advisory_xact_lock" in line for line in connection.log), (
        "a lock the transaction owns is given back while the copies are still there"
    )
    assert not any("pg_advisory_unlock" in line for line in connection.log), (
        "the run gives the schema back when it drops the copies, not before"
    )


def test_preparing_the_copies_twice_takes_the_one_lock() -> None:
    """A run that prepares again is a run that never let go: a second lock on the same key
    would have to be released twice, and one release would leave the schema held."""
    connection = FakeConnection(counts={"drivers": 100})
    backend = _backend(connection)
    backend.prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)
    backend.prepare_shuffled_copies(("drivers",), seed="2", row_limit=1_000)

    assert len([line for line in connection.log if "pg_advisory_lock" in line]) == 1
    assert connection.lock_keys == [_lock_key(DEFAULT_SCRATCH_SCHEMA)]


def test_a_scratch_schema_another_run_holds_is_a_refusal_naming_the_wait() -> None:
    """Waiting on the lock for as long as the run holding it takes would make one audit's
    length the other's, so the wait is bounded and what it did not get is said."""
    connection = FakeConnection(counts={"drivers": 100}, refuses_the_lock=True)
    with pytest.raises(
        BackendRefused,
        match=f"scratch schema {DEFAULT_SCRATCH_SCHEMA} was not locked "
        f"within {LOCK_WAIT_SECONDS} seconds",
    ) as refused:
        _backend(connection).prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)
    assert refused.value.step == "prepare_shuffled_copies"
    assert not any("CREATE TABLE" in line for line in connection.log)
    assert connection.log[-1] == "ROLLBACK"


def test_a_scratch_schema_that_is_not_there_is_a_refusal_and_no_write() -> None:
    connection = FakeConnection(counts={"drivers": 100}, scratch_exists=False)
    with pytest.raises(BackendRefused, match="attestql_scratch does not exist"):
        _backend(connection).prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)
    assert not any("CREATE TABLE" in line for line in connection.log)
    assert connection.log[-1] == "ROLLBACK"


def test_a_scratch_schema_the_role_cannot_create_in_is_a_refusal_and_no_write() -> None:
    connection = FakeConnection(counts={"drivers": 100}, scratch_writable=False)
    with pytest.raises(BackendRefused, match="cannot create in the scratch schema"):
        _backend(connection).prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)
    assert not any("CREATE TABLE" in line for line in connection.log)
    assert connection.log[-1] == "ROLLBACK"


def test_a_shuffled_rerun_sets_the_search_path_inside_the_read_only_transaction() -> None:
    connection = FakeConnection(counts={"drivers": 100})
    backend = _backend(connection)
    backend.prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)
    connection.log.clear()
    backend.execute_shuffled(STATEMENT, statement_timeout_seconds=30)
    path = next(index for index, line in enumerate(connection.log) if "search_path" in line)
    assert connection.log[0] == "BEGIN READ ONLY"
    assert path < connection.log.index(STATEMENT)
    assert "attestql_scratch" in connection.log[path]
    assert connection.log[connection.log.index(STATEMENT) + 1] == "ROLLBACK"


def test_a_shuffled_rerun_without_copies_is_refused_rather_than_run_against_the_tables() -> None:
    connection = FakeConnection()
    with pytest.raises(BackendRefused, match="no shuffled copies"):
        _backend(connection).execute_shuffled(STATEMENT, statement_timeout_seconds=30)
    assert STATEMENT not in connection.log


def test_the_plan_variant_reads_the_same_tables_three_fewer_ways() -> None:
    connection = FakeConnection()
    _backend(connection).execute_plan_variant(STATEMENT, statement_timeout_seconds=30)
    controls = [line for line in connection.log if "enable_" in line]
    assert len(controls) == 3
    assert all(
        connection.log.index(control) < connection.log.index(STATEMENT) for control in controls
    )


def test_dropping_the_copies_removes_the_tables_this_run_made_and_no_others() -> None:
    connection = FakeConnection(counts={"drivers": 100})
    backend = _backend(connection)
    backend.prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)
    connection.log.clear()
    backend.drop_shuffled_copies()
    dropped = [line for line in connection.log if "DROP TABLE IF EXISTS" in line]
    assert len(dropped) == 1
    assert "drivers" in dropped[0] and "attestql_scratch" in dropped[0]
    assert connection.log[connection.log.index(dropped[0]) + 1] == "COMMIT"


def test_dropping_the_copies_gives_the_scratch_schema_back() -> None:
    """The run's hold on the schema ends where its copies do, and not before: the lock is
    released after the last table is gone, on the key it was taken on."""
    connection = FakeConnection(counts={"drivers": 100})
    backend = _backend(connection)
    backend.prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)
    connection.log.clear()
    connection.lock_keys.clear()
    backend.drop_shuffled_copies()

    dropped = next(index for index, line in enumerate(connection.log) if "DROP TABLE" in line)
    released = next(
        index for index, line in enumerate(connection.log) if "pg_advisory_unlock" in line
    )
    assert dropped < released
    assert connection.lock_keys == [_lock_key(DEFAULT_SCRATCH_SCHEMA)]


def test_a_drop_the_server_refuses_gives_the_scratch_schema_back_anyway() -> None:
    """A copy this run cannot remove is stranded and the caller is told so. The schema is
    not stranded with it: a run that ended still holding the lock would keep every later
    run out of a schema whose copies nobody is reading."""
    connection = FakeConnection(counts={"drivers": 100})
    backend = _backend(connection)
    backend.prepare_shuffled_copies(("drivers",), seed="1", row_limit=1_000)
    connection.refuses_drops = True
    connection.lock_keys.clear()

    with pytest.raises(BackendRefused, match="permission denied") as refused:
        backend.drop_shuffled_copies()
    assert refused.value.step == "drop_shuffled_copies"
    assert any("pg_advisory_unlock" in line for line in connection.log)
    assert connection.lock_keys == [_lock_key(DEFAULT_SCRATCH_SCHEMA)]


def test_dropping_the_copies_is_safe_when_there_are_none() -> None:
    """A run that prepared nothing has nothing of its own in the schema to remove."""
    connection = FakeConnection()
    _backend(connection).drop_shuffled_copies()
    assert connection.log == []


def test_the_column_types_are_grouped_by_the_qualified_table() -> None:
    connection = FakeConnection(
        schema=(
            ("public", "results", "fastestlapspeed", "text"),
            ("public", "results", "laps", "bigint"),
        )
    )
    types = _backend(connection).column_types(("results",))
    assert {name: dict(columns) for name, columns in types.items()} == {
        "public.results": {"fastestlapspeed": "text", "laps": "bigint"}
    }


def test_the_census_counts_the_rows_the_nulls_the_empties_and_the_rest() -> None:
    connection = FakeConnection(census=(23_179, 18_185, 0, 0))
    census = _backend(connection).numeric_text_census("results", "fastestlapspeed", "^[0-9]+$")
    assert (census.rows, census.nulls, census.empty_strings, census.non_numeric) == (
        23_179,
        18_185,
        0,
        0,
    )
    assert census.pattern == "^[0-9]+$"
