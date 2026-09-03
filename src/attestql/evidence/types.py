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

``SessionSettings`` and ``FixtureDigest`` are what a comparison of two executions has to
agree on before an inequality between them means anything (ADR-0013 point 6). Both are
read from the server rather than configured beside it, and both are stated in full: the
settings that change rendered bytes or row order are named fields, everything else the
session reported is recorded beside them and blocks nothing.
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


@dataclass(frozen=True)
class SessionSettings:
    """The settings the session held, with the five that decide comparability named.

    The five named fields are the settings that change rendered bytes or row order, so two
    executions that disagree on any of them are two experiments and not one comparison:
    the time zone and the timestamp and interval styles decide how an instant renders, the
    float digits decide how many of a number's digits are returned at all, and the
    database's default collation decides what ``ORDER BY`` on text means.

    ``recorded`` holds everything else the session reported: the statement timeout, the
    search path, the server version and whether the transaction was read only, at least.
    None of it blocks a comparison, and all of it is in the record so a reader can see the
    session that produced the result.

    ``recorded`` states the session outside any one statement's own transaction. The
    timeout a statement actually ran under is on that statement's result, in
    ``limits_in_force``, read back inside the transaction that ran it; a read of
    ``transaction_read_only`` here is the session's value and not that transaction's,
    which the executor reads back and refuses on drift. Two values, two scopes, and the
    record says which is which rather than letting one stand for the other.
    """

    time_zone: str
    date_style: str
    interval_style: str
    extra_float_digits: str
    database_collation: str
    recorded: Mapping[str, str]

    def __post_init__(self) -> None:
        for name in (
            "time_zone",
            "date_style",
            "interval_style",
            "extra_float_digits",
            "database_collation",
        ):
            if not getattr(self, name):
                raise ValueError(f"{name} is required; a setting nobody read back is not a value")
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
    "FixtureDigest",
    "QuestionMetadata",
    "ReplayRule",
    "SessionSettings",
    "SortKey",
    "read_only_counts",
    "read_only_text",
]
