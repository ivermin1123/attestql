"""What an audit needs from a database, stated without naming one.

ADR-0013 point 4: PostgreSQL first, because typed replay needs real column types, and
SQLite next, because the original BIRD runs on it. So the interface is engine-neutral
from the first commit and nothing in it is PostgreSQL's: no type oid, no search path, no
transaction syntax. A backend is asked for typed rows, for the settings that decide
whether two executions are comparable, and for digests of the data that was read; how it
gets them is its own.

Read-only is the backend's promise and not the caller's request. ``execute`` takes SQL
and a timeout and nothing that could make it write, and an implementation that cannot
prove to itself that the statement ran read-only raises ``ReadBackDrift`` rather than
returning rows whose provenance it cannot state. That is the one property ADR-0013 point
7 carried over from the deleted executor, and it lives here at the interface so a second
engine cannot quietly drop it.

The digests are three calls rather than one so that the expensive one is optional.
``schema_digest`` and ``row_counts`` are always taken; ``content_digests`` reads every
row of every table and is taken only when the caller asks for it (ADR-0013 point 6).
``content_signal`` is none of the three: it reads what the engine already counts about
its own tables, so that a measurement cached by an earlier run can be told apart from one
the data has moved under since, and from one taken before an analyze the planner has since
chosen a different plan from. ``planner_statistics`` reads the same catalogue for what a
record and a summary state: what the plan of every rerun this run makes was chosen from. ``existing_tables`` is asked before any of them, because a name the data does not hold is
one question's error and never the end of a run. It answers in two parts, because there are
two ways a name can fail to be measurable and they are repaired in different places: a table
nobody loaded is a defect in the question file, and a table the audit's login was never
granted is a defect in the grants.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from attestql.evidence.render import Json
from attestql.evidence.types import SessionSettings
from attestql.kernel.types import ExecutionResult


@dataclass(frozen=True, order=True)
class TableName:
    """One relation as a statement named it: the schema it wrote, and the relation.

    The two are kept apart because a name is not a string with a dot in it. A relation
    called ``"a.b"`` is one name, and the table ``b`` of a schema ``a`` is another; a
    string that joined them would be the same string for both, and whatever split it back
    would have to guess. So the parse hands the two parts over as it read them and nothing
    downstream takes ``text`` apart again.

    ``schema`` is the empty string when the statement named none. What an unqualified name
    means is the backend's to decide, because the answer is where the engine looks: a
    caller that filled it in here would be stating one engine's default as the parse.
    """

    schema: str
    name: str

    @property
    def text(self) -> str:
        """The name as a summary and a record print it, qualified where the statement was.

        For display and for keying, never for parsing back: whoever needs the parts has
        them beside this.
        """
        return f"{self.schema}.{self.name}" if self.schema else self.name


class BackendRefused(RuntimeError):
    """The backend will not produce a result it cannot state the provenance of.

    ``step`` names what refused, so a caller reports which of the audit's own
    preconditions was not met rather than a driver's message about a socket.
    """

    def __init__(self, step: str, detail: str) -> None:
        self.step = step
        self.detail = detail
        super().__init__(f"{step}: {detail}")


class ReadBackDrift(BackendRefused):
    """The session did not hold what the executor set on it.

    Raised instead of returning the rows. A result produced under a session whose
    read-only flag or timeout is not what was asked for is a result about a different
    execution than the one the record would describe, and the audit has no use for it.
    """


@dataclass(frozen=True)
class TextCensus:
    """How many of a text column's values look like numbers, counted on the server.

    One question, four counts, one pass over the column: the rows it has, the ones that
    are null, the ones that are empty, and the ones that are neither and still do not
    match the pattern. A smell that orders by such a column asks this before it claims
    the ordering is lexicographic over numbers, and the counts are its evidence.
    """

    rows: int
    nulls: int
    empty_strings: int
    non_numeric: int
    pattern: str


@dataclass(frozen=True)
class TableLookup:
    """Of the names asked about, the ones the database holds and the ones it will not read.

    ``present`` exists and this login may read it, which is what a fixture measurement can
    cover. ``unreadable`` exists and the login may not read it, which is a grant nobody made
    rather than a table nobody loaded; a name in neither is absent. Two states, two words,
    because the operator repairs them in two different places and a summary that spelled them
    the same way sent them to the wrong one.

    The names are the caller's spelling in the caller's order and without duplicates, because
    the caller is what has to say which of the names it asked about ended up where.
    """

    present: tuple[TableName, ...]
    unreadable: tuple[TableName, ...]


@dataclass(frozen=True)
class PlannerStatistics:
    """When one table's planner statistics were last taken, and how far its rows have moved.

    The plan a statement is read with is chosen from these, and a probe that reruns a gold
    and compares the two answers is comparing two plans whenever they moved in between. So
    they are recorded beside what was measured under them. They are never repaired here:
    the audit reads, and ANALYZE writes.

    The timestamps are the engine's own rendering of them, or ``None`` where it holds none,
    which is what a table nobody has analysed since the statistics were last reset says.
    ``n_mod_since_analyze`` is what the engine counts as changed since the last one.
    """

    last_analyze: str | None
    last_autoanalyze: str | None
    n_mod_since_analyze: int


def planner_statistics_json(statistics: Mapping[TableName, PlannerStatistics]) -> Json:
    """Those statistics as a summary and a smell's evidence write them, under the names asked.

    One rendering because two runs are compared by diffing what they wrote: a block in a
    record and a block in a summary that spelled the same three fields differently would be
    two things to read instead of one.
    """
    return {
        name.text: {
            "last_analyze": measured.last_analyze,
            "last_autoanalyze": measured.last_autoanalyze,
            "n_mod_since_analyze": measured.n_mod_since_analyze,
        }
        for name, measured in statistics.items()
    }


@dataclass(frozen=True)
class ShuffledCopies:
    """What a shuffled copy of the data covers, and what it does not.

    ``copied`` are the tables a rerun will read instead of the originals; ``skipped``
    names the tables left behind with the count that made them too large, and
    ``unreachable`` the ones a rerun would go on reading in place whatever was copied,
    each with the reason. A smell that reruns a statement says which part of the data it
    did not shuffle, and the three fields are what it says it from.

    The names are the caller's own, so a table a gold named twice in two spellings is
    answered under each of them: whether a rerun reaches a copy is a property of how the
    statement wrote the name and not of the table underneath it.
    """

    copied: tuple[TableName, ...]
    skipped: Mapping[TableName, int]
    unreachable: Mapping[TableName, str]
    seed: str
    row_limit: int


class Backend(Protocol):
    """One database, read-only, for the length of an audit."""

    def identity(self) -> str:
        """Engine, version, host or path, and database, as one line.

        Two records that name different backends are still compared: the identity is
        evidence a reader needs, not a precondition. It is one string because that is
        what a record can state about any engine without a field per engine.
        """
        raise NotImplementedError

    def effective_database_role(self) -> str:
        """The identity the statements run as, which decides what they could read."""
        raise NotImplementedError

    def session_settings(self) -> SessionSettings:
        """The seven settings that decide comparability, and everything else read back.

        Asked once for a whole run, like ``existing_tables``: the summary and every record
        state one read of the session, so that two records of one run cannot say the
        statements behind them ran under two different sessions.
        """
        raise NotImplementedError

    def execute(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        """Run one statement read-only under that timeout and return every row it gave.

        Raises ``BackendRefused`` when the statement could not be run as stated and
        ``ReadBackDrift`` when the session did not hold the envelope it was given.
        """
        raise NotImplementedError

    def existing_tables(self, tables: Sequence[TableName]) -> TableLookup:
        """Which of those names the database holds and may read, in the spelling given.

        A gold that names a table this database does not have is one question's error and
        not the end of a run, so what is measured before the questions asks this first
        rather than discovering it by failing: what exists and can be read is measured, the
        rest is named in the summary, and the questions that reference it fail on their own
        lines with the server's own message.

        Existence and readability are one question here and not two, because an
        implementation that asked them apart could answer them of two different moments,
        and because the answer is asked once for a whole run.
        """
        raise NotImplementedError

    def schema_digest(self, tables: Sequence[TableName]) -> str:
        """One digest over the table, column, type and nullability of those tables."""
        raise NotImplementedError

    def row_counts(self, tables: Sequence[TableName]) -> Mapping[str, int]:
        """The exact number of rows in each table, counted rather than estimated."""
        raise NotImplementedError

    def content_digests(self, tables: Sequence[TableName]) -> Mapping[str, str]:
        """A digest of the sorted rows of each table. The expensive one, asked for by name."""
        raise NotImplementedError

    def content_signal(self, tables: Sequence[TableName]) -> Mapping[str, str]:
        """One cheap string per qualified table that moves when the table's rows move.

        Read from whatever the engine already counts about its own tables, so that asking
        it costs one question for a whole run rather than a pass over the data. It is not
        a digest and never appears in a record: it exists so that a cached measurement of
        data that has since changed can be recognised as stale and taken again.
        """
        raise NotImplementedError

    def planner_statistics(
        self, tables: Sequence[TableName]
    ) -> Mapping[TableName, PlannerStatistics]:
        """Per table, when the planner's statistics for it were last taken and how far off.

        Asked because the shuffle probe reruns a gold over copies of the data and reads
        both with whatever plan the planner chose, and the planner chooses from these. A
        probe that fires on one run and is quiet on the next over the same data has this
        underneath it, and a run that did not record them leaves a reader to guess.

        Answered under the caller's own names, like ``column_types``, and a name the engine
        keeps no statistics for gets no entry rather than an invented zero: an engine that
        counts nothing of the kind answers with nothing at all.
        """
        raise NotImplementedError

    def column_types(self, tables: Sequence[TableName]) -> Mapping[TableName, Mapping[str, str]]:
        """Per table, the declared type of each of its columns.

        Asked because an ordering key that resolves to a column is only interesting to a
        smell when the column is declared as text: what is being looked for is an
        ordering that is lexicographic where the question means numeric, and the
        statement alone cannot say which one it is.

        Answered under the caller's own names, unlike the digests above, because the
        caller resolves a key against the name its statement wrote: two tables of one bare
        name in two schemas are two entries here, and a lookup that had to match them by
        the tail would read either one.
        """
        raise NotImplementedError

    def numeric_text_census(self, table: TableName, column: str, pattern: str) -> TextCensus:
        """Count that column's rows, nulls, empties and values the pattern rejects.

        ``pattern`` is a POSIX regular expression. It is the caller's, so what counts as
        a numeric-looking value is stated once, in the smell that decides it, rather than
        once per engine; an engine whose pattern dialect differs translates it here.
        """
        raise NotImplementedError

    def prepare_shuffled_copies(
        self, tables: Sequence[TableName], *, seed: str, row_limit: int
    ) -> ShuffledCopies:
        """Copy those tables into scratch storage in a seeded order, once for a run.

        A copy holds the same rows in another physical order, so a statement rerun
        against it answers whether the result was a function of the data or of the order
        the rows happened to be stored in. The order is seeded, so a run reproduces. A
        table with more rows than ``row_limit`` is skipped and named in the answer rather
        than copied, and so is a name a rerun would not reach the copy of however it was
        made: the answer says which tables a rerun really reads differently, because a
        smell that assumed the rest reports a statement as surviving a shuffle it never
        had.

        The scratch storage exists before the run and is not made here: an implementation
        writes its copies into a place the login already holds and creates no container of
        its own, because the audit's login is a read-only one and a tool that needed the
        right to create one could not be run by the people this is for. Scratch storage
        that is missing or that the login cannot write to is a ``BackendRefused`` naming
        which of the two it was, and the caller reports the shuffle as not run rather than
        stopping the audit.
        """
        raise NotImplementedError

    def drop_shuffled_copies(self) -> None:
        """Remove the copies this run made, and nothing else it did not.

        Called in a finally, and safe when there are none. The scratch storage itself
        outlives the run: it was arranged for the login and may hold another run's work,
        so what is removed is what this run created in it.
        """
        raise NotImplementedError

    def execute_shuffled(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        """Run one statement read-only against the shuffled copies rather than the tables."""
        raise NotImplementedError

    def execute_plan_variant(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        """Run one statement read-only with the engine steered away from its chosen plan.

        The same rows read another way. What the steering is belongs to the engine: the
        interface asks for another plan over the same data and does not name a setting.
        """
        raise NotImplementedError

    def default_collation(self) -> str:
        """The database's default collation, which decides what ordering text means.

        Read separately from ``session_settings`` because it is a property of the
        database and not of the session, and stated inside it because a record compares
        one value: an implementation reads it here and puts it there, so the two can
        never disagree.
        """
        raise NotImplementedError


__all__ = [
    "Backend",
    "BackendRefused",
    "PlannerStatistics",
    "ReadBackDrift",
    "ShuffledCopies",
    "TableLookup",
    "TableName",
    "TextCensus",
    "planner_statistics_json",
]
