"""Reading a record's rendering back into the values it was rendered from.

``render`` writes a record out and hashes what it wrote; this reads one back and takes
the same two hashes again, so that a reader who was handed the file rather than the run
can check it. That is the whole of what this module is for: it builds an
``ExecutionResult`` and the descriptor it was rendered under, and those two are what
``result_digest`` needs.

The rendering is typed, so the reading is too. Every cell states the tag its value was
rendered under and the reading dispatches on that tag alone: a ``dec`` is a ``Decimal``
however the payload was written, an ``int`` never becomes one, and a payload whose tag
this module does not know is refused rather than guessed at, for the reason
``serialize`` refuses a value it has no rule for.

What this does not do is rebuild the record. An ``EvidenceRecord`` states twenty-one
fields and a page reads them as the document holds them; the two hashes are what a
reader cannot take from the document by eye, and they are what this returns.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import cast

from attestql.evidence.render import Json, digest_of, result_digest
from attestql.evidence.serialize import SerializationDescriptor, UndecodedText
from attestql.kernel.types import ColumnType, ExecutionLimits, ExecutionResult

RESULT_HASH = "result_hash"
RECORD_HASH = "record_hash"
"""The two keys ``record_json`` adds after the fields, in that order. ``record_hash`` is
taken over the document with ``result_hash`` already in it and itself not yet in it, so a
reader checks it by removing that one key and hashing what is left."""


class UnreadableRecord(ValueError):
    """This document is not a record's rendering, and no value is made up for it.

    Raised rather than answered with a default. A reading that filled a missing field in
    would produce a hash that differs from the recorded one for a reason no reader could
    find, which is the one thing this module exists to make visible.
    """


@dataclass(frozen=True)
class Recomputed:
    """One hash as the document states it and as it was taken again from the document."""

    stated: str
    recomputed: str

    @property
    def match(self) -> bool:
        return self.stated == self.recomputed


@dataclass(frozen=True)
class LoadedRecord:
    """What a record's rendering yields: its result, its rules, and its two hashes retaken."""

    result: ExecutionResult
    serialization: SerializationDescriptor
    result_hash: Recomputed
    record_hash: Recomputed


def load_value(cell: Json) -> object:
    """One rendered cell back as the value it was rendered from, by the tag it carries."""
    tag = _text(cell, "type")
    payload = cell.get("value")
    if tag == "null":
        return None
    if tag == "bool":
        return bool(payload)
    if tag == "int":
        return _integer(payload)
    if tag == "dec":
        return _decimal(payload)
    if tag == "str":
        return _string(payload)
    if tag == "text-bytes":
        return _undecoded_text(payload)
    if tag == "ts":
        return _instant(payload, datetime.fromisoformat, "a timestamp")
    if tag == "date":
        return _instant(payload, date.fromisoformat, "a date")
    raise UnreadableRecord(f"no reading is stated for a cell tagged {tag!r}")


def _undecoded_text(payload: object) -> UndecodedText:
    """The hex a text value that did not decode was rendered as, back as those bytes."""
    if not isinstance(payload, str):
        raise UnreadableRecord(
            f"a text-bytes cell holds {type(payload).__name__} and its value is hex text"
        )
    try:
        return UndecodedText(bytes.fromhex(payload))
    except ValueError as unreadable:
        raise UnreadableRecord(
            f"a text-bytes cell holds {payload!r}, which is no hex"
        ) from unreadable


def load_row(row: Sequence[Json]) -> tuple[object, ...]:
    """One rendered row as the values its cells were rendered from."""
    return tuple(load_value(_object(cell, "a cell")) for cell in row)


def load_result(result: Json) -> ExecutionResult:
    """A record's ``result`` block back as the execution result it renders.

    ``limits_in_force`` is rebuilt from the one timeout the block states, which is the
    whole of what ``ExecutionLimits`` holds; the backend identity is the result's own and
    not the record's checkout identity, because those are two statements about one
    execution and the serialization reads neither.
    """
    columns = tuple(
        ColumnType(name=_text(column, "name"), declared_type=_text(column, "declared_type"))
        for column in _rows(result, "columns")
    )
    return ExecutionResult(
        columns=columns,
        rows=tuple(load_row(_list(row, "a row")) for row in _rows(result, "rows")),
        backend_identity=_text(result, "backend_identity"),
        limits_in_force=ExecutionLimits(
            statement_timeout_ms=_integer(result.get("statement_timeout_ms"))
        ),
        truncated=bool(result.get("truncated")),
    )


def load_descriptor(serialization: Json) -> SerializationDescriptor:
    """A record's ``serialization`` block back as the descriptor its result was rendered under."""
    return SerializationDescriptor(
        version=_text(serialization, "version"),
        numeric_scale=_integer(serialization.get("numeric_scale")),
        timestamp_format=_text(serialization, "timestamp_format"),
        timezone=_text(serialization, "timezone"),
        null_rendering=_text(serialization, "null_rendering"),
        encoding=_text(serialization, "encoding"),
    )


def load_record(document: Json) -> LoadedRecord:
    """A record's rendering as its result, its descriptor and its two hashes taken again.

    The result hash is taken over the loaded result under the loaded descriptor, which is
    the same computation the run made over the values it had in memory; the record hash is
    taken over this document with ``record_hash`` removed, which is the rule
    ``record_json`` states for checking it. Neither is compared here: a page states both
    values when they differ, and a caller that only wants the answer reads ``match``.
    """
    result = load_result(_object(document.get("result"), "the result block"))
    serialization = load_descriptor(
        _object(document.get("serialization"), "the serialization block")
    )
    without_the_hash = {key: value for key, value in document.items() if key != RECORD_HASH}
    return LoadedRecord(
        result=result,
        serialization=serialization,
        result_hash=Recomputed(
            stated=_text(document, RESULT_HASH),
            recomputed=result_digest(result, serialization),
        ),
        record_hash=Recomputed(
            stated=_text(document, RECORD_HASH), recomputed=digest_of(without_the_hash)
        ),
    )


def _text(document: Json, key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise UnreadableRecord(f"{key} is not text: {value!r}")
    return value


def _string(payload: object) -> str:
    if not isinstance(payload, str):
        raise UnreadableRecord(f"a cell tagged str carries {payload!r}")
    return payload


def _integer(payload: object) -> int:
    if not isinstance(payload, int) or isinstance(payload, bool):
        raise UnreadableRecord(f"a whole number was expected, got {payload!r}")
    return payload


def _decimal(payload: object) -> Decimal:
    """A numeric back from the text it was written as, which is where its scale is."""
    if not isinstance(payload, str):
        raise UnreadableRecord(f"a cell tagged dec carries {payload!r}")
    try:
        return Decimal(payload)
    except InvalidOperation as unreadable:
        raise UnreadableRecord(f"a cell tagged dec carries {payload!r}") from unreadable


def _instant(payload: object, read: Callable[[str], object], what: str) -> object:
    """A timestamp or a date back through the standard library's own reading of ISO 8601."""
    if not isinstance(payload, str):
        raise UnreadableRecord(f"a cell tagged as {what} carries {payload!r}")
    try:
        return read(payload)
    except ValueError as unreadable:
        raise UnreadableRecord(f"{payload!r} is not {what}") from unreadable


def _object(value: object, what: str) -> Json:
    if not isinstance(value, dict):
        raise UnreadableRecord(f"{what} is not a JSON object: {value!r}")
    return cast("Json", value)


def _list(value: object, what: str) -> list[Json]:
    if not isinstance(value, list):
        raise UnreadableRecord(f"{what} is not a JSON array: {value!r}")
    return cast("list[Json]", value)


def _rows(document: Json, key: str) -> list[Json]:
    return _list(document.get(key), key)


__all__ = [
    "RECORD_HASH",
    "RESULT_HASH",
    "LoadedRecord",
    "Recomputed",
    "UnreadableRecord",
    "load_descriptor",
    "load_record",
    "load_result",
    "load_row",
    "load_value",
]
