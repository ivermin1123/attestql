"""Building a complete evidence record from one real execution.

Every field of ``EvidenceRecord`` is either taken from what the execution itself
produced or handed in as a value only the caller can know. Nothing is defaulted
and nothing is invented, so there is no partly built record and no field a caller
can leave for later: a record either states all of it or is not constructed.

Where the run states a value, that is the value used, and the caller cannot
supply another. The executed SQL is the admitted statement's text rather than a
reconstruction of it; the validator identity and the checks that passed are the
admitted statement's own; the backend identity and the row count are what the
result reported. A configured constant standing beside the run and echoed into the
record would state what the deployment was meant to be rather than what the run
was, which is the defect this module exists to make unreachable.

Two cross-checks refuse a record whose stated inputs contradict the execution.
The bound parameters the caller states must be exactly the parameters the
validator admitted, which is what stops the failure the plan names: a record that
stores the question and the SQL but not the bound parameters. And the executed
SQL's own placeholders must be exactly those parameters, so a statement admitted
with no parameters whose text still carries ``$1`` is refused here rather than
recorded as evidence that cannot be replayed.

The third cross-check went with ADR-0013. It compared the limits the product fixed
for a request against the limits the result read back, and there is no second place
that fixes limits now: the executor sets its own timeout, reads it back and refuses
the execution on drift, so the value on the result has already been checked against
the value asked for by the only party that asked for it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from attestql.evidence.record import EvidenceRecord, ValidationOutcome
from attestql.evidence.serialize import SerializationDescriptor
from attestql.evidence.types import (
    FixtureDigest,
    QuestionMetadata,
    ReplayRule,
    SessionSettings,
    SortKey,
)
from attestql.kernel.types import BoundParameter, ExecutionResult, ValidatedStatement

_PLACEHOLDER = re.compile(r"\$(\d+)")
"""Every ``$n`` the executed text carries. A statement that quotes text containing one
is refused rather than recorded with a parameter list that does not cover its own
placeholders."""


class IncompleteEvidence(ValueError):
    """The record cannot be built, so no record is built.

    Raised in place of a record with a field filled from something other than the
    run that produced it. Every case is a contradiction between what the caller
    states and what the execution reports, and a record carrying either half of a
    contradiction is evidence of nothing.
    """


@dataclass(frozen=True)
class ExecutionIdentity:
    """The two values about an execution that the result itself does not report.

    The role decides what the statement could read, so two executions run under
    different roles are not comparable evidence; the run identifier says which run
    produced the record. Both are read from the session and the run rather than
    configured beside them, and they are carried here rather than checked: the record
    is what refuses an empty one, and a second check beside it could only disagree.
    """

    effective_database_role: str
    run_id: str


def _by_position(parameters: tuple[BoundParameter, ...]) -> tuple[BoundParameter, ...]:
    return tuple(sorted(parameters, key=lambda parameter: parameter.position))


def _require_stated_parameters(
    statement: ValidatedStatement, bound_parameters: tuple[BoundParameter, ...]
) -> tuple[BoundParameter, ...]:
    """The admitted parameters, once the caller has stated the same ones.

    Compared on the whole parameter and not on the shape alone: two runs of one
    statement share a shape and differ in the values they bound, and a record naming
    the wrong values is a record of a different execution.
    """
    admitted = _by_position(statement.parameters)
    stated = _by_position(tuple(bound_parameters))
    if stated != admitted:
        raise IncompleteEvidence(
            "the bound parameters stated for this record are not the parameters the "
            f"validator admitted: stated {stated!r}, admitted {admitted!r}"
        )
    placeholders = {int(position) for position in _PLACEHOLDER.findall(statement.sql)}
    positions = {parameter.position for parameter in admitted}
    if placeholders != positions:
        raise IncompleteEvidence(
            "the executed SQL's placeholders and its bound parameters do not cover each "
            f"other: placeholders {sorted(placeholders)}, parameters {sorted(positions)}"
        )
    return admitted


def build_evidence_record(
    *,
    question_as_asked: str,
    question: QuestionMetadata,
    question_set_version: str,
    statement: ValidatedStatement,
    bound_parameters: tuple[BoundParameter, ...],
    result: ExecutionResult,
    identity: ExecutionIdentity,
    session_settings_in_force: SessionSettings,
    canonical_ordering: tuple[SortKey, ...],
    serialization: SerializationDescriptor,
    replay_rule: ReplayRule,
    fixture: FixtureDigest,
    data_as_of: datetime,
    executed_at: datetime,
    rerun_instruction: str,
) -> EvidenceRecord:
    """A complete ``EvidenceRecord`` for one execution.

    ``statement`` and ``result`` are the execution. ``fixture`` and
    ``session_settings_in_force`` are what was measured on the server the statement
    read, so a comparison can say whether two records are about the same data read
    under the same rules; the caller that took those measurements states them.
    """
    admitted_parameters = _require_stated_parameters(statement, bound_parameters)
    return EvidenceRecord(
        question_as_asked=question_as_asked,
        question=question,
        question_set_version=question_set_version,
        executed_sql=statement.sql,
        bound_parameters=admitted_parameters,
        validation_outcome=ValidationOutcome(statement.checks_passed, True),
        validator_version=statement.validator_version,
        effective_database_role=identity.effective_database_role,
        backend_identity_at_checkout=result.backend_identity,
        session_settings_in_force=session_settings_in_force,
        result=result,
        row_count=len(result.rows),
        canonical_ordering=canonical_ordering,
        serialization=serialization,
        replay_rule=replay_rule,
        fixture=fixture,
        data_as_of=data_as_of,
        executed_at=executed_at,
        run_id=identity.run_id,
        rerun_instruction=rerun_instruction,
    )


__all__ = ["ExecutionIdentity", "IncompleteEvidence", "build_evidence_record"]
