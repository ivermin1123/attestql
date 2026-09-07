"""The two replay rules, and the difference between a disagreement and another experiment.

``NOT_EQUAL`` says the two results differ. ``NOT_COMPARABLE`` is not a disagreement at
all, and the tests that matter most here are the ones that show a comparison producing
the second where a careless one would produce the first: every precondition field, and
every field naming the rule the comparison would have been performed under, is made
to differ one at a time on records whose results also differ, and the verdict stays
``NOT_COMPARABLE`` and names the field.

ADR-0013 narrowed the preconditions to what point 6 names, and the two memory settings
the executor holds every statement to were added beside them once a hash aggregate that
spilled was measured changing a float aggregate: the fixture digest and the
seven session settings that change rendered bytes or row order. The validator, the
question set and the server version are recorded and never block, because a record whose
validator differs is still a record of the same data and calling that pair incomparable
would hide the disagreement an audit exists to report.

R-ORD and R-SET are separated by the two cases that tell them apart: rows in another
order, which R-ORD is required to call a difference and R-SET is required to ignore,
and values of another type holding the same amount, which the typed multiset is
required to call a difference.

The third case both rules answer the same way is a column named otherwise. A projection
is compared by position and declared type, so an alias is the same answer under another
label; the tests below fix that under both rules, keep a declared type that differs at a
position a difference, and show that a name is never among the fields a verdict names.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from attestql.evidence.record import EvidenceRecord, ValidationOutcome
from attestql.evidence.replay import (
    PRECONDITION_FIELDS,
    RULE_FIELDS,
    SESSION_PRECONDITIONS,
    ComparabilityResult,
    ComparabilityVerdict,
    compare_r_ord,
    compare_r_set,
    precondition_mismatches,
    preconditions_match,
)
from attestql.evidence.serialize import SerializationDescriptor, UnsupportedValue
from attestql.evidence.types import (
    ENGINE_POSTGRESQL,
    ENGINE_SQLITE,
    FixtureDigest,
    QuestionMetadata,
    ReplayRule,
    SessionSettings,
    SortKey,
    StatementSource,
)
from attestql.kernel.types import BoundParameter, ColumnType, ExecutionLimits, ExecutionResult

COLUMNS = (ColumnType("feature", "text"), ColumnType("adopting_account_count", "int8"))
CLOCK = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

QUESTION = QuestionMetadata(
    question_id="q-under-test",
    question_set="question-set-under-test",
    question_text="Which features are adopted by how many accounts?",
    evidence_text="",
)


SETTINGS = SessionSettings(
    engine=ENGINE_POSTGRESQL,
    time_zone="UTC",
    date_style="ISO, MDY",
    interval_style="postgres",
    extra_float_digits="1",
    database_collation="en_US.UTF-8",
    work_mem="4096",
    hash_mem_multiplier="2",
    recorded={"statement_timeout": "5000", "server_version_num": "160004"},
)
FIXTURE = FixtureDigest(
    schema_digest="sha256:schema-under-test",
    row_counts={"feature_usage": 12},
    content_digests={},
    source_file_sha256="",
)
SOURCE = StatementSource(
    path="questions-under-test.json",
    digest="sha256:question-file-under-test",
    origin=None,
    date=None,
)


@pytest.fixture
def execution_limits() -> ExecutionLimits:
    return ExecutionLimits(statement_timeout_ms=5000)


@pytest.fixture
def serialization_descriptor() -> SerializationDescriptor:
    return SerializationDescriptor(
        version="serialization-under-test",
        numeric_scale=6,
        timestamp_format="%Y-%m-%dT%H:%M:%S.%fZ",
        timezone="UTC",
        null_rendering="NULL",
        encoding="utf-8",
    )


@pytest.fixture
def make_evidence_record(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> Callable[..., EvidenceRecord]:
    """Factory: a complete record under R-SET, built here, with keyword overrides.

    Every value is this file's own, so what the comparator is exercised against is a pair
    of records and not a catalogue.
    """

    def factory(**overrides: Any) -> EvidenceRecord:
        fields: dict[str, Any] = dict(
            question_as_asked=QUESTION.question_text,
            question=QUESTION,
            executed_sql="SELECT feature, count(*) AS adopting_account_count FROM feature_usage "
            "WHERE event_ts >= $1 GROUP BY feature",
            bound_parameters=(BoundParameter(1, CLOCK, "timestamptz"),),
            validation_outcome=ValidationOutcome(("single_statement", "select_only"), True),
            validator_version="validator-under-test",
            question_set_version="sha256:question-set-under-test",
            statement_source=SOURCE,
            effective_database_role="attestql_readonly_under_test",
            backend_identity_at_checkout="backend-under-test",
            session_settings_in_force=SETTINGS,
            result=_result(execution_limits, ()),
            row_count=0,
            canonical_ordering=(),
            serialization=serialization_descriptor,
            data_as_of=CLOCK,
            executed_at=CLOCK,
            fixture=FIXTURE,
            run_id="run-under-test",
            rerun_instruction="test input only; not reproducible",
            replay_rule=ReplayRule.R_SET,
        )
        fields.update(overrides)
        result: ExecutionResult = fields["result"]
        fields.setdefault("row_count", len(result.rows))
        if "result" in overrides and "row_count" not in overrides:
            # The record refuses a count its own result contradicts, so a test that
            # overrides the result gets the count that goes with it.
            fields["row_count"] = len(result.rows)
        return EvidenceRecord(**fields)

    return factory


@pytest.fixture
def r_ord_overrides() -> dict[str, Any]:
    return dict(
        replay_rule=ReplayRule.R_ORD,
        canonical_ordering=(SortKey("count(*)", descending=True),),
    )


def _result(
    limits: ExecutionLimits,
    rows: tuple[tuple[object, ...], ...],
    *,
    columns: tuple[ColumnType, ...] = COLUMNS,
    truncated: bool = False,
) -> ExecutionResult:
    return ExecutionResult(
        columns=columns,
        rows=rows,
        backend_identity="backend-under-test",
        limits_in_force=limits,
        truncated=truncated,
    )


TWO_ROWS: tuple[tuple[object, ...], ...] = (("reporting", 12), ("export", 7))
SWAPPED: tuple[tuple[object, ...], ...] = (("export", 7), ("reporting", 12))

ALIASED = (ColumnType("feature_name", "text"), ColumnType("accounts", "int8"))
"""The same projection under other names: what a prediction that renames its columns
returns."""

RETYPED = (ColumnType("feature", "text"), ColumnType("adopting_account_count", "numeric"))
"""The same names at another declared type in the second position."""


ANOTHER_ENGINE = SessionSettings(
    engine=ENGINE_SQLITE,
    time_zone=None,
    date_style=None,
    interval_style=None,
    extra_float_digits=None,
    database_collation=None,
    work_mem=None,
    hash_mem_multiplier=None,
    recorded={"journal_mode": "delete"},
)
"""The same run on the other engine: a file has no session, so the seven are absent there
and cannot be varied one at a time the way the settings of one engine can."""


def _differing(field: str) -> dict[str, Any]:
    """One record override that makes exactly that precondition differ.

    A session setting is named through the field that holds it, so the override has to
    reach inside ``session_settings_in_force`` rather than replace a field of the record.
    The engine is the one that cannot be varied on its own: changing it changes which of
    the seven settings a record may state at all, so the override is the other engine's
    whole settings block.
    """
    if field == "fixture":
        return {"fixture": dataclasses.replace(FIXTURE, schema_digest="sha256:another-schema")}
    setting = field.removeprefix("session_settings_in_force.")
    assert setting in SESSION_PRECONDITIONS, f"{field} is not a precondition this test knows"
    if setting == "engine":
        return {"session_settings_in_force": ANOTHER_ENGINE}
    return {
        "session_settings_in_force": dataclasses.replace(SETTINGS, **{setting: "another-value"})
    }


def test_two_records_of_the_same_ordered_result_are_equal(
    make_evidence_record: Any, r_ord_overrides: dict[str, Any], execution_limits: ExecutionLimits
) -> None:
    result = _result(execution_limits, TWO_ROWS)
    verdict = compare_r_ord(
        make_evidence_record(result=result, **r_ord_overrides),
        make_evidence_record(result=result, **r_ord_overrides),
    )
    assert verdict == ComparabilityVerdict(ComparabilityResult.EQUAL, ())


def test_an_ordered_re_run_whose_rows_changed_is_a_failure(
    make_evidence_record: Any, r_ord_overrides: dict[str, Any], execution_limits: ExecutionLimits
) -> None:
    verdict = compare_r_ord(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS), **r_ord_overrides),
        make_evidence_record(
            result=_result(execution_limits, (("reporting", 12), ("export", 8))),
            **r_ord_overrides,
        ),
    )
    assert verdict.result is ComparabilityResult.NOT_EQUAL
    assert verdict.mismatched == ()


def test_under_r_ord_the_same_rows_in_another_order_are_not_equal(
    make_evidence_record: Any, r_ord_overrides: dict[str, Any], execution_limits: ExecutionLimits
) -> None:
    verdict = compare_r_ord(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS), **r_ord_overrides),
        make_evidence_record(result=_result(execution_limits, SWAPPED), **r_ord_overrides),
    )
    assert verdict.result is ComparabilityResult.NOT_EQUAL


def test_under_r_set_the_same_rows_in_another_order_are_equal(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    verdict = compare_r_set(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS)),
        make_evidence_record(result=_result(execution_limits, SWAPPED)),
    )
    assert verdict == ComparabilityVerdict(ComparabilityResult.EQUAL, ())


def test_under_r_set_a_row_occurring_twice_is_not_a_row_occurring_once(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    verdict = compare_r_set(
        make_evidence_record(result=_result(execution_limits, (("export", 7), ("export", 7)))),
        make_evidence_record(result=_result(execution_limits, (("export", 7),))),
    )
    assert verdict.result is ComparabilityResult.NOT_EQUAL


def test_under_r_set_the_same_amount_of_another_type_is_not_the_same_value(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    """Python holds these equal and hashes them alike; typed equality does not."""
    columns = (ColumnType("share", "numeric"),)
    verdict = compare_r_set(
        make_evidence_record(result=_result(execution_limits, ((1,),), columns=columns)),
        make_evidence_record(result=_result(execution_limits, ((Decimal(1),),), columns=columns)),
    )
    assert verdict.result is ComparabilityResult.NOT_EQUAL
    booleans = compare_r_set(
        make_evidence_record(result=_result(execution_limits, ((1,),), columns=columns)),
        make_evidence_record(result=_result(execution_limits, ((True,),), columns=columns)),
    )
    assert booleans.result is ComparabilityResult.NOT_EQUAL


def test_under_r_set_numeric_values_are_compared_as_the_result_returned_them(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    """Two amounts the descriptor's scale would render alike are still two amounts."""
    columns = (ColumnType("share", "numeric"),)
    verdict = compare_r_set(
        make_evidence_record(
            result=_result(execution_limits, ((Decimal("0.1234565"),),), columns=columns)
        ),
        make_evidence_record(
            result=_result(execution_limits, ((Decimal("0.1234564"),),), columns=columns)
        ),
    )
    assert verdict.result is ComparabilityResult.NOT_EQUAL


def _a_not_a_number() -> tuple[tuple[object, ...], ...]:
    """One row holding a fresh NaN. Two executions never return the same object and Python
    keys a NaN by its identity, so a shared one would compare equal for the wrong reason."""
    return ((Decimal("NaN"),),)


def test_under_r_set_a_not_a_number_is_the_one_value_postgresql_groups_it_as(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    """PostgreSQL holds NaN equal to NaN and groups the two as one value. Python holds two of
    them unequal and hashes each by its identity, so a multiset keyed on the value the result
    returned would count one answer as two and call two of the same result a disagreement."""
    columns = (ColumnType("share", "float8"),)
    verdict = compare_r_set(
        make_evidence_record(result=_result(execution_limits, _a_not_a_number(), columns=columns)),
        make_evidence_record(result=_result(execution_limits, _a_not_a_number(), columns=columns)),
    )
    assert verdict == ComparabilityVerdict(ComparabilityResult.EQUAL, ())
    one_side = compare_r_set(
        make_evidence_record(result=_result(execution_limits, _a_not_a_number(), columns=columns)),
        make_evidence_record(
            result=_result(execution_limits, ((Decimal("1.5"),),), columns=columns)
        ),
    )
    assert one_side.result is ComparabilityResult.NOT_EQUAL


def test_under_r_set_an_infinity_is_equal_to_an_infinity_and_not_to_the_other_one(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    """The other two values a float column returns beside a number, which Decimal already
    holds the way PostgreSQL orders them: one infinity is one value, and the two are not."""
    columns = (ColumnType("share", "float8"),)
    infinite: tuple[tuple[object, ...], ...] = ((Decimal("Infinity"),),)
    verdict = compare_r_set(
        make_evidence_record(result=_result(execution_limits, infinite, columns=columns)),
        make_evidence_record(
            result=_result(execution_limits, ((Decimal("Infinity"),),), columns=columns)
        ),
    )
    assert verdict == ComparabilityVerdict(ComparabilityResult.EQUAL, ())
    signed = compare_r_set(
        make_evidence_record(result=_result(execution_limits, infinite, columns=columns)),
        make_evidence_record(
            result=_result(execution_limits, ((Decimal("-Infinity"),),), columns=columns)
        ),
    )
    assert signed.result is ComparabilityResult.NOT_EQUAL


def test_the_same_values_under_another_alias_are_the_same_answer(
    make_evidence_record: Any, r_ord_overrides: dict[str, Any], execution_limits: ExecutionLimits
) -> None:
    """Under both rules. A prediction that aliases a column differently answers the
    question the same way, and the benchmark this audit compares against never sees the
    name: it compares result tuples by position."""
    under_r_set = compare_r_set(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS)),
        make_evidence_record(result=_result(execution_limits, TWO_ROWS, columns=ALIASED)),
    )
    under_r_ord = compare_r_ord(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS), **r_ord_overrides),
        make_evidence_record(
            result=_result(execution_limits, TWO_ROWS, columns=ALIASED), **r_ord_overrides
        ),
    )
    assert under_r_set == ComparabilityVerdict(ComparabilityResult.EQUAL, ())
    assert under_r_ord == ComparabilityVerdict(ComparabilityResult.EQUAL, ())


def test_another_declared_type_at_a_position_is_another_result(
    make_evidence_record: Any, r_ord_overrides: dict[str, Any], execution_limits: ExecutionLimits
) -> None:
    """The names are not read and the types at each position are: a count returned as a
    numeric is not the same result as a count returned as an integer."""
    under_r_set = compare_r_set(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS)),
        make_evidence_record(result=_result(execution_limits, TWO_ROWS, columns=RETYPED)),
    )
    under_r_ord = compare_r_ord(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS), **r_ord_overrides),
        make_evidence_record(
            result=_result(execution_limits, TWO_ROWS, columns=RETYPED), **r_ord_overrides
        ),
    )
    assert under_r_set.result is ComparabilityResult.NOT_EQUAL
    assert under_r_ord.result is ComparabilityResult.NOT_EQUAL


def test_a_column_name_is_never_among_the_fields_that_block_a_comparison(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    """The pair below differs in its fixture and in every column name. What made it
    incomparable is the fixture and nothing else; a rename is not a precondition."""
    verdict = compare_r_set(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS)),
        make_evidence_record(
            result=_result(execution_limits, TWO_ROWS, columns=ALIASED),
            fixture=dataclasses.replace(FIXTURE, schema_digest="sha256:another-schema"),
        ),
    )
    assert verdict.result is ComparabilityResult.NOT_COMPARABLE
    assert verdict.mismatched == ("fixture",)
    assert [column.name for column in ALIASED] != [column.name for column in COLUMNS], (
        "the two projections have to disagree on the names for this test to observe anything"
    )


def test_under_r_set_a_bounded_result_is_not_a_complete_one(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    verdict = compare_r_set(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS)),
        make_evidence_record(result=_result(execution_limits, TWO_ROWS, truncated=True)),
    )
    assert verdict.result is ComparabilityResult.NOT_EQUAL


@pytest.mark.parametrize("field", PRECONDITION_FIELDS)
def test_a_precondition_that_differs_makes_an_ordered_re_run_another_experiment(
    field: str,
    make_evidence_record: Any,
    r_ord_overrides: dict[str, Any],
    execution_limits: ExecutionLimits,
) -> None:
    """The results differ too, so a comparison that ran anyway would report a failure."""
    verdict = compare_r_ord(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS), **r_ord_overrides),
        make_evidence_record(
            result=_result(execution_limits, SWAPPED), **_differing(field), **r_ord_overrides
        ),
    )
    assert verdict.result is ComparabilityResult.NOT_COMPARABLE
    assert verdict.mismatched == (field,)


@pytest.mark.parametrize("field", PRECONDITION_FIELDS)
def test_a_precondition_that_differs_makes_an_unordered_re_run_another_experiment(
    field: str, make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    verdict = compare_r_set(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS)),
        make_evidence_record(
            result=_result(execution_limits, (("export", 7),)), **_differing(field)
        ),
    )
    assert verdict.result is ComparabilityResult.NOT_COMPARABLE
    assert verdict.mismatched == (field,)
    assert not preconditions_match(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS)),
        make_evidence_record(result=_result(execution_limits, TWO_ROWS), **_differing(field)),
    )


def test_records_rendered_under_another_descriptor_are_not_compared(
    make_evidence_record: Any,
    r_ord_overrides: dict[str, Any],
    execution_limits: ExecutionLimits,
    serialization_descriptor: SerializationDescriptor,
) -> None:
    other = dataclasses.replace(serialization_descriptor, numeric_scale=2)
    result = _result(execution_limits, TWO_ROWS)
    ordered = compare_r_ord(
        make_evidence_record(result=result, **r_ord_overrides),
        make_evidence_record(result=result, serialization=other, **r_ord_overrides),
    )
    assert ordered.result is ComparabilityResult.NOT_COMPARABLE
    assert ordered.mismatched == ("serialization",)
    unordered = compare_r_set(
        make_evidence_record(result=result),
        make_evidence_record(result=result, serialization=other),
    )
    assert unordered.mismatched == ("serialization",)


def test_records_declaring_another_ordering_are_not_compared(
    make_evidence_record: Any, r_ord_overrides: dict[str, Any], execution_limits: ExecutionLimits
) -> None:
    result = _result(execution_limits, TWO_ROWS)
    verdict = compare_r_ord(
        make_evidence_record(result=result, **r_ord_overrides),
        make_evidence_record(
            result=result,
            replay_rule=ReplayRule.R_ORD,
            canonical_ordering=(SortKey("adopting_account_count", descending=True),),
        ),
    )
    assert verdict.result is ComparabilityResult.NOT_COMPARABLE
    assert verdict.mismatched == ("canonical_ordering",)


def test_records_declaring_different_rules_are_not_compared(
    make_evidence_record: Any, r_ord_overrides: dict[str, Any], execution_limits: ExecutionLimits
) -> None:
    result = _result(execution_limits, TWO_ROWS)
    ordered = compare_r_ord(
        make_evidence_record(result=result, **r_ord_overrides),
        make_evidence_record(result=result),
    )
    assert ordered.result is ComparabilityResult.NOT_COMPARABLE
    assert ordered.mismatched == ("replay_rule", "canonical_ordering")
    unordered = compare_r_set(
        make_evidence_record(result=result),
        make_evidence_record(result=result, **r_ord_overrides),
    )
    assert unordered.mismatched == ("replay_rule",)


def test_comparing_under_a_rule_neither_record_declared_is_a_caller_error(
    make_evidence_record: Any, r_ord_overrides: dict[str, Any], execution_limits: ExecutionLimits
) -> None:
    result = _result(execution_limits, TWO_ROWS)
    with pytest.raises(ValueError, match="chose the wrong rule"):
        compare_r_ord(make_evidence_record(result=result), make_evidence_record(result=result))
    with pytest.raises(ValueError, match="chose the wrong rule"):
        compare_r_set(
            make_evidence_record(result=result, **r_ord_overrides),
            make_evidence_record(result=result, **r_ord_overrides),
        )


def test_everything_that_differs_is_named_and_not_only_the_first(
    make_evidence_record: Any,
    execution_limits: ExecutionLimits,
    serialization_descriptor: SerializationDescriptor,
) -> None:
    verdict = compare_r_set(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS)),
        make_evidence_record(
            result=_result(execution_limits, TWO_ROWS),
            fixture=dataclasses.replace(FIXTURE, schema_digest="sha256:another-schema"),
            session_settings_in_force=dataclasses.replace(SETTINGS, date_style="SQL, DMY"),
            serialization=dataclasses.replace(serialization_descriptor, timezone="Europe/Berlin"),
        ),
    )
    assert verdict.result is ComparabilityResult.NOT_COMPARABLE
    assert verdict.mismatched == (
        "fixture",
        "session_settings_in_force.date_style",
        "serialization",
    )


def test_a_verdict_names_what_differed_when_and_only_when_it_is_not_comparable() -> None:
    with pytest.raises(ValueError, match="names what differed"):
        ComparabilityVerdict(ComparabilityResult.NOT_COMPARABLE, ())
    with pytest.raises(ValueError, match="names what differed"):
        ComparabilityVerdict(ComparabilityResult.NOT_EQUAL, ("fixture",))
    with pytest.raises(ValueError, match="names what differed"):
        ComparabilityVerdict(ComparabilityResult.EQUAL, ("fixture",))


def test_two_engines_are_never_comparable_and_the_verdict_names_the_engine_alone(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    """The seven settings the other engine does not hold are not seven disagreements.

    A SQLite record states none of them because there is no session to read them from,
    so listing them beside the engine would report an absence this tool already knows
    the reason for as seven separate findings a reader has to dismiss one by one.
    """
    on_postgresql = make_evidence_record(result=_result(execution_limits, TWO_ROWS))
    on_sqlite = make_evidence_record(
        result=_result(execution_limits, TWO_ROWS), session_settings_in_force=ANOTHER_ENGINE
    )

    assert precondition_mismatches(on_postgresql, on_sqlite) == (
        "session_settings_in_force.engine",
    )
    assert not preconditions_match(on_postgresql, on_sqlite)
    assert compare_r_set(on_postgresql, on_sqlite) == ComparabilityVerdict(
        ComparabilityResult.NOT_COMPARABLE, ("session_settings_in_force.engine",)
    )


def test_the_precondition_fields_and_the_rule_fields_are_disjoint() -> None:
    """The nine are what must match before equality is required; the rule fields are what
    equality would be required under. ADR-0013 point 6 names five of them, the two memory
    settings the executor holds every statement to are two more, and ADR-0014 puts the
    engine they are all read in ahead of the list."""
    assert set(PRECONDITION_FIELDS).isdisjoint(RULE_FIELDS)
    assert PRECONDITION_FIELDS == (
        "fixture",
        "session_settings_in_force.engine",
        "session_settings_in_force.time_zone",
        "session_settings_in_force.date_style",
        "session_settings_in_force.interval_style",
        "session_settings_in_force.extra_float_digits",
        "session_settings_in_force.database_collation",
        "session_settings_in_force.work_mem",
        "session_settings_in_force.hash_mem_multiplier",
    )


def test_what_a_record_states_beside_the_preconditions_never_blocks_a_comparison(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    """A record whose validator, question set or role differs is still about the same data."""
    verdict = compare_r_set(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS)),
        make_evidence_record(
            result=_result(execution_limits, TWO_ROWS),
            validator_version="another-validator",
            question_set_version="sha256:another-question-set",
            effective_database_role="another_role",
            backend_identity_at_checkout="another-backend",
            session_settings_in_force=dataclasses.replace(
                SETTINGS, recorded={"server_version_num": "170001"}
            ),
        ),
    )
    assert verdict == ComparabilityVerdict(ComparabilityResult.EQUAL, ())


def test_content_digests_are_compared_only_when_both_records_carry_them(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    """A measurement one side did not take is not a difference the two disagree about."""
    measured = dataclasses.replace(FIXTURE, content_digests={"feature_usage": "md5:abc"})
    other = dataclasses.replace(FIXTURE, content_digests={"feature_usage": "md5:def"})
    both_ways = compare_r_set(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS), fixture=measured),
        make_evidence_record(result=_result(execution_limits, TWO_ROWS)),
    )
    assert both_ways == ComparabilityVerdict(ComparabilityResult.EQUAL, ())
    disagreeing = compare_r_set(
        make_evidence_record(result=_result(execution_limits, TWO_ROWS), fixture=measured),
        make_evidence_record(result=_result(execution_limits, TWO_ROWS), fixture=other),
    )
    assert disagreeing.result is ComparabilityResult.NOT_COMPARABLE
    assert disagreeing.mismatched == ("fixture",)


def test_a_fixture_whose_row_counts_differ_is_another_body_of_data(
    make_evidence_record: Any, execution_limits: ExecutionLimits
) -> None:
    counted = dataclasses.replace(FIXTURE, row_counts={"feature_usage": 13})
    a = make_evidence_record(result=_result(execution_limits, TWO_ROWS))
    b = make_evidence_record(result=_result(execution_limits, TWO_ROWS), fixture=counted)
    assert precondition_mismatches(a, b) == ("fixture",)


def test_a_value_the_engine_has_no_rule_for_is_refused_under_both_rules(
    make_evidence_record: Any, r_ord_overrides: dict[str, Any], execution_limits: ExecutionLimits
) -> None:
    columns = (ColumnType("share", "float8"),)
    unrenderable = _result(execution_limits, ((1.5,),), columns=columns)
    with pytest.raises(UnsupportedValue, match="float"):
        compare_r_ord(
            make_evidence_record(result=unrenderable, **r_ord_overrides),
            make_evidence_record(result=unrenderable, **r_ord_overrides),
        )
    with pytest.raises(UnsupportedValue, match="float"):
        compare_r_set(
            make_evidence_record(result=unrenderable),
            make_evidence_record(result=unrenderable),
        )
