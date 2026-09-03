"""Every stub raises NotImplementedError when called with plausible arguments.

A stub that returns a value, any value, produces fake evidence downstream. This
test fails if a stub is replaced by a silent default. When a milestone implements
a stub for real, remove it from STUB_CALLS in the same change.
"""

from __future__ import annotations

import copy
import dataclasses
import inspect
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from attestql.evidence import replay, serialize
from attestql.kernel.ports import KernelIdentity, QueryExecutor, SqlValidator
from attestql.kernel.types import (
    BoundParameter,
    ExecutionContext,
    ResultWidthProof,
    ValidatedStatement,
)


class _InheritsValidator(SqlValidator):
    pass


class _InheritsExecutor(QueryExecutor):
    pass


class _InheritsIdentity(KernelIdentity):
    pass


STUB_CALLS: dict[str, Callable[[SimpleNamespace], object]] = {
    "kernel.ports.SqlValidator.validate": lambda c: _InheritsValidator().validate(  # pyright: ignore[reportAbstractUsage]  # the inherited stub body raising is the point
        c.sql, c.parameters
    ),
    "kernel.ports.QueryExecutor.execute": lambda c: _InheritsExecutor().execute(  # pyright: ignore[reportAbstractUsage]  # the inherited stub body raising is the point
        c.statement, c.context
    ),
    "kernel.ports.KernelIdentity.versions": lambda c: _InheritsIdentity().versions(),  # pyright: ignore[reportAbstractUsage]  # the inherited stub body raising is the point
    # The V2.9 adapter's two stubs left this table with the adapter itself: ADR-0013
    # deleted the vendored validator, and a stub for a class that no longer exists would
    # assert nothing about this repository.
}


@pytest.fixture
def ctx(
    validated_statement: ValidatedStatement,
    bound_parameters: tuple[BoundParameter, ...],
    execution_context: ExecutionContext,
    result_width_proof: ResultWidthProof,
) -> SimpleNamespace:
    return SimpleNamespace(
        sql=validated_statement.sql,
        parameters=bound_parameters,
        statement=validated_statement,
        context=execution_context,
        width_proof=result_width_proof,
    )


@pytest.mark.parametrize("label", sorted(STUB_CALLS))
def test_stub_raises_not_implemented(label: str, ctx: SimpleNamespace) -> None:
    with pytest.raises(NotImplementedError):
        STUB_CALLS[label](ctx)


def test_the_port_requires_a_context_and_has_no_one_argument_form() -> None:
    """Execution authority is stated in the port itself, so no implementation can
    supply an executor that reads whatever the statement happens to imply."""
    parameters = inspect.signature(QueryExecutor.execute).parameters
    assert list(parameters) == ["self", "statement", "context"]
    assert parameters["context"].annotation == "ExecutionContext"
    assert parameters["context"].default is inspect.Parameter.empty


def test_execution_context_is_frozen(ctx: SimpleNamespace) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.context.authorized_tenant = "other-tenant"


@pytest.mark.parametrize(
    "presented",
    ["presented_tenant", "dsn", "pool_key", "rls_context", "database_role", "session_user"],
)
def test_execution_context_has_no_place_for_anything_a_caller_chose(presented: str) -> None:
    """Refused for want of a field, not accepted and then ignored. A field that does
    not exist cannot be quietly honoured by a later implementation either."""
    assert presented not in {field.name for field in dataclasses.fields(ExecutionContext)}
    with pytest.raises(TypeError):
        ExecutionContext(  # type: ignore[call-arg]
            request_id="run-test",
            authorized_tenant="sandbox-test",
            tenant_login_role="attestql_readonly_test",
            authorization_policy_version="authorization-policy-test",
            **{presented: "chosen-by-the-caller"},
        )


@pytest.mark.parametrize(
    "name",
    ["request_id", "authorized_tenant", "tenant_login_role", "authorization_policy_version"],
)
def test_execution_context_states_every_value_it_carries(name: str) -> None:
    complete = {
        "request_id": "run-test",
        "authorized_tenant": "sandbox-test",
        "tenant_login_role": "attestql_readonly_test",
        "authorization_policy_version": "authorization-policy-test",
    }
    assert ExecutionContext(**complete)
    with pytest.raises(ValueError, match=name):
        ExecutionContext(**{**complete, name: ""})


def test_validated_statement_is_only_constructible_through_admit(ctx: SimpleNamespace) -> None:
    assert isinstance(ctx.statement, ValidatedStatement)
    with pytest.raises(TypeError, match="admit"):
        ValidatedStatement(ctx.sql, ctx.parameters, "v", ("single_statement",), ctx.width_proof)


def test_validated_statement_cannot_be_altered_by_replace(ctx: SimpleNamespace) -> None:
    """dataclasses.replace and copy.replace rebuild through __init__, so both must fail:
    otherwise a caller could swap the SQL while keeping the admitted status."""
    with pytest.raises(TypeError, match="admit"):
        dataclasses.replace(ctx.statement, sql="SELECT 1")
    replace = getattr(copy, "replace", None)
    if replace is not None:  # Python 3.13+
        with pytest.raises(TypeError, match="admit"):
            replace(ctx.statement, sql="SELECT 1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.statement.sql = "SELECT 1"  # type: ignore[misc]
    assert ctx.statement.sql == ctx.sql


# Every public function in a stub module is either registered above or is real
# code with its own tests. A new function that is neither fails here.
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
            if qualified not in STUB_CALLS and qualified not in REAL_FUNCTIONS:
                unaccounted.append(qualified)
    assert not unaccounted, f"functions neither registered as stubs nor as real code: {unaccounted}"


def test_every_port_method_is_registered_as_a_stub() -> None:
    """No implementation of these ports ships now, so each one must still refuse to answer.

    A port that quietly grew a default would produce evidence nobody executed, which is
    the failure this whole file exists to catch."""
    methods = {
        f"kernel.ports.{port.__name__}.{name}"
        for port in (SqlValidator, QueryExecutor, KernelIdentity)
        for name, obj in vars(port).items()
        if inspect.isfunction(obj) and not name.startswith("_")
    }
    assert methods == set(STUB_CALLS)
