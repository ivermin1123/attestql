"""What the audit reads off a statement, on the three rows ADR-0013 was written from.

The rule is not a choice: it is read off the gold's own ORDER BY. Two of the three rows
carry one and are compared as ordered answers; the third does not and is compared as a
multiset, which is what makes its DISTINCT and its row multiplicity the thing at issue.

The statements are the upstream ones, quoted here so a reader can see what is being
parsed. The ordering key is the parser's own rendering of the expression, so a cast
written as ``::numeric`` and one written as ``CAST(... AS numeric)`` are one key and not
two, and a record that ordered by an expression it does not project still states it. Which
of the two spellings the key comes back as is the writer's and not this project's: the
previous parser wrote ``CAST(x AS numeric)`` where this one writes ``x::numeric``, and the
four Mini-Dev golds whose key holds a cast are the whole of what that changed.
"""

from __future__ import annotations

import pytest

from attestql.audit.backend import TableName
from attestql.audit.statements import (
    CHECKS_PASSED,
    VALIDATOR_VERSION,
    ParsedStatement,
    StatementRefused,
    parse_statement,
)
from attestql.evidence.types import ReplayRule, SortKey

Q1029_GOLD = (
    "SELECT t1.buildUpPlaySpeed FROM Team_Attributes AS t1 "
    "INNER JOIN Team AS t2 ON t1.team_api_id = t2.team_api_id "
    "ORDER BY t1.buildUpPlaySpeed ASC NULLS FIRST LIMIT 4"
)
Q879_GOLD = (
    "SELECT T1.nationality FROM drivers AS T1 "
    "INNER JOIN results AS T2 ON T2.driverId = T1.driverId "
    "ORDER BY T2.fastestLapSpeed DESC NULLS LAST LIMIT 1"
)
Q879_CORRECTION = (
    "SELECT T1.nationality FROM drivers AS T1 "
    "INNER JOIN results AS T2 ON T2.driverId = T1.driverId "
    "ORDER BY T2.fastestLapSpeed::numeric DESC NULLS LAST LIMIT 1"
)
Q207_CORRECTION = (
    "SELECT DISTINCT T1.element FROM atom AS T1 "
    "JOIN connected AS T2 ON T1.atom_id = T2.atom_id "
    "JOIN bond AS T3 ON T2.bond_id = T3.bond_id "
    "WHERE T3.bond_type = '='"
)


def test_the_rule_is_read_off_the_statement_and_not_chosen() -> None:
    assert parse_statement(Q1029_GOLD).replay_rule is ReplayRule.R_ORD
    assert parse_statement(Q879_GOLD).replay_rule is ReplayRule.R_ORD
    assert parse_statement(Q207_CORRECTION).replay_rule is ReplayRule.R_SET


def test_an_ascending_null_first_key_is_reported_as_written() -> None:
    """Row A: the defect is the direction, so direction and nulls are both read."""
    parsed = parse_statement(Q1029_GOLD)
    key = parsed.ordering[0]
    assert (key.expression, key.descending, key.nulls) == ("t1.buildupplayspeed", False, "first")
    assert parsed.limit_count == 4
    assert set(parsed.tables) == {TableName("", "team_attributes"), TableName("", "team")}
    assert parsed.distinct is False


def test_a_cast_in_the_ordering_key_is_part_of_the_key() -> None:
    """Row B: gold and correction differ only inside the ORDER BY, and that shows here."""
    gold, correction = parse_statement(Q879_GOLD), parse_statement(Q879_CORRECTION)
    assert gold.ordering[0].expression == "t2.fastestlapspeed"
    assert correction.ordering[0].expression == "t2.fastestlapspeed::numeric"
    assert gold.ordering[0].expression != correction.ordering[0].expression
    for parsed in (gold, correction):
        assert parsed.ordering[0].descending is True
        assert parsed.ordering[0].nulls == "last"
        assert parsed.limit_count == 1
        assert set(parsed.tables) == {TableName("", "drivers"), TableName("", "results")}


def test_a_statement_with_no_ordering_carries_no_ordering_and_still_reports_its_shape() -> None:
    """Row C: R-SET, three tables, and a DISTINCT that a multiset comparison will feel."""
    parsed = parse_statement(Q207_CORRECTION)
    assert parsed.ordering == ()
    assert parsed.sort_keys == ()
    assert parsed.limit_count is None
    assert parsed.distinct is True
    assert set(parsed.tables) == {
        TableName("", "atom"),
        TableName("", "connected"),
        TableName("", "bond"),
    }


def test_the_ordering_a_record_states_is_the_expression_and_its_direction() -> None:
    assert parse_statement(Q879_CORRECTION).sort_keys == (
        SortKey("t2.fastestlapspeed::numeric", descending=True),
    )


def test_a_qualified_table_keeps_its_schema_and_a_bare_one_is_left_bare() -> None:
    """The audit does not invent a schema here; the backend decides what a bare name means."""
    assert parse_statement("SELECT a FROM public.t ORDER BY a").tables == (
        TableName("public", "t"),
    )
    assert parse_statement("SELECT a FROM t").tables == (TableName("", "t"),)
    assert parse_statement('SELECT a FROM "Quoted".t').tables == (TableName("Quoted", "t"),)


def test_a_relation_whose_name_holds_a_dot_is_one_name_and_not_two() -> None:
    """``"a.b"`` is a relation called ``a.b`` and not the table ``b`` of a schema ``a``.

    The grammar hands identifiers back with their quoting taken off, so the two are the
    same string once they are joined, and everything downstream reads the pair instead.
    """
    dotted = parse_statement('SELECT x FROM "a.b"')
    assert dotted.tables == (TableName("", "a.b"),)
    assert dotted.tables != parse_statement("SELECT x FROM a.b").tables
    assert parse_statement("SELECT x FROM a.b").tables == (TableName("a", "b"),)


def test_the_relation_an_alias_names_keeps_the_schema_the_from_clause_wrote() -> None:
    """An ordering key resolved through an alias resolves to the table the statement meant,
    and not to another table of that name in another schema."""
    parsed = parse_statement('SELECT t.a FROM "Quoted".y AS t ORDER BY t.a')
    assert dict(parsed.aliases) == {"t": TableName("Quoted", "y")}
    assert dict(parse_statement("SELECT a FROM y").aliases) == {"y": TableName("", "y")}


def test_a_table_named_twice_is_named_once() -> None:
    parsed = parse_statement("SELECT a.x FROM t AS a JOIN t AS b ON a.x = b.x")
    assert parsed.tables == (TableName("", "t"),)


def test_a_name_a_with_clause_defines_is_not_a_table() -> None:
    """Mini-Dev golds 944, 955, 1011, 1014, 518 and 282 open with WITH; the data behind the
    expression is measured through the tables it names, and its own name is not counted."""
    parsed = parse_statement(
        "WITH fastest AS (SELECT r.driverId, MIN(r.milliseconds) AS ms FROM results AS r "
        "GROUP BY r.driverId) "
        "SELECT d.surname FROM fastest JOIN drivers AS d ON d.driverId = fastest.driverId "
        "ORDER BY fastest.ms LIMIT 1"
    )
    assert set(parsed.tables) == {TableName("", "results"), TableName("", "drivers")}

    nested = parse_statement(
        "SELECT * FROM (WITH inner_rows AS (SELECT a FROM t) SELECT a FROM inner_rows) AS s"
    )
    assert nested.tables == (TableName("", "t"),)


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("SELECT 1; SELECT 2", "2 statements in one text"),
        ("UPDATE t SET x = 1", "is a UpdateStmt"),
        ("INSERT INTO t VALUES (1)", "is a InsertStmt"),
        ("SELECT * FROM t WHERE x = $1", r"placeholders \[1\]"),
        ("SELECT FROM WHERE", "does not parse"),
    ],
)
def test_anything_that_is_not_one_plain_select_is_refused_by_name(sql: str, reason: str) -> None:
    with pytest.raises(StatementRefused, match=reason):
        parse_statement(sql)


def test_the_refusal_carries_its_reason_as_a_value() -> None:
    """A caller writes the reason into a summary line rather than deciding what it meant."""
    with pytest.raises(StatementRefused) as refused:
        parse_statement("DELETE FROM t")
    assert refused.value.reason == refused.value.args[0]
    assert "DeleteStmt" in refused.value.reason


def test_a_placeholder_is_counted_from_the_tree_and_a_literal_that_looks_like_one_is_not() -> None:
    """``'$5 off'`` is a price and not a parameter, and only the parse can tell them apart.

    The count used to be a regular expression over the raw text, which refused any gold
    holding a string with a dollar and a digit in it while naming a parameter the statement
    never had."""
    parsed = parse_statement("SELECT name FROM t WHERE note = '$5 off'")
    assert parsed.tables == (TableName("", "t"),)
    with pytest.raises(StatementRefused, match=r"placeholders \[1\]"):
        parse_statement("SELECT name FROM t WHERE id = $1")


def test_the_parse_names_itself_and_the_checks_it_ran() -> None:
    """Two records checked by different validators are not one experiment."""
    assert VALIDATOR_VERSION == "audit:libpg_query-parse"
    assert CHECKS_PASSED == (
        "parses_as_exactly_one_statement",
        "the_one_statement_is_a_select",
        "no_placeholder_without_a_bound_parameter",
    )


def test_a_parsed_statement_is_frozen() -> None:
    parsed = parse_statement(Q1029_GOLD)
    with pytest.raises(AttributeError):
        parsed.sql = "SELECT 1"  # pyright: ignore[reportAttributeAccessIssue]  # frozen by design
    assert isinstance(parsed, ParsedStatement)
