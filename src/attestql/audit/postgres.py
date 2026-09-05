"""The PostgreSQL backend: read-only execution with the envelope read back.

The one property ADR-0013 point 7 carried over from the deleted product executor lives
here. Every statement runs inside ``BEGIN READ ONLY`` with a ``SET LOCAL
statement_timeout``, with the gather turned off and with the two memory settings a hash
aggregate spills at held at PostgreSQL 16's defaults, and before the statement is sent the
session is asked what it actually holds. If it does not hold all five, the execution is
refused: rows returned by a session that is not the session the record would describe are
not evidence, and a record that stated the timeout it asked for rather than the one in
force would be stating an intention as a fact. The last three are there because a float
sum is added in the order the plan produced its parts: a gather adds the partial sums in
whatever order the workers returned them, and a hash aggregate that outgrew ``work_mem``
adds them per spilled batch. Either way two executions of one statement over one table can
disagree in a late digit, and a comparison that showed that difference would be reporting
the plan and calling it the statement.

This is the only module in the project that imports the driver, which ``tests/
test_boundary.py`` asserts by walking the AST of every source file. Everything above it
speaks to ``audit.backend.Backend``, so the second engine ADR-0013 point 4 names lands
beside this file rather than inside the code that uses it.

No driver exception leaves this module. Every cursor is taken through ``_cursor`` and
every statement runs inside a ``psycopg.Error`` handler, so a connection that died between
two questions is a ``BackendRefused`` naming the step that asked, which the audit reports
as that one question's error; a raw driver error crossing this seam would abort a run that
has questions left to answer.

The connection is handed in rather than built here, except by ``connect``, so a test can
drive the read-back refusal with a connection that answers differently. The driver's own
connection is passed through one cast at that seam: psycopg's cursor is overloaded and
generic, and matching those overloads structurally would state something about the
driver's typing rather than about what this module needs from a connection.

Two result types are loaded as the server renders them rather than as the driver would
otherwise decide. A ``float4`` or ``float8`` arrives as the exact decimal the server
printed for it: the canonical serialization states no rendering for a Python float, and
in Mini-Dev 107 of 498 gold statements return one, so without this a fifth of the corpus
would be refused rather than measured. ``extra_float_digits`` is a precondition, so that
text is the shortest form that round-trips and no digit is invented or lost. An
``interval`` arrives as its own text for the same kind of reason and under the
``IntervalStyle`` precondition. Both keep the type the server named on the column, so a
reader of a record sees ``float8`` beside a value tagged ``dec`` and ``interval`` beside
one tagged ``str``.

One thing here writes, and it is named so that nothing else has to be guessed at: the
shuffled copies of ADR-0013 point 2's fourth smell are created as tables in a scratch
schema that already exists and that the role already owns, and dropped again at the end
of the run. This tool creates no schema and drops none: the login a benchmark maintainer
audits with holds SELECT and one place to write, so a shuffle that needed CREATE on the
database would be a shuffle nobody could run. The copies are made inside an explicit
``BEGIN; SET TRANSACTION READ WRITE``, which is what a role whose
``default_transaction_read_only`` is on has to state to write at all. Around the whole run
is a session-level advisory lock keyed on the scratch schema name, taken before the first
copy is made and released after the last one is dropped: a lock the writing transaction
owned would be given back at its commit, and a second run told the same schema would then
recreate or drop the copies the first is still rerunning against. Every audited statement
still runs inside ``BEGIN READ ONLY``, and no table the audit reads is ever written to.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager, suppress
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, cast

import psycopg
from psycopg import pq
from psycopg import sql as sql_builder
from psycopg.abc import Buffer
from psycopg.adapt import Loader

from attestql.audit.backend import (
    BackendRefused,
    PlannerStatistics,
    ReadBackDrift,
    ShuffledCopies,
    TableLookup,
    TableName,
    TextCensus,
)
from attestql.evidence.types import ENGINE_POSTGRESQL, SessionSettings
from attestql.kernel.types import ColumnType, ExecutionLimits, ExecutionResult

DRIVER_ERROR: type[Exception] = psycopg.Error
"""The one failure this module translates, named so that it can be raised from outside.

Everything the driver raises is one of these, and everything this module does with one is
to name the step that met it and refuse. It is stated here because no other file may import
the driver (``tests/test_boundary.py``), and a test that has to prove a lost connection
becomes a refusal rather than an exception has to be able to raise what one raises."""

NO_PARALLEL_AGGREGATION = "SET LOCAL max_parallel_workers_per_gather = 0"
"""One worker, so that a float sum is added in one order.

A gather splits an aggregate across workers and adds the partial sums in whatever order
they came back, so the same statement over the same rows can return a different last digit
on two executions, and a comparison of the two would blame the statement for the plan. It
is ``SET LOCAL``, so it holds for the statement's own transaction and is gone with the
rollback: what the session was found holding is what a summary records."""

WORK_MEM = "SET LOCAL work_mem = '4MB'"
"""The memory a sort or a hash may use before it spills, stated rather than inherited.

One worker is not enough to fix the order a float sum is added in. A hash aggregate that
outgrows this bound spills its groups to disk in batches and adds each batch's partial sums
where the batch was finished, so the same statement over the same rows returns other last
digits: measured on three of the nine summation-order-sensitive Mini-Dev golds (q1473,
q1476, q1482) between 64 kB and this value with the gather already off
(``plans/reports/research-260904-postgres-result-preconditions/hashagg_workmem_demo.json``).
Four megabytes is PostgreSQL 16's own default, written out here so that the bytes a record
states depend on this tool and not on what the server or the role happened to be
configured with."""

HASH_MEM_MULTIPLIER = "SET LOCAL hash_mem_multiplier = 2"
"""What a hash may use, as a multiple of ``work_mem``. The other half of the same bound.

A hash aggregate spills at ``work_mem`` times this, so a server holding another multiplier
spills where this one does not and the two settings decide the summation order together.
Two is PostgreSQL 16's own default and is stated for the same reason as the value above."""

MEMORY_SETTINGS: tuple[tuple[str, str, str], ...] = (
    ("work_mem", WORK_MEM, "4096"),
    ("hash_mem_multiplier", HASH_MEM_MULTIPLIER, "2"),
)
"""The two memory settings the envelope holds: each one's name, the statement that sets it,
and what ``pg_settings`` reports when it is held.

``work_mem`` reads back as 4096 rather than as ``4MB`` because that view renders a memory
setting in kilobytes, and a read-back that compared the text that was sent would compare
the spelling instead of the value. Both are set on every execution's own transaction and
read back there, and ``session_settings`` sets and reads them on a transaction of its own,
so what a record states is what its statement ran with."""

PRECONDITION_SETTINGS: tuple[str, ...] = (
    "TimeZone",
    "DateStyle",
    "IntervalStyle",
    "extra_float_digits",
    *(name for name, _, _ in MEMORY_SETTINGS),
)
"""The six session settings that are preconditions. The seventh, the database's default
collation, is a property of the database and is read separately.

The first four are ADR-0013 point 6's own and are read from the session as it was found.
The two memory settings are not: this tool sets them on every execution, so the session's
values would state a bound no statement ran under, and they are read back from inside a
transaction that set them. Both are asked of the session here as well, so that a server
which reports no value for one at all is refused where the settings are read rather than
at the first execution."""

RECORDED_SETTINGS: tuple[str, ...] = (
    "statement_timeout",
    "search_path",
    "server_version",
    "server_version_num",
    "transaction_read_only",
    "max_parallel_workers_per_gather",
    "server_encoding",
)
"""What is read back beside the preconditions, recorded and never blocking.

``server_version`` is here beside the number because the number says 160004 and the build
string says which PostgreSQL that was, which is what a reader of two summaries compares.
``max_parallel_workers_per_gather`` is the session's own, read before anything is set on
it: every execution turns the gather off on its own transaction, so this says what the
server would otherwise have been free to do rather than what any statement ran with.
``server_encoding`` is the database's own and cannot be set on a session; it is what every
text value the server rendered was rendered in, and two records made on two databases that
disagree on it are comparing bytes produced under two encodings."""

DATABASE_LOCALE = (
    "SELECT to_jsonb(d) FROM pg_catalog.pg_database AS d WHERE d.datname = current_database()"
)
"""The database's own row, read as JSON so that one query serves two servers.

The ICU locale's column was renamed: PostgreSQL 16 calls it ``daticulocale`` and 17 calls
it ``datlocale``, so a query naming either fails on the other. A row read as JSON carries
whichever key its server holds, and the reader below takes the one that is there."""

ICU_LOCALE_COLUMNS: tuple[str, ...] = ("daticulocale", "datlocale")
"""What the ICU locale is called, PostgreSQL 16's name first and 17's second. A record
states it under the first of the two whichever server answered, because a key that changed
with the server would make a reader of two records look for two names for one thing."""

RECORDED_DATABASE_LOCALE: tuple[str, ...] = (
    "datlocprovider",
    "daticulocale",
    "datcollversion",
)
"""What is recorded beside the database's collation, and never blocks a comparison.

``database_collation`` is the precondition it always was. These three say which library
sorted the text and which version of its data: the same ``en_US.utf8`` on another glibc or
ICU build can order text differently, and a reader of two records needs the provider and
the version to see that it could have. They are recorded and not preconditions because
making them block would refuse every comparison made across two hosts, including all the
ones where the sort did not change, and this repository has measured no cross-host drift
of its own (`docs/claims-register.md`, section 3)."""

ORDER_SENSITIVE_AGGREGATE_TYPES: frozenset[str] = frozenset({"float4", "float8"})
"""The result types whose aggregates depend on the order their rows were added in.

What a probe forgives a rerun for changing, named here because which types they are is a
property of how this engine adds and not of the probe. A result column carries the server's
own type name, which is what these are spelled as.
"""

DEFAULT_SCHEMA = "public"
"""Where a table named without a schema is looked for. BIRD's gold names bare tables and
the dump loads them into one schema, so an unqualified name means this one, stated here
rather than left to whatever the session's search path happens to be."""

DEFAULT_SCRATCH_SCHEMA = "attestql_scratch"
"""The schema the shuffled copies are made in, which this tool never creates or drops.

It is a schema the role already owns, arranged once by whoever grants the login its
SELECT, because a read-only auditing role cannot create a schema and should not be able
to. Only the tables this run made in it are dropped, and only at the end of the run, since
the schema is not this tool's to remove. The audited tables are never written to."""

QUALIFIED_NAME_IS_NOT_REACHED = (
    "the statement names this table's schema, and a name that states its schema is read "
    "from that schema whatever the search path holds, so the rerun reads this table and "
    "not a copy of it"
)
"""Why a copy of a table a statement qualified would not be the table the rerun reads.

The copies are reached by putting the scratch schema on the search path, which is
consulted for a name that states no schema and for no other. Written here, beside the
search path that makes it true, and carried out to the caller so that a smell reports what
its rerun covered rather than assuming it covered everything."""

LOCK_WAIT_SECONDS = 60
"""How long a run waits for the scratch schema before it is told another run holds it.

The lock is held for the length of a run, so a run that waited on it without a bound would
wait for the length of the run that holds it, and a maintainer auditing a large question
set twice at once would see the second command sitting there saying nothing. A minute is
long enough to outlast the copies of a run that is finishing and short enough that what
comes back is an answer: the shuffle was not run because the schema is held, and every
other measurement of that run still is."""

PLAN_CONTROLS: tuple[sql_builder.SQL, ...] = (
    sql_builder.SQL("SET LOCAL enable_seqscan = off"),
    sql_builder.SQL("SET LOCAL enable_hashjoin = off"),
    sql_builder.SQL("SET LOCAL enable_mergejoin = off"),
)
"""The same statement over the same rows, with three fewer ways to read them."""

CENSUS_SQL = """
SELECT count(*),
       count(*) FILTER (WHERE {column} IS NULL),
       count(*) FILTER (WHERE {column} = ''),
       count(*) FILTER (WHERE {column} IS NOT NULL AND {column} <> '' AND {column} !~ %s)
FROM {table}
"""
"""One pass over a text column for the four counts a numeric-text census is."""


class NumericFromFloatText(Loader):
    """``float4`` and ``float8`` as the exact decimal the server printed for them."""

    format = pq.Format.TEXT

    def load(self, data: Buffer) -> Decimal:
        text = bytes(data).decode("utf-8")
        try:
            return Decimal(text)
        except InvalidOperation as unreadable:
            # The server printed something no decimal can hold. Refusing names the value;
            # returning a float would put a type in a record that has no rendering.
            raise BackendRefused("float_loader", f"the server printed {text!r} for a float") from (
                unreadable
            )


class TextFromInterval(Loader):
    """``interval`` as the server's own text, under the ``IntervalStyle`` precondition."""

    format = pq.Format.TEXT

    def load(self, data: Buffer) -> str:
        return bytes(data).decode("utf-8")


class ColumnDescription(Protocol):
    """One column as the driver describes it: its name and its type oid."""

    @property
    def name(self) -> str: ...

    @property
    def type_code(self) -> int: ...


class Cursor(Protocol):
    """What this module needs from a cursor, and nothing else.

    A cell is ``Any`` because the driver decides what Python type a column comes back as,
    which is the point of a typed replay: the value is carried as it arrived and the
    canonical serialization is what states its type.
    """

    @property
    def description(self) -> Sequence[ColumnDescription] | None: ...

    def execute(self, query: object, params: Sequence[object] | None = None) -> object: ...

    def fetchall(self) -> Sequence[tuple[Any, ...]]: ...

    def fetchone(self) -> tuple[Any, ...] | None: ...

    def close(self) -> None: ...


class LoaderRegistry(Protocol):
    """Where a connection is told what Python type a server type loads as.

    The parameters are positional so that this states what is asked of the driver and
    not what the driver happens to call its arguments.
    """

    def register_loader(self, type_name: str, loader: type[Loader], /) -> None: ...


class Connection(Protocol):
    """What this module needs from a connection: cursors, and the loaders it registers."""

    @property
    def adapters(self) -> LoaderRegistry: ...

    def cursor(self) -> Cursor: ...


class PostgresBackend:
    """One PostgreSQL connection, read-only, behind ``audit.backend.Backend``.

    The connection must be in autocommit mode: this class opens and rolls back its own
    transactions by statement, and a driver managing a transaction underneath would make
    ``BEGIN READ ONLY`` mean something other than what it says. ``connect`` builds one
    that way.
    """

    def __init__(
        self, connection: Connection, *, scratch_schema: str = DEFAULT_SCRATCH_SCHEMA
    ) -> None:
        self._connection = connection
        self._identity: str | None = None
        self._session_settings: SessionSettings | None = None
        self._database_locale_read: Mapping[str, str] | None = None
        self._shuffled: ShuffledCopies | None = None
        self._scratch_schema = scratch_schema
        self._holds_the_scratch_schema = False
        """Whether this session took the run's advisory lock, so that it is taken once and
        given back once whatever the copies did."""
        connection.adapters.register_loader("float4", NumericFromFloatText)
        connection.adapters.register_loader("float8", NumericFromFloatText)
        connection.adapters.register_loader("interval", TextFromInterval)

    @classmethod
    def connect(
        cls,
        dsn: str,
        *,
        password: str | None = None,
        scratch_schema: str = DEFAULT_SCRATCH_SCHEMA,
    ) -> PostgresBackend:
        """Open one autocommit connection from a DSN, with the credential kept out of it.

        The password is a separate argument so a DSN that is written into a record or a
        log never has to carry one. The scratch schema is named here because it is a
        property of the login: it is where this role may write, and the run is told it
        rather than looking for somewhere it could.
        """
        try:
            connection = psycopg.connect(dsn, password=password, autocommit=True)
        except psycopg.Error as failed:
            # Named the way this interface names failures, so a caller that must not
            # import the driver can still tell a server it could not reach from a
            # question it could not answer.
            raise BackendRefused("connect", str(failed).strip()) from failed
        return cls(cast("Connection", connection), scratch_schema=scratch_schema)

    @property
    def scratch_schema(self) -> str:
        """Where the shuffled copies are made. Named so a summary can state it."""
        return self._scratch_schema

    def identity(self) -> str:
        """Version, server, and database, read once and repeated verbatim after that."""
        if self._identity is None:
            row = self._one(
                "SELECT version(), coalesce(inet_server_addr()::text, 'local'), "
                "coalesce(inet_server_port(), 0), current_database()",
                step="identity",
            )
            self._identity = f"{row[0]} | server={row[1]}:{row[2]} | database={row[3]}"
        return self._identity

    def effective_database_role(self) -> str:
        return str(self._one("SELECT current_user", step="role")[0])

    def default_collation(self) -> str:
        """The database's ``datcollate``, which is the precondition of the four read here."""
        return self._database_locale()["datcollate"]

    def _database_locale(self) -> Mapping[str, str]:
        """The collation the database was made with, and what a reader needs to place it.

        One question, asked once and repeated after that, because the collation is a
        precondition and the three beside it are recorded, and two round trips for one row
        of the catalogue would be one too many.

        A NULL is the empty string here. A database on the libc provider has no ICU locale
        and a ``C`` collation has no version, and a record states that absence as a value
        rather than leaving the key out: a reader comparing two records is then told what
        was measured on both sides.
        """
        if self._database_locale_read is None:
            answered = self._one(DATABASE_LOCALE, step="collation")[0]
            if not isinstance(answered, Mapping):
                raise BackendRefused(
                    "collation", "the server did not answer with a row of its database catalogue"
                )
            row = cast("Mapping[str, object]", answered)
            icu = next((row[name] for name in ICU_LOCALE_COLUMNS if name in row), None)
            read = {name: _as_text(row.get(name)) for name in RECORDED_DATABASE_LOCALE}
            read["datcollate"] = _as_text(row.get("datcollate"))
            read["daticulocale"] = _as_text(icu)
            if not read["datcollate"]:
                raise BackendRefused("collation", "the database states no default collation")
            self._database_locale_read = read
        return self._database_locale_read

    def session_settings(self) -> SessionSettings:
        """The seven settings that decide comparability, and the six recorded beside them.

        Read once and repeated after that, the way the identity is. Five of the seven the
        session was found holding and nothing here sets, so a second read of them could
        only say what the first one said at the cost of two more round trips.

        The two memory settings are the exception, and they are read from inside a
        transaction that set them to what every execution sets them to. The session's own
        values would state a bound no statement ran under, and a record whose settings
        block did not say what its statement ran with is where a comparison between two
        records would go wrong silently.

        ``recorded`` holds what the session reported and, beside the collation that blocks,
        the provider, ICU locale and collation version of the database that sorted the
        text.
        """
        if self._session_settings is None:
            read_back = self._settings((*PRECONDITION_SETTINGS, *RECORDED_SETTINGS))
            missing = sorted(name for name in PRECONDITION_SETTINGS if name not in read_back)
            if missing:
                raise BackendRefused(
                    "session_settings", f"the session reported no value for {missing}"
                )
            held = self._memory_in_force()
            locale = self._database_locale()
            self._session_settings = SessionSettings(
                engine=ENGINE_POSTGRESQL,
                time_zone=read_back["TimeZone"],
                date_style=read_back["DateStyle"],
                interval_style=read_back["IntervalStyle"],
                extra_float_digits=read_back["extra_float_digits"],
                database_collation=locale["datcollate"],
                work_mem=held["work_mem"],
                hash_mem_multiplier=held["hash_mem_multiplier"],
                recorded={
                    **{name: read_back[name] for name in RECORDED_SETTINGS if name in read_back},
                    **{name: locale[name] for name in RECORDED_DATABASE_LOCALE},
                },
            )
        return self._session_settings

    def _memory_in_force(self) -> Mapping[str, str]:
        """What ``MEMORY_SETTINGS`` holds, measured where an execution would hold it.

        One read-only transaction, the same two statements every execution sends, the same
        read-back, and a rollback. The read-back is not a formality here either: a server
        that refused one of the two would otherwise put a value into a record that no
        statement of the run could reach, and every execution would then refuse anyway.
        """
        cursor = self._cursor("memory_settings")
        try:
            try:
                cursor.execute("BEGIN READ ONLY")
                for _, statement, _ in MEMORY_SETTINGS:
                    cursor.execute(statement)
                cursor.execute(
                    "SELECT name, setting FROM pg_settings WHERE name = ANY(%s)",
                    [[name for name, _, _ in MEMORY_SETTINGS]],
                )
                held = {str(row[0]): str(row[1]) for row in cursor.fetchall()}
            except psycopg.Error as failed:
                raise BackendRefused("memory_settings", str(failed).strip()) from failed
            _require_the_memory("memory_settings", held)
        finally:
            _roll_back(cursor)
        return held

    def execute(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        """One statement, read-only, with the envelope read back before it is sent."""
        return self._execute(sql, statement_timeout_seconds=statement_timeout_seconds)

    def execute_shuffled(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        """The same statement over the shuffled copies, reached by the search path.

        The statement is not rewritten: an unqualified table name finds the copy because
        the scratch schema is ahead of ``public`` on the path, and a name the statement
        qualified itself still finds the table it qualified, since a qualified name
        consults no search path at all. Which tables a rerun therefore reads differently
        is what ``prepare_shuffled_copies`` returned, and a caller states it beside the
        result rather than assuming every table moved.
        """
        if self._shuffled is None:
            raise BackendRefused("execute_shuffled", "no shuffled copies have been prepared")
        path = sql_builder.SQL("SET LOCAL search_path = {}, {}").format(
            sql_builder.Identifier(self._scratch_schema), sql_builder.Identifier(DEFAULT_SCHEMA)
        )
        return self._execute(
            sql, statement_timeout_seconds=statement_timeout_seconds, before=(path,)
        )

    def execute_plan_variant(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        """The same statement over the same tables, with three ways to read them off."""
        return self._execute(
            sql, statement_timeout_seconds=statement_timeout_seconds, before=PLAN_CONTROLS
        )

    def _execute(
        self, sql: str, *, statement_timeout_seconds: int, before: Sequence[object] = ()
    ) -> ExecutionResult:
        """One statement, read-only, with the envelope read back before it is sent.

        ``before`` runs inside the same transaction and after the read-back, so anything
        it sets is ``SET LOCAL`` and is gone with the rollback. It never carries the
        statement itself and never changes what read-only means. The gather and the two
        memory settings are held ahead of the read-back rather than in ``before``, because
        they are not a variant of this execution: every way in runs one statement over one
        plan whose aggregate is summed in one order.
        """
        if statement_timeout_seconds < 1:
            raise BackendRefused("timeout", "a statement timeout is a whole number of seconds")
        timeout_ms = statement_timeout_seconds * 1000
        cursor = self._cursor("begin")
        try:
            try:
                cursor.execute("BEGIN READ ONLY")
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, true)", [str(timeout_ms)]
                )
                cursor.fetchall()
                cursor.execute(NO_PARALLEL_AGGREGATION)
                for _, statement, _ in MEMORY_SETTINGS:
                    cursor.execute(statement)
            except psycopg.Error as failed:
                # The envelope itself, which is where a connection that went away between
                # two questions surfaces. Named like every other refusal, so the audit
                # reports one question's error rather than ending on a driver exception.
                raise BackendRefused("begin", str(failed).strip()) from failed
            self._require_the_envelope(cursor, timeout_ms)
            try:
                for control in before:
                    cursor.execute(control)
                cursor.execute(sql)
                described = tuple(
                    (column.name, column.type_code) for column in cursor.description or ()
                )
                rows = tuple(tuple(row) for row in cursor.fetchall())
            except psycopg.Error as failed:
                # The driver's own error, named the way this interface names failures, so
                # a caller of Backend never has to know which driver refused.
                raise BackendRefused("execute", str(failed).strip()) from failed
        finally:
            _roll_back(cursor)
        return ExecutionResult(
            columns=self._columns(described),
            rows=rows,
            backend_identity=self.identity(),
            limits_in_force=ExecutionLimits(statement_timeout_ms=timeout_ms),
            truncated=False,
        )

    def existing_tables(self, tables: Sequence[TableName]) -> TableLookup:
        """Which of those names the catalogue holds, and which of them this login may read.

        ``information_schema.tables`` cannot answer this: it lists only the tables the
        current role holds some privilege on, so a table that is there and was never
        granted is absent from it and indistinguishable from a table nobody loaded. That
        is one word over two defects, and the two are repaired in different places. The
        catalogue lists what is there whatever the grants are, and
        ``has_table_privilege`` says of each row whether this login may read it, in the
        same round trip. The information schema is also a view over these same catalogues
        and is slower for it on a large one.

        ``relkind`` names the relations a gold can select from: ordinary and partitioned
        tables, views, materialised views and foreign tables. A gold that reads one of
        those is reading a table as far as this is concerned.
        """
        wanted = tuple(dict.fromkeys(tables))
        if not wanted:
            return TableLookup((), ())
        rows = self._all(
            "SELECT n.nspname, c.relname, has_table_privilege(c.oid, 'SELECT') "
            "FROM pg_catalog.pg_class AS c "
            "JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace "
            "JOIN unnest(%s::text[], %s::text[]) AS asked(nspname, relname) "
            "ON asked.nspname = n.nspname AND asked.relname = c.relname "
            "WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')",
            _asked_for(_qualified(wanted)),
            step="existing_tables",
        )
        readable = {TableName(str(row[0]), str(row[1])): bool(row[2]) for row in rows}
        return TableLookup(
            tuple(name for name in wanted if readable.get(_qualify(name)) is True),
            tuple(name for name in wanted if readable.get(_qualify(name)) is False),
        )

    def schema_digest(self, tables: Sequence[TableName]) -> str:
        """One digest over the columns of those tables, in a stated order."""
        rows = self._all(
            "SELECT c.table_schema, c.table_name, c.column_name, c.data_type, c.is_nullable "
            "FROM information_schema.columns AS c "
            "JOIN unnest(%s::text[], %s::text[]) AS asked(table_schema, table_name) "
            "ON asked.table_schema = c.table_schema::text "
            "AND asked.table_name = c.table_name::text "
            "ORDER BY c.table_schema, c.table_name, c.ordinal_position",
            _asked_for(_qualified(tables)),
            step="schema_digest",
        )
        payload = json.dumps([[str(value) for value in row] for row in rows], separators=(",", ":"))
        return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"

    def row_counts(self, tables: Sequence[TableName]) -> Mapping[str, int]:
        """The exact count of each table, counted one table at a time."""
        counts: dict[str, int] = {}
        for name in _qualified(tables):
            statement = sql_builder.SQL("SELECT count(*) FROM {}").format(_identifier(name))
            counts[name.text] = int(self._one(statement, step="row_counts")[0])
        return counts

    def column_types(self, tables: Sequence[TableName]) -> Mapping[TableName, Mapping[str, str]]:
        """Per table asked about, the declared type of every column, under the caller's name.

        The catalogue answers under the schema it holds the table in, and the answer is
        given back under the name the caller asked with, because that is the name its
        statement wrote and the name it will resolve an ordering key against.
        """
        wanted = tuple(dict.fromkeys(tables))
        if not wanted:
            return {}
        rows = self._all(
            "SELECT c.table_schema, c.table_name, c.column_name, c.data_type "
            "FROM information_schema.columns AS c "
            "JOIN unnest(%s::text[], %s::text[]) AS asked(table_schema, table_name) "
            "ON asked.table_schema = c.table_schema::text "
            "AND asked.table_name = c.table_name::text "
            "ORDER BY c.table_schema, c.table_name, c.ordinal_position",
            _asked_for(_qualified(wanted)),
            step="column_types",
        )
        held: dict[TableName, dict[str, str]] = {}
        for row in rows:
            held.setdefault(TableName(str(row[0]), str(row[1])), {})[str(row[2])] = str(row[3])
        types: dict[TableName, Mapping[str, str]] = {}
        for name in wanted:
            columns = held.get(_qualify(name))
            if columns is not None:
                types[name] = columns
        return types

    def order_sensitive_aggregate_types(self) -> frozenset[str]:
        """The two floating types PostgreSQL adds up value by value, by their server names.

        ``float4`` and ``float8`` are the ones whose aggregate moves with the order the rows
        arrive in: an ``AVG`` or a ``SUM`` over them is a running double, and a gather that
        returns its partials in another order or a hash aggregate that spilled into another
        set of batches gives another last digit. ``numeric`` is exact and is not one of them.
        """
        return ORDER_SENSITIVE_AGGREGATE_TYPES

    def numeric_text_census(self, table: TableName, column: str, pattern: str) -> TextCensus:
        """The four counts, taken in one pass over the column the caller named."""
        statement = sql_builder.SQL(CENSUS_SQL).format(
            column=sql_builder.Identifier(column), table=_identifier(_qualify(table))
        )
        counted = self._one(statement, [pattern], step="numeric_text_census")
        rows, nulls, empties, non_numeric = (int(value) for value in counted)
        return TextCensus(
            rows=rows,
            nulls=nulls,
            empty_strings=empties,
            non_numeric=non_numeric,
            pattern=pattern,
        )

    def prepare_shuffled_copies(
        self, tables: Sequence[TableName], *, seed: str, row_limit: int
    ) -> ShuffledCopies:
        """One copy of each table small enough, in an order the seed fixes, made once.

        This is the write, and it happens in the scratch schema this backend was given and
        nowhere else. Every copy is a ``CREATE TABLE AS SELECT`` off the table it copies,
        preceded by a ``DROP TABLE IF EXISTS`` that clears a copy a previous run left
        behind, and the tables themselves are only ever read. A copy carries no key, no
        index and no constraint of its own, so a statement whose grouping relied on a
        primary key will not run against it; that is the rerun's error and is reported per
        statement rather than hidden here.

        Only a name that states no schema is copied. ``execute_shuffled`` reaches the
        copies by putting the scratch schema first on the search path, which a qualified
        name never consults, so a copy made for one would be a table nothing reads: it is
        named as unreachable instead, with the reason, and the rerun that goes on reading
        the original says so. That is also what keeps the copies apart from each other,
        since two tables of one bare name in two schemas would otherwise be copied over
        each other under that one name.

        The schema is taken before anything is counted or created and is held until the
        copies are dropped, because the reruns that read them are the reason they exist. The
        lock is a session-level advisory lock keyed on the scratch schema name: a second run
        told the same schema waits ``LOCK_WAIT_SECONDS`` for it and is then told the schema
        is held, rather than making its own copies over this run's.

        A scratch schema that does not exist, that this role cannot create in, or that
        another run holds, is a refusal naming which of the three it was. It is not a tool
        error: the caller reports the shuffle as not run and audits everything else.
        """
        if row_limit < 1:
            raise BackendRefused("prepare_shuffled_copies", "a row limit is at least one row")
        self._hold_the_scratch_schema()
        wanted = tuple(dict.fromkeys(tables))
        reachable = tuple(sorted(name for name in wanted if not name.schema))
        unreachable = {name: QUALIFIED_NAME_IS_NOT_REACHED for name in wanted if name.schema}
        counts = self.row_counts(reachable)
        copied: list[TableName] = []
        skipped: dict[TableName, int] = {}
        self._shuffled = None
        with self._writing("prepare_shuffled_copies") as cursor:
            self._require_the_scratch_schema(cursor)
            for name in reachable:
                rows = counts[_qualify(name).text]
                if rows > row_limit:
                    skipped[name] = rows
                    continue
                cursor.execute(self._drop_copy(name.name))
                cursor.execute(
                    sql_builder.SQL(
                        "CREATE TABLE {scratch}.{table} AS "
                        "SELECT * FROM {source} AS t ORDER BY md5({seed} || t::text)"
                    ).format(
                        scratch=sql_builder.Identifier(self._scratch_schema),
                        table=sql_builder.Identifier(name.name),
                        source=_identifier(_qualify(name)),
                        seed=sql_builder.Literal(seed),
                    )
                )
                copied.append(name)
        prepared = ShuffledCopies(
            copied=tuple(copied),
            skipped=skipped,
            unreachable=unreachable,
            seed=seed,
            row_limit=row_limit,
        )
        self._shuffled = prepared
        return prepared

    def drop_shuffled_copies(self) -> None:
        """Drop the copies this run made, one table at a time, and give the schema back.

        The scratch schema outlives the run and is not this tool's to remove, and a table
        in it that this run did not create is somebody else's. A run that prepared nothing
        has nothing to drop and asks the server nothing.

        This is the end of the run's hold on the schema, so the advisory lock keyed on its
        name is released whatever the drop did: a copy this run could not remove is stranded
        and said so above, and a lock stranded with it would keep every later run out of a
        schema whose copies nobody is reading.
        """
        prepared, self._shuffled = self._shuffled, None
        if prepared is None and not self._holds_the_scratch_schema:
            return
        try:
            if prepared is not None:
                with self._writing("drop_shuffled_copies") as cursor:
                    for name in prepared.copied:
                        cursor.execute(self._drop_copy(name.name))
        finally:
            self._release_the_scratch_schema()

    def _hold_the_scratch_schema(self) -> None:
        """Take the run's advisory lock on the scratch schema, once, under a bounded wait.

        Session-level rather than transaction-level, so that it outlives the transaction
        that makes the copies and covers every rerun that reads them. Taken in its own short
        transaction because ``SET LOCAL lock_timeout`` needs one, and committed rather than
        rolled back so that nothing about the copies waits on this. A run that already holds
        the schema does not take a second lock on it: two would need two releases, and one
        release would leave the schema held for the life of the connection.
        """
        if self._holds_the_scratch_schema:
            return
        cursor = self._cursor("prepare_shuffled_copies")
        try:
            cursor.execute("BEGIN")
            cursor.execute("SELECT set_config('lock_timeout', %s, true)", [f"{LOCK_WAIT_SECONDS}s"])
            cursor.fetchall()
            cursor.execute("SELECT pg_advisory_lock(%s)", [_lock_key(self._scratch_schema)])
            cursor.fetchall()
            cursor.execute("COMMIT")
        except psycopg.Error as failed:
            _undo(cursor)
            raise BackendRefused(
                "prepare_shuffled_copies",
                f"the scratch schema {self._scratch_schema} was not locked within "
                f"{LOCK_WAIT_SECONDS} seconds: {str(failed).strip()}",
            ) from failed
        finally:
            _close(cursor)
        self._holds_the_scratch_schema = True

    def _release_the_scratch_schema(self) -> None:
        """Give the run's lock back, and never let that replace what is already being raised.

        A release the server refuses is nothing to report: a lock this session does not hold
        comes back false, and a connection that is gone gave the lock back on the server when
        it went. What a caller has to see is the run's own result, not the tidying up after
        it, so this asks and says nothing about the answer.
        """
        if not self._holds_the_scratch_schema:
            return
        self._holds_the_scratch_schema = False
        with suppress(psycopg.Error):
            cursor = self._connection.cursor()
            try:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [_lock_key(self._scratch_schema)])
                cursor.fetchall()
            finally:
                _close(cursor)

    def _drop_copy(self, table: str) -> sql_builder.Composed:
        """Remove one copy if it is there, which is how a leftover from a run that was
        interrupted is cleared before the same copy is made again."""
        return sql_builder.SQL("DROP TABLE IF EXISTS {scratch}.{table}").format(
            scratch=sql_builder.Identifier(self._scratch_schema),
            table=sql_builder.Identifier(table),
        )

    def _require_the_scratch_schema(self, cursor: Cursor) -> None:
        """Refuse before writing anything unless the schema is there and the role may use it."""
        cursor.execute(
            "SELECT count(*) FROM pg_namespace WHERE nspname = %s", [self._scratch_schema]
        )
        found = cursor.fetchone()
        if found is None or not int(found[0]):
            raise BackendRefused(
                "prepare_shuffled_copies",
                f"the scratch schema {self._scratch_schema} does not exist and this tool "
                "creates none",
            )
        cursor.execute(
            "SELECT current_user, has_schema_privilege(%s, 'CREATE')", [self._scratch_schema]
        )
        privilege = cursor.fetchone()
        if privilege is None or not bool(privilege[1]):
            raise BackendRefused(
                "prepare_shuffled_copies",
                f"the role {'' if privilege is None else privilege[0]} cannot create in the "
                f"scratch schema {self._scratch_schema}",
            )

    @contextmanager
    def _writing(self, step: str) -> Generator[Cursor]:
        """One read-write transaction in the scratch schema, under the run's own lock.

        ``SET TRANSACTION READ WRITE`` is stated rather than assumed: the login this tool
        is written for has ``default_transaction_read_only`` on, which is a default and not
        a privilege, so the one transaction that writes says so and every other one stays
        read only. What keeps two runs told one scratch schema apart is not this
        transaction: the caller holds the session-level advisory lock keyed on the schema
        name for the whole run, from before the copies are made until after they are
        dropped, and a lock taken here would be given back at the commit below.
        """
        cursor = self._cursor(step)
        try:
            cursor.execute("BEGIN")
            cursor.execute("SET TRANSACTION READ WRITE")
            yield cursor
            cursor.execute("COMMIT")
        except psycopg.Error as failed:
            _undo(cursor)
            raise BackendRefused(step, str(failed).strip()) from failed
        except BackendRefused:
            # This backend's own refusal, raised inside the transaction: the transaction is
            # unwound and the refusal is what the caller sees.
            _undo(cursor)
            raise
        finally:
            _close(cursor)

    def content_digests(self, tables: Sequence[TableName]) -> Mapping[str, str]:
        """A digest of every row of each table, taken in a sorted order the server fixes."""
        digests: dict[str, str] = {}
        for name in _qualified(tables):
            statement = sql_builder.SQL(
                "SELECT md5(coalesce(string_agg(t::text, chr(10) ORDER BY t::text), '')) "
                "FROM {} AS t"
            ).format(_identifier(name))
            digests[name.text] = f"md5:{self._one(statement, step='content_digests')[0]}"
        return digests

    def planner_statistics(
        self, tables: Sequence[TableName]
    ) -> Mapping[TableName, PlannerStatistics]:
        """What the plans over those tables are chosen from, in one question.

        The same catalogue and the same join shape as ``content_signal``, read for what a
        record states rather than for what a cache keys on. The join is an inner one: a name
        ``pg_stat_user_tables`` holds no row for is a view, a catalogue table or a relation
        that is not there, and none of the three has statistics an audit could record.

        Answered under the caller's own names, because the caller is what will write them
        down beside a statement that named them that way.
        """
        wanted = tuple(dict.fromkeys(tables))
        if not wanted:
            return {}
        rows = self._all(
            "SELECT n.nspname, c.relname, "
            "s.last_analyze::text, s.last_autoanalyze::text, s.n_mod_since_analyze "
            "FROM pg_catalog.pg_class AS c "
            "JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace "
            "JOIN pg_catalog.pg_stat_user_tables AS s ON s.relid = c.oid "
            "JOIN unnest(%s::text[], %s::text[]) AS asked(nspname, relname) "
            "ON asked.nspname = n.nspname AND asked.relname = c.relname",
            _asked_for(_qualified(wanted)),
            step="planner_statistics",
        )
        held = {
            TableName(str(row[0]), str(row[1])): PlannerStatistics(
                last_analyze=None if row[2] is None else str(row[2]),
                last_autoanalyze=None if row[3] is None else str(row[3]),
                n_mod_since_analyze=int(row[4]),
            )
            for row in rows
        }
        statistics: dict[TableName, PlannerStatistics] = {}
        for name in wanted:
            measured = held.get(_qualify(name))
            if measured is not None:
                statistics[name] = measured
        return statistics

    def content_signal(self, tables: Sequence[TableName]) -> Mapping[str, str]:
        """The counters the server already keeps for those tables, in one question.

        ``relfilenode`` changes when the relation was rewritten, which is what a table
        dropped and loaded again looks like, and the four tuple counters move on every
        insert, update and delete the server saw. The last three are the planner's: what a
        cached measurement is worth depends on the plan a rerun of a gold would get, and an
        analyze between two runs changes that without moving a row. Together they are eight
        values a run can ask for in a single round trip against a catalogue, where reading
        the rows costs a pass over every table.

        A name the catalogue answers nothing for gets the empty string rather than an
        invented number: a view has no file and no tuple counters, and a table that is not
        there is about to be refused by whatever asks for its rows.

        The tuple counters are cumulative statistics the server publishes after the writing
        transaction ended and at most about once a second rather than at commit, and
        ``relfilenode`` does not move on an UPDATE or a DELETE, so a run that starts inside
        that window reads the counters from before another session's write and sees a signal
        that did not move.
        """
        wanted = _qualified(tables)
        if not wanted:
            return {}
        rows = self._all(
            "SELECT n.nspname, c.relname, c.relfilenode, "
            "coalesce(s.n_tup_ins, 0), coalesce(s.n_tup_upd, 0), "
            "coalesce(s.n_tup_del, 0), coalesce(s.n_live_tup, 0), "
            "coalesce(s.n_mod_since_analyze, 0), "
            "coalesce(s.last_analyze::text, ''), coalesce(s.last_autoanalyze::text, '') "
            "FROM pg_catalog.pg_class AS c "
            "JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace "
            "LEFT JOIN pg_catalog.pg_stat_user_tables AS s ON s.relid = c.oid "
            "JOIN unnest(%s::text[], %s::text[]) AS asked(nspname, relname) "
            "ON asked.nspname = n.nspname AND asked.relname = c.relname",
            _asked_for(wanted),
            step="content_signal",
        )
        counted = {
            TableName(str(row[0]), str(row[1])): "/".join(str(value) for value in row[2:])
            for row in rows
        }
        return {name.text: counted.get(name, "") for name in wanted}

    def _require_the_envelope(self, cursor: Cursor, timeout_ms: int) -> None:
        """Refuse the execution unless the session holds what was just set on it."""
        try:
            cursor.execute(
                "SELECT name, setting FROM pg_settings WHERE name = ANY(%s)",
                [
                    [
                        "statement_timeout",
                        "transaction_read_only",
                        "max_parallel_workers_per_gather",
                        *(name for name, _, _ in MEMORY_SETTINGS),
                    ]
                ],
            )
            held = {str(row[0]): str(row[1]) for row in cursor.fetchall()}
        except psycopg.Error as failed:
            raise BackendRefused("read_back", str(failed).strip()) from failed
        if held.get("transaction_read_only") != "on":
            raise ReadBackDrift(
                "read_back",
                "the transaction is not read only; it reports "
                f"{held.get('transaction_read_only', 'nothing')}",
            )
        if held.get("statement_timeout") != str(timeout_ms):
            raise ReadBackDrift(
                "read_back",
                f"statement_timeout was set to {timeout_ms} and the session holds "
                f"{held.get('statement_timeout', 'nothing')}",
            )
        if held.get("max_parallel_workers_per_gather") != "0":
            raise ReadBackDrift(
                "read_back",
                "max_parallel_workers_per_gather was set to 0 and the session holds "
                f"{held.get('max_parallel_workers_per_gather', 'nothing')}",
            )
        _require_the_memory("read_back", held)

    def _columns(self, described: Sequence[tuple[str, int]]) -> tuple[ColumnType, ...]:
        """The projection, with the server's own name for each result type oid."""
        oids = [oid for _, oid in described]
        names: dict[int, str] = {}
        if oids:
            rows = self._all(
                "SELECT oid, typname FROM pg_type WHERE oid = ANY(%s)", [oids], step="pg_type"
            )
            names = {int(row[0]): str(row[1]) for row in rows}
        return tuple(
            ColumnType(name=name, declared_type=names.get(oid, f"oid:{oid}"))
            for name, oid in described
        )

    def _settings(self, names: Sequence[str]) -> dict[str, str]:
        rows = self._all(
            "SELECT name, setting FROM pg_settings WHERE name = ANY(%s)",
            [list(names)],
            step="session_settings",
        )
        return {str(row[0]): str(row[1]) for row in rows}

    def _cursor(self, step: str) -> Cursor:
        """One cursor, with a connection that is gone named the way this interface names it.

        Every question this module asks starts here. A connection the server closed raises
        from the driver on the cursor rather than on the statement, so the step that asked
        is named here too and no caller of ``Backend`` ever sees a ``psycopg`` exception.
        """
        try:
            return self._connection.cursor()
        except psycopg.Error as failed:
            raise BackendRefused(step, str(failed).strip()) from failed

    def _all(
        self, statement: object, params: Sequence[object] | None = None, *, step: str
    ) -> Sequence[tuple[Any, ...]]:
        """One question this module asks the server, with the driver's error named."""
        cursor = self._cursor(step)
        try:
            cursor.execute(statement, params)
            return cursor.fetchall()
        except psycopg.Error as failed:
            raise BackendRefused(step, str(failed).strip()) from failed
        finally:
            _close(cursor)

    def _one(
        self, statement: object, params: Sequence[object] | None = None, *, step: str
    ) -> tuple[Any, ...]:
        rows = self._all(statement, params, step=step)
        if not rows:
            raise BackendRefused(
                step, "the server returned no row for a question it always answers"
            )
        return rows[0]


def _as_text(value: object) -> str:
    """One catalogue value as a record states it, with a NULL as the empty string."""
    return "" if value is None else str(value)


def _require_the_memory(step: str, held: Mapping[str, str]) -> None:
    """Refuse unless the transaction holds both memory settings the envelope sets.

    One rule for the two places that set them: before a statement is sent, and where the
    settings a record states are measured. The value compared is what ``pg_settings``
    reports, so ``work_mem`` is named in the kilobytes that view renders it in and not in
    the ``4MB`` the statement spelled.
    """
    for name, _, expected in MEMORY_SETTINGS:
        if held.get(name) != expected:
            raise ReadBackDrift(
                step,
                f"{name} was set to {expected} and the session holds {held.get(name, 'nothing')}",
            )


def _undo(cursor: Cursor) -> None:
    """End the transaction whatever happened.

    A rollback that fails has nothing left to undo: the transaction is already gone, and
    letting that failure out would replace the refusal or the driver error that is the
    reason this is being unwound at all.
    """
    with suppress(psycopg.Error):
        cursor.execute("ROLLBACK")


def _roll_back(cursor: Cursor) -> None:
    """Unwind the transaction, and close the cursor whatever that did."""
    try:
        _undo(cursor)
    finally:
        _close(cursor)


def _close(cursor: Cursor) -> None:
    """Give the cursor back, and never let that replace what is already being raised.

    Closing happens in a finally, and a cursor on a connection the server closed can refuse
    to close. What a caller has to see is the refusal being unwound, not the failure of the
    tidying up after it.
    """
    with suppress(psycopg.Error):
        cursor.close()


def _lock_key(scratch_schema: str) -> int:
    """The advisory lock key of one scratch schema: the same number in every process.

    Derived from the name rather than from a sequence or a random draw, so two runs that
    were told the same scratch schema take the same lock and two that were told different
    ones do not wait on each other.
    """
    return int.from_bytes(
        hashlib.sha256(scratch_schema.encode("utf-8")).digest()[:8], "big", signed=True
    )


def _qualify(table: TableName) -> TableName:
    """One table name as the catalogue holds it: the schema it named, or the default one.

    Where an unqualified name is looked for is the engine's answer and not the parse's,
    which is why the parse leaves the schema empty and this fills it in.
    """
    return table if table.schema else TableName(DEFAULT_SCHEMA, table.name)


def _qualified(tables: Sequence[TableName]) -> tuple[TableName, ...]:
    """The table names, each under a schema, deduplicated and in a fixed order.

    Two spellings of one table are one name here: a gold that writes ``public.x`` and one
    that writes ``x`` name the same rows, and measuring both would count them twice and
    digest them twice.
    """
    return tuple(sorted({_qualify(name) for name in tables}))


def _asked_for(tables: Sequence[TableName]) -> list[list[str]]:
    """Those names as two arrays, for a query that matches a schema and a relation apart.

    Matching on ``nspname || '.' || relname`` would make one string of two identifiers,
    and a relation whose own name holds a dot would then match a table nobody named.
    """
    return [[name.schema for name in tables], [name.name for name in tables]]


def _identifier(qualified: TableName) -> sql_builder.Identifier:
    """One qualified name as the two identifiers it is, quoted by the driver."""
    return sql_builder.Identifier(qualified.schema, qualified.name)


__all__ = [
    "CENSUS_SQL",
    "DEFAULT_SCHEMA",
    "DEFAULT_SCRATCH_SCHEMA",
    "DRIVER_ERROR",
    "ORDER_SENSITIVE_AGGREGATE_TYPES",
    "PLAN_CONTROLS",
    "PRECONDITION_SETTINGS",
    "QUALIFIED_NAME_IS_NOT_REACHED",
    "RECORDED_SETTINGS",
    "ColumnDescription",
    "Connection",
    "Cursor",
    "LoaderRegistry",
    "NumericFromFloatText",
    "PostgresBackend",
    "TextFromInterval",
]
