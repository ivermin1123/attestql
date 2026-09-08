"""The SQLite backend: one file, opened read-only, behind ``audit.backend.Backend``.

ADR-0014 point 2. Everything above this module speaks to ``Backend``, so what a SQLite
file cannot state is stated as such here rather than faked further up.

**Values, and why a REAL becomes a Decimal.** SQLite types values and not columns, so the
type of a cell is its storage class and nothing else (ADR-0004). An INTEGER comes back as
``int``, a TEXT as ``str``, a NULL as ``None``, and a REAL as ``Decimal(repr(value))``: the
shortest decimal that round-trips the double the file holds. Two reasons, and they are the
same reason twice. The canonical serialization states no rendering for a Python float, so a
float reaching a record would be refused rather than written; and under R-SET a value only
meets a value of its own storage class, so a REAL ``1.0`` and an INTEGER ``1`` have to stay
two values, which they do when one is ``dec`` and the other ``int``. A BLOB has no
rendering either and no decimal to become, so a statement that returns one is refused the
way the PostgreSQL backend refuses a float its server printed unreadably: named, at the
value, rather than carried into a record nothing can serialize.

**A TEXT cell whose bytes are not UTF-8 is the data, and is recorded.** SQLite stores what it
was given, and a benchmark database can hold a text column whose bytes no encoding decodes;
Python's driver raises in its decoder there and the whole statement fails, which is two Spider
golds nobody can audit. The connection's ``text_factory`` therefore answers with the text when
it decodes and with ``UndecodedText`` when it does not, which is the bytes themselves under a
tag of their own. The cell stays a TEXT cell: its storage class is TEXT, it is never equal to
text that decoded, and it is never equal to a BLOB holding the same bytes either.

**What a result column's type is.** A SQLite column has no declared result type, so
``declared_type`` carries the storage class the column's cells were observed at, read from
the fetched rows: one class name when every cell agrees and the sorted classes joined with
``|`` when they do not. The comparator types every cell through ``typed_row`` already, so a
mixed column is compared per cell without anything changing there; this is what a reader of
the record is told the column was.

**Read-only is the file.** The connection is opened ``file:<path>?mode=ro`` and holds
``PRAGMA query_only = 1``, which is read back before every statement exactly as the
PostgreSQL backend reads its ``SET LOCAL``s back, and drift is refused the same way. Both
refuse a write with SQLite's own ``attempt to write a readonly database``.

**A file in WAL mode on read-only media is read through a private copy.** SQLite creates a
``-shm`` and a ``-wal`` beside a database whose header says WAL, even to read it, so a directory
that cannot be written to refuses the open with ``attempt to write a readonly database``. Rather
than tell SQLite the file is immutable, which is a promise a run cannot check, the whole file and
whatever sidecars it has are copied into a private directory and the copy is opened. The original
is what the identity, the size and the content signal are read from, because the original is what
was audited; the copy is named in the session settings under ``read_through_private_copy`` and goes
when the run does. It costs what the file weighs, which is 262 MB for BIRD's ``card_games``.

**The shuffled copies live in TEMP, on a connection of their own.** SQLite resolves an
unqualified name in ``temp`` before ``main``, so a copy named like the table shadows it for
the gold's own text, which is what the PostgreSQL scratch schema on the search path
achieves. A TEMP table belongs to the connection that made it, so the copies are made and
read on a second connection to the same file and the audited connection never sees them;
``query_only`` is turned off for the copy statements alone and is on again for every rerun.
There is no lock and none is needed: one file, one process, and a TEMP table no other
connection can even name. Nothing is created in the file, which ``mode=ro`` could not do
anyway, and the copies go with the connection at the end of the run.

**The digests are this module's own, and Python-side.** SQLite has no ``md5`` and no
ordered ``string_agg``, so ``content_digests`` renders every row here and sorts the rows by
their rendered bytes, which makes the digest independent of the order the rows are stored
in. ``schema_digest`` is taken over the ``sqlite_master`` DDL text of the tables asked
about, in name order. ``planner_statistics`` answers with nothing at all: SQLite keeps
statistics in ``sqlite_stat1``, which exists only after an ``ANALYZE``, and an audit reads.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
import time
import weakref
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager, suppress
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

from attestql.audit.backend import (
    READ_THROUGH_PRIVATE_COPY,
    BackendRefused,
    PlannerStatistics,
    ReadBackDrift,
    ShuffledCopies,
    StatementTimedOut,
    TableLookup,
    TableName,
    TextCensus,
    folded,
)
from attestql.evidence.serialize import UndecodedText
from attestql.evidence.types import ENGINE_SQLITE, SessionSettings
from attestql.kernel.types import ColumnType, ExecutionLimits, ExecutionResult

DRIVER_ERROR: type[Exception] = sqlite3.Error
"""The one failure this module translates, named so that it can be raised from outside.

Everything the driver raises is one of these, and everything this module does with one is to
name the step that met it and refuse. It is stated here for the reason the PostgreSQL
backend states its own: a test that has to prove a lost file becomes a refusal rather than
an exception has to be able to raise what one raises."""

DEFAULT_SCHEMA = "main"
"""Where a table named without a schema is looked for. A SQLite file that has attached
nothing holds one schema and this is its name, stated here rather than left implicit, so a
gold that writes ``main.t`` and one that writes ``t`` name one table."""

TEMP_SCHEMA = "temp"
"""Where the shuffled copies are made. Every connection has it, nobody grants it, and it is
gone when the connection is."""

QUERY_ONLY = "PRAGMA query_only"
"""The envelope. Set to 1 on every connection this module opens and read back before every
statement, because a session that is not the session the record would describe returns rows
that are not evidence."""

STORAGE_CLASSES: Mapping[type, str] = {
    type(None): "NULL",
    int: "INTEGER",
    float: "REAL",
    str: "TEXT",
    UndecodedText: "TEXT",
    bytes: "BLOB",
}
"""SQLite's five storage classes, by the Python type its driver hands each one back as.

The mapping is exact and not by subclass: it is what the driver returns for a cell and the
whole of what a SQLite value can be, so a type that is not here is a driver that has been
told to adapt something and a value this module cannot say the storage class of. That is why
``UndecodedText`` is here beside ``str``: it is a TEXT cell this reader could not decode, and
a lookup by subclass would have called it a BLOB."""

ORDER_SENSITIVE_AGGREGATE_TYPES: frozenset[str] = frozenset()
"""The result types whose aggregates depend on the order their rows were added in: none.

SQLite has one floating type and adds it with a compensated summation, so no aggregate over
it moves with the order the rows arrive in. The set is empty rather than absent because the
question is asked of every engine and the empty answer is this engine's own.
"""

MIXED_CLASSES = "|"
"""What joins the storage classes of a column whose cells do not agree on one."""

UNOBSERVED = "UNOBSERVED"
"""What a column of a result with no rows is typed as. A storage class is a property of a
value, so a column that returned no value was observed at none; the field is never empty,
because a reader comparing two records has to be told that this was measured and came back
with nothing rather than left out."""

NUMERIC_TEXT_FUNCTION = "regexp"
"""The name SQLite's ``X REGEXP Y`` operator calls, which the file does not define. It is
registered from Python for the length of the connection, so the census asks the same
question here that it asks of PostgreSQL's ``!~``."""

SHUFFLE_FUNCTION = "attestql_shuffle"
"""The order a shuffled copy is written in: a digest of the run's seed and the source row's
own identity. Registered from Python because SQLite has no hash function of its own, and
deterministic, so a run reproduces and two runs under one seed write one order."""

TEXT_AFFINITY_MARKS: tuple[str, ...] = ("CHAR", "CLOB", "TEXT")
"""What a declaration has to contain for SQLite to give the column TEXT affinity.

Rule 2 of the affinity rules, and the reason a declared type is read here by what it holds
rather than by what it equals: SQLite keeps the text of the CREATE statement verbatim and
decides affinity from that text, so ``VARCHAR(50)`` and ``NATIVE CHARACTER(70)`` are text
columns and match no list of type names. The comparison is over the declaration upper-cased,
because the rule is case-insensitive and a file may be written either way."""

INTERRUPT_MESSAGE = "interrupted"
"""What SQLite calls the abort a progress handler asked for, and the whole of how a statement
this module stopped is told from one the file refused.

Every other error is the engine's own answer about the statement and keeps its own message,
however long the statement had been running when it arrived: a clock that has passed the
deadline does not turn a missing table into a slow one."""

PROGRESS_INSTRUCTIONS = 1000
"""How often the statement timeout is checked, in SQLite virtual-machine instructions.

SQLite has no statement timeout to set and read back, so the bound is enforced here: the
progress handler is asked this often and aborts the statement once the deadline has passed.
Small enough that a runaway statement is stopped promptly and large enough that the check is
not what the statement spends its time on."""

WAL_IN_THE_HEADER = 2
"""What bytes 18 and 19 of a SQLite file hold when the file is in WAL mode."""

PRIVATE_COPY_PREFIX = "attestql-sqlite-"
"""The prefix of the private directory a WAL file on read-only media is copied into."""

CANNOT_WRITE = ("attempt to write a readonly database", "unable to open database file")
"""What SQLite says when it cannot create the sidecars a WAL file needs to be read."""

RECORDED_PRAGMAS: tuple[str, ...] = (
    "encoding",
    "reverse_unordered_selects",
    "query_only",
    "journal_mode",
    "data_version",
)
"""The five settings a record states that are read straight off a pragma of one value.

The other four of ADR-0014's nine are read differently and beside them: the version is a
function, the compile options and the collation list are many rows, and
``case_sensitive_like`` is a pragma SQLite only accepts and never answers, so what is
recorded for it is what the file was observed doing."""

CENSUS_SQL = (
    "SELECT count(*), "
    "coalesce(sum(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END), 0), "
    "coalesce(sum(CASE WHEN {column} = '' THEN 1 ELSE 0 END), 0), "
    "coalesce(sum(CASE WHEN {column} IS NOT NULL AND {column} <> '' "
    "AND NOT ({column} REGEXP ?) THEN 1 ELSE 0 END), 0) "
    "FROM {schema}.{table}"
)
"""One pass over a text column for the four counts a numeric-text census is.

``sum`` over no rows is NULL in SQLite, so each count is read as the zero it means; the
PostgreSQL backend gets the same four from ``count(*) FILTER``."""

SHUFFLED_COPY = (
    "CREATE TEMP TABLE {copy} AS SELECT * FROM {schema}.{table} ORDER BY attestql_shuffle(?, rowid)"
)
"""One shuffled copy, in the order the run's seed and the source row's rowid fix. The
function it orders by is the one ``SHUFFLE_FUNCTION`` registers on the connection."""

CASE_SENSITIVE_LIKE = "SELECT CASE WHEN 'A' LIKE 'a' THEN 0 ELSE 1 END"
"""``PRAGMA case_sensitive_like`` can be set and cannot be read, so the setting is measured
rather than asked for: the answer is the behaviour a statement of this run would meet."""

WITHOUT_A_ROW_IDENTITY = (
    "the relation has no rowid, so there is no stable row identity to order a seeded copy "
    "by, and the rerun reads the relation itself"
)
"""Why a view and a WITHOUT ROWID table are not copied. Both answer the same way to the same
probe, and both are read in place by a rerun, which is what the caller states."""

NOT_IN_THIS_FILE = (
    "this file holds no relation of that name, so there is nothing to copy and the rerun "
    "meets the same missing relation the statement itself does"
)
"""Why a name nobody loaded is not shuffled. The run says so rather than stopping: a table
the data does not hold is one question's error line."""

QUALIFIED_NAME_IS_NOT_REACHED = (
    "the statement names this table's schema, and a name that states its schema is read from "
    "that schema whatever TEMP holds, so the rerun reads this table and not a copy of it"
)
"""Why a copy of a table a statement qualified would not be the table the rerun reads.

The copies are reached because SQLite resolves an unqualified name in ``temp`` before
``main``, and for no other name. Written here, beside the rule that makes it true, and
carried out to the caller so that a smell reports what its rerun covered."""


def _identifier(name: str) -> str:
    """One identifier quoted the way SQLite quotes one, with an embedded quote doubled."""
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def _sql(template: str, **identifiers: str) -> str:
    """One of this module's own statements, with every name put into it quoted for SQLite.

    The templates are written out in this file and the only thing that ever reaches one from
    outside is an identifier, which is quoted here and nowhere else. That is what keeps the
    quoting in one place: the PostgreSQL backend has its driver's identifier builder for
    this and the standard library's SQLite driver has none.
    """
    return template.format(**{key: _identifier(name) for key, name in identifiers.items()})


def _over(table: TableName) -> dict[str, str]:
    """The two identifiers a statement of this module names one table by."""
    return {"schema": table.schema or DEFAULT_SCHEMA, "table": table.name}


def _qualify(table: TableName) -> TableName:
    """One table name as this file holds it: the schema it named, or the default one."""
    return table if table.schema else TableName(DEFAULT_SCHEMA, table.name)


def _in_this_file(table: TableName, held: Mapping[str, str]) -> TableName | None:
    """That name as the file spells it, or ``None`` when the file holds no such relation.

    SQLite matches a relation name without regard to the case of its ASCII letters, so a
    gold that writes ``Team_Attributes`` reads the table the file created as
    ``team_attributes``. The file's
    own spelling is what every statement of this module then writes and what every
    measurement is keyed by, so two spellings of one table are one table here rather than one
    that is measured and one that is reported missing.

    A name that states a schema other than ``main`` is held by nothing: a file that has
    attached nothing has one schema.
    """
    if table.schema not in ("", DEFAULT_SCHEMA):
        return None
    by_folded_name = {folded(name): name for name in held}
    found = by_folded_name.get(folded(table.name))
    return None if found is None else TableName(DEFAULT_SCHEMA, found)


def _storage_class(value: object) -> str:
    """The SQLite storage class of one cell, by the Python type the driver returned it as."""
    found = STORAGE_CLASSES.get(type(value))
    if found is None:
        raise BackendRefused(
            "storage_class",
            f"the driver returned a {type(value).__name__}, which is no SQLite storage class",
        )
    return found


def _as_recorded(value: object) -> object:
    """One cell as a record holds it: a REAL as a decimal, a BLOB refused, the rest as it is.

    ``repr`` of a Python float is the shortest decimal text that round-trips the double, so
    the decimal built from it holds exactly the number the file holds and no digit is
    invented or lost. A BLOB has no canonical rendering and no decimal to become, so it is
    refused here rather than carried into a record that could not be written. Text that did
    not decode has one, and is a TEXT cell rather than a BLOB, so it goes into the record as
    the bytes it is.
    """
    if isinstance(value, UndecodedText):
        return value
    if isinstance(value, bytes):
        raise BackendRefused(
            "blob_value",
            f"the file holds a BLOB of {len(value)} bytes in this result and the canonical "
            "serialization states no rendering for one",
        )
    if isinstance(value, float):
        return Decimal(repr(value))
    return value


def _declared_type(observed: Iterable[str]) -> str:
    """What a result column is typed as, from the storage classes its cells were seen at."""
    classes = sorted(set(observed))
    if not classes:
        return UNOBSERVED
    return MIXED_CLASSES.join(classes)


def _rendered_cell(value: object) -> str:
    """One cell as this module's content digest renders it: its class, then its value.

    Typed, for the reason the canonical serialization is typed: an INTEGER 1 and a TEXT '1'
    are two values and a digest that rendered both as ``1`` would call two tables one. A
    REAL is rendered from ``repr`` so the text round-trips the double, and a BLOB as hex so
    that every storage class has a rendering here even though a record has none for that
    one.
    """
    storage = _storage_class(value)
    if isinstance(value, UndecodedText):
        # TEXT is its storage class and hex is the only rendering its bytes have, so the
        # class is qualified here: without that, text reading "ff" and the byte 0xff would
        # render alike and a digest would call two tables one.
        return f"{storage}-undecoded:{value.hex()}"
    if value is None:
        payload = ""
    elif isinstance(value, bytes):
        payload = value.hex()
    elif isinstance(value, float):
        payload = repr(value)
    else:
        payload = str(value)
    return f"{storage}:{payload}"


def _rendered_row(row: Sequence[object]) -> bytes:
    """One row of a table as the content digest reads it, unambiguously separated."""
    return json.dumps([_rendered_cell(value) for value in row], separators=(",", ":")).encode(
        "utf-8"
    )


def _numeric_text(pattern: str, value: object) -> bool | None:
    """``X REGEXP Y`` for one cell: whether the pattern matches, and NULL for a NULL.

    ``re.search`` and not ``re.match``, because the pattern is the caller's and is anchored
    by the caller where it means to be, which is what PostgreSQL's ``!~`` does with the same
    text. A cell that is not text is answered about its own rendering, so a census over a
    column that turned out to hold a number counts it as the number it prints as.
    """
    if value is None:
        return None
    if isinstance(value, UndecodedText):
        # Its bytes are not text and their hex is not the value: a census over a column
        # holding one counts it as matching nothing, which keeps the smell conservative.
        return False
    text = value.hex() if isinstance(value, bytes) else str(value)
    return re.search(pattern, text) is not None


def _shuffle_key(seed: object, rowid: object) -> str:
    """Where one row of a copy is written: a digest of the run's seed and the row's rowid.

    Deterministic and stated rather than random, so a run reproduces; over the rowid rather
    than over the row's own values, so two identical rows still land in two places and a
    copy holds the same multiset the table does.
    """
    return hashlib.sha256(f"{seed}:{rowid}".encode()).hexdigest()


class SqliteBackend:
    """One SQLite file, read-only, behind ``audit.backend.Backend``.

    The connection is handed in rather than built here, except by ``connect``, so a test can
    drive the read-back refusal with a connection whose envelope is not the one this backend
    asks for. It must be in autocommit mode: this module opens no transaction and a driver
    managing one underneath would hold a read lock across the whole run.
    """

    def __init__(
        self, connection: sqlite3.Connection, *, path: Path, copy: Path | None = None
    ) -> None:
        self._connection = connection
        self._path = path
        self._file = path if copy is None else copy
        self._copy = copy
        if copy is not None:
            # The run holds the only reference to the copy, so it goes when the run does,
            # at the end of the process as well as under an exception that unwinds past here.
            weakref.finalize(self, shutil.rmtree, str(copy.parent), ignore_errors=True)
        self._shuffle_connection: sqlite3.Connection | None = None
        self._shuffled: ShuffledCopies | None = None
        self._identity: str | None = None
        self._session_settings: SessionSettings | None = None
        _prepare(connection)

    @classmethod
    def connect(cls, target: str, *, scratch: str = TEMP_SCHEMA) -> SqliteBackend:
        """Open one read-only connection to that file. ``target`` is the file's path.

        ``scratch`` is the neutral name for the storage a shuffled copy is written to, and
        on this engine it names nothing that has to be arranged: the copies go into the
        connection's own TEMP database, which every connection has and which no grant
        controls. It is accepted so that one command line drives either engine and is
        recorded in the summary as what the run was told.
        """
        path = Path(target).expanduser()
        if not path.is_file():
            raise BackendRefused("connect", f"there is no SQLite file at {path}")
        found = path.resolve()
        try:
            return cls(_opened_and_read(found), path=found)
        except BackendRefused as refused:
            if not _needs_a_private_copy(refused, found):
                raise
        copy = _private_copy(found)
        return cls(_opened_and_read(copy), path=found, copy=copy)

    @property
    def scratch(self) -> str:
        """``temp``, whatever the run was told, because that is where the copies go.

        The name a run is given is accepted and names nothing that has to be arranged on
        this engine, so a summary that echoed it would state a place no copy was made in.
        """
        return TEMP_SCHEMA

    def identity(self) -> str:
        """Version, file and size, read once and repeated verbatim after that."""
        if self._identity is None:
            version = str(self._one("SELECT sqlite_version()", step="identity")[0])
            self._identity = f"SQLite {version} | file={self._path} | size={self._size()}"
        return self._identity

    def _size(self) -> int:
        """How many bytes the file holds, or zero when it has gone since it was opened."""
        try:
            return self._path.stat().st_size
        except OSError:
            return 0

    def effective_database_role(self) -> str:
        """What the statements run as. A file has no role: whoever opened it reads it, and
        the read-only guarantee is ``mode=ro`` and the envelope above it, not a grant."""
        return "file"

    def default_collation(self) -> str:
        """SQLite has none. A collation belongs to a column or to an expression here, so
        there is no database default to precondition and the record states none."""
        return ""

    def session_settings(self) -> SessionSettings:
        """The nine settings a SQLite file can be asked for, and the seven it does not hold.

        Read once and repeated after that, as the identity is. None of the nine blocks a
        comparison: a SQLite record states no session setting that decides comparability,
        which is why the seven named fields are absent and everything read is recorded.
        """
        if self._session_settings is None:
            recorded = {
                "sqlite_version": str(self._one("SELECT sqlite_version()", step="session")[0]),
                **{name: self._pragma(name) for name in RECORDED_PRAGMAS},
                "compile_options": self._pragma_list("compile_options", column=0),
                "collation_list": self._pragma_list("collation_list", column=1),
                "case_sensitive_like": str(self._one(CASE_SENSITIVE_LIKE, step="session")[0]),
            }
            if self._copy is not None:
                recorded[READ_THROUGH_PRIVATE_COPY] = str(self._copy)
            self._session_settings = SessionSettings(
                engine=ENGINE_SQLITE,
                time_zone=None,
                date_style=None,
                interval_style=None,
                extra_float_digits=None,
                database_collation=None,
                work_mem=None,
                hash_mem_multiplier=None,
                recorded=recorded,
            )
        return self._session_settings

    def _pragma(self, name: str) -> str:
        """One pragma of one value, as the text a record states it by."""
        rows = self._all(f"PRAGMA {name}", step="session")
        return "" if not rows else str(rows[0][0])

    def _pragma_list(self, name: str, *, column: int) -> str:
        """One pragma of many rows, joined into the one string a record states."""
        rows = self._all(f"PRAGMA {name}", step="session")
        return ",".join(str(row[column]) for row in rows)

    def execute(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        """One statement, read-only, with the envelope read back before it is sent."""
        return self._execute(
            self._connection, sql, statement_timeout_seconds=statement_timeout_seconds
        )

    def execute_shuffled(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        """The same statement over the shuffled copies, reached by TEMP shadowing ``main``.

        The statement is not rewritten: an unqualified table name finds the copy because
        SQLite resolves it in ``temp`` first, and a name the statement qualified still finds
        the table it qualified. Which tables a rerun therefore reads differently is what
        ``prepare_shuffled_copies`` returned.
        """
        if self._shuffled is None or self._shuffle_connection is None:
            raise BackendRefused("execute_shuffled", "no shuffled copies have been prepared")
        return self._execute(
            self._shuffle_connection, sql, statement_timeout_seconds=statement_timeout_seconds
        )

    def execute_plan_variant(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        """The same statement over the same rows, with one fewer way to read them.

        SQLite exposes one plan control to a reader: the transient index it builds for a
        join it has no index for. Turned off, a statement that depended on one is read
        another way, and a statement that did not is read the way it was, which the probe
        that compares the two answers reports as agreeing rather than as steered.
        """
        return self._execute(
            self._connection,
            sql,
            statement_timeout_seconds=statement_timeout_seconds,
            without_automatic_indexes=True,
        )

    def _execute(
        self,
        connection: sqlite3.Connection,
        sql: str,
        *,
        statement_timeout_seconds: int,
        without_automatic_indexes: bool = False,
    ) -> ExecutionResult:
        """One statement, read-only, with the envelope read back before it is sent.

        The timeout is this process's own: SQLite has no statement timeout to set on a
        session and read back, so a progress handler is asked every
        ``PROGRESS_INSTRUCTIONS`` instructions whether the deadline has passed and aborts the
        statement when it has. What the result states as in force is therefore what was
        enforced, which is the same claim the PostgreSQL backend makes about a value it read
        back off the server.
        """
        if statement_timeout_seconds < 1:
            raise BackendRefused("timeout", "a statement timeout is a whole number of seconds")
        self._require_the_envelope(connection)
        timeout_ms = statement_timeout_seconds * 1000
        with _plan_controls(connection, without_automatic_indexes):
            described, rows = _fetch(connection, sql, statement_timeout_seconds)
        typed = tuple(tuple(_as_recorded(value) for value in row) for row in rows)
        return ExecutionResult(
            columns=_columns(described, rows),
            rows=typed,
            backend_identity=self.identity(),
            limits_in_force=ExecutionLimits(statement_timeout_ms=timeout_ms),
            truncated=False,
        )

    def _require_the_envelope(self, connection: sqlite3.Connection) -> None:
        """Refuse the execution unless the connection still holds ``query_only``."""
        rows = _all(connection, QUERY_ONLY, step="read_back")
        held = "" if not rows else str(rows[0][0])
        if held != "1":
            raise ReadBackDrift(
                "read_back",
                f"query_only was set to 1 and the connection holds {held or 'nothing'}",
            )

    def existing_tables(self, tables: Sequence[TableName]) -> TableLookup:
        """Which of those names the file holds, in the spelling given.

        ``unreadable`` is always empty. A file has no grants: whoever can open it can read
        every table in it, so the second of the two ways a name can fail to be measurable
        does not arise on this engine and the caller is told so rather than being given a
        word that means something else here.

        A name that states a schema other than ``main`` is absent, because a file that
        attached nothing holds one schema and a statement naming another names nothing this
        run can measure.
        """
        wanted = tuple(dict.fromkeys(tables))
        if not wanted:
            return TableLookup((), ())
        held = self._relations()
        return TableLookup(
            tuple(name for name in wanted if _in_this_file(name, held) is not None), ()
        )

    def _relations(self) -> Mapping[str, str]:
        """Every table and view the file holds, by name, with the DDL that made it.

        Views are in it because a gold that selects from one is reading a table as far as
        this is concerned, which is the same set the PostgreSQL backend's ``relkind`` list
        admits.
        """
        rows = self._all(
            "SELECT name, coalesce(sql, '') FROM main.sqlite_master "
            "WHERE type IN ('table', 'view')",
            step="existing_tables",
        )
        return {str(row[0]): str(row[1]) for row in rows}

    def _measured(self, tables: Sequence[TableName]) -> tuple[TableName, ...]:
        """Those names as the file spells them, deduplicated and in a fixed order.

        A name the file does not hold keeps the caller's spelling, so whatever asks for its
        rows meets the engine's own message about a relation that is not there rather than a
        silence this module invented.
        """
        held = self._relations()
        return tuple(sorted({_in_this_file(name, held) or _qualify(name) for name in tables}))

    def schema_digest(self, tables: Sequence[TableName]) -> str:
        """One digest over the DDL of those tables, in name order.

        The DDL is what the file itself holds for the relation: the column names, their
        declared types and every constraint written on them, as the statement that created
        it was written. It is the whole of what SQLite states about a table's shape, so a
        digest over it moves for exactly the changes the PostgreSQL digest over columns,
        types and nullability moves for.
        """
        held = self._relations()
        payload = json.dumps(
            [[name.text, held.get(name.name, "")] for name in self._measured(tables)],
            separators=(",", ":"),
        )
        return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"

    def row_counts(self, tables: Sequence[TableName]) -> Mapping[str, int]:
        """The exact count of each table, counted one table at a time."""
        return {
            name.text: int(
                self._one(
                    _sql("SELECT count(*) FROM {schema}.{table}", **_over(name)),
                    step="row_counts",
                )[0]
            )
            for name in self._measured(tables)
        }

    def content_digests(self, tables: Sequence[TableName]) -> Mapping[str, str]:
        """A digest of every row of each table, sorted by the bytes each row renders to.

        Sorted here and not by the file, so the digest is a function of the rows and not of
        the order they are stored in: the shuffled copies of a later probe hold the same
        rows in another physical order and digest the same.
        """
        digests: dict[str, str] = {}
        for name in self._measured(tables):
            rows = self._all(
                _sql("SELECT * FROM {schema}.{table}", **_over(name)), step="content_digests"
            )
            running = hashlib.sha256()
            for rendered in sorted(_rendered_row(row) for row in rows):
                running.update(rendered)
                running.update(b"\n")
            digests[name.text] = f"sha256:{running.hexdigest()}"
        return digests

    def content_signal(self, tables: Sequence[TableName]) -> Mapping[str, str]:
        """What moves when the file moves: its size, its mtime, and its two version counters.

        ``data_version`` moves when another connection has committed a change to the file
        and ``schema_version`` when its schema was altered, and the size and the
        modification time move when the file was written or replaced. All four are the
        file's own and are therefore the same for every table in it, which is stated rather
        than worked around: this is not a digest and never appears in a record, and a signal
        that is the same for every table of one file still tells a cached measurement of
        that file from one taken since it changed.
        """
        wanted = self._measured(tables)
        if not wanted:
            return {}
        try:
            stat = self._path.stat()
            file_signal = f"{stat.st_size}/{stat.st_mtime_ns}"
        except OSError:
            file_signal = "0/0"
        signal = "/".join(
            (file_signal, self._pragma("data_version"), self._pragma("schema_version"))
        )
        return {name.text: signal for name in wanted}

    def planner_statistics(
        self, tables: Sequence[TableName]
    ) -> Mapping[TableName, PlannerStatistics]:
        """Nothing, which is what SQLite keeps until somebody runs ANALYZE.

        SQLite's planner reads ``sqlite_stat1``, and that table exists only after an
        ANALYZE, which writes and which a reader of somebody else's file never runs. There
        is also nothing in it that answers what this states: no time of the last analysis
        and no count of the rows changed since. An engine that counts nothing of the kind
        answers with nothing at all rather than with an invented zero.
        """
        return {}

    def column_types(self, tables: Sequence[TableName]) -> Mapping[TableName, Mapping[str, str]]:
        """Per table asked about, the declared type of every column, under the caller's name.

        This is the catalogue's own text, kept exactly as the file holds it, empty string
        included: SQLite lets a column be declared with no type at all, and an empty
        declaration IS what the catalogue holds for one. What a value in such a column
        turned out to be is a different question and is answered on the result.
        """
        types: dict[TableName, Mapping[str, str]] = {}
        held = self._relations()
        for name in dict.fromkeys(tables):
            found = _in_this_file(name, held)
            if found is None:
                continue
            rows = self._all(
                "SELECT name, type FROM pragma_table_info(?)", (found.name,), step="column_types"
            )
            if rows:
                types[name] = {str(row[0]): str(row[1]) for row in rows}
        return types

    def declared_type_is_text(self, declared_type: str) -> bool:
        """Whether a column declared that way has TEXT affinity, by SQLite's own rule.

        Read off the text of the declaration, which is all this engine keeps of it and all
        it decides affinity from. A column declared with no type at all holds none of the
        marks and is not text here, which is what SQLite makes of it too: no declaration is
        BLOB affinity, and what such a column actually held is answered on the result.
        """
        held = declared_type.upper()
        return any(mark in held for mark in TEXT_AFFINITY_MARKS)

    def order_sensitive_aggregate_types(self) -> frozenset[str]:
        """Nothing: SQLite adds a REAL aggregate with a compensation, so its order cannot show.

        ``sum``, ``total`` and ``avg`` carry a Kahan-Babuska-Neumaier correction beside the
        running double and add it back at the end (SQLite 3.43.0), so the same REALs read in
        another physical order give the same total. Measured over 28,000 multisets and on the
        sandbox in ``plans/reports/session-260904-autonomous-run/b4-sqlite-float-sums/``.

        The consequence is the answer: a REAL cell that does change under a shuffled copy on
        this engine changed for some other order-dependent reason, and that is the statement
        depending on the storage order rather than arithmetic. It is therefore reported under
        the stronger name, which is what the empty set makes the probe do.
        """
        return ORDER_SENSITIVE_AGGREGATE_TYPES

    def numeric_text_census(self, table: TableName, column: str, pattern: str) -> TextCensus:
        """The four counts, taken in one pass over the column the caller named.

        The pattern is the caller's POSIX one and is answered by a ``REGEXP`` function
        registered from Python, because SQLite defines the operator and no function behind
        it. ``sum`` over no rows is NULL in SQLite and is read here as the zero it means.
        """
        found = _in_this_file(table, self._relations()) or _qualify(table)
        counted = self._one(
            _sql(CENSUS_SQL, column=column, **_over(found)),
            (pattern,),
            step="numeric_text_census",
        )
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

        The copies are TEMP tables on a second connection to the same file, and they are the
        only thing this backend writes. A TEMP table belongs to the connection that made it,
        so the audited connection cannot see them and no statement of the run reads a copy
        unless it was sent to ``execute_shuffled``; the file is never written to, which
        ``mode=ro`` would refuse anyway.

        Only a name that states no schema is copied, because only such a name is resolved in
        ``temp`` first, and a copy made for a qualified name would be a table nothing reads.
        A view and a WITHOUT ROWID table are not copied either: the order is a function of
        the source row's rowid and neither has one.

        There is no lock and none is taken. The PostgreSQL backend holds one because two
        runs told one scratch schema would write over each other's copies; a TEMP table is
        private to a connection, so two runs over one file cannot meet at all.
        """
        if row_limit < 1:
            raise BackendRefused("prepare_shuffled_copies", "a row limit is at least one row")
        wanted = tuple(dict.fromkeys(tables))
        reachable = tuple(sorted(name for name in wanted if not name.schema))
        unreachable = {name: QUALIFIED_NAME_IS_NOT_REACHED for name in wanted if name.schema}
        held = self._relations()
        # Which names the file holds is asked before anything is counted, because counting a
        # relation that is not there is the engine's error and a name that is not there is
        # this answer's ``NOT_IN_THIS_FILE``: a gold that names a table nobody loaded is one
        # question's problem and never the end of the shuffle.
        present: dict[TableName, TableName] = {}
        for name in reachable:
            found = _in_this_file(name, held)
            if found is None:
                unreachable[name] = NOT_IN_THIS_FILE
            else:
                present[name] = found
        counts = self.row_counts(tuple(present.values()))
        copied: list[TableName] = []
        skipped: dict[TableName, int] = {}
        made: set[TableName] = set()
        self._shuffled = None
        connection = self._writing_connection()
        for name, found in present.items():
            if not self._has_a_row_identity(connection, found):
                unreachable[name] = WITHOUT_A_ROW_IDENTITY
                continue
            rows = counts[found.text]
            if rows > row_limit:
                skipped[name] = rows
                continue
            if found not in made:
                # One copy per relation and not per spelling: SQLite matches a name without
                # regard to case, so the copy a rerun reaches under one spelling is the copy
                # it reaches under the other, and making it twice would drop the first.
                _run(
                    connection,
                    _sql(SHUFFLED_COPY, copy=found.name, **_over(found)),
                    (seed,),
                    step="prepare_shuffled_copies",
                )
                made.add(found)
            copied.append(name)
        _run(connection, f"{QUERY_ONLY} = 1", step="prepare_shuffled_copies")
        prepared = ShuffledCopies(
            copied=tuple(copied),
            skipped=skipped,
            unreachable=unreachable,
            seed=seed,
            row_limit=row_limit,
        )
        self._shuffled = prepared
        return prepared

    def _writing_connection(self) -> sqlite3.Connection:
        """The second connection, opened once, with the envelope off for the copies alone.

        ``query_only`` blocks a TEMP table as it blocks every other write, so it is turned
        off here and turned back on before any rerun is sent, which is what the read-back on
        every execution then proves.
        """
        if self._shuffle_connection is None:
            self._shuffle_connection = _open(self._file, step="prepare_shuffled_copies")
        _run(self._shuffle_connection, f"{QUERY_ONLY} = 0", step="prepare_shuffled_copies")
        return self._shuffle_connection

    def _has_a_row_identity(self, connection: sqlite3.Connection, name: TableName) -> bool:
        """Whether a seeded copy of that relation can be ordered by the source row's rowid.

        Asked of the relation rather than read off its DDL: a view and a WITHOUT ROWID table
        both answer that there is no such column, and asking is what makes the answer the
        engine's rather than this module's reading of a CREATE statement.
        """
        try:
            _run(
                connection,
                _sql("SELECT rowid FROM {schema}.{table} LIMIT 0", **_over(name)),
                step="prepare_shuffled_copies",
            )
        except BackendRefused:
            return False
        return True

    def drop_shuffled_copies(self) -> None:
        """Remove the copies this run made, and close the connection that held them.

        Called in a finally, and safe when there are none. A TEMP table goes with its
        connection, so closing would be enough; the copies are dropped by name first so that
        what this run created is removed by the same rule the PostgreSQL backend removes its
        own, and a connection that cannot be closed is not what a caller has to be told
        about.
        """
        prepared, self._shuffled = self._shuffled, None
        connection, self._shuffle_connection = self._shuffle_connection, None
        if connection is None:
            return
        try:
            if prepared is not None:
                with suppress(BackendRefused):
                    _run(connection, f"{QUERY_ONLY} = 0", step="drop_shuffled_copies")
                    for name in {folded(copy.name): copy for copy in prepared.copied}.values():
                        _run(
                            connection,
                            _sql(
                                "DROP TABLE IF EXISTS {schema}.{table}",
                                schema=TEMP_SCHEMA,
                                table=name.name,
                            ),
                            step="drop_shuffled_copies",
                        )
        finally:
            with suppress(sqlite3.Error):
                connection.close()

    def _all(
        self, statement: str, params: Sequence[object] = (), *, step: str
    ) -> Sequence[tuple[Any, ...]]:
        """One question this module asks the file, with the driver's error named."""
        return _all(self._connection, statement, params, step=step)

    def _one(self, statement: str, params: Sequence[object] = (), *, step: str) -> tuple[Any, ...]:
        rows = self._all(statement, params, step=step)
        if not rows:
            raise BackendRefused(step, "the file returned no row for a question it always answers")
        return rows[0]


def _opened_and_read(path: Path, *, step: str = "connect") -> sqlite3.Connection:
    """One read-only connection that has read from the file, not one that only holds it.

    ``sqlite3.connect`` opens nothing: the driver reaches the file at the first statement,
    and a file this process cannot read is therefore a connection that succeeds and a
    question that fails. The schema is read here so that a caller which asked to connect is
    told at that point, and so that the one refusal a WAL file on read-only media gives is
    raised where it can still be answered with a copy.
    """
    connection = _open(path, step=step)
    try:
        _all(connection, "SELECT 1 FROM sqlite_master LIMIT 1", step=step)
    except BackendRefused:
        with suppress(sqlite3.Error):
            connection.close()
        raise
    return connection


def _needs_a_private_copy(refused: BackendRefused, path: Path) -> bool:
    """Whether that refusal is SQLite asking for the sidecars a WAL file is read through.

    Both halves are required: the message SQLite gives when it cannot write beside the file,
    and the file's own header saying it is in WAL mode. A refusal for any other reason, and a
    file that is not in WAL mode, are the file this run cannot read.
    """
    if not any(said in str(refused) for said in CANNOT_WRITE):
        return False
    try:
        with path.open("rb") as opened:
            header = opened.read(20)
    except OSError:
        return False
    return len(header) >= 20 and WAL_IN_THE_HEADER in (header[18], header[19])


def _private_copy(path: Path) -> Path:
    """That file and its sidecars in a private directory, as the bytes they are.

    ``copyfile`` and not ``copy2``: the copy is read and thrown away, and the mode of the
    original is what made it unreadable in the first place.
    """
    directory = Path(tempfile.mkdtemp(prefix=PRIVATE_COPY_PREFIX))
    copy = directory / path.name
    shutil.copyfile(path, copy)
    for suffix in ("-wal", "-shm"):
        sidecar = path.with_name(path.name + suffix)
        if sidecar.is_file():
            shutil.copyfile(sidecar, copy.with_name(copy.name + suffix))
    return copy


def _open(path: Path, *, step: str) -> sqlite3.Connection:
    """One read-only connection to that file, with the envelope on and the functions bound."""
    try:
        connection = sqlite3.connect(_uri(path), uri=True, isolation_level=None)
    except sqlite3.Error as failed:
        # Named the way this interface names failures, so a caller that must not import a
        # driver can still tell a file it could not open from a question it could not answer.
        raise BackendRefused(step, str(failed).strip()) from failed
    _prepare(connection)
    return connection


def _uri(path: Path) -> str:
    """That file as a URI, with the path escaped so that ``mode=ro`` is still a parameter.

    A URI filename ends at the first ``?`` or ``#``, so a path holding one would end there
    and leave the rest of the path in front of ``mode=ro`` in the query, where SQLite reads
    it as a parameter it does not know and ignores: the connection is then read-write over a
    file whose name is the part before the ``?``, and SQLite creates that file when it is not
    there. A ``%`` is the other one, because it begins an escape in a URI and a path is not
    written in one. So every character but the separator is escaped here, and the path this
    is given is absolute, so nothing about it is resolved twice.
    """
    return f"file:{quote(str(path), safe='/')}?mode=ro"


def _text_or_its_bytes(raw: bytes) -> str | UndecodedText:
    """One TEXT cell as text, or as the bytes it holds when they are not UTF-8.

    The driver hands a text value over as UTF-8 whatever the file's own encoding is, so what
    fails to decode here is a value the database holds and no encoding renders. Answering with
    the bytes is what lets the row be recorded and compared; the default answer raises, and one
    cell then fails the whole statement.
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return UndecodedText(raw)


def _prepare(connection: sqlite3.Connection) -> None:
    """Put the envelope on one connection and register the two functions this module needs."""
    connection.text_factory = _text_or_its_bytes
    connection.create_function(NUMERIC_TEXT_FUNCTION, 2, _numeric_text, deterministic=True)
    connection.create_function(SHUFFLE_FUNCTION, 2, _shuffle_key, deterministic=True)
    _run(connection, f"{QUERY_ONLY} = 1", step="connect")


@contextmanager
def _plan_controls(
    connection: sqlite3.Connection, without_automatic_indexes: bool
) -> Generator[None]:
    """Hold the one plan control SQLite has for one statement, and give it back after.

    It is a connection setting and not a statement's own, so it is turned back on whatever
    the statement did: a variant that failed must not leave every later execution of the run
    reading its tables another way.
    """
    if not without_automatic_indexes:
        yield
        return
    _run(connection, "PRAGMA automatic_index = 0", step="execute")
    try:
        yield
    finally:
        with suppress(BackendRefused):
            _run(connection, "PRAGMA automatic_index = 1", step="execute")


def _fetch(
    connection: sqlite3.Connection, sql: str, statement_timeout_seconds: int
) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]]:
    """Run one statement under the deadline and return the column names and every row.

    The deadline is this process's own and is enforced by the progress handler, which aborts
    the statement with SQLite's ``interrupted``. That error, and only that error, is reported
    as the timeout: an error the file raised about the statement itself is what it says it is
    whatever the clock has done since the deadline was set, and reporting it as a timeout
    would send a reader looking for a slow statement rather than at a missing table.
    """
    deadline = time.monotonic() + statement_timeout_seconds
    connection.set_progress_handler(_deadline(deadline), PROGRESS_INSTRUCTIONS)
    try:
        cursor = connection.execute(sql)
        try:
            described = tuple(str(column[0]) for column in cursor.description or ())
            return described, tuple(tuple(row) for row in cursor.fetchall())
        finally:
            cursor.close()
    except sqlite3.Error as failed:
        message = str(failed).strip()
        if INTERRUPT_MESSAGE in message and time.monotonic() > deadline:
            raise StatementTimedOut(
                statement_timeout_seconds,
                f"the statement ran past its {statement_timeout_seconds}s timeout",
            ) from failed
        # The driver's own error, named the way this interface names failures, so a caller
        # of Backend never has to know which driver refused.
        raise BackendRefused("execute", message) from failed
    finally:
        connection.set_progress_handler(None, 0)


def _deadline(deadline: float) -> Callable[[], int]:
    """The progress handler: non-zero once the statement has run past its deadline."""

    def passed() -> int:
        return 1 if time.monotonic() > deadline else 0

    return passed


def _columns(described: Sequence[str], rows: Sequence[Sequence[object]]) -> tuple[ColumnType, ...]:
    """The projection, with each column typed by the storage classes its cells came back at."""
    return tuple(
        ColumnType(
            name=name,
            declared_type=_declared_type(_storage_class(row[index]) for row in rows),
        )
        for index, name in enumerate(described)
    )


def _all(
    connection: sqlite3.Connection,
    statement: str,
    params: Sequence[object] = (),
    *,
    step: str,
) -> Sequence[tuple[Any, ...]]:
    """One question, with every driver error named by the step that asked it."""
    try:
        cursor = connection.execute(statement, tuple(params))
    except sqlite3.Error as failed:
        raise BackendRefused(step, str(failed).strip()) from failed
    try:
        return cursor.fetchall()
    except sqlite3.Error as failed:
        raise BackendRefused(step, str(failed).strip()) from failed
    finally:
        with suppress(sqlite3.Error):
            cursor.close()


def _run(
    connection: sqlite3.Connection,
    statement: str,
    params: Sequence[object] = (),
    *,
    step: str,
) -> None:
    """One statement this module sends for its effect rather than for its rows."""
    _all(connection, statement, params, step=step)


__all__ = [
    "CASE_SENSITIVE_LIKE",
    "CENSUS_SQL",
    "DEFAULT_SCHEMA",
    "DRIVER_ERROR",
    "INTERRUPT_MESSAGE",
    "MIXED_CLASSES",
    "NOT_IN_THIS_FILE",
    "ORDER_SENSITIVE_AGGREGATE_TYPES",
    "PROGRESS_INSTRUCTIONS",
    "QUALIFIED_NAME_IS_NOT_REACHED",
    "QUERY_ONLY",
    "RECORDED_PRAGMAS",
    "SHUFFLED_COPY",
    "STORAGE_CLASSES",
    "TEMP_SCHEMA",
    "TEXT_AFFINITY_MARKS",
    "UNOBSERVED",
    "WITHOUT_A_ROW_IDENTITY",
    "SqliteBackend",
]
