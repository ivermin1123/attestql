"""What sqlglot's SQLite dialect reads off a statement, and the one shape it refuses.

The sibling of ``tests/test_audit_reads_the_statement_before_running_it.py``, and the same
questions asked of the other grammar: what the statement names, whether it orders and by
what, whether it bounds itself, and whether it is one plain SELECT at all.

Two things are observed here that the PostgreSQL parser's tests do not have to observe.
Every rewrite is executed against a real SQLite file rather than only compared as text,
because a variant rendered in one dialect and run by another engine would be a rewrite of a
different statement. And the double-quoted token, which sqlglot reads as an identifier
everywhere and SQLite reads as a string literal wherever it resolves to no column, is
followed through all four places it can appear: refused where the parse would state a sort
key it cannot support, and kept verbatim everywhere else.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from attestql.audit.backend import TableName
from attestql.audit.parse import ORDERING_KEY_PREFIX, StatementRefused
from attestql.audit.sqlite_statements import (
    DIALECT,
    PARSER,
    SQLGLOT_VERSION,
    VALIDATOR_VERSION,
    parse_statement,
)
from attestql.evidence.types import ReplayRule

SCHOOLS = "SELECT name FROM schools"
"""The shape every reading below is a variation of: one table, one column, no bound."""

WIDE_COLUMN = "Free Meal Count (K-12)"
"""A real column name holding spaces and punctuation, which a BIRD SQLite gold has to
double-quote to name at all. The shape ADR-0014's double-quote rule is measured against; the
statements below spell it out rather than interpolate it, so what a reader compares with the
refusal is the text the parser was handed."""


def _file(tmp_path: Path) -> Path:
    """One SQLite file with the two tables every executed rewrite below reads."""
    path = tmp_path / "reading.sqlite"
    connection = sqlite3.connect(path)
    with connection:
        connection.execute(
            f'CREATE TABLE schools (id INTEGER PRIMARY KEY, name TEXT, "{WIDE_COLUMN}" TEXT)'
        )
        connection.executemany(
            "INSERT INTO schools VALUES (?, ?, ?)",
            ((1, "Alder", "30"), (2, "Birch", "200"), (3, "Cedar", "7")),
        )
        connection.execute("CREATE TABLE districts (id INTEGER PRIMARY KEY, name TEXT)")
        connection.executemany("INSERT INTO districts VALUES (?, ?)", ((1, "North"), (2, "South")))
    connection.close()
    return path


def _run(path: Path, sql: str) -> list[tuple[object, ...]]:
    """That statement on that file, as SQLite itself answers it."""
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return [tuple(row) for row in connection.execute(sql).fetchall()]
    finally:
        connection.close()


def test_the_parser_names_itself_by_the_release_and_the_dialect_that_read_the_text() -> None:
    """A record states which validator admitted its statement and a summary states what that
    validator was, because a SQLite statement read by an imitation of SQLite is not the same
    check as one read by SQLite."""
    assert PARSER.validator == VALIDATOR_VERSION
    assert PARSER.json() == {
        "validator": VALIDATOR_VERSION,
        "sqlglot": SQLGLOT_VERSION,
        "dialect": DIALECT,
    }
    assert PARSER.checks == (
        "parses_as_exactly_one_statement",
        "the_one_statement_is_a_select",
        "no_placeholder_without_a_bound_parameter",
    ), "the ambiguous sort key is named rather than judged here; judging it needs a catalogue"


def test_a_statement_that_orders_itself_is_replayed_under_the_ordered_rule() -> None:
    ordered = parse_statement(f"{SCHOOLS} ORDER BY name ASC LIMIT 2")
    unordered = parse_statement(SCHOOLS)

    assert ordered.replay_rule is ReplayRule.R_ORD
    assert unordered.replay_rule is ReplayRule.R_SET
    assert ordered.sort_keys[0].column == "name"
    assert ordered.limit_count == 2
    assert unordered.limit_count is None and not unordered.limit_stated


def test_the_tables_are_read_with_the_schema_the_statement_wrote_and_a_cte_is_not_one() -> None:
    """``main`` is the only schema a file that attached nothing holds, so a qualified name
    and a bare one are two spellings the backend resolves to one table; a name a WITH clause
    defines is not a table at all, and the data behind it is measured through the tables the
    expression itself names."""
    parsed = parse_statement(
        "WITH big AS (SELECT id FROM main.schools) "
        "SELECT d.name FROM districts AS d JOIN big ON big.id = d.id"
    )

    assert parsed.tables == (TableName("", "districts"), TableName("main", "schools"))


def test_the_nulls_of_a_key_that_states_none_are_where_sqlite_puts_them() -> None:
    """SQLite sorts a NULL below every value, so an ascending key puts its nulls first and a
    descending key puts them last. The parse states the placement either way, because a probe
    that reads a bounded result has to be told which it was rather than guess it."""
    ascending = parse_statement(f"{SCHOOLS} ORDER BY name")
    descending = parse_statement(f"{SCHOOLS} ORDER BY name DESC")

    assert (ascending.ordering[0].descending, ascending.ordering[0].nulls) == (False, "first")
    assert (descending.ordering[0].descending, descending.ordering[0].nulls) == (True, "last")


def test_a_written_nulls_placement_wins_over_the_engine_s_own() -> None:
    parsed = parse_statement(f"{SCHOOLS} ORDER BY name ASC NULLS LAST")

    assert parsed.ordering[0].nulls == "last"


def test_the_two_part_bound_sqlite_writes_is_read_as_the_count_and_the_offset() -> None:
    """``LIMIT 3, 2`` is SQLite's own spelling of ``LIMIT 2 OFFSET 3``, which libpg_query
    refuses outright; both halves are read and neither is invented."""
    parsed = parse_statement(f"{SCHOOLS} ORDER BY id LIMIT 3, 2")

    assert (parsed.limit_count, parsed.limit_stated) == (2, True)
    assert (parsed.offset_count, parsed.offset_stated) == (3, True)


def test_a_bound_the_statement_did_not_write_as_a_number_is_not_read_as_one() -> None:
    """Nothing here evaluates a bound: a statement that bounds itself by an expression states
    that it is bounded and states no count, and a probe that reads a count is asking what the
    statement said."""
    parsed = parse_statement(f"{SCHOOLS} ORDER BY id LIMIT 1 + 1")

    assert parsed.limit_stated and parsed.limit_count is None


def test_the_select_list_s_own_aliases_and_the_from_clause_s_are_read_apart() -> None:
    parsed = parse_statement(
        "SELECT s.name AS school, d.name FROM schools AS s JOIN districts AS d ON s.id = d.id"
    )

    assert parsed.output_names == ("school",)
    assert dict(parsed.aliases) == {
        "s": TableName("", "schools"),
        "d": TableName("", "districts"),
    }
    assert not parsed.from_has_subquery


def test_a_subquery_in_from_resolves_no_alias_and_says_so() -> None:
    parsed = parse_statement("SELECT name FROM (SELECT name FROM schools) AS inner_rows")

    assert parsed.from_has_subquery
    assert dict(parsed.aliases) == {}


def test_a_set_operation_is_named_as_one_and_carries_no_select_list_s_distinct() -> None:
    """``UNION`` de-duplicates and is not a select list's DISTINCT: a parse that read the one
    as the other would tell a smell the statement removed rows it never removed."""
    parsed = parse_statement("SELECT name FROM schools UNION SELECT name FROM districts")

    assert parsed.set_operation
    assert not parsed.distinct
    assert parsed.tables == (TableName("", "schools"), TableName("", "districts"))


def test_a_select_list_that_de_duplicates_says_so() -> None:
    assert parse_statement("SELECT DISTINCT name FROM schools").distinct


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA table_info('schools')",
        "ATTACH DATABASE 'other.sqlite' AS other",
        "INSERT INTO schools (name) VALUES ('Deal')",
        "UPDATE schools SET name = 'Deal'",
        "DELETE FROM schools",
        "CREATE TABLE probe (x INTEGER)",
        "DROP TABLE schools",
    ],
)
def test_anything_that_is_not_one_select_is_refused_by_what_it_is(sql: str) -> None:
    """The allowlist is the root of the parse and nothing else: an audit runs one query, and
    what a refusal says is which other thing the text turned out to be."""
    with pytest.raises(StatementRefused, match="not a SELECT"):
        parse_statement(sql)


def test_two_statements_in_one_text_are_refused_before_either_is_read() -> None:
    with pytest.raises(StatementRefused, match="2 statements in one text"):
        parse_statement("SELECT name FROM schools; SELECT name FROM districts")


def test_a_with_clause_before_a_select_is_a_select() -> None:
    parsed = parse_statement("WITH big AS (SELECT id FROM schools) SELECT id FROM big")

    assert parsed.replay_rule is ReplayRule.R_SET
    assert parsed.tables == (TableName("", "schools"),)


def test_a_placeholder_is_refused_because_the_audit_binds_no_parameters() -> None:
    with pytest.raises(StatementRefused, match=r"placeholders \['\?'\]"):
        parse_statement("SELECT name FROM schools WHERE id = ?")


def test_a_question_mark_inside_a_string_is_a_string_and_not_a_placeholder() -> None:
    """Read off the tree and not off the text, which is what a regular expression over the
    raw statement got wrong."""
    parsed = parse_statement("SELECT name FROM schools WHERE name = 'who?'")

    assert parsed.tables == (TableName("", "schools"),)


def test_the_text_the_grammar_cannot_read_at_all_is_refused_with_what_it_met() -> None:
    with pytest.raises(StatementRefused, match="does not parse"):
        parse_statement("SELECT FROM WHERE ORDER")


def test_the_cast_rewrite_is_rendered_as_sqlite_writes_one_and_runs(tmp_path: Path) -> None:
    """The one rewrite the numeric-text smell reruns. ``CAST(x AS REAL)`` is what SQLite
    calls it and what a BIRD SQLite gold writes, and the answer it gives is the ordering over
    numbers that the text ordering was not."""
    path = _file(tmp_path)
    sql = 'SELECT name FROM schools ORDER BY "Free Meal Count (K-12)" DESC LIMIT 1'
    parsed = parse_statement(
        'SELECT name FROM schools ORDER BY schools."Free Meal Count (K-12)" DESC LIMIT 1'
    )
    variant = parsed.with_ordering_key_cast_to_numeric(0)

    assert "CAST(" in variant and "AS REAL)" in variant
    assert _run(path, sql) == [("Cedar",)], "'7' is the largest string"
    assert _run(path, variant) == [("Birch",)], "200 is the largest number"


def test_the_cast_rewrite_refuses_a_key_the_statement_does_not_have() -> None:
    parsed = parse_statement(f"{SCHOOLS} ORDER BY name")

    with pytest.raises(IndexError, match="1 ordering keys"):
        parsed.with_ordering_key_cast_to_numeric(1)


def test_the_unbounded_rewrite_keeps_the_projection_and_adds_the_keys(tmp_path: Path) -> None:
    """What the arbitrary-cut smell reads at the cut: every row the bound left out, the
    columns the statement projected, and the ordering keys beside them under a name the smell
    can tell from the statement's own."""
    path = _file(tmp_path)
    parsed = parse_statement("SELECT name FROM schools ORDER BY id DESC LIMIT 1")
    variant = parsed.without_the_bound_and_projecting_its_keys()

    assert f"{ORDERING_KEY_PREFIX}0" in variant
    assert "LIMIT" not in variant.upper()
    assert _run(path, variant) == [("Cedar", 3), ("Birch", 2), ("Alder", 1)]


@pytest.mark.parametrize(
    ("sql", "named"),
    [
        ("SELECT DISTINCT name FROM schools ORDER BY id LIMIT 2", ("id",)),
        ("SELECT DISTINCT name, id FROM schools ORDER BY id LIMIT 2", ()),
        ("SELECT name FROM schools ORDER BY id LIMIT 2", ()),
        ("SELECT DISTINCT name AS n FROM schools ORDER BY n LIMIT 2", ()),
        ("SELECT DISTINCT name FROM schools ORDER BY 1 LIMIT 2", ()),
    ],
)
def test_a_distinct_statement_names_the_ordering_keys_it_does_not_project(
    sql: str, named: tuple[str, ...]
) -> None:
    """SQLite allows a DISTINCT statement to order by a column its select list does not hold,
    and PostgreSQL refuses one, so this is the engine that has to answer for the shape. An
    alias and an ordinal both resolve to the target they name, so neither is unprojected."""
    assert parse_statement(sql).keys_not_projected_under_distinct == named


def test_projecting_an_unprojected_key_under_distinct_returns_rows_the_statement_did_not(
    tmp_path: Path,
) -> None:
    """Why the smell refuses the shape rather than reading it.

    Adding the key to the select list de-duplicates on the pair instead of on the column, so
    the rewrite returns a row for every value of the key. The statement's own result already
    held every distinct name; the rewrite's extra rows are an artefact of the rewrite, and a
    smell that read them would report a tie at a cut the statement never made.
    """
    path = _file(tmp_path)
    connection = sqlite3.connect(path)
    with connection:
        connection.execute("CREATE TABLE repeated (name TEXT, nine INTEGER)")
        connection.executemany(
            "INSERT INTO repeated VALUES (?, ?)", (("Alder", 1), ("Alder", 2), ("Birch", 3))
        )
    connection.close()
    sql = "SELECT DISTINCT name FROM repeated ORDER BY nine LIMIT 2"
    parsed = parse_statement(sql)

    assert parsed.keys_not_projected_under_distinct == ("nine",)
    assert len(_run(path, sql)) == 2, "the statement's own answer holds every distinct name"
    assert len(_run(path, parsed.without_the_bound_and_projecting_its_keys())) == 3, (
        "the rewrite de-duplicates on the pair and so returns one row per key value"
    )


def test_the_unbounded_rewrite_resolves_an_ordinal_key_to_the_column_it_names(
    tmp_path: Path,
) -> None:
    """An ordinal added to a select list would be the constant and not the column, so it is
    resolved back to the target it names before it is projected."""
    path = _file(tmp_path)
    parsed = parse_statement("SELECT name FROM schools ORDER BY 1 DESC LIMIT 1")

    assert _run(path, parsed.without_the_bound_and_projecting_its_keys()) == [
        ("Cedar", "Cedar"),
        ("Birch", "Birch"),
        ("Alder", "Alder"),
    ]


def test_the_unbounded_rewrite_keeps_distinct_and_the_keys_it_adds_group_with_it(
    tmp_path: Path,
) -> None:
    """Dropping DISTINCT would collapse the very ties this is asked about and answer a
    question about a different statement."""
    path = _file(tmp_path)
    parsed = parse_statement("SELECT DISTINCT name FROM schools ORDER BY name LIMIT 1")
    variant = parsed.without_the_bound_and_projecting_its_keys()

    assert "DISTINCT" in variant
    assert _run(path, variant) == [("Alder", "Alder"), ("Birch", "Birch"), ("Cedar", "Cedar")]


def test_a_backtick_identifier_is_an_identifier_and_runs(tmp_path: Path) -> None:
    """The shape libpg_query refuses on 127 of BIRD dev's golds. sqlglot reads it correctly
    and writes it back double-quoted, which SQLite reads as the same column."""
    path = _file(tmp_path)
    parsed = parse_statement("SELECT `name` FROM `schools` ORDER BY `name` LIMIT 1")

    assert parsed.tables == (TableName("", "schools"),)
    assert parsed.ordering[0].column_reference == ("name",)
    assert _run(path, parsed.without_the_bound_and_projecting_its_keys()) == [
        ("Alder", "Alder"),
        ("Birch", "Birch"),
        ("Cedar", "Cedar"),
    ]


def test_a_double_quoted_column_name_in_the_projection_is_read_and_runs(tmp_path: Path) -> None:
    """BIRD's own shape: a real column whose name holds spaces, which can only be named in
    double quotes. Nothing is read off it here beyond the table, so nothing about it is
    ambiguous, and the statement runs."""
    path = _file(tmp_path)
    sql = 'SELECT "Free Meal Count (K-12)" FROM schools WHERE id = 2'
    parsed = parse_statement(sql)

    assert parsed.tables == (TableName("", "schools"),)
    assert parsed.output_names == (), "a quoted column is not an alias the select list wrote"
    assert _run(path, sql) == [("200",)]


def test_a_double_quoted_ordering_key_the_statement_qualified_is_read_and_runs(
    tmp_path: Path,
) -> None:
    """SQLite allows no string literal after a table qualifier, so a qualified token is a
    column under either reading and the sort key it states is one this parse can support."""
    path = _file(tmp_path)
    sql = 'SELECT name FROM schools ORDER BY schools."Free Meal Count (K-12)" ASC LIMIT 1'
    parsed = parse_statement(sql)

    assert parsed.ordering[0].column_reference == ("schools", WIDE_COLUMN)
    assert _run(path, sql) == [("Birch",)], "'200' is the smallest string"


def test_a_bare_double_quoted_ordering_key_is_named_rather_than_judged() -> None:
    """The one path by which the wrong reading would reach an answer (ADR-0014 point 3). The
    parse cannot tell that token from a string literal without a schema and must not hold one,
    so it names the key and decides nothing; whoever runs the statement resolves it against
    the columns the backend reports, and refuses only a key that names none.

    Both the BIRD shape and a key no column could match are named here. What separates them
    is the catalogue, and the catalogue is not this module's to ask.
    """
    bird_shape = parse_statement(
        'SELECT "Free Meal Count (K-12)" FROM schools ORDER BY "Free Meal Count (K-12)" DESC'
    )
    no_column = parse_statement(f'{SCHOOLS} ORDER BY "a name no column has" DESC')

    assert bird_shape.unresolved_ordering_keys == (WIDE_COLUMN,)
    assert no_column.unresolved_ordering_keys == ("a name no column has",)
    assert bird_shape.replay_rule is ReplayRule.R_ORD


def test_a_qualified_or_backtick_ordering_key_is_never_one_to_resolve() -> None:
    """SQLite allows no string literal after a table qualifier and none in backticks, so a key
    written either way is a column under both readings and there is nothing to ask about."""
    qualified = parse_statement(
        'SELECT name FROM schools ORDER BY schools."Free Meal Count (K-12)" DESC'
    )
    backticked = parse_statement("SELECT name FROM schools ORDER BY `name` DESC")
    plain = parse_statement(f"{SCHOOLS} ORDER BY name DESC")

    assert qualified.unresolved_ordering_keys == ()
    assert backticked.unresolved_ordering_keys == ()
    assert plain.unresolved_ordering_keys == ()


def test_a_double_quoted_ordering_key_inside_a_subquery_is_not_the_statement_s_own() -> None:
    """What is named is the top-level ORDER BY, which is the only one whose keys a record
    states. An ORDER BY inside a subquery states nothing about the answer's order."""
    parsed = parse_statement(
        'SELECT name FROM (SELECT name FROM schools ORDER BY "Free Meal Count (K-12)") '
        "ORDER BY name"
    )

    assert parsed.replay_rule is ReplayRule.R_ORD
    assert parsed.ordering[0].expression == "name"
    assert parsed.unresolved_ordering_keys == ()


def test_a_double_quoted_string_in_a_where_clause_is_kept_and_means_what_sqlite_means(
    tmp_path: Path,
) -> None:
    """sqlglot calls this token a column and SQLite calls it a string, because no column of
    that name is in scope. Nothing is read off the WHERE clause here, and the rewrites write
    the token back exactly as it came, so what the variant means to SQLite is what the
    statement meant: the row where the name equals that string.
    """
    path = _file(tmp_path)
    sql = 'SELECT id FROM schools WHERE name = "Birch" ORDER BY id LIMIT 1'
    parsed = parse_statement(sql)
    variant = parsed.without_the_bound_and_projecting_its_keys()

    assert '"Birch"' in variant
    assert _run(path, sql) == [(2,)]
    assert _run(path, variant) == [(2, 2)]
