"""The evidence record: one execution of one statement, stated in full.

Every field is required and nothing is defaulted. A record that cannot state its
replay rule, the data it read or the session it read it under is not constructible,
which is the whole of the guarantee: a reader never has to ask what a missing field
would have said.

ADR-0013 re-cut the record for a benchmark comparison. Nine fields of the released
answer went with the product path they served: the subject an answer was released to,
the credential and the operation it was released under, the tenant and the row-level
security context it was scoped by, the mapping and authorization policy versions that
decided those, the width policy version that admitted its projection, and the
evaluation clock a relative window would have resolved against. None of them has a
counterpart in a benchmark row, and a field carrying a marker that says so states
nothing a reader can rely on.

What replaced them says what a comparison needs. ``session_settings_in_force`` names
the seven settings that change rendered bytes or row order and records the rest.
``fixture`` is a digest of the data the statement actually read, taken from the server
rather than from a constant beside it, which is what the retired ``schema_version``
could never honestly hold. ``question_set_version`` is the one version a benchmark row
has: the set it was read from. ``statement_source`` is the file this record's own statement
was read from, with its digest and whatever the run was told about where that file came
from; for a prediction that is not the file the question came from. ``executed_at`` and
``row_count`` are the two values the old execution metadata carried that were not already
stated elsewhere; the database identity it also held is ``backend_identity_at_checkout``
and one record holding one value twice is a record that can disagree with itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from attestql.contract.clock import require_utc
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


@dataclass(frozen=True)
class ValidationOutcome:
    """Which validation checks ran and that all passed."""

    checks_run: tuple[str, ...]
    all_passed: bool

    def __post_init__(self) -> None:
        if not self.checks_run:
            raise ValueError("at least one validation check must be recorded")


@dataclass(frozen=True)
class EvidenceRecord:
    question_as_asked: str
    question: QuestionMetadata
    question_set_version: str
    statement_source: StatementSource
    executed_sql: str
    bound_parameters: tuple[BoundParameter, ...]
    validation_outcome: ValidationOutcome
    validator_version: str
    effective_database_role: str
    backend_identity_at_checkout: str
    session_settings_in_force: SessionSettings
    result: ExecutionResult
    row_count: int
    canonical_ordering: tuple[SortKey, ...]
    serialization: SerializationDescriptor
    replay_rule: ReplayRule
    fixture: FixtureDigest
    data_as_of: datetime
    executed_at: datetime
    run_id: str
    rerun_instruction: str

    def __post_init__(self) -> None:
        if not isinstance(self.replay_rule, ReplayRule):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            raise ValueError("an evidence record must declare its replay rule")
        for name in (
            "question_as_asked",
            "question_set_version",
            "executed_sql",
            "validator_version",
            "effective_database_role",
            "backend_identity_at_checkout",
            "run_id",
            "rerun_instruction",
        ):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")
        if self.validation_outcome.all_passed is not True:
            raise ValueError(
                "a record exists only for a statement whose validation passed; "
                "a failure is never rendered as an answer"
            )
        if (
            not isinstance(self.row_count, int)  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            or isinstance(self.row_count, bool)
            or self.row_count < 0
        ):
            raise ValueError("row_count must be a non-negative int")
        if self.row_count != len(self.result.rows):
            # The count and the rows are one statement about one result, so a record
            # that could hold two of them could disagree with itself about its own size.
            raise ValueError(
                f"row_count states {self.row_count} for a result of {len(self.result.rows)} rows"
            )
        require_utc(self.data_as_of, "data_as_of")
        require_utc(self.executed_at, "executed_at")
        if self.replay_rule is ReplayRule.R_ORD and not self.canonical_ordering:
            raise ValueError("R-ORD requires a canonical ordering")
        if self.replay_rule is ReplayRule.R_SET and self.canonical_ordering:
            raise ValueError("R-SET states that row order is not part of the contract")


__all__ = ["EvidenceRecord", "ValidationOutcome"]
