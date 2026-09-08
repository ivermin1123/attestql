"""The canonical rendering is deterministic, typed, and made of the descriptor's rules.

Each of the descriptor's rules is observed being *applied*: a test renders data the
rule reaches, changes only that rule, and observes the bytes change. A descriptor
field nobody applies would pass a test that only asserted the field exists, and the
first sign of it would be two runs compared under rules that were never in force.

The typing is observed the same way: a text column holding the descriptor's null
rendering and an actual null are data a rendering of strings alone cannot tell apart,
so the test that separates them is the one that shows the rendering is typed.
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from attestql.evidence.serialize import (
    FORMAT_IDENTITY,
    SerializationDescriptor,
    UndecodedText,
    UnsupportedValue,
    canonical_serialize,
    canonical_type_tag,
    typed_row,
    typed_value,
)
from attestql.kernel.types import ColumnType, ExecutionLimits, ExecutionResult


def _result(
    limits: ExecutionLimits,
    columns: tuple[tuple[str, str], ...],
    rows: tuple[tuple[object, ...], ...],
    *,
    truncated: bool = False,
) -> ExecutionResult:
    return ExecutionResult(
        columns=tuple(ColumnType(name, declared_type) for name, declared_type in columns),
        rows=rows,
        backend_identity="backend-under-test",
        limits_in_force=limits,
        truncated=truncated,
    )


def _one_value(limits: ExecutionLimits, declared_type: str, value: object) -> ExecutionResult:
    return _result(limits, (("cell", declared_type),), ((value,),))


def _rendered(result: ExecutionResult, descriptor: SerializationDescriptor) -> str:
    return canonical_serialize(result, descriptor).decode(descriptor.encoding)


def test_the_same_result_under_the_same_descriptor_renders_to_the_same_bytes(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    rows = (
        (1, Decimal("0.5"), date(2026, 7, 15), "alpha", datetime(2026, 7, 15, tzinfo=UTC)),
        (2, None, date(2026, 7, 16), "beta", datetime(2026, 7, 16, 3, 4, 5, tzinfo=UTC)),
    )
    columns = (
        ("n", "int8"),
        ("share", "numeric"),
        ("day", "date"),
        ("label", "text"),
        ("at", "timestamptz"),
    )
    first = canonical_serialize(_result(execution_limits, columns, rows), serialization_descriptor)
    second = canonical_serialize(_result(execution_limits, columns, rows), serialization_descriptor)
    assert first == second
    assert first.decode("utf-8").startswith(FORMAT_IDENTITY)


POSTGRESQL_COLUMNS = (
    ("n", "int8"),
    ("share", "numeric"),
    ("day", "date"),
    ("label", "text"),
    ("at", "timestamptz"),
)
POSTGRESQL_ROWS: tuple[tuple[object, ...], ...] = (
    (1, Decimal("0.5"), date(2026, 7, 15), "alpha", datetime(2026, 7, 15, tzinfo=UTC)),
    (2, None, date(2026, 7, 16), "beta", datetime(2026, 7, 16, 3, 4, 5, tzinfo=UTC)),
)
POSTGRESQL_DOCUMENT = (
    "attestql/canonical-serialization/1\n"
    "serialization\tserialization-test\n"
    "numeric-scale\t6\n"
    "timestamp-format\t%Y-%m-%dT%H:%M:%S.%fZ\n"
    "timezone\tUTC\n"
    "null-rendering\tNULL\n"
    "encoding\tutf-8\n"
    "truncated\tfalse\n"
    "columns\t5\n"
    "column\tn\tint8\n"
    "column\tshare\tnumeric\n"
    "column\tday\tdate\n"
    "column\tlabel\ttext\n"
    "column\tat\ttimestamptz\n"
    "rows\t2\n"
    "row\tint:1\tdec:0.500000\tdate:2026-07-15\tstr:alpha\tts:2026-07-15T00:00:00.000000Z\n"
    "row\tint:2\tnull:NULL\tdate:2026-07-16\tstr:beta\tts:2026-07-16T03:04:05.000000Z\n"
)
POSTGRESQL_DIGEST = "sha256:ef5615efcb8c5ee7d74e6bdf588505be50e86ba6c7d6abde08b4481c0c02b9d3"


def test_a_postgresql_result_renders_to_the_bytes_it_always_rendered_to(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    """The document a column line writes is the type's value, never the field it is held in.

    The literals here were taken from the rendering this serializer produced before a
    column's ``pg_type`` became its ``declared_type``, so the contract that moved is
    observed leaving every byte and the digest over them where they were. That is why the
    format identity is still ``/1``: nothing a reader of two documents compares changed.
    """
    result = _result(execution_limits, POSTGRESQL_COLUMNS, POSTGRESQL_ROWS)
    rendered = canonical_serialize(result, serialization_descriptor)

    assert rendered == POSTGRESQL_DOCUMENT.encode("utf-8")
    assert f"sha256:{hashlib.sha256(rendered).hexdigest()}" == POSTGRESQL_DIGEST


def test_a_change_of_numeric_scale_changes_the_rendering_of_a_numeric(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    result = _one_value(execution_limits, "numeric", Decimal("0.1234567"))
    at_six = _rendered(result, serialization_descriptor)
    at_two = _rendered(result, dataclasses.replace(serialization_descriptor, numeric_scale=2))
    assert "dec:0.123457" in at_six
    assert "dec:0.12" in at_two
    assert at_six != at_two


def test_a_change_of_timestamp_format_changes_the_rendering_of_an_instant(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    result = _one_value(execution_limits, "timestamptz", datetime(2026, 7, 15, 6, 7, 8, tzinfo=UTC))
    iso_like = _rendered(result, serialization_descriptor)
    day_only = _rendered(
        result,
        dataclasses.replace(serialization_descriptor, timestamp_format="%Y-%m-%d"),
    )
    assert "ts:2026-07-15T06:07:08.000000Z" in iso_like
    assert "ts:2026-07-15\n" in day_only
    assert iso_like != day_only


def test_a_change_of_timezone_moves_the_instant_the_rendering_states(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    result = _one_value(execution_limits, "timestamptz", datetime(2026, 7, 15, 0, 0, tzinfo=UTC))
    in_utc = _rendered(result, serialization_descriptor)
    in_berlin = _rendered(
        result,
        dataclasses.replace(serialization_descriptor, timezone="Europe/Berlin"),
    )
    assert "ts:2026-07-15T00:00:00.000000Z" in in_utc
    assert "ts:2026-07-15T02:00:00.000000Z" in in_berlin
    assert in_utc != in_berlin


def test_a_change_of_null_rendering_changes_the_rendering_of_a_null(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    result = _one_value(execution_limits, "numeric", None)
    as_null = _rendered(result, serialization_descriptor)
    as_absent = _rendered(result, dataclasses.replace(serialization_descriptor, null_rendering="~"))
    assert "null:NULL" in as_null
    assert "null:~" in as_absent
    assert as_null != as_absent


def test_a_change_of_encoding_changes_the_bytes(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    result = _one_value(execution_limits, "text", "alpha")
    in_utf8 = canonical_serialize(result, serialization_descriptor)
    in_utf16 = canonical_serialize(
        result, dataclasses.replace(serialization_descriptor, encoding="utf-16")
    )
    assert in_utf8 != in_utf16
    assert in_utf16.decode("utf-16").startswith(FORMAT_IDENTITY)


def test_a_change_of_serialization_version_changes_the_bytes(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    result = _one_value(execution_limits, "text", "alpha")
    stated = canonical_serialize(result, serialization_descriptor)
    restated = canonical_serialize(
        result, dataclasses.replace(serialization_descriptor, version="other")
    )
    assert stated != restated


def test_a_text_holding_the_null_rendering_is_not_rendered_as_a_null(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    text = _rendered(_one_value(execution_limits, "text", "NULL"), serialization_descriptor)
    absent = _rendered(_one_value(execution_limits, "text", None), serialization_descriptor)
    assert "str:NULL" in text
    assert "null:NULL" in absent
    assert text != absent


def test_an_integer_and_a_numeric_of_the_same_amount_render_differently(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    as_int = _rendered(_one_value(execution_limits, "int8", 1), serialization_descriptor)
    as_numeric = _rendered(
        _one_value(execution_limits, "numeric", Decimal(1)), serialization_descriptor
    )
    assert "int:1" in as_int
    assert "dec:1.000000" in as_numeric
    assert as_int != as_numeric


def test_a_date_renders_as_a_calendar_day_and_not_under_the_timestamp_format(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    rendered = _rendered(
        _one_value(execution_limits, "date", date(2026, 7, 15)), serialization_descriptor
    )
    assert "date:2026-07-15" in rendered
    assert "date:2026-07-15T" not in rendered


def test_a_value_of_a_type_the_rendering_has_no_rule_for_is_refused(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    with pytest.raises(UnsupportedValue, match="float"):
        canonical_serialize(_one_value(execution_limits, "float8", 1.5), serialization_descriptor)


def test_a_naive_datetime_is_refused_rather_than_assigned_a_timezone(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    naive = datetime(2026, 7, 15, 0, 0)
    with pytest.raises(UnsupportedValue, match="naive"):
        canonical_serialize(
            _one_value(execution_limits, "timestamp", naive), serialization_descriptor
        )


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_a_non_finite_numeric_is_refused_rather_than_rendered_at_a_scale(
    value: Decimal,
    execution_limits: ExecutionLimits,
    serialization_descriptor: SerializationDescriptor,
) -> None:
    """A comparison that counts rows keys a NaN as one value; a rendering at a fixed scale
    still has nothing to write for one, and refusing is what it has always done."""
    with pytest.raises(UnsupportedValue, match="non-finite"):
        canonical_serialize(
            _one_value(execution_limits, "numeric", value), serialization_descriptor
        )


def test_a_descriptor_naming_an_unknown_timezone_renders_nothing(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    unknown = dataclasses.replace(serialization_descriptor, timezone="Mars/Olympus")
    with pytest.raises(UnsupportedValue, match="unknown timezone"):
        canonical_serialize(
            _one_value(execution_limits, "timestamptz", datetime(2026, 7, 15, tzinfo=UTC)), unknown
        )


def test_a_text_carrying_a_cell_separator_cannot_forge_another_cell(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    forged = _result(execution_limits, (("cell", "text"),), (("a\tstr:b",),))
    two_cells = _result(execution_limits, (("l", "text"), ("r", "text")), (("a", "b"),))
    assert canonical_serialize(forged, serialization_descriptor) != canonical_serialize(
        two_cells, serialization_descriptor
    )
    assert "str:a\\tstr:b" in _rendered(forged, serialization_descriptor)


def test_a_text_carrying_a_line_break_cannot_forge_another_row(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    forged = _result(execution_limits, (("cell", "text"),), (("a\nrow\tstr:b",),))
    two_rows = _result(execution_limits, (("cell", "text"),), (("a",), ("b",)))
    assert "str:a\\nrow\\tstr:b" in _rendered(forged, serialization_descriptor)
    assert canonical_serialize(forged, serialization_descriptor) != canonical_serialize(
        two_rows, serialization_descriptor
    )


def test_a_numeric_rounded_to_zero_at_the_scale_renders_without_a_sign(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    below = _one_value(execution_limits, "numeric", Decimal("-0.0000001"))
    above = _one_value(execution_limits, "numeric", Decimal("0.0000001"))
    rendered = _rendered(below, serialization_descriptor)
    assert "dec:0.000000" in rendered
    assert "dec:-0" not in rendered
    assert canonical_serialize(below, serialization_descriptor) == canonical_serialize(
        above, serialization_descriptor
    )


def test_the_rows_render_in_the_order_the_result_holds_them(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    ascending = _result(execution_limits, (("n", "int8"),), ((1,), (2,)))
    descending = _result(execution_limits, (("n", "int8"),), ((2,), (1,)))
    assert canonical_serialize(ascending, serialization_descriptor) != canonical_serialize(
        descending, serialization_descriptor
    )


def test_the_projection_and_the_truncation_boundary_are_part_of_the_rendering(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    named = _result(execution_limits, (("n", "int8"),), ((1,),))
    renamed = _result(execution_limits, (("m", "int8"),), ((1,),))
    retyped = _result(execution_limits, (("n", "int4"),), ((1,),))
    bounded = _result(execution_limits, (("n", "int8"),), ((1,),), truncated=True)
    renderings = {
        canonical_serialize(result, serialization_descriptor)
        for result in (named, renamed, retyped, bounded)
    }
    assert len(renderings) == 4


def test_the_backend_that_served_a_result_is_not_part_of_its_rendering(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    """A re-run on another backend is another session, not another result."""
    here = _result(execution_limits, (("n", "int8"),), ((1,),))
    there = ExecutionResult(
        columns=here.columns,
        rows=here.rows,
        backend_identity="another-backend",
        limits_in_force=here.limits_in_force,
        truncated=here.truncated,
    )
    assert canonical_serialize(here, serialization_descriptor) == canonical_serialize(
        there, serialization_descriptor
    )


def test_an_instant_stated_in_another_offset_renders_at_the_descriptor_timezone(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    """Two spellings of one instant are one instant, and render as one."""
    in_utc = _one_value(execution_limits, "timestamptz", datetime(2026, 7, 15, tzinfo=UTC))
    elsewhere = _one_value(
        execution_limits,
        "timestamptz",
        datetime(2026, 7, 15, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
    )
    assert canonical_serialize(in_utc, serialization_descriptor) == canonical_serialize(
        elsewhere, serialization_descriptor
    )


def test_every_type_the_engine_understands_carries_its_own_tag() -> None:
    tags = {
        canonical_type_tag(None),
        canonical_type_tag(True),
        canonical_type_tag(1),
        canonical_type_tag(Decimal(1)),
        canonical_type_tag("a"),
        canonical_type_tag(datetime(2026, 7, 15, tzinfo=UTC)),
        canonical_type_tag(date(2026, 7, 15)),
    }
    assert tags == {"null", "bool", "int", "dec", "str", "ts", "date"}
    assert canonical_type_tag(True) != canonical_type_tag(1)
    assert canonical_type_tag(datetime(2026, 7, 15, tzinfo=UTC)) != canonical_type_tag(
        date(2026, 7, 15)
    )


def test_a_not_a_number_is_keyed_as_the_one_value_it_is_compared_as() -> None:
    """Both replay rules and the tie detector key a row through this. A NaN is folded to a
    stand-in because PostgreSQL groups every NaN as one value and Python neither hashes a
    Decimal NaN nor holds two of them equal."""
    assert typed_value(Decimal("NaN")) == typed_value(Decimal("-NaN"))
    assert len({typed_value(Decimal("NaN")), typed_value(Decimal("NaN"))}) == 1
    assert typed_value(Decimal("NaN")) != typed_value(Decimal(0))
    assert typed_value(Decimal("NaN")) != typed_value(Decimal("Infinity"))


def test_an_infinity_is_keyed_as_itself_and_not_as_the_other_one() -> None:
    """The rest of what a float column returns beside a number, which needs no stand-in."""
    assert typed_value(Decimal("Infinity")) == typed_value(Decimal("Infinity"))
    assert typed_value(Decimal("Infinity")) != typed_value(Decimal("-Infinity"))
    assert len({typed_value(Decimal("Infinity"))}) == 1


def test_a_typed_row_keys_every_value_by_the_type_it_came_back_as() -> None:
    """Python holds 1, True and Decimal(1) equal and hashes them alike, so a multiset keyed
    on the values alone would count three results as one."""
    assert len(set(typed_row((1, True, Decimal(1))))) == 3


def test_text_that_did_not_decode_renders_as_the_bytes_it_holds(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    """A text column can hold bytes no encoding decodes. They are the data, so they are
    rendered rather than refused, as hex under a tag of their own."""
    rendered = _rendered(
        _one_value(execution_limits, "text", UndecodedText(b"\xff\xfe")),
        serialization_descriptor,
    )
    assert "text-bytes:fffe" in rendered


def test_text_that_did_not_decode_is_never_the_text_of_its_own_hex(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    """The byte 0xff and a text column holding the two characters "ff" are two values, and
    a rendering that told them apart only by their payload would call them one."""
    as_bytes = _rendered(
        _one_value(execution_limits, "text", UndecodedText(b"\xff")), serialization_descriptor
    )
    as_text = _rendered(_one_value(execution_limits, "text", "ff"), serialization_descriptor)
    assert as_bytes != as_text
    assert typed_value(UndecodedText(b"\xff")) != typed_value("ff")
    assert canonical_type_tag(UndecodedText(b"\xff")) == "text-bytes"


def test_bytes_that_are_not_text_are_still_refused(
    execution_limits: ExecutionLimits, serialization_descriptor: SerializationDescriptor
) -> None:
    """Only a text value that did not decode has a rendering here. A BLOB is a value of
    another storage class, and giving it this one would hold the two equal."""
    with pytest.raises(UnsupportedValue, match="bytes"):
        canonical_serialize(_one_value(execution_limits, "blob", b"\xff"), serialization_descriptor)
