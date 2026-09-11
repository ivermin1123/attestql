"""What an audit reads off one statement, stated without naming a grammar.

The sibling of ``backend.py``, and a module of its own rather than a section of it: that
one says what an audit needs from a database, and a parse reaches no database at all. It
happens before a connection is taken out, it decides which rule the comparison will run
under, and on an engine whose grammar is not the server's it is the only thing that ever
reads the statement's text. Two subjects, two modules, and ``engines.py`` is where one
engine's answer to both is named in one place.

ADR-0014 point 3: one parser per engine, behind the surface ``compare.py``, ``smells.py``
and ``cli.py`` already read. Nothing of a particular grammar reaches through it. A parse
tree, a node type and a deparser are the implementation's own, and the two rewrites below
are methods rather than free functions taking a tree for exactly that reason: the caller
asks the statement that was parsed for a variant of itself, and whatever produces it is
the business of whoever parsed it.

``ParserIdentity`` is what a record and a summary say about the thing that judged the
statement. The validator name goes into every record, because two records checked by
different validators are not one experiment; ``reported`` is what the summary states
beside it, under the engine's own key names, because what identifies a grammar differs
by grammar and a block with a field per engine would say nothing about most of them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from attestql.audit.backend import TableName
from attestql.evidence.render import Json
from attestql.evidence.types import ReplayRule, SortKey

ORDERING_KEY_PREFIX = "attestql_ordering_key_"
"""What ``without_the_bound_and_projecting_its_keys`` names the columns it adds.

A reader of the result of that variant is told which columns the statement projected and
which this tool added: the projected columns come first, and the added ones carry this
prefix and the key's position after it. It is stated here and not in one parser, because
the smell that reads those columns back reads them the same way whichever parser wrote
them."""


class StatementRefused(ValueError):
    """This text is not something the audit can run, and the reason says which part.

    ``reason`` is the whole of the refusal, so a caller writes it into a summary line
    rather than deciding for itself what a parse failure meant.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class ParserIdentity:
    """What judged a statement, as a record and a summary state it.

    ``validator`` is the one a record carries: it names a parse and claims a parse, and
    two records admitted by different validators are not one experiment. ``checks`` are
    the checks that parse ran, in the order it ran them, which a record's validation
    outcome lists. ``reported`` is everything else the summary says about the parser,
    under the names that parser's own ecosystem uses: a grammar version, a binding's
    release, whatever identifies the thing that read the text.
    """

    validator: str
    checks: tuple[str, ...]
    reported: Mapping[str, str | int]

    def __post_init__(self) -> None:
        if not self.validator:
            raise ValueError("validator is required")
        if not self.checks:
            raise ValueError("checks must name at least one check the parse ran")

    def json(self) -> Json:
        """The summary's parser block: the validator, then what the parser reports of itself."""
        return {"validator": self.validator, **dict(self.reported)}


@dataclass(frozen=True)
class OrderingKey:
    """One top-level ORDER BY element, as a parser reports it.

    ``expression`` is the key written out again by the parser's own writer, so
    ``t2.fastestLapSpeed::numeric`` and ``CAST(t2.fastestLapSpeed AS numeric)`` are one
    string and not two. ``nulls`` is ``first``, ``last`` or ``default``: where the nulls
    go is part of what an ordered answer is, and a probe that asks whether a bounded
    result is null-first needs to be told rather than to guess from the direction.

    ``column_reference`` is the dotted name when the key is a plain column reference and
    ``None`` when it is anything else. A smell that asks what type an ordering key has
    can only ask it of a column, and this is how it is told the key names one; the name
    is resolved to a table through the statement's aliases, which the statement carries.

    A concrete type and not a protocol: these four are the whole of what a key is here,
    and every parser has them to state.
    """

    expression: str
    descending: bool
    nulls: str
    column_reference: tuple[str, ...] | None

    def sort_key(self) -> SortKey:
        """The ordering key as a record states it: the expression and its direction."""
        return SortKey(column=self.expression, descending=self.descending)


class ParsedStatement(Protocol):
    """Everything the audit reads off one statement without running it.

    The four fields after the ordering and the bound are what the smells read and the
    comparison never does. ``aliases`` maps every name the FROM clause can be referred to
    by onto the relation it names, so an ordering key written ``t2.laps`` resolves to a
    column of a table rather than staying a string. ``output_names`` are the select
    list's own aliases, which an ordering key may name instead of a column.
    ``set_operation`` and ``from_has_subquery`` are the two shapes in which neither
    resolution is sound, and a smell that meets one reports itself not applicable rather
    than guessing. ``keys_not_projected_under_distinct`` is a third such shape, and the one
    engine that can state it is SQLite.
    """

    @property
    def sql(self) -> str:
        """The statement's own text, as it was handed to the parser."""
        ...

    @property
    def tables(self) -> tuple[TableName, ...]:
        """Every table the statement names, in first-seen order, each once."""
        ...

    @property
    def ordering(self) -> tuple[OrderingKey, ...]:
        """The top-level ORDER BY, empty when the statement states none."""
        ...

    @property
    def limit_count(self) -> int | None:
        """The bound when the statement states a constant one, ``None`` otherwise."""
        ...

    @property
    def limit_stated(self) -> bool:
        """Whether a bound was written at all, which a non-constant one also is."""
        ...

    @property
    def offset_count(self) -> int | None:
        """The offset when the statement states a constant one, ``None`` otherwise."""
        ...

    @property
    def offset_stated(self) -> bool:
        """Whether an offset was written at all."""
        ...

    @property
    def keys_not_projected_under_distinct(self) -> tuple[str, ...]:
        """The ordering keys a DISTINCT statement does not already project, as their text.

        Projecting a key widens the grain a DISTINCT de-duplicates on, so a rewrite that
        added one would return rows the statement itself never returned, and a smell reading
        those rows would be reading a different statement. Empty when the statement states no
        DISTINCT, and empty when every key is already in the select list.
        """
        ...

    @property
    def distinct(self) -> bool:
        """Whether the statement de-duplicates its rows."""
        ...

    @property
    def aliases(self) -> Mapping[str, TableName]:
        """Every name the FROM clause can be referred to by, onto the relation it names."""
        ...

    @property
    def output_names(self) -> tuple[str, ...]:
        """The select list's own aliases, which an ordering key may name."""
        ...

    @property
    def set_operation(self) -> bool:
        """Whether the statement is a UNION, INTERSECT or EXCEPT of two others."""
        ...

    @property
    def from_has_subquery(self) -> bool:
        """Whether the FROM clause holds a subquery, which no alias resolves through."""
        ...

    @property
    def unresolved_ordering_keys(self) -> tuple[str, ...]:
        """The top-level ORDER BY keys this parse read as columns and cannot prove are ones.

        A grammar whose sort keys are never ambiguous answers with nothing, and most do: a
        token in a sort key is a column or it is a syntax error. One does not. SQLite
        resolves a double-quoted token against the schema at prepare time and reads it as a
        string literal wherever it names no column, and a parse holds no schema, so the
        parser reads it as the column a gold almost always means and names it here instead
        of guessing.

        What is named here is the key's own name, and a caller that holds the catalogue
        resolves it before the statement runs: a key that names a column of the statement's
        tables is that column, and a key that names none is a sort key over a literal and is
        refused. That is where the resolution belongs, because a parse reaches no database
        and this one still must not.
        """
        ...

    @property
    def parser(self) -> ParserIdentity:
        """What judged this statement, which its record states and its summary reports."""
        ...

    @property
    def replay_rule(self) -> ReplayRule:
        """R-ORD when the statement has a top-level ORDER BY, R-SET when it has none."""
        ...

    @property
    def sort_keys(self) -> tuple[SortKey, ...]:
        """The ordering as a record states it."""
        ...

    def with_ordering_key_cast_to_numeric(self, index: int) -> str:
        """This statement with ordering key ``index`` cast to numeric, and nothing else.

        The rewrite differs from the statement in exactly the cast and in whatever the
        parser's own writer normalises about both of them equally.
        """
        ...

    def without_the_bound_and_projecting_its_keys(self) -> str:
        """This statement with its bound removed and its ordering keys projected.

        Everything else is left as the statement wrote it, and the added columns are
        named with ``ORDERING_KEY_PREFIX`` and the key's position, so the smell that
        compares rows at the cut can tell them from the ones the statement projected.
        """
        ...


__all__ = [
    "ORDERING_KEY_PREFIX",
    "OrderingKey",
    "ParsedStatement",
    "ParserIdentity",
    "StatementRefused",
]
