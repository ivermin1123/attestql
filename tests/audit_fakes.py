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

Two ways to fail are scripted because a real database has them and a fake without them
made them untestable. ``missing_tables`` names tables this database does not hold, which
is what a gold that names a table nobody loaded meets: they are absent from
``existing_tables`` and counting them refuses the way a server refuses. ``refusing`` is
the connection that went away: set it at any moment, from a writer between two questions,
and every call after it refuses naming its own step, which is what the audit sees when the
server closed the socket under it. The identity, the role and the settings are read once
before the questions and never refuse, so a fake built with ``refusing`` already set is a
connection that went away after the run had started rather than one that never opened.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from attestql.audit.backend import BackendRefused, ShuffledCopies, TextCensus
from attestql.evidence.serialize import SerializationDescriptor
from attestql.evidence.types import SessionSettings
from attestql.kernel.types import ColumnType, ExecutionLimits, ExecutionResult

IDENTITY = "FakeSQL 1.0 | server=memory:0 | database=fake"
ROLE = "fake_reader"
TIMEOUT_MS = 30_000
SCHEMA_DIGEST = "sha256:fake-schema-digest"

DESCRIPTOR = SerializationDescriptor(
    version="audit-test/1",
    numeric_scale=6,
    timestamp_format="%Y-%m-%dT%H:%M:%S.%fZ",
    timezone="UTC",
    null_rendering="NULL",
    encoding="utf-8",
)

SETTINGS = SessionSettings(
    time_zone="UTC",
    date_style="ISO, MDY",
    interval_style="postgres",
    extra_float_digits="1",
    database_collation="en_US.UTF-8",
    recorded={
        "statement_timeout": "30000",
        "search_path": '"$user", public',
        "server_version_num": "160004",
        "transaction_read_only": "off",
    },
)


def fake_result(
    columns: Sequence[tuple[str, str]],
    rows: Sequence[tuple[object, ...]],
    *,
    identity: str = IDENTITY,
    truncated: bool = False,
) -> ExecutionResult:
    """One result as a backend would return it: typed columns and every row it fetched."""
    return ExecutionResult(
        columns=tuple(ColumnType(name, pg_type) for name, pg_type in columns),
        rows=tuple(rows),
        backend_identity=identity,
        limits_in_force=ExecutionLimits(statement_timeout_ms=TIMEOUT_MS),
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
        column_types: Mapping[str, Mapping[str, str]] | None = None,
        censuses: Mapping[tuple[str, str], TextCensus] | None = None,
        shuffled_results: Mapping[str, ExecutionResult] | None = None,
        plan_results: Mapping[str, ExecutionResult] | None = None,
        skipped_tables: Mapping[str, int] | None = None,
        scratch_refusal: str | None = None,
        missing_tables: Sequence[str] = (),
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
        self._censuses = dict(censuses or {})
        self._shuffled_results = dict(shuffled_results or {})
        self._plan_results = dict(plan_results or {})
        self._skipped_tables = dict(skipped_tables or {})
        self._scratch_refusal = scratch_refusal
        self._missing_tables = set(missing_tables)
        self.refusing = refusing
        """What every call refuses with from now on, or ``None`` while the server is there."""
        self.executed: list[tuple[str, int]] = []
        self.existing_table_calls: list[tuple[str, ...]] = []
        self.schema_digest_calls: list[tuple[str, ...]] = []
        self.row_count_calls: list[tuple[str, ...]] = []
        self.content_digest_calls: list[tuple[str, ...]] = []
        self.column_type_calls: list[tuple[str, ...]] = []
        self.census_calls: list[tuple[str, str, str]] = []
        self.executed_shuffled: list[tuple[str, int]] = []
        self.executed_plan_variant: list[tuple[str, int]] = []
        self.prepared: list[tuple[tuple[str, ...], str, int]] = []
        self.dropped = 0

    def identity(self) -> str:
        return self._identity

    def effective_database_role(self) -> str:
        return self._role

    def session_settings(self) -> SessionSettings:
        return self._settings

    def default_collation(self) -> str:
        return self._settings.database_collation

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

    def existing_tables(self, tables: Sequence[str]) -> tuple[str, ...]:
        self.existing_table_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("existing_tables")
        return tuple(name for name in dict.fromkeys(tables) if name not in self._missing_tables)

    def schema_digest(self, tables: Sequence[str]) -> str:
        self.schema_digest_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("schema_digest")
        return self._schema_digest

    def row_counts(self, tables: Sequence[str]) -> Mapping[str, int]:
        self.row_count_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("row_counts")
        absent = [name for name in tables if name in self._missing_tables]
        if absent:
            # What counting a table nobody loaded costs on a server, in the words a server
            # uses, because that message is what reaches the question's line.
            raise BackendRefused("row_counts", f'relation "{absent[0]}" does not exist')
        return {name: self._row_counts.get(name, 0) for name in tables}

    def content_digests(self, tables: Sequence[str]) -> Mapping[str, str]:
        self.content_digest_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("content_digests")
        return {name: self._content_digests.get(name, f"md5:{name}") for name in tables}

    def column_types(self, tables: Sequence[str]) -> Mapping[str, Mapping[str, str]]:
        self.column_type_calls.append(tuple(tables))
        self._refuse_if_the_server_went_away("column_types")
        return {name: dict(columns) for name, columns in self._column_types.items()}

    def numeric_text_census(self, table: str, column: str, pattern: str) -> TextCensus:
        self.census_calls.append((table, column, pattern))
        self._refuse_if_the_server_went_away("numeric_text_census")
        scripted = self._censuses.get((table, column))
        if scripted is None:
            raise AssertionError(f"no census was scripted for {table}.{column}")
        return scripted

    def prepare_shuffled_copies(
        self, tables: Sequence[str], *, seed: str, row_limit: int
    ) -> ShuffledCopies:
        self.prepared.append((tuple(tables), seed, row_limit))
        self._refuse_if_the_server_went_away("prepare_shuffled_copies")
        if self._scratch_refusal is not None:
            # The shape of a scratch schema that is missing or that the login cannot write
            # to: the backend refuses, and the audit runs without the shuffled reruns.
            raise BackendRefused("prepare_shuffled_copies", self._scratch_refusal)
        return ShuffledCopies(
            copied=tuple(name for name in tables if name not in self._skipped_tables),
            skipped={name: rows for name, rows in self._skipped_tables.items() if name in tables},
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
