"""Rendering records, results and row differences as JSON a reader can diff.

The rendering is for people and for tools that are not this one, so every cell carries
the tag of the type it came back as: a JSON document that wrote ``1`` for an integer, a
numeric and a boolean would lose exactly the distinction the typed comparison is for.

Nothing here decides anything. The verdict, the rule and the preconditions are computed
in ``replay`` and written out unchanged, and a document that named a field the record
does not have would be a second, quieter statement of what a record is; the coverage
check below refuses that rather than letting the two drift.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from attestql.evidence.record import EvidenceRecord
from attestql.evidence.serialize import (
    SerializationDescriptor,
    canonical_serialize,
    canonical_type_tag,
)
from attestql.evidence.types import StatementSource
from attestql.kernel.types import ExecutionResult

Json = dict[str, Any]
"""A JSON object. ``Any`` is the payload's own type: a document holds strings, numbers,
booleans, nulls, lists and objects, and narrowing that here would only re-state the JSON
grammar in a type the standard library's own encoder does not use."""

ROWS_IN_ARTIFACT = 25
"""How many distinct rows a difference shows per side. The records hold all of them."""


def json_value(value: object) -> Json:
    """One cell as its canonical type tag and a JSON-safe payload."""
    tag = canonical_type_tag(value)
    if value is None:
        payload: object = None
    elif isinstance(value, bool | int | str):
        payload = value
    elif isinstance(value, Decimal):
        payload = format(value, "f")
    elif isinstance(value, datetime):
        payload = value.isoformat()
    else:
        payload = str(value)
    return {"type": tag, "value": payload}


def json_row(row: Sequence[object]) -> list[Json]:
    return [json_value(value) for value in row]


def digest_of(document: Json) -> str:
    """The sha256 of a document with its keys sorted, so a reader can recompute it."""
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def write_json(path: Path, document: Json) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def result_digest(result: ExecutionResult, descriptor: SerializationDescriptor) -> str:
    """The sha256 of the canonical rendering, column names included; R-ORD compares the same
    rendering with each column named by its position, so an alias moves this hash and not
    the verdict."""
    return f"sha256:{hashlib.sha256(canonical_serialize(result, descriptor)).hexdigest()}"


def result_json(
    result: ExecutionResult,
    descriptor: SerializationDescriptor,
    *,
    bound: int = ROWS_IN_ARTIFACT,
) -> Json:
    """A bounded view of a result, with the hash taken over all of it."""
    return {
        "columns": [{"name": c.name, "pg_type": c.pg_type} for c in result.columns],
        "row_count": len(result.rows),
        "truncated": result.truncated,
        "rows_shown": min(bound, len(result.rows)),
        "rows": [json_row(row) for row in result.rows[:bound]],
        "result_hash": result_digest(result, descriptor),
    }


@dataclass(frozen=True)
class RowGroup:
    """One distinct typed row and how many times it occurred."""

    row: tuple[object, ...]
    count: int


@dataclass(frozen=True)
class RowDifference:
    """The two one-sided multiset differences, each bounded, each with its total.

    Bounded for the document and totalled for the truth: a reader sees the first rows of
    each side and is told how many there are, so a difference of thousands of rows is
    never mistaken for a difference of twenty-five.
    """

    only_left: tuple[RowGroup, ...]
    only_left_total: int
    only_right: tuple[RowGroup, ...]
    only_right_total: int
    bound: int


def _multiset(rows: Sequence[tuple[object, ...]]) -> Counter[tuple[tuple[str, object], ...]]:
    """The rows as a multiset of typed cells: the keying the R-SET comparison uses."""
    return Counter(tuple((canonical_type_tag(value), value) for value in row) for row in rows)


def row_difference(
    left: Sequence[tuple[object, ...]],
    right: Sequence[tuple[object, ...]],
    *,
    bound: int = ROWS_IN_ARTIFACT,
) -> RowDifference:
    """What each side holds that the other does not, as multisets of typed rows."""
    counted_left, counted_right = _multiset(left), _multiset(right)
    only_left, only_right = counted_left - counted_right, counted_right - counted_left

    def grouped(difference: Counter[tuple[tuple[str, object], ...]]) -> tuple[RowGroup, ...]:
        items = sorted(difference.items(), key=lambda item: (-item[1], repr(item[0])))
        return tuple(
            RowGroup(row=tuple(value for _, value in row), count=count)
            for row, count in items[:bound]
        )

    return RowDifference(
        only_left=grouped(only_left),
        only_left_total=sum(only_left.values()),
        only_right=grouped(only_right),
        only_right_total=sum(only_right.values()),
        bound=bound,
    )


def row_difference_json(difference: RowDifference, *, left_key: str, right_key: str) -> Json:
    """The difference under the two names the document that holds it calls its sides."""
    return {
        left_key: [
            {"row": json_row(group.row), "count": group.count} for group in difference.only_left
        ],
        f"{left_key}_total": difference.only_left_total,
        right_key: [
            {"row": json_row(group.row), "count": group.count} for group in difference.only_right
        ],
        f"{right_key}_total": difference.only_right_total,
        "rows_shown_per_side": difference.bound,
    }


def statement_source_json(source: StatementSource) -> Json:
    """Where one statement's text came from: the file, its digest, and what the run was told
    about the file. ``origin`` and ``date`` are null when the run was told nothing."""
    return {
        "path": source.path,
        "digest": source.digest,
        "origin": source.origin,
        "date": source.date,
    }


def record_json(record: EvidenceRecord) -> Json:
    """Every field of the record, whole, in a form a reader can diff.

    The result is written in full rather than bounded: the record holds all of it and the
    hash below covers all of it, so a truncated rendering here would be a document whose
    hash nothing could check.

    Two hashes are added at the end. ``result_hash`` is the sha256 of the result under the
    canonical serialization the record itself declares, names included; R-ORD compares that
    rendering byte for byte with the columns taken by position, so the names are evidence. ``record_hash`` is the sha256 of this document with its keys sorted,
    taken with ``result_hash`` already in it and ``record_hash`` not yet in it, so a reader
    checks it by deleting that one key and hashing what is left.
    """
    settings = record.session_settings_in_force
    document: Json = {
        "question_as_asked": record.question_as_asked,
        "question": {
            "question_id": record.question.question_id,
            "question_set": record.question.question_set,
            "question_text": record.question.question_text,
            "evidence_text": record.question.evidence_text,
        },
        "question_set_version": record.question_set_version,
        "statement_source": statement_source_json(record.statement_source),
        "executed_sql": record.executed_sql,
        "bound_parameters": [
            {"position": p.position, "value": json_value(p.value), "declared_type": p.declared_type}
            for p in record.bound_parameters
        ],
        "validation_outcome": {
            "checks_run": list(record.validation_outcome.checks_run),
            "all_passed": record.validation_outcome.all_passed,
        },
        "validator_version": record.validator_version,
        "effective_database_role": record.effective_database_role,
        "backend_identity_at_checkout": record.backend_identity_at_checkout,
        "session_settings_in_force": {
            "time_zone": settings.time_zone,
            "date_style": settings.date_style,
            "interval_style": settings.interval_style,
            "extra_float_digits": settings.extra_float_digits,
            "database_collation": settings.database_collation,
            "recorded": dict(settings.recorded),
        },
        "result": {
            "columns": [{"name": c.name, "pg_type": c.pg_type} for c in record.result.columns],
            "row_count": len(record.result.rows),
            "truncated": record.result.truncated,
            "rows": [json_row(row) for row in record.result.rows],
            "backend_identity": record.result.backend_identity,
            "statement_timeout_ms": record.result.limits_in_force.statement_timeout_ms,
        },
        "row_count": record.row_count,
        "canonical_ordering": [
            {"column": key.column, "descending": key.descending}
            for key in record.canonical_ordering
        ],
        "serialization": {
            "version": record.serialization.version,
            "numeric_scale": record.serialization.numeric_scale,
            "timestamp_format": record.serialization.timestamp_format,
            "timezone": record.serialization.timezone,
            "null_rendering": record.serialization.null_rendering,
            "encoding": record.serialization.encoding,
        },
        "replay_rule": record.replay_rule.value,
        "fixture": {
            "schema_digest": record.fixture.schema_digest,
            "row_counts": dict(record.fixture.row_counts),
            "content_digests": dict(record.fixture.content_digests),
            "source_file_sha256": record.fixture.source_file_sha256,
        },
        "data_as_of": record.data_as_of.isoformat(),
        "executed_at": record.executed_at.isoformat(),
        "run_id": record.run_id,
        "rerun_instruction": record.rerun_instruction,
    }
    declared = {field.name for field in fields(EvidenceRecord)}
    if set(document) != declared:
        raise ValueError(
            "the rendering and the record disagree on the field set: "
            f"{sorted(set(document) ^ declared)}"
        )
    document["result_hash"] = result_digest(record.result, record.serialization)
    document["record_hash"] = digest_of(document)
    return document


__all__ = [
    "ROWS_IN_ARTIFACT",
    "Json",
    "RowDifference",
    "RowGroup",
    "digest_of",
    "json_row",
    "json_value",
    "record_json",
    "result_digest",
    "result_json",
    "row_difference",
    "row_difference_json",
    "statement_source_json",
    "write_json",
]
