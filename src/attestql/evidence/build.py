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
    StatementSource,
)
from attestql.kernel.types import BoundParameter, ExecutionResult

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


def _require_the_parameters_the_sql_binds(
    executed_sql: str, bound_parameters: tuple[BoundParameter, ...]
) -> tuple[BoundParameter, ...]:
    """The parameters this record states, once the SQL's own placeholders cover them.

    Until 2026-09-14 this also compared them with the parameters a validator had admitted,
    which is the half that went with the admission: nothing admitted a statement before it
    ran, so the second list was built from the first and could not disagree with it. What is
    left is the check that was ever about the record. A record whose SQL names ``$1`` and
    ``$2`` and whose parameters are ``$1`` alone is a record nobody can re-run.
    """
    stated = _by_position(tuple(bound_parameters))
    placeholders = {int(position) for position in _PLACEHOLDER.findall(executed_sql)}
    positions = {parameter.position for parameter in stated}
    if placeholders != positions:
        raise IncompleteEvidence(
            "the executed SQL's placeholders and its bound parameters do not cover each "
            f"other: placeholders {sorted(placeholders)}, parameters {sorted(positions)}"
        )
    return stated


def build_evidence_record(
    *,
    question_as_asked: str,
    question: QuestionMetadata,
    question_set_version: str,
    statement_source: StatementSource,
    executed_sql: str,
    validator_version: str,
    checks_passed: tuple[str, ...],
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

    ``executed_sql`` and ``result`` are the execution, and ``validator_version`` and
    ``checks_passed`` name the parser that read the statement and what it checked, which is
    what the record states about how it was read. ``statement_source`` is the file the
    statement's text was read from, which only the caller that opened it knows. ``fixture``
    and ``session_settings_in_force`` are what was measured on the server the statement
    read, so a comparison can say whether two records are about the same data read
    under the same rules; the caller that took those measurements states them.

    The four arrived as one ``ValidatedStatement`` until 2026-09-14, built by ``admit`` after
    the statement had already run. A validated statement is a promise that what the validator
    admitted is what reached the wire, and an admission taken afterwards is not that promise,
    so the record now takes the values it states and nothing that reads as a guarantee.
    """
    stated_parameters = _require_the_parameters_the_sql_binds(executed_sql, bound_parameters)
    return EvidenceRecord(
        question_as_asked=question_as_asked,
        question=question,
        question_set_version=question_set_version,
        statement_source=statement_source,
        executed_sql=executed_sql,
        bound_parameters=stated_parameters,
        validation_outcome=ValidationOutcome(checks_passed, True),
        validator_version=validator_version,
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
