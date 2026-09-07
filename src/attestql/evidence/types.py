"""The types a record is written in: the replay rule, a sort key, the question, the
session settings that were in force and the digest of the data that was read.

These lived in the question catalogue while a record was a record of a catalogue
question. They belong to the record: a record states the rule its result was compared
under and the ordering that rule was applied to, and a replay of a record reads them
back without the catalogue that produced it ever being present.

``QuestionMetadata`` is what a record says about the question it answers. It carries the
question's own identity and text and the set it was read from, and nothing derived from
them: no metric, no window, no dimension, no join path. A benchmark row has no metric
contract to resolve against, and a record that carried an empty resolution would state
that a resolution had happened.

``StatementSource`` is where the executed statement's text was read from. A gold and a
prediction come out of two different files, and a record that did not name the one its own
statement came from would leave a reader with a statement and no way back to its file.

``SessionSettings`` and ``FixtureDigest`` are what a comparison of two executions has to
agree on before an inequality between them means anything (ADR-0013 point 6). Both are
read from the server rather than configured beside it, and both are stated in full: the
settings that change rendered bytes or row order are named fields, everything else the
session reported is recorded beside them and blocks nothing. ``SessionSettings`` names
the engine first, because that is the namespace the settings and every declared type of
the result are read in, and it is what lets an engine with no session state that it has
none rather than fill the seven fields with something (ADR-0014). One block states either
engine, so a reader of any record reads one shape: the engine, then the seven settings that
decide comparability, then what that session reported.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType


class ReplayRule(Enum):
    """Exactly one rule applies to a result and is recorded in its evidence."""

    R_ORD = "R-ORD"
    """Deterministic ordering plus canonical typed serialization: byte-identical rendering."""
    R_SET = "R-SET"
    """Typed semantic equality of the row multiset; row order is disregarded."""


@dataclass(frozen=True)
class SortKey:
    """One element of a deterministic ordering.

    ``column`` is an ordering expression, written as the statement writes it, and not
    necessarily a column of the result. A statement may order by an expression it does not
    project: BIRD's q879 orders by ``CAST(t2.fastestLapSpeed AS FLOAT)`` over a projection
    of nationality alone. The field kept its name because a record already written under it
    means the same thing, and a bare column name is the expression that names a column.
    """

    column: str
    descending: bool

    def __post_init__(self) -> None:
        if not self.column:
            raise ValueError("column is required")
        if not isinstance(self.descending, bool):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            raise TypeError("descending must be a bool")


@dataclass(frozen=True)
class QuestionMetadata:
    """The question a record answers, as the set that holds it states it.

    ``evidence_text`` is the hint a question set supplies beside its question, which BIRD
    calls evidence and often leaves empty. Empty is a value here and absence is not: a
    record either states what hint the question carried or is not constructed.
    """

    question_id: str
    question_set: str
    question_text: str
    evidence_text: str

    def __post_init__(self) -> None:
        for name in ("question_id", "question_set"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")
        for name in ("question_text", "evidence_text"):
            if not isinstance(getattr(self, name), str):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
                raise TypeError(f"{name} must be a string")


@dataclass(frozen=True)
class StatementSource:
    """The file the executed statement's text was read from, and what it is known to be.

    ``path`` is the path the run was given and ``digest`` the sha256 of what was read
    there, so a reader who has the file can check that it is the same one. ``origin`` and
    ``date`` are what the run was told about where that file came from and when, and are
    ``None`` when it was told nothing, which is a stated absence and not a default.
    """

    path: str
    digest: str
    origin: str | None
    date: str | None

    def __post_init__(self) -> None:
        for name in ("path", "digest"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")


def read_only_text(name: str, value: Mapping[str, str]) -> Mapping[str, str]:
    """Snapshot a mapping of names to values so a frozen record cannot be edited through it.

    A key names something and is never empty. A value may be: a server that reports a
    setting as the empty string has reported it, and a record that refused to hold that
    would be a record that cannot state what the session actually said. A mapping whose
    values are this project's own, and so never empty, says so at its own field.
    """
    snapshot = dict(value)
    for key, item in snapshot.items():
        if not isinstance(key, str) or not key:  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            raise ValueError(f"{name} keys must be non-empty strings")
        if not isinstance(item, str):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            raise ValueError(f"{name}[{key}] must be a string")
    return MappingProxyType(snapshot)


def read_only_counts(name: str, value: Mapping[str, int]) -> Mapping[str, int]:
    """Snapshot a mapping of names to counts. A count is a non-negative int and never a bool."""
    snapshot = dict(value)
    for key, item in snapshot.items():
        if not isinstance(key, str) or not key:  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            raise ValueError(f"{name} keys must be non-empty strings")
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            raise ValueError(f"{name}[{key}] must be a non-negative int")
    return MappingProxyType(snapshot)


ENGINE_POSTGRESQL = "postgresql"
"""The engine whose session states the seven settings below."""

ENGINE_SQLITE = "sqlite"
"""The engine that has none of them: a file has no session to precondition, and what it can
be asked about itself is recorded instead."""

ENGINES: tuple[str, ...] = (ENGINE_POSTGRESQL, ENGINE_SQLITE)
"""Every engine a record may name. A record of an engine nobody stated the settings rule
for is not constructible, because a reader of it could not tell an absent setting from a
setting the engine has and nobody read back."""


@dataclass(frozen=True)
class SessionSettings:
    """The engine, and the settings that session held, with the seven that decide
    comparability named.

    ``engine`` is the namespace everything else here and every column's declared type is
    read in, and it is stated once per record rather than on each of them. Two records
    that name two engines are two experiments: the same setting name, the same type name
    and the same value mean what their own engine says they mean.

    The seven named fields are the settings that change rendered bytes or row order, so two
    executions that disagree on any of them are two experiments and not one comparison:
    the time zone and the timestamp and interval styles decide how an instant renders, the
    float digits decide how many of a number's digits are returned at all, the database's
    default collation decides what ``ORDER BY`` on text means, and the two memory settings
    decide where a hash aggregate spills and therefore in what order a float sum is added.
    They are PostgreSQL's, and a SQLite record states all seven as absent rather than
    inventing a value for a session that does not exist: no time zone, no styles, no float
    digits, no memory bound, and a collation that belongs to a column or an expression and
    not to the database.

    The two memory settings are what a statement ran under rather than what the session was
    found holding: the executor sets both on every execution's own transaction, so a record
    that repeated the session's own values would name a bound no statement of it reached.

    ``recorded`` holds everything else the session reported, and is required and non-empty
    on either engine: an engine that preconditions nothing still states what it is. On
    PostgreSQL that is the statement timeout, the search path, the server version, whether
    the transaction was read only, what the gather was free to do, the server encoding, and
    the provider, ICU locale and version of the collation that sorted the text. On SQLite it
    is the nine a file can be asked for: ``sqlite_version``, ``encoding``,
    ``compile_options``, ``collation_list``, ``case_sensitive_like``,
    ``reverse_unordered_selects``, ``query_only``, ``journal_mode`` and ``data_version``
    (ADR-0014). None of it blocks a comparison, and all of it is in the record so a reader
    can see the session that produced the result.

    ``recorded`` states the session outside any one statement's own transaction. The
    timeout a statement actually ran under is on that statement's result, in
    ``limits_in_force``, read back inside the transaction that ran it; a read of
    ``transaction_read_only`` here is the session's value and not that transaction's,
    which the executor reads back and refuses on drift. Two values, two scopes, and the
    record says which is which rather than letting one stand for the other.
    """

    engine: str
    time_zone: str | None
    date_style: str | None
    interval_style: str | None
    extra_float_digits: str | None
    database_collation: str | None
    work_mem: str | None
    hash_mem_multiplier: str | None
    recorded: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.engine not in ENGINES:
            raise ValueError(f"engine must be one of {ENGINES}; got {self.engine!r}")
        stated = {
            name: getattr(self, name)
            for name in (
                "time_zone",
                "date_style",
                "interval_style",
                "extra_float_digits",
                "database_collation",
                "work_mem",
                "hash_mem_multiplier",
            )
        }
        if self.engine == ENGINE_POSTGRESQL:
            for name, value in stated.items():
                if not value:
                    raise ValueError(
                        f"{name} is required on {self.engine}; "
                        "a setting nobody read back is not a value"
                    )
        else:
            named = sorted(name for name, value in stated.items() if value is not None)
            if named:
                raise ValueError(
                    f"{self.engine} has no session to precondition, so {named} state "
                    "settings this engine does not hold"
                )
        object.__setattr__(self, "recorded", read_only_text("recorded", self.recorded))
        if not self.recorded:
            raise ValueError(
                "recorded must state the other settings the session reported; a session "
                "nobody asked anything else about is a session nobody looked at"
            )


@dataclass(frozen=True)
class FixtureDigest:
    """What the data looked like, measured on the server the statement read.

    ``schema_digest`` covers the table, column, type and nullability of every table the
    statement referenced, in a stated order. ``row_counts`` is the exact count per table,
    counted and not estimated. Those two are always computed and are what a comparison
    requires: two answers about different data are not evidence about each other.

    ``content_digests`` is a per-table digest of the sorted rows and is optional because
    it costs a full read of every table. An empty mapping means it was not computed, and a
    comparison between one record that carries content digests and one that does not
    ignores them rather than reporting a difference nobody measured.

    ``source_file_sha256`` is the digest of the file the data was loaded from, when the
    caller named one, and the empty string when none was given. It is recorded and is
    never a precondition: a dump loaded twice into two servers is the same data, and the
    digests above are what say so.
    """

    schema_digest: str
    row_counts: Mapping[str, int]
    content_digests: Mapping[str, str]
    source_file_sha256: str

    def __post_init__(self) -> None:
        if not self.schema_digest:
            raise ValueError("schema_digest is required")
        if not isinstance(self.source_file_sha256, str):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            raise TypeError("source_file_sha256 must be a string; absence is the empty string")
        object.__setattr__(self, "row_counts", read_only_counts("row_counts", self.row_counts))
        object.__setattr__(
            self, "content_digests", read_only_text("content_digests", self.content_digests)
        )
        for table, digest in self.content_digests.items():
            # These are this project's own digests, so an empty one is a digest nobody
            # took recorded as a digest somebody took.
            if not digest:
                raise ValueError(f"content_digests[{table}] is empty; a digest is never absent")


__all__ = [
    "ENGINES",
    "ENGINE_POSTGRESQL",
    "ENGINE_SQLITE",
    "FixtureDigest",
    "QuestionMetadata",
    "ReplayRule",
    "SessionSettings",
    "SortKey",
    "StatementSource",
    "read_only_counts",
    "read_only_text",
]
