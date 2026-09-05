"""A complete record is built from what one execution produced, or it is not built.

The builder is exercised through the kernel's own admission and the executor port rather
than around them: the statement comes out of ``admit`` and the result out of a stub behind
``QueryExecutor``, so what the tests observe is a record of an admission and an execution
rather than of values assembled beside them. The inputs are this file's own; a record that
could only be built from a catalogue would be a record of the catalogue.

Two failures have their own tests because the plan names them. A record that stores
the question and the SQL but not the bound parameters is the one this module exists
to make unbuildable, and a record that cannot state its replay rule was already
unbuildable and stays so.

The third such cross-check went with ADR-0013: the builder no longer compares limits the
product fixed against limits the result read back, because nothing beside the executor
fixes them now. The executor reads its own envelope back and refuses on drift, which
``tests/test_audit_executor_refuses_a_session_that_drifted.py`` states.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from attestql.evidence.build import ExecutionIdentity, IncompleteEvidence, build_evidence_record
from attestql.evidence.record import EvidenceRecord
from attestql.evidence.serialize import SerializationDescriptor
from attestql.evidence.types import (
    ENGINE_POSTGRESQL,
    FixtureDigest,
    QuestionMetadata,
    ReplayRule,
    SessionSettings,
    SortKey,
    StatementSource,
)
from attestql.kernel.ports import QueryExecutor
from attestql.kernel.types import (
    BoundParameter,
    ColumnType,
    ExecutionContext,
    ExecutionLimits,
    ExecutionResult,
    ProjectedColumnWidth,
    ResultWidthProof,
    ValidatedStatement,
    admit,
)

CLOCK = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
QUESTION_SET_VERSION = "sha256:question-set-under-test"
BACKEND = "PostgreSQL 16.4 on x86_64, backend 4711"
ROWS: tuple[tuple[object, ...], ...] = ((68,),)

SQL = (
    "SELECT count(DISTINCT account_id) AS active_accounts FROM usage_event "
    "WHERE event_ts >= $1 AND event_ts < $2"
)
CHECKS = ("single_statement", "select_only", "parameter_shape")
PARAMETERS = (
    BoundParameter(1, CLOCK - timedelta(days=30), "timestamptz"),
    BoundParameter(2, CLOCK, "timestamptz"),
)
WIDTH_PROOF = ResultWidthProof(
    columns=(ProjectedColumnWidth("active_accounts", "int8", 20, 8),),
    policy_version="width-policy-under-test",
)
QUESTION = QuestionMetadata(
    question_id="q-under-test",
    question_set="question-set-under-test",
    question_text="How many accounts were active in the last 30 days?",
    evidence_text="",
)
SETTINGS = SessionSettings(
    engine=ENGINE_POSTGRESQL,
    time_zone="UTC",
    date_style="ISO, MDY",
    interval_style="postgres",
    extra_float_digits="1",
    database_collation="en_US.UTF-8",
    recorded={"statement_timeout": "5000", "server_version_num": "160004"},
)
SOURCE = StatementSource(
    path="questions-under-test.json",
    digest="sha256:question-file-under-test",
    origin="https://example.org/questions-under-test.json",
    date="2026-01-18",
)
FIXTURE = FixtureDigest(
    schema_digest="sha256:schema-under-test",
    row_counts={"usage_event": 4},
    content_digests={},
    source_file_sha256="",
)


class _StubExecutor:
    """Reports a fixed result, the limits it was told were in force, and its identity."""

    def __init__(self, limits: ExecutionLimits, *, backend: str = BACKEND) -> None:
        self._limits = limits
        self._backend = backend

    def execute(self, statement: ValidatedStatement, context: ExecutionContext) -> ExecutionResult:
        assert statement.sql == SQL
        assert context.authorized_tenant
        return ExecutionResult(
            columns=(ColumnType("active_accounts", "bigint"),),
            rows=ROWS,
            backend_identity=self._backend,
            limits_in_force=self._limits,
            truncated=False,
        )


@pytest.fixture
def execution_limits() -> ExecutionLimits:
    return ExecutionLimits(statement_timeout_ms=5000)


@pytest.fixture
def execution_context() -> ExecutionContext:
    return ExecutionContext(
        request_id="run-under-test",
        authorized_tenant="tenant-under-test",
        tenant_login_role="attestql_readonly_under_test",
        authorization_policy_version="authorization-policy-under-test",
    )


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
def identity() -> ExecutionIdentity:
    return ExecutionIdentity(
        effective_database_role="attestql_readonly_under_test", run_id="run-under-test"
    )


@pytest.fixture
def executed(
    execution_limits: ExecutionLimits, execution_context: ExecutionContext
) -> tuple[ValidatedStatement, ExecutionResult]:
    """One admission and one execution through the port, as a caller would do it."""
    statement = admit(SQL, PARAMETERS, "validator-under-test", CHECKS, WIDTH_PROOF)
    executor: QueryExecutor = _StubExecutor(execution_limits)
    return statement, executor.execute(statement, execution_context)


@pytest.fixture
def build(
    executed: tuple[ValidatedStatement, ExecutionResult],
    identity: ExecutionIdentity,
    serialization_descriptor: SerializationDescriptor,
) -> Any:
    statement, result = executed

    def factory(**overrides: Any) -> EvidenceRecord:
        arguments: dict[str, Any] = dict(
            question_as_asked=QUESTION.question_text,
            question=QUESTION,
            question_set_version=QUESTION_SET_VERSION,
            statement_source=SOURCE,
            statement=statement,
            bound_parameters=statement.parameters,
            result=result,
            identity=identity,
            session_settings_in_force=SETTINGS,
            canonical_ordering=(),
            serialization=serialization_descriptor,
            replay_rule=ReplayRule.R_SET,
            fixture=FIXTURE,
            data_as_of=CLOCK,
            executed_at=CLOCK,
            rerun_instruction="re-run against the fixture named in this record",
        )
        arguments.update(overrides)
        return build_evidence_record(**arguments)

    return factory


@pytest.fixture
def make_record(build: Any) -> Any:
    """The same record, constructed directly, so the record's own refusals are reachable."""
    base: EvidenceRecord = build()

    def factory(**overrides: Any) -> EvidenceRecord:
        fields: dict[str, Any] = {
            field.name: getattr(base, field.name) for field in dataclasses.fields(EvidenceRecord)
        }
        fields.update(overrides)
        return EvidenceRecord(**fields)

    return factory


def test_a_record_is_built_from_an_execution_through_the_kernel_ports(build: Any) -> None:
    record = build()
    assert isinstance(record, EvidenceRecord)
    for field in dataclasses.fields(EvidenceRecord):
        assert getattr(record, field.name) is not None


def test_every_value_the_execution_states_is_taken_from_the_execution(
    build: Any,
    executed: tuple[ValidatedStatement, ExecutionResult],
    identity: ExecutionIdentity,
) -> None:
    statement, result = executed
    record = build()
    assert record.executed_sql == statement.sql
    assert record.bound_parameters == statement.parameters
    assert record.validator_version == statement.validator_version
    assert record.validation_outcome.checks_run == statement.checks_passed
    assert record.backend_identity_at_checkout == result.backend_identity
    assert record.result is result
    assert record.row_count == len(result.rows)
    assert record.effective_database_role == identity.effective_database_role
    assert record.run_id == identity.run_id


def test_the_measurements_the_caller_took_are_the_caller_s_and_not_a_module_constant(
    build: Any,
) -> None:
    """The question, the set it came from, the data and the session are all stated."""
    record = build()
    assert record.question == QUESTION
    assert record.question_as_asked == QUESTION.question_text
    assert record.question_set_version == QUESTION_SET_VERSION
    assert record.statement_source == SOURCE
    assert record.session_settings_in_force == SETTINGS
    assert record.fixture == FIXTURE
    other = build(question_set_version="sha256:another-question-set")
    assert other.question_set_version == "sha256:another-question-set"


def test_the_backend_a_record_names_is_the_one_the_result_reported(
    build: Any,
    execution_limits: ExecutionLimits,
    execution_context: ExecutionContext,
) -> None:
    """Not a value configured beside the run: change the server, change the record."""
    other = "PostgreSQL 16.4 on aarch64, backend 9001"
    statement = admit(SQL, PARAMETERS, "validator-under-test", CHECKS, WIDTH_PROOF)
    executor: QueryExecutor = _StubExecutor(execution_limits, backend=other)
    record = build(statement=statement, result=executor.execute(statement, execution_context))
    assert record.backend_identity_at_checkout == other


def test_a_record_for_a_parameterized_statement_without_its_parameters_cannot_be_built(
    build: Any,
) -> None:
    with pytest.raises(IncompleteEvidence, match="not the parameters the validator admitted"):
        build(bound_parameters=())


def test_a_record_cannot_state_parameter_values_the_validator_did_not_admit(
    build: Any, executed: tuple[ValidatedStatement, ExecutionResult]
) -> None:
    statement, _ = executed
    shifted = tuple(
        BoundParameter(
            parameter.position,
            parameter.value + timedelta(days=1)
            if isinstance(parameter.value, datetime)
            else parameter.value,
            parameter.declared_type,
        )
        for parameter in statement.parameters
    )
    assert shifted != statement.parameters
    with pytest.raises(IncompleteEvidence, match="not the parameters the validator admitted"):
        build(bound_parameters=shifted)


def test_a_statement_whose_placeholders_are_not_all_bound_cannot_be_recorded(build: Any) -> None:
    """The admitted parameter list can be empty while the text still asks for a value."""
    unbound = admit(
        "SELECT count(*) AS n FROM usage_event WHERE event_ts >= $1",
        (),
        "validator-under-test",
        ("single_statement",),
        ResultWidthProof((ProjectedColumnWidth("n", "int8", 20, 8),), "width-policy-under-test"),
    )
    with pytest.raises(IncompleteEvidence, match="placeholders"):
        build(statement=unbound, bound_parameters=())


def test_a_record_cannot_state_a_row_count_its_own_result_contradicts(make_record: Any) -> None:
    """One result, one size. The builder takes the count from the rows for this reason."""
    with pytest.raises(ValueError, match="row_count states 99"):
        make_record(row_count=99)


def test_a_record_with_no_declared_replay_rule_is_rejected(build: Any, make_record: Any) -> None:
    with pytest.raises(ValueError, match="must declare its replay rule"):
        build(replay_rule=None)
    with pytest.raises(ValueError, match="must declare its replay rule"):
        make_record(replay_rule=None)


def test_an_ordered_record_states_the_ordering_and_an_unordered_one_states_none(
    make_record: Any,
) -> None:
    with pytest.raises(ValueError, match="R-ORD requires a canonical ordering"):
        make_record(replay_rule=ReplayRule.R_ORD, canonical_ordering=())
    with pytest.raises(ValueError, match="row order is not part of the contract"):
        make_record(canonical_ordering=(SortKey("active_accounts", descending=True),))


def test_a_record_states_where_the_statement_it_ran_was_read_from(make_record: Any) -> None:
    """The path and the digest are measured and required; what the run was told about the
    file may be nothing, and nothing is a value here."""
    for name in ("path", "digest"):
        with pytest.raises(ValueError, match=f"{name} is required"):
            make_record(statement_source=dataclasses.replace(SOURCE, **{name: ""}))
    told_nothing = make_record(statement_source=dataclasses.replace(SOURCE, origin=None, date=None))
    assert told_nothing.statement_source.origin is None
    assert told_nothing.statement_source.date is None


def test_a_record_states_the_question_it_answers(make_record: Any) -> None:
    """The identity and the set are required; the hint may be empty and is never absent."""
    with pytest.raises(ValueError, match="question_id"):
        make_record(question=dataclasses.replace(QUESTION, question_id=""))
    with pytest.raises(ValueError, match="question_set"):
        make_record(question=dataclasses.replace(QUESTION, question_set=""))
    assert make_record(question=dataclasses.replace(QUESTION, evidence_text="")) is not None


@pytest.mark.parametrize(
    "field",
    [
        "question_as_asked",
        "question_set_version",
        "executed_sql",
        "validator_version",
        "effective_database_role",
        "backend_identity_at_checkout",
        "run_id",
        "rerun_instruction",
    ],
)
def test_every_field_a_record_states_in_words_is_required(make_record: Any, field: str) -> None:
    with pytest.raises(ValueError, match=f"{field} is required"):
        make_record(**{field: ""})


def test_a_record_states_the_session_it_ran_under_and_the_data_it_read(make_record: Any) -> None:
    with pytest.raises(ValueError, match="time_zone is required"):
        make_record(session_settings_in_force=dataclasses.replace(SETTINGS, time_zone=""))
    with pytest.raises(ValueError, match="database_collation is required"):
        make_record(session_settings_in_force=dataclasses.replace(SETTINGS, database_collation=""))
    with pytest.raises(ValueError, match="recorded must state"):
        make_record(session_settings_in_force=dataclasses.replace(SETTINGS, recorded={}))
    with pytest.raises(ValueError, match="schema_digest is required"):
        make_record(fixture=dataclasses.replace(FIXTURE, schema_digest=""))


def test_no_evidence_record_field_carries_a_default() -> None:
    """A defaulted field is a field a caller can leave for later and never state."""
    for field in dataclasses.fields(EvidenceRecord):
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING


def test_no_question_metadata_or_measurement_field_carries_a_default() -> None:
    for shape in (QuestionMetadata, SessionSettings, FixtureDigest):
        for field in dataclasses.fields(shape):
            assert field.default is dataclasses.MISSING
            assert field.default_factory is dataclasses.MISSING


def test_the_record_holds_exactly_the_fields_adr_0013_re_cut_it_to() -> None:
    """Twenty-one fields: the twenty ADR-0013 re-cut the record to, and the source of the
    statement each one is a record of."""
    assert tuple(field.name for field in dataclasses.fields(EvidenceRecord)) == (
        "question_as_asked",
        "question",
        "question_set_version",
        "statement_source",
        "executed_sql",
        "bound_parameters",
        "validation_outcome",
        "validator_version",
        "effective_database_role",
        "backend_identity_at_checkout",
        "session_settings_in_force",
        "result",
        "row_count",
        "canonical_ordering",
        "serialization",
        "replay_rule",
        "fixture",
        "data_as_of",
        "executed_at",
        "run_id",
        "rerun_instruction",
    )


def test_the_two_instants_a_record_states_must_be_utc(build: Any) -> None:
    with pytest.raises(ValueError, match="executed_at"):
        build(executed_at=datetime(2026, 7, 15, 0, 0, tzinfo=None))
    with pytest.raises(ValueError, match="data_as_of"):
        build(data_as_of=datetime(2026, 7, 15, 0, 0, tzinfo=None))
    assert build(executed_at=datetime(2026, 7, 15, 12, tzinfo=UTC)) is not None


def test_the_mappings_a_record_holds_cannot_be_edited_through_it(build: Any) -> None:
    record = build()
    with pytest.raises(TypeError):
        record.fixture.row_counts["usage_event"] = 5  # pyright: ignore[reportIndexIssue]  # read-only by design
    with pytest.raises(TypeError):
        record.session_settings_in_force.recorded["search_path"] = "public"  # pyright: ignore[reportIndexIssue]  # read-only by design
