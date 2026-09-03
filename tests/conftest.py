"""Shared test inputs, and the gate that decides whether a sandbox test runs at all.

These build plausible *inputs* so that stubs can be called and contract types
can be exercised. Nothing here is evidence: rows are empty, hashes are labelled
as test values, and nothing is persisted.

The exception is ``sandbox_backend``, the one fixture in this file that reaches a real
server: the one ``tools/audit-sandbox/run.sh`` is holding open around the process that
collected this file. A ``sandbox``-marked test skips itself when that runner is not the
one running it, so the default suite needs no server and the merge gate still gets the
end-to-end run ADR-0013 point 11 asks for.
"""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

from attestql.audit.postgres import PostgresBackend
from attestql.contract.clock import EVALUATION_CLOCK
from attestql.evidence.serialize import SerializationDescriptor
from attestql.kernel.types import (
    BoundParameter,
    ColumnType,
    ExecutionContext,
    ExecutionLimits,
    ExecutionResult,
    ProjectedColumnWidth,
    ResultWidthProof,
    ValidatedStatement,
    admit,
)

TEST_SQL = (
    "SELECT count(DISTINCT account_id) AS active_accounts FROM usage_event "
    "WHERE event_ts >= $1 AND event_ts < $2"
)
TEST_CHECKS = ("single_statement", "select_only", "parameter_shape")

SANDBOX_GATE = "ATTESTQL_AUDIT_SANDBOX"
"""Presence-only, exported by the sandbox runner. It carries no secret and names no host."""

SANDBOX_DSN = "ATTESTQL_AUDIT_DSN"
"""The connection string the runner exported, which carries no password."""

SANDBOX_CREDENTIAL = "PGPASSWORD"
"""Where the auditor's generated password is, under the name libpq itself reads it from."""


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip a sandbox-marked test unless the sandbox runner is holding a server open."""
    if item.get_closest_marker("sandbox") is not None and not os.environ.get(SANDBOX_GATE):
        pytest.skip(f"{SANDBOX_GATE} is not set; run under tools/audit-sandbox/run.sh")


def _required(name: str) -> str:
    """One environment value the runner promises, or a failure that says who promises it."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set; tools/audit-sandbox/run.sh exports it")
    return value


@pytest.fixture(scope="session")
def sandbox_backend() -> PostgresBackend:
    """The audit's own backend, opened on the DSN the sandbox runner exported.

    The password is passed beside the DSN rather than written into it, so a DSN that
    reaches a record or a log never carries one. The connection lives as long as this
    process, which is the process the runner tears the server down under.
    """
    return PostgresBackend.connect(_required(SANDBOX_DSN), password=_required(SANDBOX_CREDENTIAL))


@pytest.fixture
def execution_limits() -> ExecutionLimits:
    return ExecutionLimits(statement_timeout_ms=5000)


@pytest.fixture
def bound_parameters() -> tuple[BoundParameter, ...]:
    return (
        BoundParameter(1, EVALUATION_CLOCK - timedelta(days=30), "timestamptz"),
        BoundParameter(2, EVALUATION_CLOCK, "timestamptz"),
    )


@pytest.fixture
def result_width_proof() -> ResultWidthProof:
    return ResultWidthProof(
        columns=(ProjectedColumnWidth("active_accounts", "int8", 20, 8),),
        policy_version="width-policy-test",
    )


@pytest.fixture
def validated_statement(
    bound_parameters: tuple[BoundParameter, ...], result_width_proof: ResultWidthProof
) -> ValidatedStatement:
    return admit(TEST_SQL, bound_parameters, "validator-test", TEST_CHECKS, result_width_proof)


@pytest.fixture
def execution_context() -> ExecutionContext:
    return ExecutionContext(
        request_id="run-test",
        authorized_tenant="sandbox-test",
        tenant_login_role="attestql_readonly_test",
        authorization_policy_version="authorization-policy-test",
    )


@pytest.fixture
def execution_result(execution_limits: ExecutionLimits) -> ExecutionResult:
    return ExecutionResult(
        columns=(ColumnType("active_accounts", "bigint"),),
        rows=(),
        backend_identity="postgresql-test-identity",
        limits_in_force=execution_limits,
        truncated=False,
    )


@pytest.fixture
def serialization_descriptor() -> SerializationDescriptor:
    return SerializationDescriptor(
        version="serialization-test",
        numeric_scale=6,
        timestamp_format="%Y-%m-%dT%H:%M:%S.%fZ",
        timezone="UTC",
        null_rendering="NULL",
        encoding="utf-8",
    )
