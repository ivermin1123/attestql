"""A backend that answers from a script, and the values the audit tests are written in.

No server is reached anywhere in this suite. ``FakeBackend`` answers exactly what a test
scripted for a statement and refuses anything else, so a test that expected an execution
that never happened fails on that rather than on a missing row. It records what it was
asked, which is how the tests state that the audit set the timeout it said it would and
measured the tables the statements actually name.

The two rerun modes fall back to the plain answer when a test scripted none for them,
which is what a rerun that changed nothing looks like: a test about a shuffle that
changes an answer scripts the changed one, and every other test says nothing and gets
the quiet case rather than a line of setup per statement. ``scratch_refusal`` is the
other shape: a backend that will not make the copies at all, which is what a scratch
schema that is missing or unwritable looks like from above.

Three ways to fail are scripted because a real database has them and a fake without them
made them untestable. ``missing_tables`` names tables this database does not hold, which
is what a gold that names a table nobody loaded meets: they are absent from
``existing_tables`` and counting them refuses the way a server refuses.
``unreadable_tables`` names tables it holds and this login was never granted, which
``existing_tables`` answers under its own word and counting refuses with the server's other
message; the two are kept apart here because telling them apart is what is being tested.
``refusing`` is the connection that went away: set it at any moment, from a writer between
two questions, and every call after it refuses naming its own step, which is what the audit
sees when the server closed the socket under it. The identity, the role and the settings are
read once before the questions and never refuse, so a fake built with ``refusing`` already set
is a connection that went away after the run had started rather than one that never opened.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from attestql.audit.backend import (
    BackendRefused,
    PlannerStatistics,
    ShuffledCopies,
    TableLookup,
    TableName,
    TextCensus,
)
from attestql.evidence.serialize import SerializationDescriptor
from attestql.evidence.types import ENGINE_POSTGRESQL, SessionSettings, StatementSource
from attestql.kernel.types import ColumnType, ExecutionLimits, ExecutionResult

IDENTITY = "FakeSQL 1.0 | server=memory:0 | database=fake"
ROLE = "fake_reader"
SCRATCH = "attestql_scratch"
TIMEOUT_MS = 30_000
SCHEMA_DIGEST = "sha256:fake-schema-digest"

POSTGRESQL_FLOAT_TYPES: frozenset[str] = frozenset({"float4", "float8"})
"""What this fake answers as the types whose aggregates depend on the order they were added.

PostgreSQL's two, because these statements are written in PostgreSQL's type names, and
spelled here rather than imported so that a change to that backend's answer is a change a
test notices rather than one it follows."""

NOT_REACHED = "the statement names this table's schema, so the rerun reads it and not a copy"
"""Why a copy of a table a statement qualified is not what its rerun reads, in this fake's
words. A real backend states its own, because how the copies are reached is the engine's."""

DESCRIPTOR = SerializationDescriptor(
    version="audit-test/1",
    numeric_scale=6,
    timestamp_format="%Y-%m-%dT%H:%M:%S.%fZ",
    timezone="UTC",
    null_rendering="NULL",
    encoding="utf-8",
)

QUESTIONS_SOURCE = StatementSource(
    path="questions.json", digest="sha256:the-question-file", origin=None, date=None
)
PREDICTIONS_SOURCE = StatementSource(
    path="predictions.json", digest="sha256:the-predictions-file", origin=None, date=None
)
"""The two files a record can name as the source of its statement. No file is opened here:
a scripted backend runs statements this suite writes, and what a record states about where
they came from is the test's to say."""

SETTINGS = SessionSettings(
    engine=ENGINE_POSTGRESQL,
    time_zone="UTC",
    date_style="ISO, MDY",
    interval_style="postgres",
    extra_float_digits="1",
    database_collation="en_US.UTF-8",
    work_mem="4096",
    hash_mem_multiplier="2",
    recorded={
        "statement_timeout": "30000",
        "search_path": '"$user", public',
        "server_version": "16.4 (Debian 16.4-1.pgdg120+1)",
        "server_version_num": "160004",
        "transaction_read_only": "off",
        "max_parallel_workers_per_gather": "2",
        "server_encoding": "UTF8",
        "datlocprovider": "c",
        "daticulocale": "",
        "datcollversion": "2.41",
    },
)
"""The session a scripted run states it held. The gather is on, as it is on a server nobody
configured: what each execution sets on its own transaction is not this. The two memory
settings are the exception and state what the executions ran under, in the kilobytes and
the bare multiple ``pg_settings`` reports them in. The three catalogue values beside the
collation are what a libc database answers: a provider, no ICU locale, and the version of
the locale data that sorted the text."""


def fake_result(
    columns: Sequence[tuple[str, str]],
    rows: Sequence[tuple[object, ...]],
    *,
    identity: str = IDENTITY,
    truncated: bool = False,
    timeout_ms: int = TIMEOUT_MS,
) -> ExecutionResult:
    """One result as a backend would return it: typed columns and every row it fetched.

    ``timeout_ms`` is what the execution ran under, which a real backend reads back inside
    the transaction rather than repeating from the request. It is stated here for a test
    about what a record says the statement ran under, and is the default everywhere else.
    """
    return ExecutionResult(
        columns=tuple(ColumnType(name, declared_type) for name, declared_type in columns),
        rows=tuple(rows),
        backend_identity=identity,
        limits_in_force=ExecutionLimits(statement_timeout_ms=timeout_ms),
        truncated=truncated,
    )


class FakeBackend:
    """A ``Backend`` whose answers are the test's own."""

    def __init__(
        self,
        results: Mapping[str, ExecutionResult],
        *,
        identity: str = IDENTITY,
        role: str = ROLE,
        settings: SessionSettings = SETTINGS,
        schema_digest: str = SCHEMA_DIGEST,
        row_counts: Mapping[str, int] | None = None,
        content_digests: Mapping[str, str] | None = None,
        column_types: Mapping[TableName, Mapping[str, str]] | None = None,
        planner_statistics: Mapping[TableName, PlannerStatistics] | None = None,
        censuses: Mapping[tuple[TableName, str], TextCensus] | None = None,
        shuffled_results: Mapping[str, ExecutionResult] | None = None,
        plan_results: Mapping[str, ExecutionResult] | None = None,
        skipped_tables: Mapping[TableName, int] | None = None,
        scratch_refusal: str | None = None,
        order_sensitive_aggregate_types: frozenset[str] = POSTGRESQL_FLOAT_TYPES,
        missing_tables: Sequence[TableName] = (),
        unreadable_tables: Sequence[TableName] = (),
        refusing: str | None = None,
    ) -> None:
        self._results = dict(results)
        self._identity = identity
        self._role = role
        self._settings = settings
        self._schema_digest = schema_digest
        self._row_counts = dict(row_counts or {})
        self._content_digests = dict(content_digests or {})
        self._column_types = {name: dict(columns) for name, columns in (column_types or {}).items()}
        self._planner_statistics = dict(planner_statistics or {})
        self._censuses = dict(censuses or {})
        self._shuffled_results = dict(shuffled_results or {})
        self._plan_results = dict(plan_results or {})
        self._skipped_tables = dict(skipped_tables or {})
        self._scratch_refusal = scratch_refusal
        self._order_sensitive_aggregate_types = order_sensitive_aggregate_types
        self._missing_tables = set(missing_tables)
        self._unreadable_tables = set(unreadable_tables)
        self.refusing = refusing
        """What every call refuses with from now on, or ``None`` while the server is there."""
        self.executed: list[tuple[str, int]] = []
        self.settings_calls = 0
        """How many times the run asked what session it holds, which a run asks once."""
        self.existing_table_calls: list[tuple[TableName, ...]] = []
        self.schema_digest_calls: list[tuple[TableName, ...]] = []
        self.row_count_calls: list[tuple[TableName, ...]] = []
        self.content_digest_calls: list[tuple[TableName, ...]] = []
        self.content_signal_calls: list[tuple[TableName, ...]] = []
        self.column_type_calls: list[tuple[TableName, ...]] = []
        self.planner_statistics_calls: list[tuple[TableName, ...]] = []
        self.census_calls: list[tuple[TableName, str, str]] = []
        self.executed_shuffled: list[tuple[str, int]] = []
        self.executed_plan_variant: list[tuple[str, int]] = []
        self.prepared: list[tuple[tuple[TableName, ...], str, int]] = []
        self.dropped = 0

    @property
    def scratch(self) -> str:
        """Where this fake would make its copies, in PostgreSQL's words like the rest of it,
        and spelled here rather than imported so that a change to that backend's default is
        a change a test notices rather than one it follows."""
        return SCRATCH

    def identity(self) -> str:
        return self._identity

    def effective_database_role(self) -> str:
        return self._role

    def session_settings(self) -> SessionSettings:
        self.settings_calls += 1
        return self._settings

    def default_collation(self) -> str:
        """What this fake's session states, which on PostgreSQL is never absent."""
        collation = self._settings.database_collation
        if collation is None:
            raise AssertionError(f"a fake on {self._settings.engine} states no default collation")
        return collation

    def _refuse_if_the_server_went_away(self, step: str) -> None:
        """Every call after ``refusing`` was set, named the way this backend names failures."""
        if self.refusing is not None:
            raise BackendRefused(step, self.refusing)

    def execute(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        self.executed.append((sql, statement_timeout_seconds))
        self._refuse_if_the_server_went_away("execute")
        if sql not in self._results:
            raise AssertionError(f"no result was scripted for {sql!r}")
        return self._results[sql]

    def existing_tables(self, tables: Sequence[TableName]) -> TableLookup:
        self.existing_table_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("existing_tables")
        wanted = tuple(dict.fromkeys(tables))
        absent = self._missing_tables | self._unreadable_tables
        return TableLookup(
            tuple(name for name in wanted if name not in absent),
            tuple(name for name in wanted if name in self._unreadable_tables),
        )

    def schema_digest(self, tables: Sequence[TableName]) -> str:
        self.schema_digest_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("schema_digest")
        return self._schema_digest

    def row_counts(self, tables: Sequence[TableName]) -> Mapping[str, int]:
        self.row_count_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("row_counts")
        absent = [name for name in tables if name in self._missing_tables]
        if absent:
            # What counting a table nobody loaded costs on a server, in the words a server
            # uses, because that message is what reaches the question's line.
            raise BackendRefused("row_counts", f'relation "{absent[0].text}" does not exist')
        denied = [name for name in tables if name in self._unreadable_tables]
        if denied:
            # The other message, for the table that is there and was never granted.
            raise BackendRefused("row_counts", f"permission denied for table {denied[0].name}")
        return {name.text: self._row_counts.get(name.text, 0) for name in tables}

    def content_digests(self, tables: Sequence[TableName]) -> Mapping[str, str]:
        self.content_digest_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("content_digests")
        return {
            name.text: self._content_digests.get(name.text, f"md5:{name.text}") for name in tables
        }

    def content_signal(self, tables: Sequence[TableName]) -> Mapping[str, str]:
        """What a server's own counters would say about these rows, derived from them here.

        A fake whose signal were scripted apart from its rows could be told to hold new rows
        under the counters of the old ones, which is a database nobody has: on a server the
        counters move because the rows did. So the signal is read off what this backend was
        built with, and a test states a reload by building one that holds other rows.

        The planner's statistics are in it for the same reason they are in a server's: what
        a cached measurement is worth depends on the plan the data is read with, and an
        analyze between two runs changes that without moving a row.
        """
        self.content_signal_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("content_signal")
        return {
            name.text: (
                f"{self._row_counts.get(name.text, 0)}/{self._content_digests.get(name.text, '')}"
                f"/{self._planner_statistics.get(name)}"
            )
            for name in tables
        }

    def column_types(self, tables: Sequence[TableName]) -> Mapping[TableName, Mapping[str, str]]:
        self.column_type_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("column_types")
        return {name: dict(columns) for name, columns in self._column_types.items()}

    def planner_statistics(
        self, tables: Sequence[TableName]
    ) -> Mapping[TableName, PlannerStatistics]:
        """The statistics a test built this backend with, for the names it holds any for."""
        self.planner_statistics_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("planner_statistics")
        return {
            name: self._planner_statistics[name]
            for name in dict.fromkeys(tables)
            if name in self._planner_statistics
        }

    def order_sensitive_aggregate_types(self) -> frozenset[str]:
        """What this fake's engine adds up value by value, PostgreSQL's two by default.

        A test about an engine that compensates its sums builds the fake with the empty set,
        which is SQLite's answer and the one that forgives nothing.
        """
        return self._order_sensitive_aggregate_types

    def numeric_text_census(self, table: TableName, column: str, pattern: str) -> TextCensus:
        self.census_calls.append((table, column, pattern))
        self._refuse_if_the_server_went_away("numeric_text_census")
        scripted = self._censuses.get((table, column))
        if scripted is None:
            raise AssertionError(f"no census was scripted for {table.text}.{column}")
        return scripted

    def prepare_shuffled_copies(
        self, tables: Sequence[TableName], *, seed: str, row_limit: int
    ) -> ShuffledCopies:
        """The copies a real backend would make: of the bare names, minus the large ones.

        A name that states its schema is copied by no backend, because a rerun reaches the
        copies by the search path and a qualified name consults none, so it comes back
        under ``unreachable`` here the way a server's backend reports it.
        """
        self.prepared.append((tuple(tables), seed, row_limit))
        self._refuse_if_the_server_went_away("prepare_shuffled_copies")
        if self._scratch_refusal is not None:
            # The shape of a scratch schema that is missing or that the login cannot write
            # to: the backend refuses, and the audit runs without the shuffled reruns.
            raise BackendRefused("prepare_shuffled_copies", self._scratch_refusal)
        reachable = [name for name in tables if not name.schema]
        return ShuffledCopies(
            copied=tuple(name for name in reachable if name not in self._skipped_tables),
            skipped={
                name: rows for name, rows in self._skipped_tables.items() if name in reachable
            },
            unreachable={name: NOT_REACHED for name in tables if name.schema},
            seed=seed,
            row_limit=row_limit,
        )

    def drop_shuffled_copies(self) -> None:
        self._refuse_if_the_server_went_away("drop_shuffled_copies")
        self.dropped += 1

    def execute_shuffled(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        self.executed_shuffled.append((sql, statement_timeout_seconds))
        self._refuse_if_the_server_went_away("execute_shuffled")
        return self._scripted(self._shuffled_results, sql, "shuffled")

    def execute_plan_variant(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        self.executed_plan_variant.append((sql, statement_timeout_seconds))
        self._refuse_if_the_server_went_away("execute_plan_variant")
        return self._scripted(self._plan_results, sql, "the plan variant")

    def _scripted(
        self, results: Mapping[str, ExecutionResult], sql: str, variant: str
    ) -> ExecutionResult:
        """The rerun a test scripted, or the plain answer when it scripted none."""
        if sql in results:
            return results[sql]
        if sql not in self._results:
            raise AssertionError(f"no result was scripted for {sql!r} under {variant}")
        return self._results[sql]
