"""SQLite's parse of one statement: ``parse.py``'s surface, filled in by sqlglot.

The sibling of ``statements.py``, and the same questions asked of another grammar. Where
the PostgreSQL parser reads a statement with the server's own grammar built as a library,
this one cannot: SQLite ships no grammar a program can link against, so a SQLite statement
is read by a parser written to imitate it. That is a difference a reader of a record has to
be told about, which is why ``PARSER`` below names sqlglot, its release and the dialect it
read the text in, and why the record's validator names this parse and not the other.

The parser is ``sqlglot`` (MIT) in its SQLite dialect, pinned to one release. R-D measured
it reading every gold of BIRD dev (1,534) and of both Mini-Dev SQLite copies (500 each),
where libpg_query refuses 127, 45 and 46 of the same golds over backtick identifiers and
``LIMIT offset, count`` (``plans/reports/research-260904-sqlite-before-backend.md``).

**The one thing it reads differently, and what is done about it.** SQLite resolves a bare
double-quoted token against the schema at prepare time: it is an identifier where it
resolves to a column and falls back to a string literal where it does not. sqlglot holds no
schema, so it reads every double-quoted token as an identifier. The exposure is small and is
measured: 1 of those 2,534 golds carries a double-quoted token at all and none carries one
as a string literal. It is also confined. A double-quoted token never becomes a table name
here, never becomes an output alias, and both rewrites below keep it verbatim, so an
executed variant still means to SQLite what the statement meant. The single path by which
the wrong reading would reach an answer is a top-level ``ORDER BY`` key that is a bare
double-quoted token, where the parse would state a sort key over a column that may not
exist.

Such a key is therefore not refused here and not read as settled either: it is named in
``unresolved_ordering_keys``, and whoever executes the statement resolves it against the
columns the backend reports for the statement's tables, which is what SQLite itself does and
what a parse must not do. A key that names a column is that column; a key that names none is
a sort key over a string literal and is refused there, with the token and the rule. That
keeps the correct golds which double-quote a column name holding spaces, and still refuses
the one shape whose two readings reach two answers (ADR-0014 point 3).

Which quote character a token was written with is read off the tokenizer's offsets: the tree
records that an identifier was quoted and not which quote did it, so a backtick identifier
and a double-quoted one are one node and two tokens.

Two things sqlglot normalises on the way back out, and both are meaning-preserving on
SQLite: ``LIMIT 3, 2`` is written as ``LIMIT 2 OFFSET 3``, and a backtick identifier is
written double-quoted. The rewrites are rendered in the SQLite dialect and executed, so
what a probe reruns is a statement SQLite reads the way this parse read it.

This is not a safety validator and nothing here should be read as claiming so. It proves
the text is a single SELECT carrying no placeholder it has no value for and no sort key it
cannot support, which is what a record's ``validation_outcome`` then states.
"""

from __future__ import annotations

import importlib.metadata
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

import sqlglot
from sqlglot import exp
from sqlglot.dialects.sqlite import SQLite
from sqlglot.errors import SqlglotError
from sqlglot.tokenizer_core import Token, TokenType

from attestql.audit.backend import TableName
from attestql.audit.parse import (
    ORDERING_KEY_PREFIX,
    OrderingKey,
    ParsedStatement,
    ParserIdentity,
    StatementRefused,
)
from attestql.evidence.types import ReplayRule, SortKey

DIALECT = "sqlite"
"""The dialect every parse and every rendering in this module is made in. One name, used
for both directions, so a statement can never be read in one grammar and written in
another."""

VALIDATOR_VERSION = "audit:sqlglot-sqlite-parse"
"""What a record states as the validator that admitted its statement. It names the parser
and the grammar it imitated, because a SQLite statement read by an imitation of SQLite and
one read by SQLite itself are not checked by the same thing, and two records checked by
different validators are not one experiment."""

SQLGLOT_VERSION: Final[str] = importlib.metadata.version("sqlglot")
"""The parser's own release, read off the installed distribution rather than written down.
A version stated here and a parser underneath it that moved would be two claims about one
statement. It is what the summary reports beside the dialect, so a reader of a run is told
what read its statements."""

CHECKS_PASSED: tuple[str, ...] = (
    "parses_as_exactly_one_statement",
    "the_one_statement_is_a_select",
    "no_placeholder_without_a_bound_parameter",
)
"""The three checks ``parse_statement`` runs, in the order it runs them. The same three the
PostgreSQL parse runs: the ambiguous sort key this grammar has to deal with is named rather
than judged here, because judging it needs the catalogue and a parse reaches no database."""

PARSER = ParserIdentity(
    validator=VALIDATOR_VERSION,
    checks=CHECKS_PASSED,
    reported={"sqlglot": SQLGLOT_VERSION, "dialect": DIALECT},
)
"""This parser as a record and a summary name it: the validator every record states, the
checks it ran, the parser's release and the dialect it read the statement in. The dialect
is in it because sqlglot reads many, and a summary that named only the release would not
say which grammar admitted the statement."""

NO_ALIASES: Mapping[str, TableName] = MappingProxyType({})
"""What a set operation's FROM clause resolves: nothing. The relations are inside its
branches, an ordering key at the top resolves through none of them, and every smell that
would ask reports itself not applicable on a set operation."""

FROM_CLAUSE = "from_"
"""What the parser calls the FROM clause among a statement's parts. Named once, because
``Select.from_`` is a builder method on the same object and reading the clause off it would
be calling it."""

DOUBLE_QUOTE = '"'
"""The character SQLite reads two ways and sqlglot reads one way."""


@dataclass(frozen=True)
class SqliteStatement:
    """What sqlglot read off one statement: ``parse.py``'s ``ParsedStatement``.

    The fields are what that protocol states. The two rewrites are made on a fresh parse of
    this statement's own text and written back out by sqlglot's SQLite writer, so a variant
    differs from the statement in exactly what was asked for and in whatever the writer
    normalises about both of them equally.
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
    unresolved_ordering_keys: tuple[str, ...]

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
        """This statement with ordering key ``index`` cast to REAL, and nothing else.

        ``REAL`` is what SQLite calls the numeric type a text key has to be read as before
        an ordering over it is an ordering over numbers, and ``CAST(x AS REAL)`` is what a
        BIRD SQLite gold writes for it.
        """
        root = _root_of(_parse_one(self.sql))
        keys = _ordered_elements(root)
        if not 0 <= index < len(keys):
            raise IndexError(f"the statement has {len(keys)} ordering keys, not {index + 1}")
        key = keys[index]
        key.set(
            "this", exp.Cast(this=key.this.copy(), to=exp.DataType.build("REAL", dialect=DIALECT))
        )
        return root.sql(dialect=DIALECT)

    def without_the_bound_and_projecting_its_keys(self) -> str:
        """This statement with LIMIT and OFFSET removed and its ordering keys projected.

        Everything else is left as the statement wrote it: DISTINCT stays, because dropping
        it would collapse the very ties this is asked about, and the select list keeps every
        column it had. The ordering keys are added after it, because a tie is a tie in the
        keys and the keys need not be projected.

        A key written as an ordinal or as an output alias is resolved back to the expression
        it names first: an ordinal added to a select list would be the constant and not the
        column.
        """
        root = _root_of(_parse_one(self.sql))
        if not isinstance(root, exp.Select):
            raise ValueError("a set operation has no select list of its own to project into")
        keys = [element.this.copy() for element in _ordered_elements(root)]
        projected = [_projected_key(root, key) for key in keys]
        root.set("limit", None)
        root.set("offset", None)
        root.set(
            "expressions",
            [
                *root.expressions,
                *(
                    exp.alias_(key, f"{ORDERING_KEY_PREFIX}{position}")
                    for position, key in enumerate(projected)
                ),
            ],
        )
        return root.sql(dialect=DIALECT)


def _parse_one(sql: str) -> exp.Expr:
    """The parse of one text, or a refusal naming what the grammar could not read."""
    try:
        parsed = sqlglot.parse(sql, dialect=DIALECT)
    except SqlglotError as broken:
        raise StatementRefused(f"the text does not parse: {broken}") from broken
    statements = [statement for statement in parsed if statement is not None]
    if len(statements) != 1:
        raise StatementRefused(f"{len(statements)} statements in one text; an audit runs one")
    return statements[0]


def _root_of(statement: exp.Expr) -> exp.Select | exp.SetOperation:
    """The statement, refused unless it is one SELECT or one set operation of SELECTs.

    This is the whole of the allowlist. Everything SQLite can be told that is not a query
    is another node type here -- ``ATTACH``, ``PRAGMA``, ``INSERT``, ``UPDATE``, ``DELETE``,
    every ``CREATE`` and every ``DROP`` -- so naming what the root is says which of them was
    written, and a ``WITH ... SELECT`` is a SELECT carrying its own definitions and passes.
    """
    if isinstance(statement, (exp.Select, exp.SetOperation)):
        return statement
    raise StatementRefused(
        f"the statement is a {type(statement).__name__.upper()} and not a SELECT"
    )


def _ordered_elements(root: exp.Select | exp.SetOperation) -> list[exp.Ordered]:
    """The top-level ORDER BY as the parser holds it, empty when the statement states none."""
    order = root.args.get("order")
    if not isinstance(order, exp.Order):
        return []
    return [element for element in order.expressions if isinstance(element, exp.Ordered)]


def _tables_named(statement: exp.Expr) -> tuple[TableName, ...]:
    """Every table the statement names, with the schema it qualified it with beside it.

    A name a ``WITH`` clause defines is not a table: a bare reference to it reads the common
    table expression, which is what SQLite resolves it to, so it is set aside and the data
    behind it is measured through the tables the expression itself names.

    The names come back in the order the tree is walked, each once. ``schema`` is empty for
    a bare name and ``main`` for one the statement qualified, which is the only schema a
    SQLite file that attached nothing has.
    """
    defined = {cte.alias for cte in statement.find_all(exp.CTE)}
    names = [
        TableName(table.db, table.name)
        for table in statement.find_all(exp.Table)
        if table.name and isinstance(table.this, exp.Identifier)
    ]
    return tuple(name for name in dict.fromkeys(names) if name.schema or name.name not in defined)


def _placeholders(statement: exp.Expr) -> list[str]:
    """Every placeholder the statement carries, as the text the parser read it from.

    Read off the tree and not off the text, so a string holding a question mark is a string
    and not a parameter. SQLite spells a placeholder four ways and sqlglot reads them as two
    node types; both are asked for, because an audit binds no parameter whichever way it was
    written.
    """
    found = {
        node.sql(dialect=DIALECT) for node in statement.find_all(exp.Placeholder, exp.Parameter)
    }
    return sorted(found)


def _constant_count(bound: object) -> int | None:
    """A plain whole number a bound states, or ``None`` for anything else.

    Nothing here evaluates a bound the statement did not write down: a bound that is an
    expression, a parameter or a negative literal is a bound this parse does not state.
    """
    if not isinstance(bound, exp.Expr):
        return None
    inner = bound.args.get("expression")
    if not isinstance(inner, exp.Literal) or inner.is_string:
        return None
    text = inner.this
    return int(text) if isinstance(text, str) and text.isdigit() else None


def _column_reference(node: exp.Expr) -> tuple[str, ...] | None:
    """The dotted name of a plain column reference, or ``None`` when it is an expression."""
    if not isinstance(node, exp.Column):
        return None
    parts = [part.name for part in node.parts if isinstance(part, exp.Identifier)]
    return tuple(parts) if len(parts) == len(node.parts) else None


def _nulls_of(element: exp.Ordered) -> str:
    """Where this key's nulls go, under SQLite's own default where the key states none.

    SQLite sorts a NULL below every value, so an ascending key puts its nulls first and a
    descending key puts them last, and a written ``NULLS FIRST`` or ``NULLS LAST`` wins over
    both. The parser fills the default in for a key that states none, which is why this
    never answers ``default``: on this engine the placement is decided either way, and a
    probe that reads a bounded result needs to be told which it was.
    """
    return "first" if bool(element.args.get("nulls_first")) else "last"


def _ordering(root: exp.Select | exp.SetOperation) -> tuple[OrderingKey, ...]:
    return tuple(
        OrderingKey(
            expression=element.this.sql(dialect=DIALECT),
            descending=bool(element.args.get("desc")),
            nulls=_nulls_of(element),
            column_reference=_column_reference(element.this),
        )
        for element in _ordered_elements(root)
    )


def _targets(root: exp.Select) -> tuple[tuple[str | None, exp.Expr], ...]:
    """The select list as (output name, expression) pairs, in the order it was written.

    The name is the alias the statement wrote and ``None`` where it wrote none, as the
    PostgreSQL parse states it: a column that carries its own name into the result was not
    named by the select list, and an ordering key that spells that name is resolved against
    the table and not against the projection.
    """
    return tuple(
        (target.alias, target.this) if isinstance(target, exp.Alias) else (None, target)
        for target in root.expressions
    )


def _projected_key(root: exp.Select, key: exp.Expr) -> exp.Expr:
    """One ordering key as an expression a select list can carry.

    A key may be an ordinal or an output alias, and neither means anything in a select list;
    both are resolved back to the expression of the target they name.
    """
    targets = _targets(root)
    if isinstance(key, exp.Literal) and not key.is_string:
        text = key.this
        if isinstance(text, str) and text.isdigit() and 1 <= int(text) <= len(targets):
            return targets[int(text) - 1][1].copy()
    fields = _column_reference(key)
    if fields is not None and len(fields) == 1:
        for name, expression in targets:
            if name == fields[0]:
                return expression.copy()
    return key


def _sources(root: exp.Select) -> Iterator[exp.Expr]:
    """Every FROM item of the statement: the FROM clause itself and each join after it."""
    source = root.args.get(FROM_CLAUSE)
    if isinstance(source, exp.From):
        yield source.this
    for join in root.args.get("joins") or ():
        if isinstance(join, exp.Join):
            yield join.this


def _collect_aliases(root: exp.Select) -> tuple[Mapping[str, TableName], bool]:
    """Every FROM item as the name it can be referred to by, and whether one is a subquery.

    The relation keeps the schema the FROM clause wrote, so a key resolved through an alias
    is resolved against the table the statement meant. A subselect or a table-valued call in
    FROM holds columns this parse cannot attribute to a table, and a resolution that guessed
    would name the wrong one, so it is reported rather than resolved.
    """
    aliases: dict[str, TableName] = {}
    subqueries = False
    for source in _sources(root):
        if isinstance(source, exp.Table) and isinstance(source.this, exp.Identifier):
            aliases[source.alias or source.name] = TableName(source.db, source.name)
        else:
            subqueries = True
    return MappingProxyType(aliases), subqueries


def _bare_double_quoted_names(sql: str) -> frozenset[str]:
    """The double-quoted names the top-level ORDER BY writes that qualify nothing.

    Read off the tokenizer rather than off the tree, because the tree records that an
    identifier was quoted and not which quote did it: a backtick identifier and a
    double-quoted one are one node and two tokens. The region is found by paren depth, so an
    ORDER BY inside a subquery is not this statement's own; it ends at the statement's own
    LIMIT or OFFSET, which is the only thing that can follow it at that depth.

    A token beside a dot is qualified, on either side: ``t."col"`` names a column of a table
    and ``"s".t`` names a relation, and SQLite allows no string literal in either place.
    """
    tokens = SQLite().tokenize(sql)
    depth = 0
    start: int | None = None
    end = len(tokens)
    for position, token in enumerate(tokens):
        if token.token_type is TokenType.L_PAREN:
            depth += 1
        elif token.token_type is TokenType.R_PAREN:
            depth -= 1
        elif depth == 0 and token.token_type is TokenType.ORDER_BY:
            start, end = position + 1, len(tokens)
        elif (
            depth == 0
            and start is not None
            and token.token_type in (TokenType.LIMIT, TokenType.OFFSET)
        ):
            end = min(end, position)
    if start is None:
        return frozenset()
    return frozenset(
        token.text
        for position, token in enumerate(tokens[start:end], start=start)
        if _is_a_bare_double_quoted_token(sql, tokens, position)
    )


def _is_a_bare_double_quoted_token(sql: str, tokens: Sequence[Token], position: int) -> bool:
    """Whether that token is an identifier written in double quotes and qualifying nothing."""
    token = tokens[position]
    if token.token_type is not TokenType.IDENTIFIER or sql[token.start] != DOUBLE_QUOTE:
        return False
    before = tokens[position - 1] if position else None
    after = tokens[position + 1] if position + 1 < len(tokens) else None
    return not (
        (before is not None and before.token_type is TokenType.DOT)
        or (after is not None and after.token_type is TokenType.DOT)
    )


def _unresolved_ordering_keys(sql: str, ordering: Sequence[exp.Ordered]) -> tuple[str, ...]:
    """The sort keys whose token this grammar cannot tell from a string literal, by name.

    Each once and in the order the statement wrote them. Whoever runs the statement resolves
    them against the catalogue; nothing is decided here.
    """
    if not ordering:
        return ()
    written = _bare_double_quoted_names(sql)
    if not written:
        return ()
    named: list[str] = []
    for element in ordering:
        key = element.this
        if not isinstance(key, exp.Column) or len(key.parts) != 1:
            continue
        identifier = key.this
        if (
            isinstance(identifier, exp.Identifier)
            and identifier.quoted
            and identifier.name in written
        ):
            named.append(identifier.name)
    return tuple(dict.fromkeys(named))


def parse_statement(sql: str) -> ParsedStatement:
    """Parse one statement, or refuse it with a reason that names what was wrong."""
    root = _root_of(_parse_one(sql))
    placeholders = _placeholders(root)
    if placeholders:
        # An audit binds no parameters, so a text carrying a placeholder is a text whose
        # values are somewhere else, and a record of it could not be replayed.
        raise StatementRefused(f"placeholders {placeholders} and the audit binds no parameters")
    ordered = _ordered_elements(root)
    select = root if isinstance(root, exp.Select) else None
    aliases, from_has_subquery = (
        _collect_aliases(select) if select is not None else (NO_ALIASES, False)
    )
    limit, offset = root.args.get("limit"), root.args.get("offset")
    return SqliteStatement(
        sql=sql,
        tables=_tables_named(root),
        ordering=_ordering(root),
        limit_count=_constant_count(limit),
        # A set operation's own ``distinct`` says UNION rather than UNION ALL, which is not
        # what a select list's DISTINCT is; only a SELECT states one here.
        distinct=select is not None and select.args.get("distinct") is not None,
        limit_stated=limit is not None,
        offset_count=_constant_count(offset),
        offset_stated=offset is not None,
        aliases=aliases,
        output_names=(
            tuple(name for name, _ in _targets(select) if name) if select is not None else ()
        ),
        set_operation=select is None,
        from_has_subquery=from_has_subquery,
        unresolved_ordering_keys=_unresolved_ordering_keys(sql, ordered),
    )


__all__ = [
    "CHECKS_PASSED",
    "DIALECT",
    "PARSER",
    "SQLGLOT_VERSION",
    "VALIDATOR_VERSION",
    "SqliteStatement",
    "parse_statement",
]
