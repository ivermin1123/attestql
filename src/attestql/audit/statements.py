"""PostgreSQL's parse of one statement: ``parse.py``'s surface, filled in by libpg_query.

One parse per statement, and everything the audit reads off a statement is read off
that parse: the tables it names, whether it orders its rows and by what, whether it
bounds them, and whether it is one plain SELECT at all. A second parser over the same
engine would be a second opinion about the same text, and the two would disagree on the
day it mattered. A second parser over another engine is a different thing: it reads
another grammar, answers the same questions, and reaches the audit through the
``ParsedStatement`` protocol this module implements (ADR-0014 point 3).

The parser is ``postgast``, a BSD-2-Clause binding to libpg_query, which is PostgreSQL's
own grammar built as a library: the tool reads a statement the way the server that will
run it does. It replaced a GPL-licensed binding whose terms would have reached everything
that embedded this audit, and this is the only module in the product that reaches a parser
at all. ADR-0013 point 2 makes the parse part of the audit itself: the replay rule is read
off the gold's ORDER BY, and the smells are read off the gold's AST, so a parse is not
something the audit can do without.

This is not a safety validator and nothing here should be read as claiming so. It proves
the text is a single SELECT statement carrying no placeholder it has no value for, which
is what a record's ``validation_outcome`` then states, and it proves nothing else.
"""

from __future__ import annotations

import importlib.metadata
from collections import deque
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, TypeVar

import postgast
from postgast import pg_query_pb2 as nodes

from attestql.audit.backend import TableName
from attestql.audit.parse import (
    ORDERING_KEY_PREFIX,
    OrderingKey,
    ParsedStatement,
    ParserIdentity,
    StatementRefused,
)
from attestql.evidence.types import ReplayRule, SortKey

VALIDATOR_VERSION = "audit:libpg_query-parse"
"""What a record states as the validator that admitted its statement. It names a parse
and claims a parse: two records checked by different validators are not one experiment,
so the name has to say which one ran. It names the grammar rather than the binding
around it, because the grammar is what decides whether a text is one SELECT."""

CHECKS_PASSED: tuple[str, ...] = (
    "parses_as_exactly_one_statement",
    "the_one_statement_is_a_select",
    "no_placeholder_without_a_bound_parameter",
)
"""The three checks ``parse_statement`` runs, in the order it runs them."""

_PROJECTION = "SELECT "
"""The whole of the statement ``_expression_text`` wraps an expression in.

libpg_query writes SQL for a statement and not for a node, so an expression is written
out by making it the one column of a select list and taking off what the wrapper added.
The wrapper names no relation and no output column, so there is nothing else to take
off."""

GRAMMAR_VERSION: Final[int] = postgast.parse("SELECT 1").version
"""The protobuf tree version this build of libpg_query writes and reads.

Read from a parse and never written down, because a number stated here and a grammar
underneath it that moved would be two different claims about the same statement. A tree
assembled rather than parsed carries it too, so the wrapper above is deparsed by the same
grammar that parsed the expression inside it, and a wrong value would fail every deparse
in this module rather than reach a summary quietly."""

POSTGAST_VERSION: Final[str] = importlib.metadata.version("postgast")
"""The binding's own release, beside the grammar it was built around. The two move apart:
a binding can be reissued over the same libpg_query, and a summary that named only one of
them would not say what read its statements."""


PARSER = ParserIdentity(
    validator=VALIDATOR_VERSION,
    checks=CHECKS_PASSED,
    reported={"postgast": POSTGAST_VERSION, "grammar_version": GRAMMAR_VERSION},
)
"""This parser as a record and a summary name it: the validator every record states, the
checks it ran, and the two releases that decide what it read, since a binding can be
reissued over one libpg_query and a summary that named only one of them would not say
what read its statements."""


def _expression_text(node: nodes.Node) -> str:
    """One expression as SQL text, written by the parser's own writer.

    The parser deparses a statement, so the expression is projected by a bare SELECT and
    the projection is taken off again. Nothing is read off the original text: two ways of
    writing one expression come back as one string, which is what makes an ordering key
    comparable at all.
    """
    holder = nodes.ParseResult(version=GRAMMAR_VERSION)
    holder.stmts.add().stmt.select_stmt.target_list.add().res_target.val.CopyFrom(node)
    written = postgast.deparse(holder)
    if not written.startswith(_PROJECTION):
        raise ValueError(f"the parser wrote a one-expression projection as {written!r}")
    return written[len(_PROJECTION) :]


@dataclass(frozen=True)
class PostgresStatement:
    """What libpg_query read off one statement: ``parse.py``'s ``ParsedStatement``.

    The fields are what that protocol states, and the two rewrites below are made on a
    fresh parse of this statement's own text and written back out by the parser's own
    writer, so a variant differs from the statement in exactly what was asked for and in
    whatever the writer normalises about both of them equally.
    """

    sql: str
    tables: tuple[TableName, ...]
    ordering: tuple[OrderingKey, ...]
    limit_count: int | None
    distinct: bool
    limit_stated: bool
    offset_count: int | None
    offset_stated: bool
    aliases: Mapping[str, TableName]
    output_names: tuple[str, ...]
    set_operation: bool
    from_has_subquery: bool

    @property
    def parser(self) -> ParserIdentity:
        """This module's parser, which is the one that read every statement it returns."""
        return PARSER

    @property
    def replay_rule(self) -> ReplayRule:
        """R-ORD when the statement has a top-level ORDER BY, R-SET when it has none."""
        return ReplayRule.R_ORD if self.ordering else ReplayRule.R_SET

    @property
    def sort_keys(self) -> tuple[SortKey, ...]:
        """The ordering as a record states it."""
        return tuple(key.sort_key() for key in self.ordering)

    def with_ordering_key_cast_to_numeric(self, index: int) -> str:
        """This statement with ordering key ``index`` cast to numeric, and nothing else."""
        tree = _parse(self.sql)
        statement = _select_statement(tree)
        sort_clause = statement.sort_clause
        if not 0 <= index < len(sort_clause):
            raise IndexError(f"the statement has {len(sort_clause)} ordering keys, not {index + 1}")
        key = _unwrap(sort_clause[index], nodes.SortBy)
        key.node.CopyFrom(_numeric_cast(key.node))
        return postgast.deparse(tree)

    def without_the_bound_and_projecting_its_keys(self) -> str:
        """This statement with LIMIT and OFFSET removed and its ordering keys projected.

        Everything else is left as the statement wrote it: DISTINCT stays, because
        dropping it would collapse the very ties this is asked about and answer a
        question about a different statement, and the select list keeps every column it
        had, because what a smell compares at the cut is the answer the gold projects.
        The ordering keys are added after it, because a tie is a tie in the keys and the
        keys need not be projected: ``ORDER BY t2.fastestLapSpeed`` over a projection of
        nationality alone would otherwise leave nothing to compare the rows at the cut on.

        A key written as an ordinal or as an output alias is resolved back to the
        expression it names first: an ordinal added to a select list would be the
        constant, not the column. Under DISTINCT the keys are already in the select list,
        which is what PostgreSQL requires of a DISTINCT statement that orders itself, so
        the copies added here group with them and the row set does not change.
        """
        tree = _parse(self.sql)
        statement = _select_statement(tree)
        keys = [_unwrap(element, nodes.SortBy).node for element in statement.sort_clause]
        projected = [_projected_key(statement, key) for key in keys]
        statement.ClearField("limit_count")
        statement.ClearField("limit_offset")
        for position, key in enumerate(projected):
            target = statement.target_list.add().res_target
            target.val.CopyFrom(key)
            target.name = f"{ORDERING_KEY_PREFIX}{position}"
        return postgast.deparse(tree)


def _parse(sql: str) -> nodes.ParseResult:
    """The parse tree of one text, or a refusal naming what the grammar could not read."""
    try:
        return postgast.parse(sql)
    except postgast.PgQueryError as broken:
        raise StatementRefused(f"the text does not parse: {broken}") from broken


_Element = TypeVar("_Element", nodes.SortBy, nodes.ResTarget)


def _unwrap(node: nodes.Node, kind: type[_Element]) -> _Element:
    """One element of a clause as the concrete node it holds.

    Every child in this grammar's protobuf tree is wrapped in a ``Node`` carrying one
    field of many. A sort clause holds sort elements and a select list holds targets, so
    the shape is known from where the element was read; anything else there would be a
    tree this module has misread and says so rather than carrying on.
    """
    inner = postgast.unwrap_node(node)
    if not isinstance(inner, kind):
        raise ValueError(f"the parser put a {type(inner).__name__} where a {kind.__name__} goes")
    return inner


def _select_statement(tree: nodes.ParseResult) -> nodes.SelectStmt:
    """The tree's one statement, refused unless it is a SELECT."""
    statement = postgast.unwrap_node(tree.stmts[0].stmt)
    if not isinstance(statement, nodes.SelectStmt):
        raise StatementRefused(f"the statement is a {type(statement).__name__} and not a SELECT")
    return statement


def _breadth_first(tree: nodes.ParseResult) -> Iterator[Any]:
    """Every node of the tree, nearest the root first, each field in the grammar's order.

    The generated message classes carry no static shape for a walk over all of them, so
    the fields are read through the protobuf descriptor and the nodes come back untyped;
    every caller narrows with ``isinstance`` before reading anything off one, which is
    where the type comes back.

    Breadth first, and not because either order is better: it is the order the previous
    parser's visitor used, and the tables a statement names are recorded in the order
    they are first met, so a depth-first walk would rewrite that list for a hundred of
    the 498 Mini-Dev golds without a single statement having changed.
    """
    queue: deque[Any] = deque([tree])
    while queue:
        message: Any = queue.popleft()
        yield message
        for descriptor, value in message.ListFields():
            if descriptor.type != descriptor.TYPE_MESSAGE:
                continue
            children: Any = value if descriptor.is_repeated else (value,)
            for child in children:
                queue.append(postgast.unwrap_node(child))


def _tables_named(tree: nodes.ParseResult) -> tuple[TableName, ...]:
    """Every table the statement names, with the schema it qualified it with beside it.

    The schema and the relation are kept apart rather than joined into one name, because
    the grammar hands back identifiers with their quoting taken off: a relation written
    ``"a.b"`` comes back as the one name ``a.b``, and a name that had been joined could
    not be told from the table ``b`` of a schema ``a`` afterwards.

    A name a ``WITH`` clause defines is not a table: a bare reference to it reads the common
    table expression, which is what PostgreSQL resolves it to even when a table of that name
    exists, so it is set aside and the data behind it is measured through the tables the
    expression itself names. Six Mini-Dev golds are written this way, and the audit's first
    run over the real dump stopped on the first of them asking the server to count a
    relation that was never there.

    The names come back in first-seen order, each once, which is the order the tree is
    written in and not an order this module chose.
    """
    names: list[TableName] = []
    defined: set[str] = set()
    for node in _breadth_first(tree):
        if isinstance(node, nodes.RangeVar):
            if not node.relname:
                continue
            names.append(TableName(node.schemaname, node.relname))
        elif isinstance(node, nodes.CommonTableExpr):
            defined.add(node.ctename)
    return tuple(name for name in dict.fromkeys(names) if name.schema or name.name not in defined)


def _placeholders(tree: nodes.ParseResult) -> list[int]:
    """Every ``$n`` the statement carries, read off the tree and not off the text.

    A literal such as ``'$5 off'`` is a string and not a parameter, and only the parse can
    tell the two apart. This used to be a regular expression over the raw text, which
    refused a statement holding such a string for a parameter it never had.
    """
    return sorted(
        {node.number for node in _breadth_first(tree) if isinstance(node, nodes.ParamRef)}
    )


def _const_int(node: nodes.Node) -> int | None:
    """A plain integer constant, or ``None`` for anything else, NULL and expressions
    included. Nothing here evaluates a bound the statement did not write down."""
    constant = postgast.unwrap_node(node)
    if not isinstance(constant, nodes.A_Const) or not constant.HasField("ival"):
        return None
    return constant.ival.ival


def _column_ref_fields(node: nodes.Node) -> tuple[str, ...] | None:
    """The dotted name of a plain column reference, or ``None`` when it is an expression."""
    reference = postgast.unwrap_node(node)
    if not isinstance(reference, nodes.ColumnRef):
        return None
    names: list[str] = []
    for part in reference.fields:
        inner = postgast.unwrap_node(part)
        if not isinstance(inner, nodes.String):
            return None
        names.append(inner.sval)
    return tuple(names)


def _numeric_cast(node: nodes.Node) -> nodes.Node:
    """The node wrapped in a cast to ``numeric``, as the parser would have parsed one."""
    cast = nodes.Node()
    cast.type_cast.arg.CopyFrom(node)
    type_name = cast.type_cast.type_name
    for part in ("pg_catalog", "numeric"):
        type_name.names.add().string.sval = part
    type_name.typemod = -1
    return cast


def _collect_aliases(
    node: nodes.Node, aliases: dict[str, TableName], subqueries: list[bool]
) -> None:
    """Every FROM item as the name it can be referred to by, and the relation it names.

    The relation keeps the schema the FROM clause wrote, so a key resolved through an
    alias is resolved against the table the statement meant and not against another table
    of that name in another schema.
    """
    source = postgast.unwrap_node(node)
    if isinstance(source, nodes.RangeVar):
        alias = source.alias.aliasname if source.HasField("alias") else ""
        aliases[alias or source.relname] = TableName(source.schemaname, source.relname)
    elif isinstance(source, nodes.JoinExpr):
        _collect_aliases(source.larg, aliases, subqueries)
        _collect_aliases(source.rarg, aliases, subqueries)
    else:
        # A subselect or a function call in FROM: it holds columns this parse cannot
        # attribute to a table, and a resolution that guessed would name the wrong one.
        subqueries.append(True)


def _targets(statement: nodes.SelectStmt) -> tuple[tuple[str | None, nodes.Node], ...]:
    """The select list as (output name, expression) pairs, in the order it was written."""
    pairs: list[tuple[str | None, nodes.Node]] = []
    for target in statement.target_list:
        res_target = _unwrap(target, nodes.ResTarget)
        pairs.append((res_target.name or None, res_target.val))
    return tuple(pairs)


def _projected_key(statement: nodes.SelectStmt, node: nodes.Node) -> nodes.Node:
    """One ordering key as an expression a select list can carry.

    A key may be an ordinal or an output alias, and neither means anything in a select
    list; both are resolved back to the expression of the target they name.
    """
    targets = _targets(statement)
    ordinal = _const_int(node)
    if ordinal is not None and 1 <= ordinal <= len(targets):
        return targets[ordinal - 1][1]
    fields = _column_ref_fields(node)
    if fields is not None and len(fields) == 1:
        for name, expression in targets:
            if name == fields[0]:
                return expression
    return node


def _nulls_of(sort_by: nodes.SortBy) -> str:
    if sort_by.sortby_nulls == nodes.SortByNulls.SORTBY_NULLS_FIRST:
        return "first"
    if sort_by.sortby_nulls == nodes.SortByNulls.SORTBY_NULLS_LAST:
        return "last"
    return "default"


def _limit_count(statement: nodes.SelectStmt) -> int | None:
    """The bound the statement puts on its own rows, when that bound is a literal count.

    ``None`` means the statement does not bound itself, or bounds itself by an expression
    this parse does not evaluate. Nothing here computes a bound the statement did not
    write, because a probe that reads a bound is asking what the statement said.
    """
    if not statement.HasField("limit_count"):
        return None
    text = _expression_text(statement.limit_count).strip()
    return int(text) if text.isdigit() else None


def _ordering(statement: nodes.SelectStmt) -> tuple[OrderingKey, ...]:
    keys: list[OrderingKey] = []
    for element in statement.sort_clause:
        sort_by = _unwrap(element, nodes.SortBy)
        keys.append(
            OrderingKey(
                expression=_expression_text(sort_by.node),
                descending=sort_by.sortby_dir == nodes.SortByDir.SORTBY_DESC,
                nulls=_nulls_of(sort_by),
                column_reference=_column_ref_fields(sort_by.node),
            )
        )
    return tuple(keys)


def parse_statement(sql: str) -> ParsedStatement:
    """Parse one statement, or refuse it with a reason that names what was wrong."""
    tree = _parse(sql)
    if len(tree.stmts) != 1:
        raise StatementRefused(f"{len(tree.stmts)} statements in one text; an audit runs one")
    statement = _select_statement(tree)
    placeholders = _placeholders(tree)
    if placeholders:
        # An audit binds no parameters, so a text carrying a placeholder is a text whose
        # values are somewhere else, and a record of it could not be replayed.
        raise StatementRefused(f"placeholders {placeholders} and the audit binds no parameters")
    aliases: dict[str, TableName] = {}
    subqueries: list[bool] = []
    for source in statement.from_clause:
        _collect_aliases(source, aliases, subqueries)
    return PostgresStatement(
        sql=sql,
        tables=_tables_named(tree),
        ordering=_ordering(statement),
        limit_count=_limit_count(statement),
        distinct=len(statement.distinct_clause) > 0,
        limit_stated=statement.HasField("limit_count"),
        offset_count=_const_int(statement.limit_offset)
        if statement.HasField("limit_offset")
        else None,
        offset_stated=statement.HasField("limit_offset"),
        aliases=MappingProxyType(aliases),
        output_names=tuple(name for name, _ in _targets(statement) if name is not None),
        set_operation=statement.op != nodes.SetOperation.SETOP_NONE,
        from_has_subquery=bool(subqueries),
    )


__all__ = [
    "CHECKS_PASSED",
    "GRAMMAR_VERSION",
    "PARSER",
    "POSTGAST_VERSION",
    "VALIDATOR_VERSION",
    "PostgresStatement",
    "parse_statement",
]
