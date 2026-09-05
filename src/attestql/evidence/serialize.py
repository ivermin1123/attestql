"""Canonical typed serialization (brief section 8).

The rendering is a line-oriented document. Every line is a sequence of cells
separated by a tab and terminated by a line feed; the document is then encoded
with the descriptor's encoding. A payload's tab, line feed, carriage return and
backslash are backslash-escaped, so the cell boundaries are unambiguous and two
different documents can never render to the same bytes.

Every cell of a row carries the type it was rendered from, ahead of a colon, so
the rendering is typed rather than a row of strings: a text column holding the
descriptor's null rendering and an actual null are different bytes, and an
integer and a numeric holding the same amount are different bytes.

The document restates the descriptor it was rendered under. A rendering made
under one set of rules is therefore never byte-equal to a rendering made under
another, which is what makes a byte comparison of two renderings a comparison of
the results rather than of the rules that happened to be in force.

What the document deliberately leaves out is everything about the execution that
is not the result: the backend that served it and the limits that were in force.
Both are recorded on the evidence record and the limits are compared as a replay
precondition; rendering them here would make a re-run on another backend report
a different result rather than a different session.

A value the rendering has no stated rule for is refused. There is no fallback to
``str``: a fallback would render a type nobody decided a rule for, and the first
sign of it would be two renderings that disagree for a reason no reader can find.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, localcontext
from enum import Enum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from attestql.kernel.types import ExecutionResult

FORMAT_IDENTITY = "attestql/canonical-serialization/1"
"""The first line of every document. The layout below is what this name identifies."""

_CELL = "\t"
_LINE = "\n"
_ESCAPES = ((("\\"), "\\\\"), ("\t", "\\t"), ("\n", "\\n"), ("\r", "\\r"))


class UnsupportedValue(ValueError):
    """This value has no canonical rendering, so no rendering of it is produced.

    Raised rather than answered with a best effort. A value rendered by a rule
    nobody stated is a value two renderings can disagree on silently.
    """


def _escape(text: str) -> str:
    for literal, replacement in _ESCAPES:
        text = text.replace(literal, replacement)
    return text


def canonical_type_tag(value: object) -> str:
    """The tag the canonical rendering gives ``value``'s type.

    Shared with the R-SET multiset comparison so that both rules agree on which
    types this engine understands and on which values are of the same type. A
    ``bool`` is tagged ahead of an ``int`` and a ``datetime`` ahead of a ``date``
    because each is a subclass of the other and would otherwise be swallowed by it.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, Decimal):
        return "dec"
    if isinstance(value, str):
        return "str"
    if isinstance(value, datetime):
        return "ts"
    if isinstance(value, date):
        return "date"
    raise UnsupportedValue(
        f"no canonical rendering is stated for a value of type {type(value).__name__}"
    )


class _NotANumber(Enum):
    """The one value every NaN stands for once a row is keyed for a comparison."""

    NAN = "nan"


def typed_value(value: object) -> tuple[str, object]:
    """One value paired with the tag of the type it was returned as, as a comparison keys it.

    The tag is what makes a comparison typed. Python holds ``1``, ``True`` and ``Decimal(1)``
    equal and hashes them alike, so a multiset keyed on the values alone would count three
    different results as one; keyed on the pair, a value only ever meets a value of its type.

    **A NaN is one value.** PostgreSQL holds NaN equal to NaN, groups the two into one and
    sorts them together above every number, so this engine reads them as one value in every
    comparison it makes: a result holding one is equal to another holding one, a run of them
    at a bound is a tie, and a NaN on one side only is a difference like any other. Python
    disagrees twice over, holding two NaNs unequal, hashing a quiet one by its identity and
    refusing to hash a signaling one at all, so a key built from the value as it came back
    would count one answer as two and would raise on the value the server never prints.
    Standing a NaN's key in for it is what leaves the rule in one place. The infinities need
    no stand-in: Decimal already holds each equal to itself and to nothing else.

    The rendering is not what changes here. A non-finite numeric still has no rendering at a
    fixed scale and ``canonical_serialize`` still refuses one; this is how a comparison that
    counts rows rather than rendering them keys the value.
    """
    tag = canonical_type_tag(value)
    if isinstance(value, Decimal) and value.is_nan():
        return (tag, _NotANumber.NAN)
    return (tag, value)


def typed_row(row: Iterable[object]) -> tuple[tuple[str, object], ...]:
    """One row as the keys its values are compared and counted under."""
    return tuple(typed_value(value) for value in row)


def _render_decimal(value: Decimal, numeric_scale: int) -> str:
    """A numeric at the descriptor's scale, rounded half up, never in exponent form."""
    if not value.is_finite():
        raise UnsupportedValue(
            f"a non-finite numeric has no rendering at a fixed scale, got {value}"
        )
    exponent = Decimal(1).scaleb(-numeric_scale)
    with localcontext() as context:
        # The result needs room for every integral digit plus the scale; the default
        # precision would refuse a wide value rather than round it to the scale asked for.
        context.prec = max(len(value.as_tuple().digits) + numeric_scale + 1, context.prec)
        quantized = value.quantize(exponent, rounding=ROUND_HALF_UP)
    if quantized == 0:
        # Rounding a small negative amount to the scale yields a signed zero, and a
        # zero that renders two ways would report a re-run as a different result over
        # a sign the scale has just discarded.
        quantized = abs(quantized)
    return format(quantized, "f")


def _render_datetime(value: datetime, timestamp_format: str, timezone: str) -> str:
    """An instant moved into the descriptor's timezone and formatted by its rule."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise UnsupportedValue(
            "a naive datetime states no instant to move into the descriptor's timezone, "
            f"got {value!r}"
        )
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as unknown:
        raise UnsupportedValue(
            f"the descriptor names an unknown timezone: {timezone!r}"
        ) from unknown
    return value.astimezone(zone).strftime(timestamp_format)


@dataclass(frozen=True)
class SerializationDescriptor:
    """The rules used to render a result, so two renderings are comparable:
    type, precision, timezone and null rendering."""

    version: str
    numeric_scale: int
    timestamp_format: str
    timezone: str
    null_rendering: str
    encoding: str

    def __post_init__(self) -> None:
        if not self.version or not self.timestamp_format or not self.encoding:
            raise ValueError("version, timestamp_format and encoding are required")
        if self.numeric_scale < 0:
            raise ValueError("numeric_scale must be non-negative")

    def render_value(self, value: object) -> str:
        """One cell: the value's type tag, a colon, and the value under this descriptor."""
        tag = canonical_type_tag(value)
        if tag == "null":
            payload = self.null_rendering
        elif tag == "bool":
            payload = "true" if value else "false"
        elif tag == "int":
            payload = str(value)
        elif tag == "dec":
            payload = _render_decimal(_as_decimal(value), self.numeric_scale)
        elif tag == "str":
            payload = str(value)
        elif tag == "ts":
            payload = _render_datetime(_as_datetime(value), self.timestamp_format, self.timezone)
        else:
            payload = _as_date(value).isoformat()
        return f"{tag}:{_escape(payload)}"


def _as_decimal(value: object) -> Decimal:
    """Narrow a value the tag has already established is a ``Decimal``."""
    if not isinstance(value, Decimal):  # pragma: no cover - the tag decided this
        raise UnsupportedValue(f"expected a Decimal, got {type(value).__name__}")
    return value


def _as_datetime(value: object) -> datetime:
    """Narrow a value the tag has already established is a ``datetime``."""
    if not isinstance(value, datetime):  # pragma: no cover - the tag decided this
        raise UnsupportedValue(f"expected a datetime, got {type(value).__name__}")
    return value


def _as_date(value: object) -> date:
    """Narrow a value the tag has already established is a ``date``."""
    if not isinstance(value, date):  # pragma: no cover - the tag decided this
        raise UnsupportedValue(f"expected a date, got {type(value).__name__}")
    return value


def canonical_serialize(result: ExecutionResult, descriptor: SerializationDescriptor) -> bytes:
    """Render ``result`` under ``descriptor``.

    M4 contract: the same result under the same descriptor renders to the same
    bytes, and an R-ORD re-run is compared on exactly these bytes.

    Rows are rendered in the order the result holds them. Nothing here re-sorts:
    under R-ORD the order the statement produced is part of what is being
    compared, and a serializer that quietly sorted would report two differently
    ordered results as the same one.
    """
    lines: list[str] = [
        FORMAT_IDENTITY,
        _cell("serialization", descriptor.version),
        _cell("numeric-scale", str(descriptor.numeric_scale)),
        _cell("timestamp-format", descriptor.timestamp_format),
        _cell("timezone", descriptor.timezone),
        _cell("null-rendering", descriptor.null_rendering),
        _cell("encoding", descriptor.encoding),
        _cell("truncated", "true" if result.truncated else "false"),
        _cell("columns", str(len(result.columns))),
    ]
    lines.extend(
        _CELL.join(("column", _escape(column.name), _escape(column.declared_type)))
        for column in result.columns
    )
    lines.append(_cell("rows", str(len(result.rows))))
    lines.extend(
        _CELL.join(("row", *(descriptor.render_value(value) for value in row)))
        for row in result.rows
    )
    document = "".join(f"{line}{_LINE}" for line in lines)
    return document.encode(descriptor.encoding)


def _cell(key: str, value: str) -> str:
    return f"{key}{_CELL}{_escape(value)}"


__all__ = [
    "FORMAT_IDENTITY",
    "SerializationDescriptor",
    "UnsupportedValue",
    "canonical_serialize",
    "canonical_type_tag",
    "typed_row",
    "typed_value",
]
