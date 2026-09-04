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
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

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
    VERDICT_READING,
    Comparison,
    compare_statements,
    counterexample_json,
    mechanism,
    write_comparison,
)
from attestql.audit.statements import StatementRefused, parse_statement
from attestql.evidence.replay import ComparabilityResult, compare_r_ord, compare_r_set
from attestql.evidence.types import FixtureDigest, QuestionMetadata, ReplayRule, SortKey
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
SPEED = (("speed", "int8"),)

SECOND_ALIASED = "SELECT element AS symbol FROM atom"
SYMBOL = (("symbol", "text"),)


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
