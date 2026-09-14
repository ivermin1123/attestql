"""Every public function of a module that once held stubs is accounted for, and the seam
around ``ValidatedStatement`` still holds.

A stub that returns a value, any value, produces fake evidence downstream, and this file was
written to fail if one was ever replaced by a silent default. The three port protocols it
watched went with phase 5 on 2026-09-14: nothing implemented them, nothing called them, and
``admit`` ran after the statement had already executed, so the boundary they described was
not there to protect. What is left is the accounting, which fails when a module that holds
real functions grows one nobody registered, and the construction seam on
``ValidatedStatement``, which is a kernel type and stays.
"""

from __future__ import annotations

import copy
import dataclasses
import inspect

import pytest

from attestql.evidence import replay, serialize
from attestql.kernel.types import BoundParameter, ResultWidthProof, ValidatedStatement


def test_validated_statement_is_only_constructible_through_admit(
    validated_statement: ValidatedStatement,
    bound_parameters: tuple[BoundParameter, ...],
    result_width_proof: ResultWidthProof,
) -> None:
    assert isinstance(validated_statement, ValidatedStatement)
    with pytest.raises(TypeError, match="admit"):
        ValidatedStatement(
            validated_statement.sql,
            bound_parameters,
            "v",
            ("single_statement",),
            result_width_proof,
        )


def test_validated_statement_cannot_be_altered_by_replace(
    validated_statement: ValidatedStatement,
) -> None:
    """dataclasses.replace and copy.replace rebuild through __init__, so both must fail:
    otherwise a caller could swap the SQL while keeping the admitted status."""
    sql = validated_statement.sql
    with pytest.raises(TypeError, match="admit"):
        dataclasses.replace(validated_statement, sql="SELECT 1")
    replace = getattr(copy, "replace", None)
    if replace is not None:  # Python 3.13+
        with pytest.raises(TypeError, match="admit"):
            replace(validated_statement, sql="SELECT 1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        validated_statement.sql = "SELECT 1"  # type: ignore[misc]
    assert validated_statement.sql == sql


# Every public function in one of these modules is real code with its own tests. A new
# function that is not listed fails here.
REAL_FUNCTIONS = frozenset(
    {
        "evidence.serialize.canonical_serialize",
        "evidence.serialize.canonical_type_tag",
        "evidence.replay.compare_r_ord",
        "evidence.replay.compare_r_set",
        "evidence.replay.compare_results",
        "evidence.replay.precondition_mismatches",
        "evidence.replay.preconditions_match",
        "evidence.serialize.typed_row",
        "evidence.serialize.typed_value",
    }
)
STUB_MODULES = {
    "evidence.serialize": serialize,
    "evidence.replay": replay,
}


def test_every_public_function_of_a_stub_module_is_accounted_for() -> None:
    unaccounted: list[str] = []
    for label, module in STUB_MODULES.items():
        for name, obj in vars(module).items():
            if (
                name.startswith("_")
                or not inspect.isfunction(obj)
                or obj.__module__ != module.__name__
            ):
                continue
            qualified = f"{label}.{name}"
            if qualified not in REAL_FUNCTIONS:
                unaccounted.append(qualified)
    assert not unaccounted, f"functions neither registered as stubs nor as real code: {unaccounted}"
