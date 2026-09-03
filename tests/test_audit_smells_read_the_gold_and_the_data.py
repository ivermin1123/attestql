"""The four smells, each on a gold that fires it, one that is quiet, and one it skips.

No server: every rerun a smell makes is scripted, so what these tests observe is the
smell's own decision and not a database's. The variant statements are built by the parse
itself and scripted under exactly the text it produces, which is also how a test would
notice a variant that stopped being the statement it claims to rerun.

The distinction the measurement of 2026-09-02 turned into a rule is here twice: tied rows
at a cut that project the same answer are not a hazard and do not fire, and tied rows
that project different answers are and do.

Where the nulls of an ordering key go is PostgreSQL's rule and not this file's: a written
NULLS FIRST or NULLS LAST decides it, and left to the default a null sorts above every
value, so a descending key is null-first and an ascending one is not. The four cases are
below, each saying which of the two decided it.
"""

from __future__ import annotations

from decimal import Decimal

from attestql.audit.backend import ShuffledCopies, TableName, TextCensus
from attestql.audit.smells import (
    ARBITRARY_CUT,
    DIRECTION_AGAINST_QUESTION,
    FLOAT_AGGREGATE_ORDER,
    NOT_A_FUNCTION_OF_THE_DATA,
    NUMERIC_TEXT,
    ORDERING_OVER_NUMERIC_TEXT,
    QuestionText,
    Smell,
    SmellSettings,
    all_smells,
    arbitrary_cut,
    direction_against_question,
    not_a_function_of_the_data,
    ordering_over_numeric_text,
    smells_json,
)
from attestql.audit.statements import parse_statement
from tests.audit_fakes import DESCRIPTOR, FakeBackend, fake_result

SETTINGS = SmellSettings(serialization=DESCRIPTOR, statement_timeout_seconds=30)

PLAYERS = TableName("", "players")
RESULTS = TableName("", "results")
DRIVERS = TableName("", "drivers")
TOTALLED = TableName("", "t")
"""The four tables these statements name, as they name them: no gold here writes a schema,
so a copy of each is what a rerun reads and the catalogue is asked under the same names."""

SHUFFLED = ShuffledCopies(
    copied=(PLAYERS, RESULTS, DRIVERS, TOTALLED),
    skipped={},
    unreachable={},
    seed="1",
    row_limit=300_000,
)

NATIONALITY = (("nationality", "text"),)
NAME = (("name", "text"),)
NAME_AND_SCORE = (("name", "text"), ("attestql_ordering_key_0", "int8"))
TOTAL_FLOAT = (("sum", "float8"),)
TOTAL_INT = (("sum", "int8"),)

FASTEST_LAP = (
    "SELECT t1.nationality FROM drivers AS t1 JOIN results AS t2 "
    "ON t1.driverid = t2.driverid ORDER BY t2.fastestlapspeed DESC LIMIT 1"
)
BY_LAPS = (
    "SELECT t1.nationality FROM drivers AS t1 JOIN results AS t2 "
    "ON t1.driverid = t2.driverid ORDER BY t2.laps DESC LIMIT 1"
)

COLUMN_TYPES = {
    RESULTS: {"fastestlapspeed": "text", "laps": "bigint", "driverid": "bigint"},
    DRIVERS: {"driverid": "bigint", "nationality": "text"},
}

ALL_NUMERIC = TextCensus(
    rows=23_179, nulls=18_185, empty_strings=0, non_numeric=0, pattern=NUMERIC_TEXT
)
SOME_WORDS = TextCensus(
    rows=23_179, nulls=18_185, empty_strings=0, non_numeric=12, pattern=NUMERIC_TEXT
)


def _cast_variant(sql: str) -> str:
    return parse_statement(sql).with_ordering_key_cast_to_numeric(0)


def _unbounded(sql: str) -> str:
    return parse_statement(sql).without_the_bound_and_projecting_its_keys()


def _smell(smell: Smell) -> tuple[str, bool, bool]:
    return smell.name, smell.fired, smell.applicable


# ordering-over-numeric-text


def test_ordering_over_numeric_text_fires_when_the_numeric_order_answers_otherwise() -> None:
    cast = _cast_variant(FASTEST_LAP)
    backend = FakeBackend(
        {
            FASTEST_LAP: fake_result(NATIONALITY, (("Italian",),)),
            cast: fake_result(NATIONALITY, (("Brazilian",),)),
        },
        column_types=COLUMN_TYPES,
        censuses={(RESULTS, "fastestlapspeed"): ALL_NUMERIC},
    )
    parsed = parse_statement(FASTEST_LAP)
    found = ordering_over_numeric_text(
        parsed,
        backend,
        backend.execute(FASTEST_LAP, statement_timeout_seconds=30),
        settings=SETTINGS,
    )
    assert _smell(found) == (ORDERING_OVER_NUMERIC_TEXT, True, True)
    assert found.counterexample_rows == (("Italian",),)
    assert found.evidence["heuristic"] is True
    assert "sorting 9.5 above 10" in str(found.evidence["means"])
    key = found.evidence["keys"][0]
    assert key["column"] == "results.fastestlapspeed"
    assert key["census"]["non_numeric"] == 0
    assert key["verdict"] == "not_equal"
    assert key["cast_result"]["rows"][0][0]["value"] == "Brazilian"
    assert backend.census_calls == [(RESULTS, "fastestlapspeed", NUMERIC_TEXT)]


def test_ordering_over_numeric_text_is_quiet_when_the_numeric_order_agrees() -> None:
    cast = _cast_variant(FASTEST_LAP)
    same = fake_result(NATIONALITY, (("Italian",),))
    backend = FakeBackend(
        {FASTEST_LAP: same, cast: same},
        column_types=COLUMN_TYPES,
        censuses={(RESULTS, "fastestlapspeed"): ALL_NUMERIC},
    )
    found = ordering_over_numeric_text(
        parse_statement(FASTEST_LAP), backend, same, settings=SETTINGS
    )
    assert _smell(found) == (ORDERING_OVER_NUMERIC_TEXT, False, True)
    assert found.counterexample_rows == ()


def test_ordering_over_numeric_text_is_quiet_when_the_column_holds_a_word() -> None:
    """A column that is not all numbers is ordered lexicographically on purpose."""
    baseline = fake_result(NATIONALITY, (("Italian",),))
    backend = FakeBackend(
        {FASTEST_LAP: baseline},
        column_types=COLUMN_TYPES,
        censuses={(RESULTS, "fastestlapspeed"): SOME_WORDS},
    )
    found = ordering_over_numeric_text(
        parse_statement(FASTEST_LAP), backend, baseline, settings=SETTINGS
    )
    assert _smell(found) == (ORDERING_OVER_NUMERIC_TEXT, False, True)
    assert found.evidence["keys"][0]["every_value_is_numeric"] is False
    assert backend.executed == [], "the cast variant ran on a column holding words"


def test_ordering_over_numeric_text_does_not_apply_to_a_key_that_is_not_text() -> None:
    baseline = fake_result(NATIONALITY, (("Italian",),))
    backend = FakeBackend({BY_LAPS: baseline}, column_types=COLUMN_TYPES)
    found = ordering_over_numeric_text(
        parse_statement(BY_LAPS), backend, baseline, settings=SETTINGS
    )
    assert _smell(found) == (ORDERING_OVER_NUMERIC_TEXT, False, False)
    assert found.evidence["keys"][0]["not_applicable"] == "the column is not declared as text"


def test_the_key_is_resolved_against_the_table_the_statement_named() -> None:
    """Two tables called ``y`` in two schemas hold a ``weight`` of two declared types.

    The gold names the one whose weight is a number, so there is nothing here to read as a
    lexicographic ordering over numbers. Resolving the key by the relation alone found the
    other table, called its bigint column text, and censused rows the gold never read.
    """
    sql = 'SELECT label FROM "Quoted".y ORDER BY weight ASC'
    baseline = fake_result((("label", "text"),), (("a",),))
    backend = FakeBackend(
        {sql: baseline},
        column_types={
            TableName("Quoted", "y"): {"label": "text", "weight": "bigint"},
            TableName("", "y"): {"label": "text", "weight": "text"},
        },
    )
    found = ordering_over_numeric_text(parse_statement(sql), backend, baseline, settings=SETTINGS)

    key = found.evidence["keys"][0]
    assert _smell(found) == (ORDERING_OVER_NUMERIC_TEXT, False, False)
    assert key["column"] == "Quoted.y.weight"
    assert key["declared_type"] == "bigint"
    assert key["not_applicable"] == "the column is not declared as text"
    assert backend.census_calls == [], "a column of another schema's table was censused"


def test_ordering_over_numeric_text_does_not_apply_without_an_order_by() -> None:
    sql = "SELECT name FROM players"
    baseline = fake_result(NAME, (("a",),))
    found = ordering_over_numeric_text(
        parse_statement(sql), FakeBackend({sql: baseline}), baseline, settings=SETTINGS
    )
    assert _smell(found) == (ORDERING_OVER_NUMERIC_TEXT, False, False)
    assert found.evidence["reason"] == "the statement states no top level ORDER BY"


# arbitrary-cut


TOP_TWO = "SELECT name FROM players ORDER BY score DESC LIMIT 2"
BOTTOM_TWO = "SELECT name FROM players ORDER BY score LIMIT 2"
NULLS_FIRST_TWO = "SELECT name FROM players ORDER BY score NULLS FIRST LIMIT 2"
TWO_ROWS = "SELECT name FROM players LIMIT 2"


def _cut_backend(rows: tuple[tuple[object, ...], ...], sql: str = TOP_TWO) -> FakeBackend:
    return FakeBackend(
        {
            sql: fake_result(NAME, (("a",), ("b",))),
            _unbounded(sql): fake_result(NAME_AND_SCORE, rows),
        }
    )


def test_an_arbitrary_cut_fires_when_the_tied_rows_project_different_answers() -> None:
    rows = (("a", 10), ("b", 5), ("c", 5), ("d", 1))
    backend = _cut_backend(rows)
    found = arbitrary_cut(
        parse_statement(TOP_TWO),
        backend,
        backend.execute(TOP_TWO, statement_timeout_seconds=30),
        settings=SETTINGS,
    )
    assert _smell(found) == (ARBITRARY_CUT, True, True)
    assert found.evidence["case"] == "tie-at-the-cut"
    assert found.evidence["tied_at_the_cut"]["positions"] == [1, 2]
    assert found.evidence["tied_at_the_cut"]["distinct_projected_answers"] == 2
    assert found.counterexample_rows == (("b", 5), ("c", 5))


def test_an_arbitrary_cut_is_quiet_when_the_tied_rows_project_the_same_answer() -> None:
    """The rule the measurement of 2026-09-02 adopted: a tie is not a hazard by itself."""
    rows = (("a", 10), ("b", 5), ("b", 5), ("d", 1))
    backend = _cut_backend(rows)
    found = arbitrary_cut(
        parse_statement(TOP_TWO),
        backend,
        backend.execute(TOP_TWO, statement_timeout_seconds=30),
        settings=SETTINGS,
    )
    assert _smell(found) == (ARBITRARY_CUT, False, True)
    assert found.evidence["case"] is None
    assert found.evidence["tied_at_the_cut"]["distinct_projected_answers"] == 1


def test_an_arbitrary_cut_keeps_distinct_when_it_removes_the_bound() -> None:
    distinct = "SELECT DISTINCT name, score FROM players ORDER BY score DESC LIMIT 2"
    assert "DISTINCT" in _unbounded(distinct)
    assert "LIMIT" not in _unbounded(distinct)


def _cut(sql: str, rows: tuple[tuple[object, ...], ...]) -> Smell:
    backend = _cut_backend(rows, sql)
    return arbitrary_cut(
        parse_statement(sql),
        backend,
        backend.execute(sql, statement_timeout_seconds=30),
        settings=SETTINGS,
    )


def test_an_arbitrary_cut_fires_when_a_written_nulls_first_key_returns_a_null() -> None:
    """PostgreSQL puts the nulls of an ascending key last, so the NULLS FIRST written into
    this statement is what brings one to the top and into the bounded result."""
    found = _cut(NULLS_FIRST_TWO, (("a", None), ("b", 1), ("c", 2)))

    assert _smell(found) == (ARBITRARY_CUT, True, True)
    assert found.evidence["case"] == "null-first"
    assert found.evidence["ordering_keys"][0]["nulls"] == "first"
    assert found.evidence["ordering_keys"][0]["nulls_first_in_effect"] is True
    assert found.counterexample_rows == (("a", None),)


def test_an_arbitrary_cut_fires_when_a_descending_key_keeps_the_nulls_first() -> None:
    """Nothing is written, so the placement is PostgreSQL's: a null sorts above every value
    under DESC, and the bound returns one."""
    found = _cut(TOP_TWO, (("a", None), ("b", 2), ("c", 1)))

    assert _smell(found) == (ARBITRARY_CUT, True, True)
    assert found.evidence["case"] == "null-first"
    assert found.evidence["ordering_keys"][0]["nulls"] == "default"
    assert found.evidence["ordering_keys"][0]["nulls_first_in_effect"] is True
    assert found.counterexample_rows == (("a", None),)


def test_an_arbitrary_cut_is_quiet_when_an_ascending_key_keeps_the_nulls_last() -> None:
    """Nothing is written here either, and PostgreSQL puts the nulls of an ascending key
    last: the two rows the bound returns are values, so there is no null-first cut."""
    found = _cut(BOTTOM_TWO, (("a", 1), ("b", 2), ("c", None)))

    assert _smell(found) == (ARBITRARY_CUT, False, True)
    assert found.evidence["case"] is None
    assert found.evidence["ordering_keys"][0]["nulls"] == "default"
    assert found.evidence["ordering_keys"][0]["nulls_first_in_effect"] is False


def test_an_arbitrary_cut_is_quiet_when_the_nulls_go_last() -> None:
    """A written NULLS LAST wins over PostgreSQL's own placement, which under DESC would
    have been first."""
    sql = "SELECT name FROM players ORDER BY score DESC NULLS LAST LIMIT 2"
    found = _cut(sql, (("a", 10), ("b", 5), ("c", 1), ("d", None)))

    assert _smell(found) == (ARBITRARY_CUT, False, True)
    assert found.evidence["ordering_keys"][0]["nulls"] == "last"
    assert found.evidence["ordering_keys"][0]["nulls_first_in_effect"] is False


def test_an_unordered_cut_fires_when_the_shuffle_returns_other_rows() -> None:
    backend = FakeBackend(
        {TWO_ROWS: fake_result(NAME, (("a",), ("b",)))},
        shuffled_results={TWO_ROWS: fake_result(NAME, (("c",), ("d",)))},
    )
    found = arbitrary_cut(
        parse_statement(TWO_ROWS),
        backend,
        backend.execute(TWO_ROWS, statement_timeout_seconds=30),
        settings=SETTINGS,
        shuffled=SHUFFLED,
    )
    assert _smell(found) == (ARBITRARY_CUT, True, True)
    assert found.evidence["case"] == "no-ordering"
    assert found.evidence["verdict"] == "not_equal"
    assert found.counterexample_rows == (("c",), ("d",))


def test_an_unordered_cut_is_quiet_when_the_shuffle_returns_the_same_rows() -> None:
    backend = FakeBackend({TWO_ROWS: fake_result(NAME, (("a",), ("b",)))})
    found = arbitrary_cut(
        parse_statement(TWO_ROWS),
        backend,
        backend.execute(TWO_ROWS, statement_timeout_seconds=30),
        settings=SETTINGS,
        shuffled=SHUFFLED,
    )
    assert _smell(found) == (ARBITRARY_CUT, False, True)


def test_an_unordered_cut_with_nothing_to_rerun_against_was_not_asked_at_all() -> None:
    """Not applicable and not quiet: the measurement that answers this case was not taken,
    and the reason the caller had is what the evidence states."""
    backend = FakeBackend({TWO_ROWS: fake_result(NAME, (("a",), ("b",)))})
    missing = "the scratch schema attestql_scratch does not exist and this tool creates none"
    found = arbitrary_cut(
        parse_statement(TWO_ROWS),
        backend,
        backend.execute(TWO_ROWS, statement_timeout_seconds=30),
        settings=SETTINGS,
        no_shuffle=missing,
    )
    assert _smell(found) == (ARBITRARY_CUT, False, False)
    assert str(found.evidence["reason"]) == f"{missing}, so the bound was not tested"
    assert backend.executed_shuffled == []


def test_an_unordered_cut_with_no_reason_given_still_says_there_were_no_copies() -> None:
    backend = FakeBackend({TWO_ROWS: fake_result(NAME, (("a",), ("b",)))})
    found = arbitrary_cut(
        parse_statement(TWO_ROWS),
        backend,
        backend.execute(TWO_ROWS, statement_timeout_seconds=30),
        settings=SETTINGS,
    )
    assert _smell(found) == (ARBITRARY_CUT, False, False)
    assert "no shuffled copies" in str(found.evidence["reason"])


def test_a_gold_that_was_rerun_against_nothing_is_not_a_gold_that_survived_a_rerun() -> None:
    """No copies and no plan variant: nothing was rerun, so the fourth smell was not asked."""
    backend = FakeBackend({TOTAL: fake_result(TOTAL_INT, ((3,),))})
    unwritable = "the role auditor cannot create in the scratch schema attestql_scratch"
    found = not_a_function_of_the_data(
        parse_statement(TOTAL),
        backend,
        backend.execute(TOTAL, statement_timeout_seconds=30),
        settings=SETTINGS,
        no_shuffle=unwritable,
    )
    assert _smell(found) == (NOT_A_FUNCTION_OF_THE_DATA, False, False)
    assert found.evidence["shuffled_copies"] == {"run": False, "reason": unwritable}
    assert backend.executed_shuffled == []


def test_a_statement_with_no_limit_has_no_cut_to_be_arbitrary() -> None:
    sql = "SELECT name FROM players ORDER BY score DESC"
    baseline = fake_result(NAME, (("a",),))
    found = arbitrary_cut(
        parse_statement(sql), FakeBackend({sql: baseline}), baseline, settings=SETTINGS
    )
    assert _smell(found) == (ARBITRARY_CUT, False, False)
    assert found.evidence["reason"] == "the statement states no LIMIT"


# not-a-function-of-the-data


TOTAL = "SELECT sum(points) FROM t"


def test_a_result_that_changes_with_the_row_order_fires() -> None:
    backend = FakeBackend(
        {TOTAL: fake_result(TOTAL_INT, ((3,),))},
        shuffled_results={TOTAL: fake_result(TOTAL_INT, ((4,),))},
    )
    found = not_a_function_of_the_data(
        parse_statement(TOTAL),
        backend,
        backend.execute(TOTAL, statement_timeout_seconds=30),
        settings=SETTINGS,
        shuffled=SHUFFLED,
    )
    assert _smell(found) == (NOT_A_FUNCTION_OF_THE_DATA, True, True)
    assert found.evidence["shuffled_copies"]["differs"] is True
    assert found.evidence["plan_variant"]["run"] is False
    assert found.counterexample_rows == ((4,),)


def test_a_result_that_survives_the_shuffle_is_quiet() -> None:
    backend = FakeBackend({TOTAL: fake_result(TOTAL_INT, ((3,),))})
    found = not_a_function_of_the_data(
        parse_statement(TOTAL),
        backend,
        backend.execute(TOTAL, statement_timeout_seconds=30),
        settings=SETTINGS,
        shuffled=SHUFFLED,
    )
    assert _smell(found) == (NOT_A_FUNCTION_OF_THE_DATA, False, True)
    assert found.evidence["shuffled_copies"]["verdict"] == "equal"


def test_a_float_that_only_differs_in_its_last_digits_is_reported_as_summation_order() -> None:
    backend = FakeBackend(
        {TOTAL: fake_result(TOTAL_FLOAT, ((Decimal("1.5000000001"),),))},
        shuffled_results={TOTAL: fake_result(TOTAL_FLOAT, ((Decimal("1.5000000002"),),))},
    )
    found = not_a_function_of_the_data(
        parse_statement(TOTAL),
        backend,
        backend.execute(TOTAL, statement_timeout_seconds=30),
        settings=SETTINGS,
        shuffled=SHUFFLED,
    )
    assert _smell(found) == (FLOAT_AGGREGATE_ORDER, True, True)
    assert found.evidence["float_cells"][0]["pg_type"] == "float8"
    assert found.evidence["float_cells"][0]["baseline"] == "1.5000000001"
    assert found.evidence["significant_digits"] == 6


def test_a_float_that_differs_in_the_digits_that_were_compared_keeps_the_other_name() -> None:
    backend = FakeBackend(
        {TOTAL: fake_result(TOTAL_FLOAT, ((Decimal("1.5"),),))},
        shuffled_results={TOTAL: fake_result(TOTAL_FLOAT, ((Decimal("2.5"),),))},
    )
    found = not_a_function_of_the_data(
        parse_statement(TOTAL),
        backend,
        backend.execute(TOTAL, statement_timeout_seconds=30),
        settings=SETTINGS,
        shuffled=SHUFFLED,
    )
    assert _smell(found) == (NOT_A_FUNCTION_OF_THE_DATA, True, True)
    assert "float_cells" not in found.evidence


def test_the_plan_variant_runs_only_when_it_was_asked_for() -> None:
    backend = FakeBackend(
        {TOTAL: fake_result(TOTAL_INT, ((3,),))},
        plan_results={TOTAL: fake_result(TOTAL_INT, ((9,),))},
    )
    settings = SmellSettings(
        serialization=DESCRIPTOR, statement_timeout_seconds=30, plan_variant=True
    )
    found = not_a_function_of_the_data(
        parse_statement(TOTAL),
        backend,
        backend.execute(TOTAL, statement_timeout_seconds=30),
        settings=settings,
        shuffled=SHUFFLED,
    )
    assert _smell(found) == (NOT_A_FUNCTION_OF_THE_DATA, True, True)
    assert found.evidence["plan_variant"]["differs"] is True
    assert backend.executed_plan_variant == [(TOTAL, 30)]


def test_the_shuffle_evidence_names_the_tables_it_did_not_copy() -> None:
    backend = FakeBackend({TOTAL: fake_result(TOTAL_INT, ((3,),))})
    shuffled = ShuffledCopies(
        copied=(), skipped={TOTALLED: 4_000_000}, unreachable={}, seed="1", row_limit=10
    )
    found = not_a_function_of_the_data(
        parse_statement(TOTAL),
        backend,
        backend.execute(TOTAL, statement_timeout_seconds=30),
        settings=SETTINGS,
        shuffled=shuffled,
    )
    assert found.evidence["shuffle"]["tables_not_shuffled"] == ["t"]
    assert found.evidence["shuffle"]["tables_skipped_for_size"] == {"t": 4_000_000}


def test_the_shuffle_evidence_names_a_table_no_copy_could_be_reached_for() -> None:
    """A statement that qualified its table reads that table however the copies were made,
    so the rerun covered nothing of it and the evidence says so with the reason. Reported
    the way a table too large to copy is reported, because a reader is being told the same
    kind of thing: this part of the data did not move."""
    qualified = "SELECT sum(x) FROM public.t"
    backend = FakeBackend({qualified: fake_result(TOTAL_INT, ((3,),))})
    shuffled = ShuffledCopies(
        copied=(),
        skipped={},
        unreachable={TableName("public", "t"): "the statement names this table's schema"},
        seed="1",
        row_limit=10,
    )
    found = not_a_function_of_the_data(
        parse_statement(qualified),
        backend,
        backend.execute(qualified, statement_timeout_seconds=30),
        settings=SETTINGS,
        shuffled=shuffled,
    )
    shuffle = found.evidence["shuffle"]

    assert shuffle["tables_not_shuffled"] == ["public.t"]
    assert shuffle["tables_not_reached_by_a_copy"] == {
        "public.t": "the statement names this table's schema"
    }
    assert _smell(found) == (NOT_A_FUNCTION_OF_THE_DATA, False, True)


# direction-against-question


HIGHEST = "What is the nationality of the driver with the highest speed?"
ASCENDING = "SELECT name FROM players ORDER BY score ASC LIMIT 1"
DESCENDING = "SELECT name FROM players ORDER BY score DESC LIMIT 1"


def test_the_direction_smell_fires_on_a_maximum_asked_for_in_ascending_order() -> None:
    baseline = fake_result(NAME, (("a",),))
    found = direction_against_question(
        parse_statement(ASCENDING),
        FakeBackend({ASCENDING: baseline}),
        baseline,
        settings=SETTINGS,
        question=QuestionText(HIGHEST),
    )
    assert _smell(found) == (DIRECTION_AGAINST_QUESTION, True, True)
    assert found.evidence["maximum_intent_words"] == ["highest"]
    assert found.evidence["order_by"] == "score ASC"
    assert found.evidence["contradiction"] == "maximum intent with an ascending first key"


def test_the_direction_smell_is_quiet_when_the_statement_orders_the_way_it_was_asked() -> None:
    baseline = fake_result(NAME, (("a",),))
    found = direction_against_question(
        parse_statement(DESCENDING),
        FakeBackend({DESCENDING: baseline}),
        baseline,
        settings=SETTINGS,
        question=QuestionText(HIGHEST),
    )
    assert _smell(found) == (DIRECTION_AGAINST_QUESTION, False, True)
    assert found.evidence["contradiction"] is None


def test_the_direction_smell_does_not_apply_without_a_bounded_ordering() -> None:
    sql = "SELECT name FROM players ORDER BY score ASC"
    baseline = fake_result(NAME, (("a",),))
    found = direction_against_question(
        parse_statement(sql),
        FakeBackend({sql: baseline}),
        baseline,
        settings=SETTINGS,
        question=QuestionText(HIGHEST),
    )
    assert _smell(found) == (DIRECTION_AGAINST_QUESTION, False, False)


# the set of them


def _all_smells_backend() -> FakeBackend:
    """A backend that answers the gold, and the unbounded rerun the cut smell makes."""
    return FakeBackend(
        {
            ASCENDING: fake_result(NAME, (("a",),)),
            _unbounded(ASCENDING): fake_result(NAME_AND_SCORE, (("a", 1), ("b", 2))),
        },
        column_types={PLAYERS: {"name": "text", "score": "bigint"}},
    )


def test_the_experimental_smell_runs_only_when_it_was_asked_for() -> None:
    backend = _all_smells_backend()
    parsed = parse_statement(ASCENDING)
    baseline = backend.execute(ASCENDING, statement_timeout_seconds=30)
    quiet = all_smells(parsed, backend, baseline, settings=SETTINGS, question=QuestionText(HIGHEST))
    assert [smell.name for smell in quiet] == [
        ORDERING_OVER_NUMERIC_TEXT,
        ARBITRARY_CUT,
        NOT_A_FUNCTION_OF_THE_DATA,
    ]
    asked = all_smells(
        parsed,
        backend,
        baseline,
        settings=SmellSettings(
            serialization=DESCRIPTOR, statement_timeout_seconds=30, experimental_s2=True
        ),
        question=QuestionText(HIGHEST),
    )
    assert [smell.name for smell in asked][-1] == DIRECTION_AGAINST_QUESTION


def test_every_smell_says_that_it_is_a_heuristic_and_what_it_would_mean() -> None:
    backend = _all_smells_backend()
    found = all_smells(
        parse_statement(ASCENDING),
        backend,
        backend.execute(ASCENDING, statement_timeout_seconds=30),
        settings=SmellSettings(
            serialization=DESCRIPTOR, statement_timeout_seconds=30, experimental_s2=True
        ),
        question=QuestionText(HIGHEST),
    )
    assert all(smell.evidence["heuristic"] is True for smell in found)
    assert all(str(smell.evidence["means"]).strip() for smell in found)
    document = smells_json(found)
    assert "heuristic" in str(document["reading"])
    assert [entry["name"] for entry in document["smells"]] == [smell.name for smell in found]
