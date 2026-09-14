"""What a JSON document this tool reads is, as a type, and the two readings that narrow one.

Every document this tool reads was written by somebody else: a question file, a prediction
file, an evidence record, a summary, a cache. `json.loads` answers `Any`, and a reader that
kept `Any` proved nothing about the file at all, so the assumption that a field is an object
or an array was made by a `cast` after the fact. A cast is not a check. It states a shape to
the type checker, the checker stops asking, and a document of another shape walks past it to
whatever assertion or attribute access comes next, which is where several of this tool's
loader defects were found.

`JsonValue` is what JSON's own grammar guarantees and nothing more: a string, a number, a
boolean, null, an array of those, or an object of those. A reader annotates what `json.loads`
gave it once, at the one line where the document arrives, and every `isinstance` below that
line narrows the union to exactly one of its members with nothing to cast. The two readings
here are the ones that were being cast: an object and an array.

This is not the type of what this tool *writes*. `evidence/render.py` states that separately,
and the two are different problems: a writer that builds a document cannot be handed a
malformed one, and giving a writer this type would only make every literal it builds fight
the invariance of `dict`.

Each caller keeps its own refusal, as `counts.py` does and for the same reason: the type that
reaches a reader is the one that names what could not be read, a run, a record or a report.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

JsonValue: TypeAlias = "str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None"
"""One value of a JSON document, at the type its grammar guarantees.

Recursive because JSON is: an array holds values and an object holds values, and both of
those are this. `float` is here because `json.loads` builds one for every number that is not
whole, and `bool` because JSON has `true`; a reader that wants a count has to exclude `bool`
itself, which `contract/counts.py` is where that is done."""

JsonObject: TypeAlias = "dict[str, JsonValue]"
"""A JSON object. Mutable and invariant, which is what a reader holding a document has."""

Refusal: TypeAlias = "Callable[[str], Exception]"
"""The caller's own error, made from a message. Nothing here raises anything of its own."""

NOT_AN_OBJECT = "{what} is not a JSON object: {value}"
NOT_AN_ARRAY = "{what} is not a JSON array: {value}"
"""The two reasons, written once so that every reader gives one answer."""


def an_object(value: JsonValue, what: str, refuse: Refusal) -> JsonObject:
    """That value as an object, or the caller's own refusal saying what it is instead."""
    if not isinstance(value, dict):
        raise refuse(NOT_AN_OBJECT.format(what=what, value=repr(value)))
    return value


def an_array(value: JsonValue, what: str, refuse: Refusal) -> list[JsonValue]:
    """That value as an array, or the caller's own refusal saying what it is instead."""
    if not isinstance(value, list):
        raise refuse(NOT_AN_ARRAY.format(what=what, value=repr(value)))
    return value


__all__ = [
    "NOT_AN_ARRAY",
    "NOT_AN_OBJECT",
    "JsonObject",
    "JsonValue",
    "Refusal",
    "an_array",
    "an_object",
]
