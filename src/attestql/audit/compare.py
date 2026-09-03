"""Comparing a gold statement with a second statement on one database.

The rule is read off the gold, not chosen: R-ORD when the gold carries a top-level ORDER
BY, R-SET when it does not. The ordering both records are recorded under is the gold's,
so the comparison is between two answers and not between two ORDER BY clauses; each
statement's own ordering is kept beside the verdict as data, because a disagreement about
ordering is half of what a reader is being shown.

The second statement is supplied and never generated: a model's prediction, an upstream
correction, a human's fix. What comes back is a verdict, the records both executions
produced, and the rows each result holds that the other does not.

NOT_EQUAL says that these two statements disagree on this data under this rule. It does
not say which of them is wrong, and nothing in this module decides that. NOT_COMPARABLE
says a precondition differed and names it, which is not a disagreement at all.

The two projections are compared by position and declared type, so a prediction that names
its columns differently is not a disagreement either. The names both results carry are
written into the counterexample when they differ, beside the verdict rather than under it,
because a reader who sees two column lists side by side should be told they were not what
was compared instead of working it out.

``bird_ex`` is computed beside the verdict because a counterexample has to state what the
benchmark's own evaluator would say about the same two results. Where the two disagree,
that difference is the point.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from attestql.audit.backend import Backend
from attestql.audit.fixture import fixture_digest
from attestql.audit.statements import (
    CHECKS_PASSED,
    VALIDATOR_VERSION,
    OrderingKey,
    ParsedStatement,
    StatementRefused,
    parse_statement,
)
from attestql.evidence.build import ExecutionIdentity, build_evidence_record
from attestql.evidence.record import EvidenceRecord
from attestql.evidence.render import (
    Json,
    RowDifference,
    record_json,
    result_digest,
    result_json,
    row_difference,
    row_difference_json,
    statement_source_json,
    write_json,
)
from attestql.evidence.replay import ComparabilityVerdict, compare_r_ord, compare_r_set
from attestql.evidence.serialize import SerializationDescriptor
from attestql.evidence.types import (
    FixtureDigest,
    QuestionMetadata,
    ReplayRule,
    SessionSettings,
    SortKey,
    StatementSource,
)
from attestql.kernel.types import (
    ExecutionResult,
    ProjectedColumnWidth,
    ResultWidthProof,
    ValidatedStatement,
    admit,
)

DEFAULT_STATEMENT_TIMEOUT_SECONDS = 30
"""How long one statement of an audit may run. Set on the session and read back."""

WIDTH_POLICY_VERSION = "audit:observed-widths"
"""What the width proof on an audited statement is, named for what it is.

A real proof bounds a projection before the statement is sent, from a policy over a known
schema. An audit runs arbitrary benchmark SQL against a database it did not design and has
no such policy, so the widths are measured from the rendering of what came back. The
record does not carry this: ADR-0013 dropped ``policy_version`` because a version naming a
measurement taken after the fact states nothing a reader can rely on. It exists because
``admit`` requires a proof, and it is named so that nothing here reads as one."""

COUNTEREXAMPLE_FORMAT = "attestql/audit/counterexample/1"
COUNTEREXAMPLE_FILE = "counterexample.json"
GOLD_RECORD_FILE = "evidence-gold.json"
SECOND_RECORD_FILE = "evidence-second.json"

BIRD_EX_METHOD = "set(second_rows) == set(gold_rows)"
BIRD_EX_SOURCE = "https://github.com/bird-bench/mini_dev/blob/main/evaluation/evaluation_ex.py"

VERDICT_READING = (
    "NOT_EQUAL states that these two statements disagree on this data under this rule. It "
    "does not state which of them is wrong."
)

PROJECTION_NAMES_READING = (
    "The two statements name their result columns differently. A projection is compared by "
    "position and declared type, so these names did not decide the verdict. They are part of "
    "the canonical rendering each result is hashed under, so the two result hashes differ "
    "with them."
)
"""What a reader is told when a counterexample carries two projections named differently:
what those names are, and what they are not."""


@dataclass(frozen=True)
class BirdEx:
    """What BIRD's own evaluator would say about the same two results.

    ``calculate_ex`` is ``1`` when ``set(predicted) == set(gold)`` over the row tuples and
    ``0`` otherwise. It is computed here rather than imported so that what this tool claims
    the benchmark says is visible in one expression, and it is recorded beside the verdict
    so a reader can see the two answers side by side.
    """

    value: int
    equal: bool
    gold_rows: int
    second_rows: int
    gold_distinct_rows: int
    second_distinct_rows: int


@dataclass(frozen=True)
class RecordedStatement:
    """One statement, executed once, with what was read off it and what it produced.

    The gold-only mode of ADR-0013 point 2 has no second statement to compare with and
    still has to hold both: the smells read the parse, and the directory a fired smell
    writes holds the record.
    """

    parsed: ParsedStatement
    record: EvidenceRecord


@dataclass(frozen=True)
class Comparison:
    """One gold and one second statement, executed and compared, with the evidence."""

    question: QuestionMetadata
    replay_rule: ReplayRule
    verdict: ComparabilityVerdict
    gold: EvidenceRecord
    second: EvidenceRecord
    gold_result_hash: str
    second_result_hash: str
    differing_rows: RowDifference
    gold_ordering: tuple[OrderingKey, ...]
    second_ordering: tuple[OrderingKey, ...]
    bird_ex: BirdEx


def bird_ex(
    gold_rows: Sequence[tuple[object, ...]], second_rows: Sequence[tuple[object, ...]]
) -> BirdEx:
    """BIRD's execution-accuracy check over the two row sets."""
    equal = set(second_rows) == set(gold_rows)
    return BirdEx(
        value=1 if equal else 0,
        equal=equal,
        gold_rows=len(gold_rows),
        second_rows=len(second_rows),
        gold_distinct_rows=len(set(gold_rows)),
        second_distinct_rows=len(set(second_rows)),
    )


def bird_ex_json(measured: BirdEx) -> Json:
    return {
        "value": measured.value,
        "equal": measured.equal,
        "method": BIRD_EX_METHOD,
        "source": BIRD_EX_SOURCE,
        "gold_rows": measured.gold_rows,
        "second_rows": measured.second_rows,
        "gold_distinct_rows": measured.gold_distinct_rows,
        "second_distinct_rows": measured.second_distinct_rows,
    }


def width_proof(
    result: ExecutionResult, serialization: SerializationDescriptor
) -> ResultWidthProof:
    """The widths this execution measured, which is not the same thing as a width proof."""
    widths: list[ProjectedColumnWidth] = []
    for index, column in enumerate(result.columns):
        widest = _widest(result, index, serialization)
        widths.append(
            ProjectedColumnWidth(
                name=column.name,
                pg_type=column.pg_type,
                max_encoded_bytes=widest,
                max_decoded_bytes=widest,
            )
        )
    return ResultWidthProof(columns=tuple(widths), policy_version=WIDTH_POLICY_VERSION)


def _widest(result: ExecutionResult, index: int, serialization: SerializationDescriptor) -> int:
    cells = (
        len(serialization.render_value(row[index]).encode(serialization.encoding))
        for row in result.rows
    )
    return max((*cells, 1))


def _admitted(
    parsed: ParsedStatement, result: ExecutionResult, serialization: SerializationDescriptor
) -> ValidatedStatement:
    return admit(
        parsed.sql, (), VALIDATOR_VERSION, CHECKS_PASSED, width_proof(result, serialization)
    )


def _execute_and_record(
    parsed: ParsedStatement,
    *,
    question: QuestionMetadata,
    question_set_version: str,
    statement_source: StatementSource,
    backend: Backend,
    serialization: SerializationDescriptor,
    identity: ExecutionIdentity,
    settings: SessionSettings,
    fixture: FixtureDigest,
    rule: ReplayRule,
    ordering: tuple[SortKey, ...],
    rerun_instruction: str,
    data_as_of: datetime,
    statement_timeout_seconds: int,
) -> EvidenceRecord:
    """Run one statement and state, in one record, everything that produced its rows.

    The rule and the ordering are arguments and not read off ``parsed``, because the two
    sides of a comparison are recorded under the gold's rule and the gold's ordering; a
    record that stated its own would make the comparison a comparison of rules.
    """
    result = backend.execute(parsed.sql, statement_timeout_seconds=statement_timeout_seconds)
    if not result.columns:
        # PostgreSQL accepts a bare SELECT and answers it with one row of no columns, which
        # is what a model that predicted nothing at all reaches this with. There is no
        # projection to compare, to record or to hash, so it is refused the way a statement
        # that did not parse is.
        raise StatementRefused(
            "the statement projects no column, so there is no answer to record or compare"
        )
    # The clock is this process's, taken the moment the rows came back: the interface a
    # second engine implements does not promise a server clock, and a record says when the
    # audit ran the statement rather than what the server thought the time was.
    executed_at = datetime.now(UTC)
    return build_evidence_record(
        question_as_asked=question.question_text,
        question=question,
        question_set_version=question_set_version,
        statement_source=statement_source,
        statement=_admitted(parsed, result, serialization),
        bound_parameters=(),
        result=result,
        identity=identity,
        session_settings_in_force=settings,
        canonical_ordering=ordering,
        serialization=serialization,
        replay_rule=rule,
        fixture=fixture,
        data_as_of=data_as_of,
        executed_at=executed_at,
        rerun_instruction=rerun_instruction,
    )


def record_statement(
    *,
    question: QuestionMetadata,
    question_set_version: str,
    statement_source: StatementSource,
    sql: str,
    backend: Backend,
    serialization: SerializationDescriptor,
    run_id: str,
    directory: Path,
    data_as_of: datetime,
    statement_timeout_seconds: int = DEFAULT_STATEMENT_TIMEOUT_SECONDS,
    with_content_digests: bool = False,
    source_file: Path | None = None,
) -> RecordedStatement:
    """Execute one statement under its own rule and record it, with nothing to compare.

    Raises ``StatementRefused`` when the text is not a single SELECT this audit can run,
    and ``BackendRefused`` when the backend will not stand behind the result.
    """
    parsed = parse_statement(sql)
    rule = parsed.replay_rule
    fixture = fixture_digest(
        backend,
        parsed.tables,
        directory=directory,
        with_content_digests=with_content_digests,
        source_file=source_file,
    )
    record = _execute_and_record(
        parsed,
        question=question,
        question_set_version=question_set_version,
        statement_source=statement_source,
        backend=backend,
        serialization=serialization,
        identity=ExecutionIdentity(
            effective_database_role=backend.effective_database_role(), run_id=run_id
        ),
        settings=backend.session_settings(),
        fixture=fixture,
        rule=rule,
        ordering=parsed.sort_keys if rule is ReplayRule.R_ORD else (),
        rerun_instruction=_rerun_instruction(backend.identity(), rule),
        data_as_of=data_as_of,
        statement_timeout_seconds=statement_timeout_seconds,
    )
    return RecordedStatement(parsed=parsed, record=record)


def _rerun_instruction(backend_identity: str, rule: ReplayRule) -> str:
    return (
        f"re-run this statement read-only against {backend_identity} under the session "
        "settings and over the data this record's fixture digest names, and compare the "
        f"two results under {rule.value}"
    )


def compare_statements(
    *,
    question: QuestionMetadata,
    question_set_version: str,
    gold_sql: str,
    gold_source: StatementSource,
    second_sql: str,
    second_source: StatementSource,
    backend: Backend,
    serialization: SerializationDescriptor,
    run_id: str,
    directory: Path,
    data_as_of: datetime,
    statement_timeout_seconds: int = DEFAULT_STATEMENT_TIMEOUT_SECONDS,
    with_content_digests: bool = False,
    source_file: Path | None = None,
) -> Comparison:
    """Execute both statements on one backend and compare them under the gold's rule.

    Raises ``StatementRefused`` when either text is not a single SELECT this audit can
    run, and ``BackendRefused`` when the backend will not stand behind a result.
    """
    gold_parsed = parse_statement(gold_sql)
    second_parsed = parse_statement(second_sql)
    rule = gold_parsed.replay_rule
    ordering = gold_parsed.sort_keys if rule is ReplayRule.R_ORD else ()
    tables = (*gold_parsed.tables, *second_parsed.tables)
    fixture = fixture_digest(
        backend,
        tables,
        directory=directory,
        with_content_digests=with_content_digests,
        source_file=source_file,
    )
    settings = backend.session_settings()
    identity = ExecutionIdentity(
        effective_database_role=backend.effective_database_role(), run_id=run_id
    )
    rerun = _rerun_instruction(backend.identity(), rule)

    def record_of(parsed: ParsedStatement, source: StatementSource) -> EvidenceRecord:
        return _execute_and_record(
            parsed,
            question=question,
            question_set_version=question_set_version,
            statement_source=source,
            backend=backend,
            serialization=serialization,
            identity=identity,
            settings=settings,
            fixture=fixture,
            rule=rule,
            ordering=ordering,
            rerun_instruction=rerun,
            data_as_of=data_as_of,
            statement_timeout_seconds=statement_timeout_seconds,
        )

    gold_record = record_of(gold_parsed, gold_source)
    second_record = record_of(second_parsed, second_source)
    verdict = (
        compare_r_ord(gold_record, second_record)
        if rule is ReplayRule.R_ORD
        else compare_r_set(gold_record, second_record)
    )
    return Comparison(
        question=question,
        replay_rule=rule,
        verdict=verdict,
        gold=gold_record,
        second=second_record,
        gold_result_hash=result_digest(gold_record.result, serialization),
        second_result_hash=result_digest(second_record.result, serialization),
        differing_rows=row_difference(gold_record.result.rows, second_record.result.rows),
        gold_ordering=gold_parsed.ordering,
        second_ordering=second_parsed.ordering,
        bird_ex=bird_ex(gold_record.result.rows, second_record.result.rows),
    )


def _ordering_json(ordering: Sequence[OrderingKey]) -> list[Json]:
    return [
        {"expression": key.expression, "descending": key.descending, "nulls": key.nulls}
        for key in ordering
    ]


def _fixture_json(fixture: FixtureDigest) -> Json:
    return {
        "schema_digest": fixture.schema_digest,
        "row_counts": dict(fixture.row_counts),
        "content_digests": dict(fixture.content_digests),
        "source_file_sha256": fixture.source_file_sha256,
    }


def _projection_names(result: ExecutionResult) -> tuple[str, ...]:
    """The column names in order, as the execution reported them: evidence, never a verdict.

    Read here and nowhere in the comparison. ``replay`` matches a projection by position and
    declared type, so this is the one place a name is looked at at all.
    """
    return tuple(column.name for column in result.columns)


def _projection_names_note(comparison: Comparison) -> Json:
    """The column names of both results, when the two projections disagree on them.

    Empty when they agree, which is what keeps the note worth reading: a field present on
    every counterexample is one a reader stops seeing, and there is nothing to say when
    both statements named the same columns.
    """
    gold = _projection_names(comparison.gold.result)
    second = _projection_names(comparison.second.result)
    if gold == second:
        return {}
    return {
        "projection_names_differ": {
            "gold": list(gold),
            "second": list(second),
            "reading": PROJECTION_NAMES_READING,
        }
    }


def counterexample_json(comparison: Comparison) -> Json:
    """The comparison as one document: the verdict, both sides, and what differs."""
    serialization = comparison.gold.serialization
    return {
        "format": COUNTEREXAMPLE_FORMAT,
        "question": {
            "question_id": comparison.question.question_id,
            "question_set": comparison.question.question_set,
            "question_text": comparison.question.question_text,
            "evidence_text": comparison.question.evidence_text,
        },
        "question_set_version": comparison.gold.question_set_version,
        "sources": {
            "gold": statement_source_json(comparison.gold.statement_source),
            "second": statement_source_json(comparison.second.statement_source),
        },
        "replay_rule": comparison.replay_rule.value,
        "verdict": {
            "result": comparison.verdict.result.value,
            "mismatched": list(comparison.verdict.mismatched),
            "reading": VERDICT_READING,
        },
        **_projection_names_note(comparison),
        "bird_ex": bird_ex_json(comparison.bird_ex),
        "gold": {
            "executed_sql": comparison.gold.executed_sql,
            "own_ordering": _ordering_json(comparison.gold_ordering),
            "result": result_json(comparison.gold.result, serialization),
            "record": GOLD_RECORD_FILE,
        },
        "second": {
            "executed_sql": comparison.second.executed_sql,
            "own_ordering": _ordering_json(comparison.second_ordering),
            "result": result_json(comparison.second.result, comparison.second.serialization),
            "record": SECOND_RECORD_FILE,
        },
        "canonical_ordering": [
            {"column": key.column, "descending": key.descending}
            for key in comparison.gold.canonical_ordering
        ],
        "differing_rows": row_difference_json(
            comparison.differing_rows,
            left_key="in_gold_not_in_second",
            right_key="in_second_not_in_gold",
        ),
        "result_hashes": {
            "gold": comparison.gold_result_hash,
            "second": comparison.second_result_hash,
        },
        "backend_identity": comparison.gold.backend_identity_at_checkout,
        "fixture": _fixture_json(comparison.gold.fixture),
        "run_id": comparison.gold.run_id,
    }


def write_comparison(comparison: Comparison, directory: Path) -> None:
    """The counterexample and both evidence records, as three files in one directory."""
    write_json(directory / COUNTEREXAMPLE_FILE, counterexample_json(comparison))
    write_json(directory / GOLD_RECORD_FILE, record_json(comparison.gold))
    write_json(directory / SECOND_RECORD_FILE, record_json(comparison.second))


__all__ = [
    "BIRD_EX_METHOD",
    "COUNTEREXAMPLE_FILE",
    "COUNTEREXAMPLE_FORMAT",
    "DEFAULT_STATEMENT_TIMEOUT_SECONDS",
    "GOLD_RECORD_FILE",
    "PROJECTION_NAMES_READING",
    "SECOND_RECORD_FILE",
    "VERDICT_READING",
    "WIDTH_POLICY_VERSION",
    "BirdEx",
    "Comparison",
    "RecordedStatement",
    "bird_ex",
    "bird_ex_json",
    "compare_statements",
    "counterexample_json",
    "record_statement",
    "width_proof",
    "write_comparison",
]
