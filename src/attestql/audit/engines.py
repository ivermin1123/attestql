"""One engine: how a run reaches it, how it reads a statement, and what to call it.

The two seams an engine fills in live apart, because they are about different things:
``backend.py`` says what an audit needs from a database and ``parse.py`` what it reads
off a statement before any database is reached. This module is where one engine's answer
to both is named once, so that a run chooses an engine and never chooses a backend and a
parser separately (ADR-0014 points 2 and 3). Adding an engine is adding an entry to
``ENGINES``; nothing else in the audit asks which engine it is running on.

The registry is here and not in ``cli.py`` because it names the implementations, and
``cli.py`` is what a test imports to drive a scripted backend that reaches no server. It
is here and not in ``backend.py`` or ``parse.py`` because both of those are imported by
the implementations it names, and a registry inside either would be a cycle.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from attestql.audit.backend import Backend
from attestql.audit.parse import ParsedStatement, ParserIdentity
from attestql.audit.postgres import PostgresBackend
from attestql.audit.sqlite import SqliteBackend
from attestql.audit.sqlite_statements import PARSER as SQLITE_PARSER
from attestql.audit.sqlite_statements import parse_statement as parse_sqlite_statement
from attestql.audit.statements import PARSER, parse_statement
from attestql.evidence.types import ENGINE_POSTGRESQL, ENGINE_SQLITE


class Connect(Protocol):
    """Open one read-only connection to what the run was pointed at.

    ``target`` is what the run named on the command line: a connection string for a
    server, a file for an engine that is a file. ``scratch`` is the storage the login
    already holds and where a shuffled copy may be written, which is a schema on one
    engine and an attached database on another; the backend decides what the word means
    to it and creates nothing.
    """

    def __call__(self, target: str, /, *, scratch: str) -> Backend: ...


class Parse(Protocol):
    """Read one statement, or refuse it with ``StatementRefused`` naming what was wrong."""

    def __call__(self, sql: str, /) -> ParsedStatement: ...


@dataclass(frozen=True)
class Engine:
    """What a run needs to audit on one engine, chosen once and passed as one value.

    ``name`` is what the record's session settings state and what the ``--engine`` flag
    selects. ``parser`` is what the summary reports; the statements ``parse`` returns
    carry the same identity, so a record and the summary above it can never name two
    different parsers for one statement.
    """

    name: str
    connect: Connect
    parse: Parse
    parser: ParserIdentity


def _connect_postgresql(target: str, /, *, scratch: str) -> Backend:
    """The PostgreSQL backend under the neutral names: a DSN, and a schema to write in."""
    return PostgresBackend.connect(target, scratch_schema=scratch)


def _connect_sqlite(target: str, /, *, scratch: str) -> Backend:
    """The SQLite backend under the neutral names: a file, and a place to write copies in.

    The scratch name is accepted and names nothing that has to be arranged here: a SQLite
    copy goes into the connection's own TEMP database, which every connection has.
    """
    return SqliteBackend.connect(target, scratch=scratch)


POSTGRESQL = Engine(
    name=ENGINE_POSTGRESQL,
    connect=_connect_postgresql,
    parse=parse_statement,
    parser=PARSER,
)
"""PostgreSQL: psycopg over a DSN, and libpg_query over the statement."""

SQLITE = Engine(
    name=ENGINE_SQLITE,
    connect=_connect_sqlite,
    parse=parse_sqlite_statement,
    parser=SQLITE_PARSER,
)
"""SQLite: the standard library's driver over a file, and sqlglot's SQLite dialect over the
statement (ADR-0014 points 2 and 3). The target is the path to the file."""

ENGINES: Mapping[str, Engine] = {POSTGRESQL.name: POSTGRESQL, SQLITE.name: SQLITE}
"""Every engine an audit can run on, by the name the flag takes."""

DEFAULT_ENGINE = POSTGRESQL
"""What a run audits on when it names no engine. The measured numbers are PostgreSQL's."""


def engine_named(name: str) -> Engine:
    """The engine that name selects, or a refusal listing the ones there are."""
    engine = ENGINES.get(name)
    if engine is None:
        raise KeyError(f"no engine named {name!r}; there is {', '.join(sorted(ENGINES))}")
    return engine


__all__ = [
    "DEFAULT_ENGINE",
    "ENGINES",
    "POSTGRESQL",
    "SQLITE",
    "Connect",
    "Engine",
    "Parse",
    "engine_named",
]
