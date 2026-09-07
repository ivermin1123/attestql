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


class RefuseTarget(Protocol):
    """Why this engine will not be reached at that target, or ``None`` when it may be.

    Asked of the command line before anything is opened, so what it judges is the shape of
    the string and never the thing at the end of it: whether a server answers or a file is
    there is the backend's to say, at the moment it asks, with the target in the message.
    The rule differs by engine because a target does: what is a connection string on one is
    a path on another, and a rule written about one of them is wrong about the other.
    """

    def __call__(self, target: str, /) -> str | None: ...


DSN_IS_A_URI = (
    "the DSN is a URI; this tool takes the libpq keyword form, "
    "host=... port=... dbname=... user=..., because a URI is where a password is "
    "written; set PGPASSWORD or use ~/.pgpass so that no credential is ever "
    "written into a record, a log or this command line"
)
"""Why a PostgreSQL DSN written as a URI is refused before its contents are looked at.

``postgresql://user:secret@host/db`` carries the credential in the text itself, where it
would reach every record, log and process listing the DSN reaches, and no rule about what a
URI may contain is worth trusting when the keyword form has no such shape."""

DSN_NAMES_A_CREDENTIAL = (
    "the DSN names a password; set PGPASSWORD or use ~/.pgpass so that no "
    "credential is ever written into a record, a log or this command line"
)
"""Why a keyword DSN holding the word is refused. The credential reaches the driver from
the environment or from ``~/.pgpass``, so nothing has to write it on a command line."""


def _refuse_nothing_about_the_target(target: str, /) -> str | None:
    """What an engine that states no rule about the shape of its target answers.

    The default, because a rule about a target is a claim about what such a string may
    hold, and an engine that has not made one says so rather than borrowing another
    engine's.
    """
    return None


def _refuse_a_postgresql_dsn(target: str, /) -> str | None:
    """A DSN this tool will not connect with: a URI, or a keyword form naming a password.

    Both are about the credential and neither is about the server: a DSN that carries one
    is written into a record, a log and a process listing by the run that uses it, and the
    two shapes above are where one is written.
    """
    if "://" in target:
        return DSN_IS_A_URI
    if "password" in target.lower():
        return DSN_NAMES_A_CREDENTIAL
    return None


@dataclass(frozen=True)
class Engine:
    """What a run needs to audit on one engine, chosen once and passed as one value.

    ``name`` is what the record's session settings state and what the ``--engine`` flag
    selects. ``parser`` is what the summary reports; the statements ``parse`` returns
    carry the same identity, so a record and the summary above it can never name two
    different parsers for one statement. ``refuse_target`` is what the command line asks
    before it opens anything, and it is here rather than in the options because what a
    target may look like is the engine's to say.
    """

    name: str
    connect: Connect
    parse: Parse
    parser: ParserIdentity
    refuse_target: RefuseTarget = _refuse_nothing_about_the_target


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
    refuse_target=_refuse_a_postgresql_dsn,
)
"""PostgreSQL: psycopg over a DSN, and libpg_query over the statement. The target is a
libpq keyword string, and the two shapes that would carry a credential in it are refused."""

SQLITE = Engine(
    name=ENGINE_SQLITE,
    connect=_connect_sqlite,
    parse=parse_sqlite_statement,
    parser=SQLITE_PARSER,
)
"""SQLite: the standard library's driver over a file, and sqlglot's SQLite dialect over the
statement (ADR-0014 points 2 and 3). The target is the path to the file, and no shape of a
path is refused: PostgreSQL's two refusals are about a connection string, and a directory
called ``password`` or one holding ``://`` is a directory somebody made. Whether the file is
there is answered when it is opened, with the path in the message."""

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
    "DSN_IS_A_URI",
    "DSN_NAMES_A_CREDENTIAL",
    "ENGINES",
    "POSTGRESQL",
    "SQLITE",
    "Connect",
    "Engine",
    "Parse",
    "RefuseTarget",
    "engine_named",
]
