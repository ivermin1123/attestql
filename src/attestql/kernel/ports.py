"""The three ports the product owns (plan section 1.1).

The product depends on these protocols and never on a kernel's internals.
``QueryExecutor.execute`` accepts a ``ValidatedStatement`` and never a ``str``:
there is no string overload and none may be added. That is how the boundary
preserves the invariant that the statement the validator admitted is the
statement that reaches the wire.

It accepts an ``ExecutionContext`` alongside it, and that is a second invariant of
the same kind. The port, not an implementation, is where whose data a statement
may read is stated, so an executor cannot quietly derive it from the statement or
take it from whoever called.
"""

from __future__ import annotations

from typing import Protocol

from attestql.kernel.types import (
    BoundParameter,
    ExecutionContext,
    ExecutionResult,
    KernelVersions,
    ValidatedStatement,
)


class SqlValidator(Protocol):
    """Given candidate SQL and bound parameters, admit or reject. Never executes."""

    def validate(self, sql: str, parameters: tuple[BoundParameter, ...]) -> ValidatedStatement:
        """Return a ``ValidatedStatement`` or raise ``ValidationRejected`` with a named reason."""
        raise NotImplementedError


class QueryExecutor(Protocol):
    """Given a ``ValidatedStatement`` and the server-built ``ExecutionContext`` authorizing
    it, execute read-only. Never validates, and never decides whose data it may read."""

    def execute(self, statement: ValidatedStatement, context: ExecutionContext) -> ExecutionResult:
        """Execute exactly the admitted statement, under exactly that context, and return
        rows, types, identity, limits."""
        raise NotImplementedError


class KernelIdentity(Protocol):
    """Report validator, executor, parser and server identity and the limit set."""

    def versions(self) -> KernelVersions:
        """Report; do not enforce."""
        raise NotImplementedError
