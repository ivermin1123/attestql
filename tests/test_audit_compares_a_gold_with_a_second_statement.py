"""Two statements, one database, one verdict, and the record behind each side.

No server: the backend is scripted, so what these tests observe is the audit's own
decisions. The rule is the gold's; the ordering both records are recorded under is the
gold's; the second statement's own ordering is data beside the verdict rather than a
reason for one. NOT_EQUAL never says which statement is wrong and the document says so.

The two cases that separate this from the benchmark's own evaluator are here: rows that
differ only in multiplicity, and rows that differ only in order. BIRD's ``set(predicted)
== set(gold)`` calls both of them equal, and the counterexample records that it does.

The case where this tool must not separate itself from the benchmark is here too: a
prediction that names its columns differently. BIRD compares result tuples by position and
never sees a name, so calling that pair NOT_EQUAL would be this tool inventing a defect.
The names go into the counterexample instead.

The mechanism of a NOT_EQUAL is tested class by class on two results and nothing else,
because that is all it is read off: one class per test, one test for two classes holding at
once, and one for a disagreement that is none of them and says so.

The second published reading, ``test_suite_ex``, is tested rule by rule against the same
kind of results, because what is being asserted is that this is that evaluator's rule and
not this tool's: what it counts, what it forgives, and what its own reading of the gold's
text turns on.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

# ``test_suite_ex`` is reached through its module rather than imported by name: pytest
# collects every module-level name beginning with ``test`` in a test file, and a function
# imported into one is collected the same as a function written in it.
from attestql.audit import compare
from attestql.audit.compare import (
    COUNTEREXAMPLE_FILE,
    GOLD_RECORD_FILE,
    MECHANISM_MULTIPLICITY,
    MECHANISM_ORDER,
    MECHANISM_OTHER,
    MECHANISM_TRUNCATION,
    MECHANISM_TYPE,
    PROJECTION_NAMES_READING,
    SECOND_RECORD_FILE,
    TEST_SUITE_EX_METHOD,
    TEST_SUITE_EX_SOURCE,
    VERDICT_READING,
    Comparison,
    bird_ex,
    compare_statements,
    counterexample_json,
    mechanism,
    write_comparison,
)
from attestql.audit.statements import StatementRefused, parse_statement
from attestql.evidence.replay import ComparabilityResult, compare_r_ord, compare_r_set
from attestql.evidence.types import (
    ENGINE_POSTGRESQL,
    FixtureDigest,
    QuestionMetadata,
    ReplayRule,
    SortKey,
)
from tests.audit_fakes import (
    DESCRIPTOR,
    IDENTITY,
    PREDICTIONS_SOURCE,
    QUESTIONS_SOURCE,
    ROLE,
    SETTINGS,
    FakeBackend,
    fake_result,
)

QUESTION = QuestionMetadata(
    question_id="q207",
    question_set="bird_minidev_postgresql",
    question_text="Which elements are in a double bond?",
    evidence_text="double bond refers to bond_type = '='",
)
QUESTION_SET_VERSION = "sha256:question-file-under-test"
DATA_AS_OF = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

GOLD_SET = "SELECT element FROM atom"
SECOND_SET = "SELECT DISTINCT element FROM atom"
GOLD_ORD = "SELECT speed FROM team_attributes ORDER BY speed ASC NULLS FIRST LIMIT 3"
SECOND_ORD = "SELECT speed FROM team_attributes ORDER BY speed DESC NULLS LAST LIMIT 3"

ELEMENT = (("element", "text"),)
MEASURE = (("element", "float8"),)
SPEED = (("speed", "int8"),)

SECOND_ALIASED = "SELECT element AS symbol FROM atom"
SYMBOL = (("symbol", "text"),)

GOLD_AVERAGE = "SELECT avg(speed) FROM team_attributes"
SECOND_AVERAGE = "SELECT sum(speed) / count(*) FROM team_attributes"
AVERAGE_FLOAT8 = (("average", "float8"),)
AVERAGE_NUMERIC = (("average", "numeric"),)


def _compare(
    backend: FakeBackend,
    directory: Path,
    *,
    gold_sql: str,
    second_sql: str,
    statement_timeout_seconds: int = 30,
) -> Comparison:
    return compare_statements(
        question=QUESTION,
        question_set_version=QUESTION_SET_VERSION,
        gold_parsed=parse_statement(gold_sql),
        gold_source=QUESTIONS_SOURCE,
        second_parsed=parse_statement(second_sql),
        second_source=PREDICTIONS_SOURCE,
        backend=backend,
        serialization=DESCRIPTOR,
        session_settings=backend.session_settings(),
        run_id="run-under-test",
        directory=directory,
        data_as_of=DATA_AS_OF,
        statement_timeout_seconds=statement_timeout_seconds,
    )


def test_two_statements_with_the_same_rows_agree(tmp_path: Path) -> None:
    rows = (("c",), ("o",), ("n",))
    backend = FakeBackend(
        {GOLD_SET: fake_result(ELEMENT, rows), SECOND_SET: fake_result(ELEMENT, rows)},
        row_counts={"atom": 3},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=SECOND_SET)
    assert comparison.replay_rule is ReplayRule.R_SET
    assert comparison.verdict.result is ComparabilityResult.EQUAL
    assert comparison.verdict.mismatched == ()
    assert comparison.mechanism is None, "two answers that agree have no disagreement to explain"
    assert comparison.gold_result_hash == comparison.second_result_hash
    assert comparison.differing_rows.only_left_total == 0
    assert comparison.differing_rows.only_right_total == 0
    assert comparison.bird_ex.value == 1


def test_two_statements_returning_the_same_nan_agree_and_show_no_difference(
    tmp_path: Path,
) -> None:
    """A NaN is one value here, so two results holding one are equal and neither side holds a
    row the other does not.

    Both halves were broken until 2026-09-11 and for different reasons. Hashing the result
    refused a non-finite value, so an EQUAL verdict was overwritten by an error; and the
    multiset behind the row difference keyed each value with its tag itself rather than through
    the shared keying, so two NaNs counted as two values and a row was reported as differing on
    each side of results that are the same.
    """
    rows = ((Decimal("NaN"),), (Decimal("1.5"),))
    backend = FakeBackend(
        {GOLD_SET: fake_result(MEASURE, rows), SECOND_SET: fake_result(MEASURE, rows)},
        row_counts={"atom": 2},
    )

    comparison = _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=SECOND_SET)

    assert comparison.replay_rule is ReplayRule.R_SET
    assert comparison.verdict.result is ComparabilityResult.EQUAL
    assert comparison.gold_result_hash == comparison.second_result_hash
    assert comparison.differing_rows.only_left_total == 0
    assert comparison.differing_rows.only_right_total == 0


def test_a_prediction_that_renames_a_column_gives_the_same_answer(tmp_path: Path) -> None:
    """The names are evidence and not a verdict: they are written beside it, not under it."""
    rows = (("c",), ("o",), ("n",))
    backend = FakeBackend(
        {GOLD_SET: fake_result(ELEMENT, rows), SECOND_ALIASED: fake_result(SYMBOL, rows)},
        row_counts={"atom": 3},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=SECOND_ALIASED)
    note = counterexample_json(comparison)["projection_names_differ"]

    assert comparison.verdict.result is ComparabilityResult.EQUAL
    assert comparison.bird_ex.value == 1
    assert note["gold"] == ["element"]
    assert note["second"] == ["symbol"]
    assert note["reading"] == PROJECTION_NAMES_READING
    # The names are part of the canonical rendering, so the hashes differ where the verdict
    # does not. The note is what tells a reader that before they wonder about it.
    assert comparison.gold_result_hash != comparison.second_result_hash


def test_a_counterexample_says_nothing_about_names_the_two_statements_agree_on(
    tmp_path: Path,
) -> None:
    """A field on every document is a field a reader stops seeing."""
    rows = (("c",), ("o",))
    backend = FakeBackend(
        {GOLD_SET: fake_result(ELEMENT, rows), SECOND_SET: fake_result(ELEMENT, rows)},
        row_counts={"atom": 2},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=SECOND_SET)

    assert "projection_names_differ" not in counterexample_json(comparison)


def test_rows_that_differ_only_in_multiplicity_are_not_equal_and_bird_says_they_are(
    tmp_path: Path,
) -> None:
    """The F1 case: EX is 1 on these two results and the typed multiset is not."""
    gold_rows = (("c",), ("c",), ("o",))
    second_rows = (("c",), ("o",))
    backend = FakeBackend(
        {
            GOLD_SET: fake_result(ELEMENT, gold_rows),
            SECOND_SET: fake_result(ELEMENT, second_rows),
        },
        row_counts={"atom": 3},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=SECOND_SET)
    assert comparison.verdict.result is ComparabilityResult.NOT_EQUAL
    assert comparison.verdict.mismatched == ()
    assert comparison.bird_ex.value == 1
    assert comparison.bird_ex.gold_rows == 3
    assert comparison.bird_ex.second_rows == 2
    assert comparison.bird_ex.gold_distinct_rows == comparison.bird_ex.second_distinct_rows == 2
    assert comparison.differing_rows.only_left_total == 1
    assert comparison.differing_rows.only_right_total == 0
    assert comparison.differing_rows.only_left[0].row == ("c",)
    assert comparison.differing_rows.only_left[0].count == 1
    assert comparison.mechanism is not None
    assert comparison.mechanism.classification == MECHANISM_MULTIPLICITY
    assert counterexample_json(comparison)["mechanism"]["class"] == MECHANISM_MULTIPLICITY


def test_rows_that_differ_only_in_order_are_not_equal_under_the_gold_s_rule(
    tmp_path: Path,
) -> None:
    ascending = ((20,), (23,), (80,))
    descending = ((80,), (23,), (20,))
    backend = FakeBackend(
        {
            GOLD_ORD: fake_result(SPEED, ascending),
            SECOND_ORD: fake_result(SPEED, descending),
        },
        row_counts={"team_attributes": 3},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_ORD, second_sql=SECOND_ORD)
    assert comparison.replay_rule is ReplayRule.R_ORD
    assert comparison.verdict.result is ComparabilityResult.NOT_EQUAL
    assert comparison.bird_ex.value == 1, "the benchmark's own check disregards row order"
    assert comparison.differing_rows.only_left_total == 0
    assert comparison.gold_result_hash != comparison.second_result_hash


def test_a_float_column_against_a_numeric_one_is_read_as_psycopg2_hands_them_to_bird(
    tmp_path: Path,
) -> None:
    """The six rows of the measured run: one number the server returns as ``float8`` on one
    side and ``numeric`` on the other. BIRD runs psycopg2, which hands it a Python float for
    a float column and a Decimal for a numeric one, and 0.1 is not the decimal 0.1, so its
    check scores 0. This tool loads a float column as the decimal the server printed, and a
    set reading over those two decimals would say 1 about a run BIRD scored 0."""
    backend = FakeBackend(
        {
            GOLD_AVERAGE: fake_result(AVERAGE_FLOAT8, ((Decimal("0.1"),),)),
            SECOND_AVERAGE: fake_result(AVERAGE_NUMERIC, ((Decimal("0.1"),),)),
        },
        row_counts={"team_attributes": 3},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_AVERAGE, second_sql=SECOND_AVERAGE)
    assert comparison.verdict.result is ComparabilityResult.NOT_EQUAL
    assert comparison.mechanism is not None
    assert comparison.mechanism.classification == MECHANISM_TYPE
    assert comparison.bird_ex.value == 0


def test_a_float_a_double_holds_exactly_matches_the_same_numeric_under_bird_s_reading(
    tmp_path: Path,
) -> None:
    """The same pair of declared types on a number a double holds exactly: psycopg2's float
    is equal to the decimal, so BIRD scores 1 where the typed verdict is still NOT_EQUAL.
    Which of the two rows is credited is the double's business and not this tool's."""
    backend = FakeBackend(
        {
            GOLD_AVERAGE: fake_result(AVERAGE_FLOAT8, ((Decimal("0.5"),),)),
            SECOND_AVERAGE: fake_result(AVERAGE_NUMERIC, ((Decimal("0.5"),),)),
        },
        row_counts={"team_attributes": 3},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_AVERAGE, second_sql=SECOND_AVERAGE)
    assert comparison.verdict.result is ComparabilityResult.NOT_EQUAL
    assert comparison.bird_ex.value == 1


def test_two_numeric_columns_are_read_as_decimals_on_both_sides(tmp_path: Path) -> None:
    """Nothing outside a float column moves: psycopg2 hands BIRD a Decimal for a numeric one
    and both sides are compared as the server printed them."""
    backend = FakeBackend(
        {
            GOLD_AVERAGE: fake_result(AVERAGE_NUMERIC, ((Decimal("0.1"),),)),
            SECOND_AVERAGE: fake_result(AVERAGE_NUMERIC, ((Decimal("0.1"),),)),
        },
        row_counts={"team_attributes": 3},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_AVERAGE, second_sql=SECOND_AVERAGE)
    assert comparison.verdict.result is ComparabilityResult.EQUAL
    assert comparison.bird_ex.value == 1


def test_a_nan_in_a_float_column_is_unequal_to_itself_under_bird_s_reading() -> None:
    """What the reading says about a NaN is BIRD's answer and not this tool's.

    psycopg2 hands BIRD a Python float for a float column, and no Python set holds two NaNs
    equal unless they are the same object, so the check scores 0 on two results that hold
    the same one. Nothing here special-cases it. The reading is asked directly because this
    tool never compares such a pair at all: a non-finite numeric has no canonical rendering,
    so recording either result refuses before a verdict is reached.
    """
    measured = bird_ex(
        fake_result(AVERAGE_FLOAT8, ((Decimal("NaN"),),)),
        fake_result(AVERAGE_FLOAT8, ((Decimal("NaN"),),)),
        engine=ENGINE_POSTGRESQL,
    )
    assert measured.value == 0


def test_both_records_are_compared_under_the_gold_s_ordering_and_keep_their_own_as_data(
    tmp_path: Path,
) -> None:
    backend = FakeBackend(
        {
            GOLD_ORD: fake_result(SPEED, ((20,), (23,), (80,))),
            SECOND_ORD: fake_result(SPEED, ((80,), (23,), (20,))),
        },
        row_counts={"team_attributes": 3},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_ORD, second_sql=SECOND_ORD)
    gold_ordering = (SortKey("speed", descending=False),)
    assert comparison.gold.canonical_ordering == gold_ordering
    assert comparison.second.canonical_ordering == gold_ordering
    assert (comparison.gold_ordering[0].descending, comparison.gold_ordering[0].nulls) == (
        False,
        "first",
    )
    assert (comparison.second_ordering[0].descending, comparison.second_ordering[0].nulls) == (
        True,
        "last",
    )


def test_the_rule_is_the_gold_s_even_when_the_second_statement_orders_its_rows(
    tmp_path: Path,
) -> None:
    ordered_second = "SELECT element FROM atom ORDER BY element"
    backend = FakeBackend(
        {
            GOLD_SET: fake_result(ELEMENT, (("c",), ("o",))),
            ordered_second: fake_result(ELEMENT, (("c",), ("o",))),
        },
        row_counts={"atom": 2},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=ordered_second)
    assert comparison.replay_rule is ReplayRule.R_SET
    assert comparison.gold.canonical_ordering == ()
    assert comparison.second.canonical_ordering == ()
    assert comparison.second_ordering[0].expression == "element"


def test_each_record_states_the_execution_it_came_from(tmp_path: Path) -> None:
    backend = FakeBackend(
        {GOLD_SET: fake_result(ELEMENT, (("c",),)), SECOND_SET: fake_result(ELEMENT, (("c",),))},
        row_counts={"atom": 1},
    )
    comparison = _compare(
        backend, tmp_path, gold_sql=GOLD_SET, second_sql=SECOND_SET, statement_timeout_seconds=5
    )
    assert backend.executed == [(GOLD_SET, 5), (SECOND_SET, 5)]
    for record, statement in ((comparison.gold, GOLD_SET), (comparison.second, SECOND_SET)):
        assert record.executed_sql == statement
        assert record.bound_parameters == ()
        assert record.validator_version == "audit:libpg_query-parse"
        assert record.validation_outcome.all_passed is True
        assert record.effective_database_role == ROLE
        assert record.backend_identity_at_checkout == IDENTITY
        assert record.question_set_version == QUESTION_SET_VERSION
        assert record.session_settings_in_force == SETTINGS
        assert record.row_count == len(record.result.rows)
        assert record.data_as_of == DATA_AS_OF
        assert record.executed_at.tzinfo is not None
        assert record.run_id == "run-under-test"
        assert IDENTITY in record.rerun_instruction
    # The gold was read from the question file and the prediction from the predictions
    # file, and each record names the one its own statement came from.
    assert comparison.gold.statement_source == QUESTIONS_SOURCE
    assert comparison.second.statement_source == PREDICTIONS_SOURCE


def test_the_fixture_covers_the_tables_both_statements_name(tmp_path: Path) -> None:
    second = "SELECT element FROM atom JOIN bond ON bond.id = atom.id"
    backend = FakeBackend(
        {GOLD_SET: fake_result(ELEMENT, ()), second: fake_result(ELEMENT, ())},
        row_counts={"atom": 4, "bond": 9},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=second)
    assert dict(comparison.gold.fixture.row_counts) == {"atom": 4, "bond": 9}
    assert comparison.gold.fixture == comparison.second.fixture


def test_a_session_setting_that_differed_makes_the_two_records_incomparable(
    tmp_path: Path,
) -> None:
    """Not a disagreement about the answer: the second execution was another experiment."""
    backend = FakeBackend(
        {GOLD_SET: fake_result(ELEMENT, (("c",),)), SECOND_SET: fake_result(ELEMENT, (("o",),))},
        row_counts={"atom": 1},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=SECOND_SET)
    assert comparison.verdict.result is ComparabilityResult.NOT_EQUAL
    elsewhere = dataclasses.replace(
        comparison.second,
        session_settings_in_force=dataclasses.replace(SETTINGS, time_zone="Europe/Berlin"),
    )
    verdict = compare_r_set(comparison.gold, elsewhere)
    assert verdict.result is ComparabilityResult.NOT_COMPARABLE
    assert verdict.mismatched == ("session_settings_in_force.time_zone",)


def test_a_fixture_that_differed_makes_the_two_records_incomparable(tmp_path: Path) -> None:
    backend = FakeBackend(
        {
            GOLD_ORD: fake_result(SPEED, ((20,),)),
            SECOND_ORD: fake_result(SPEED, ((80,),)),
        },
        row_counts={"team_attributes": 1},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_ORD, second_sql=SECOND_ORD)
    other_data = dataclasses.replace(
        comparison.second,
        fixture=FixtureDigest(
            schema_digest=comparison.second.fixture.schema_digest,
            row_counts={"team_attributes": 2},
            content_digests={},
            source_file_sha256="",
        ),
    )
    verdict = compare_r_ord(comparison.gold, other_data)
    assert verdict.result is ComparabilityResult.NOT_COMPARABLE
    assert verdict.mismatched == ("fixture",)


def test_a_statement_the_audit_cannot_run_is_refused_before_anything_is_executed(
    tmp_path: Path,
) -> None:
    backend = FakeBackend({}, row_counts={"atom": 1})
    with pytest.raises(StatementRefused, match="UpdateStmt"):
        _compare(backend, tmp_path, gold_sql="UPDATE atom SET element = 'c'", second_sql=GOLD_SET)
    assert backend.executed == []


def test_the_comparison_is_written_as_three_files_a_reader_can_check(tmp_path: Path) -> None:
    backend = FakeBackend(
        {
            GOLD_SET: fake_result(ELEMENT, (("c",), ("c",))),
            SECOND_SET: fake_result(ELEMENT, (("c",),)),
        },
        row_counts={"atom": 2},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=SECOND_SET)
    write_comparison(comparison, tmp_path / "q207")

    document = json.loads((tmp_path / "q207" / COUNTEREXAMPLE_FILE).read_text(encoding="utf-8"))
    assert document["verdict"]["result"] == "not_equal"
    assert document["verdict"]["reading"] == VERDICT_READING
    assert document["replay_rule"] == "R-SET"
    assert document["question"]["question_id"] == "q207"
    assert document["gold"]["record"] == GOLD_RECORD_FILE
    assert document["second"]["record"] == SECOND_RECORD_FILE
    assert document["differing_rows"]["in_gold_not_in_second_total"] == 1
    assert document["differing_rows"]["in_gold_not_in_second"][0]["row"] == [
        {"type": "str", "value": "c"}
    ]
    assert document["result_hashes"]["gold"] == comparison.gold_result_hash
    assert document["bird_ex"]["value"] == 1

    gold_record = json.loads((tmp_path / "q207" / GOLD_RECORD_FILE).read_text(encoding="utf-8"))
    assert gold_record["executed_sql"] == GOLD_SET
    assert gold_record["result_hash"] == comparison.gold_result_hash
    assert gold_record["record_hash"].startswith("sha256:")
    assert gold_record["fixture"]["row_counts"] == {"atom": 2}
    second_record = json.loads((tmp_path / "q207" / SECOND_RECORD_FILE).read_text(encoding="utf-8"))
    assert second_record["executed_sql"] == SECOND_SET
    assert document["sources"] == {
        "gold": {
            "path": QUESTIONS_SOURCE.path,
            "digest": QUESTIONS_SOURCE.digest,
            "origin": None,
            "date": None,
        },
        "second": {
            "path": PREDICTIONS_SOURCE.path,
            "digest": PREDICTIONS_SOURCE.digest,
            "origin": None,
            "date": None,
        },
    }
    assert gold_record["statement_source"]["digest"] == QUESTIONS_SOURCE.digest
    assert second_record["statement_source"]["path"] == PREDICTIONS_SOURCE.path


# what makes a NOT_EQUAL


NUMBER_INT8 = (("total", "int8"),)
NUMBER_NUMERIC = (("total", "numeric"),)


def test_the_same_distinct_rows_at_different_counts_are_a_multiplicity() -> None:
    """The 138 rows of the measured run: every row of one result is in the other and one of
    them is there more often, which is what a prediction missing a DISTINCT produces."""
    found = mechanism(
        fake_result(ELEMENT, (("c",), ("c",), ("o",))),
        fake_result(ELEMENT, (("c",), ("o",))),
        ReplayRule.R_SET,
    )
    assert found.classification == MECHANISM_MULTIPLICITY
    assert found.set_equal
    assert not found.multiset_equal


def test_the_same_value_under_two_declared_types_is_a_type() -> None:
    """The other 32: SUM() against a bare column, or AVG() against one, is one number the
    server hands back at two types, and a typed comparison refuses it by design."""
    found = mechanism(
        fake_result(NUMBER_INT8, ((507,),)),
        fake_result(NUMBER_NUMERIC, ((Decimal("507"),),)),
        ReplayRule.R_SET,
    )
    assert found.classification == MECHANISM_TYPE
    assert found.gold_types == ("int8",)
    assert found.second_types == ("numeric",)


def test_a_declared_type_that_differs_is_the_class_even_where_the_counts_differ_too() -> None:
    """Two classes hold at once and the one that would still hold if the other were repaired
    is the answer: rows at different types are unequal at every count."""
    found = mechanism(
        fake_result(NUMBER_INT8, ((1,), (1,))),
        fake_result(NUMBER_NUMERIC, ((Decimal(1),),)),
        ReplayRule.R_SET,
    )
    assert found.classification == MECHANISM_TYPE
    assert not found.multiset_equal


def test_one_multiset_in_two_orders_under_the_ordered_rule_is_an_order() -> None:
    found = mechanism(
        fake_result(SPEED, ((20,), (23,), (80,))),
        fake_result(SPEED, ((80,), (23,), (20,))),
        ReplayRule.R_ORD,
    )
    assert found.classification == MECHANISM_ORDER
    assert found.multiset_equal
    assert not found.order_equal


def test_a_result_that_is_the_first_rows_of_the_other_is_a_truncation() -> None:
    """What a bound applied to one side and not the other leaves: the shorter result is the
    longer one cut, so a reader repairs it by looking at the LIMIT and not at the answer."""
    found = mechanism(
        fake_result(ELEMENT, (("c",), ("o",), ("n",))),
        fake_result(ELEMENT, (("c",), ("o",))),
        ReplayRule.R_ORD,
    )
    assert found.classification == MECHANISM_TRUNCATION
    assert found.shorter_result_is_a_prefix
    assert not found.set_equal


def test_two_results_holding_different_values_are_named_other_and_not_guessed_at() -> None:
    """None of the four classes holds: the two statements answered differently, and saying
    so is the whole of what these two results state."""
    found = mechanism(
        fake_result(ELEMENT, (("c",), ("o",))),
        fake_result(ELEMENT, (("c",), ("n",))),
        ReplayRule.R_SET,
    )
    assert found.classification == MECHANISM_OTHER
    assert not found.set_equal
    assert not found.shorter_result_is_a_prefix


def test_an_empty_result_against_a_full_one_is_not_a_truncation() -> None:
    """A result that came back empty is a different answer and not a cut of the other one."""
    found = mechanism(
        fake_result(ELEMENT, (("c",), ("o",))), fake_result(ELEMENT, ()), ReplayRule.R_ORD
    )
    assert found.classification == MECHANISM_OTHER
    assert not found.shorter_result_is_a_prefix


# the test-suite evaluator's reading, beside BIRD's


GOLD_SET_ORDERED = "SELECT element FROM atom ORDER BY element"
GOLD_COUNTED = "SELECT element, count(*) FROM atom GROUP BY element"
GOLD_COUNTED_ORDERED = GOLD_COUNTED + " ORDER BY element"

ELEMENT_AND_TOTAL = (("element", "text"), ("total", "int8"))
TOTAL_AND_ELEMENT = (("total", "int8"), ("element", "text"))
"""The same two values projected in the two orders: what the evaluator's column permutation
is for, and what a comparison by position calls a disagreement."""


def test_two_results_that_are_both_empty_are_equal_under_the_test_suite_reading() -> None:
    """The evaluator's first line: two statements that both returned nothing agree, before
    anything is read off a row that is not there."""
    measured = compare.test_suite_ex(
        fake_result(ELEMENT, ()), fake_result(ELEMENT, ()), GOLD_SET, engine=ENGINE_POSTGRESQL
    )
    assert measured.value == 1
    assert measured.equal
    assert (measured.gold_rows, measured.second_rows) == (0, 0)


def test_two_results_of_different_row_counts_are_not_equal_under_the_test_suite_reading() -> None:
    """Row counts are compared before values are, so a result that is the other one cut is
    refused without a permutation being built."""
    measured = compare.test_suite_ex(
        fake_result(ELEMENT, (("c",), ("o",))),
        fake_result(ELEMENT, (("c",),)),
        GOLD_SET,
        engine=ENGINE_POSTGRESQL,
    )
    assert measured.value == 0
    assert (measured.gold_rows, measured.second_rows) == (2, 1)


def test_a_projection_of_another_width_is_not_equal_under_the_test_suite_reading() -> None:
    """A projection of another width is refused whatever its values are: the permutation the
    evaluator searches for is a permutation and never a projection onto fewer columns."""
    measured = compare.test_suite_ex(
        fake_result(ELEMENT, (("c",),)),
        fake_result(ELEMENT_AND_TOTAL, (("c", 2),)),
        GOLD_SET,
        engine=ENGINE_POSTGRESQL,
    )
    assert measured.value == 0
    assert (measured.gold_columns, measured.second_columns) == (1, 2)


def test_the_same_rows_in_another_order_turn_on_the_gold_s_own_text() -> None:
    """The evaluator reads the gold's text for ``order by`` and nothing else, so one pair of
    results is equal under a gold that does not order and unequal under one that does. That
    reading is not this tool's rule: a gold that orders inside a subquery is R-SET here and
    ordered there, which is why the field is recorded beside the value."""
    gold = fake_result(ELEMENT, (("c",), ("o",)))
    second = fake_result(ELEMENT, (("o",), ("c",)))

    unordered = compare.test_suite_ex(gold, second, GOLD_SET, engine=ENGINE_POSTGRESQL)
    ordered = compare.test_suite_ex(gold, second, GOLD_SET_ORDERED, engine=ENGINE_POSTGRESQL)

    assert (unordered.value, unordered.order_matters) == (1, False)
    assert (ordered.value, ordered.order_matters) == (0, True)


def test_columns_that_came_back_in_another_order_are_equal_under_the_test_suite_reading() -> None:
    """What separates this reading from BIRD's in the other direction: the evaluator searches
    the column permutations and finds the one that makes these two results the same, where
    ``set(predicted) == set(gold)`` compares the tuples as they came back and does not."""
    gold = fake_result(ELEMENT_AND_TOTAL, (("c", 2), ("o", 1)))
    second = fake_result(TOTAL_AND_ELEMENT, ((2, "c"), (1, "o")))

    assert compare.test_suite_ex(gold, second, GOLD_COUNTED, engine=ENGINE_POSTGRESQL).value == 1
    assert (
        compare.test_suite_ex(gold, second, GOLD_COUNTED_ORDERED, engine=ENGINE_POSTGRESQL).value
        == 1
    ), "the rows are in the gold's order under the permutation, so ordering it changes nothing"
    assert bird_ex(gold, second, engine=ENGINE_POSTGRESQL).value == 0


def test_a_duplicate_row_bird_forgives_is_refused_by_the_test_suite_reading(
    tmp_path: Path,
) -> None:
    """The class this tool was written for, read by all three: the gold holds one row twice
    and the prediction holds it once. BIRD's set drops the duplicate and credits the pair,
    the typed multiset calls it NOT_EQUAL, and the test-suite reading refuses it on the row
    count. Where the evaluator itself would strip the prediction's DISTINCT and run it again,
    which is what would make the two the same rows, these rows are already fetched and
    nothing recovers what DISTINCT removed."""
    backend = FakeBackend(
        {
            GOLD_SET: fake_result(ELEMENT, (("c",), ("c",), ("o",))),
            SECOND_SET: fake_result(ELEMENT, (("c",), ("o",))),
        },
        row_counts={"atom": 3},
    )
    comparison = _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=SECOND_SET)

    assert comparison.verdict.result is ComparabilityResult.NOT_EQUAL
    assert comparison.bird_ex.value == 1
    assert comparison.test_suite_ex.value == 0
    assert comparison.test_suite_ex.gold_rows == 3
    assert comparison.test_suite_ex.second_rows == 2
    assert not comparison.test_suite_ex.order_matters


def test_a_float_column_is_read_as_psycopg2_returns_it_on_both_sides() -> None:
    """The two readings differ in their rule and never in their cells: a float column is the
    Python float psycopg2 builds here as it is under ``bird_ex``. Two float columns holding
    the decimal the server printed are equal, and the same value declared ``numeric`` on one
    side is not, because a double that does not hold 0.1 exactly is not the decimal 0.1."""
    as_float = fake_result(AVERAGE_FLOAT8, ((Decimal("0.1"),),))

    assert (
        compare.test_suite_ex(as_float, as_float, GOLD_AVERAGE, engine=ENGINE_POSTGRESQL).value == 1
    )
    against_numeric = compare.test_suite_ex(
        as_float,
        fake_result(AVERAGE_NUMERIC, ((Decimal("0.1"),),)),
        GOLD_AVERAGE,
        engine=ENGINE_POSTGRESQL,
    )
    assert against_numeric.value == 0
    assert (
        bird_ex(
            as_float,
            fake_result(AVERAGE_NUMERIC, ((Decimal("0.1"),),)),
            engine=ENGINE_POSTGRESQL,
        ).value
        == 0
    )


def test_the_counterexample_states_the_second_reading_beside_the_first(tmp_path: Path) -> None:
    """A reader who holds one of the two published readings against a verdict finds both in
    the document, each saying what it is and where it comes from."""
    backend = FakeBackend(
        {
            GOLD_SET: fake_result(ELEMENT, (("c",), ("c",), ("o",))),
            SECOND_SET: fake_result(ELEMENT, (("c",), ("o",))),
        },
        row_counts={"atom": 3},
    )
    document = counterexample_json(
        _compare(backend, tmp_path, gold_sql=GOLD_SET, second_sql=SECOND_SET)
    )
    block = document["test_suite_ex"]

    assert isinstance(block, dict)
    assert block["value"] == 0
    assert block["equal"] is False
    assert block["method"] == TEST_SUITE_EX_METHOD[ENGINE_POSTGRESQL]
    assert block["source"] == TEST_SUITE_EX_SOURCE
    assert block["order_matters"] is False
    keys = list(document)
    assert keys.index("test_suite_ex") == keys.index("bird_ex") + 1
