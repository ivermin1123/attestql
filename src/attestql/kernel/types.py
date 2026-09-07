"""Types that cross the kernel boundary (plan section 1.2).

Only these frozen dataclasses cross the boundary between the product and a
kernel adapter. No driver objects, no parser nodes, no harness types.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class BoundParameter:
    """One bound parameter: its ``$position`` placeholder, value and declared type."""

    position: int
    value: object
    declared_type: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.position, int)  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            or isinstance(self.position, bool)
            or self.position < 1
        ):
            raise ValueError("position is the 1-based $n placeholder index")
        if not self.declared_type:
            raise ValueError("declared_type is required")


@dataclass(frozen=True)
class ExecutionLimits:
    """What the session held while one statement ran: the statement timeout, in milliseconds.

    Nine values became one. Four of the nine were caps no server reports and the product
    counted for itself, and four more were session controls a comparison of two statements
    on one database never sets; ADR-0013 deleted the product path all eight served. What is
    left is the one control an audit does set: a statement that cannot be allowed to run
    forever gets a timeout, and the value here is what the session read back rather than
    what the caller asked for, because an executor that could not read its own timeout back
    refuses the execution instead of recording an intention as a fact.
    """

    statement_timeout_ms: int

    def __post_init__(self) -> None:
        # Every field, discovered rather than listed, so a limit added later cannot be
        # left unchecked by a list that was not updated with it.
        for field in fields(self):
            value = getattr(self, field.name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field.name} must be a positive int")


@dataclass(frozen=True)
class ExecutionContext:
    """Whose data one execution may read, decided by the server and by nothing else.

    ``execute(statement)`` had no place to say this, so an executor had to derive it
    from the statement or accept it from whoever called. Both routes let the caller
    choose. This type is the place, and it is built server-side after authorization.

    There is no field for a presented tenant, a DSN, a pool key or an RLS setting. A
    request that carries one is refused for want of somewhere to put it, rather than
    having it silently dropped, and no field added to the SQL substitutes for this.
    Immutable for the request.
    """

    request_id: str
    authorized_tenant: str
    tenant_login_role: str
    authorization_policy_version: str

    def __post_init__(self) -> None:
        for field in fields(self):
            if not getattr(self, field.name):
                raise ValueError(f"{field.name} is required")


@dataclass(frozen=True)
class ProjectedColumnWidth:
    """The proven maximum size of one projected column's cell, in bytes.

    Both bounds are finite by construction. A projection whose width is not a constant
    of its type has no bound to state here, so it is refused at admission instead of
    being discovered after the row has already crossed the wire and been decoded.
    """

    name: str
    declared_type: str
    max_encoded_bytes: int
    max_decoded_bytes: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name is required")
        if not self.declared_type:
            raise ValueError("declared_type is required")
        for bound in ("max_encoded_bytes", "max_decoded_bytes"):
            value = getattr(self, bound)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{bound} must be a finite positive int")


@dataclass(frozen=True)
class ResultWidthProof:
    """How wide the result can be, proven before the database is reached at all.

    ``columns`` is the projection in order. ``policy_version`` names the policy that
    derived the bounds, so a replay can tell a record proved under one policy from a
    record proved under another.
    """

    columns: tuple[ProjectedColumnWidth, ...]
    policy_version: str

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("a width proof must cover at least one projected column")
        if not all(isinstance(column, ProjectedColumnWidth) for column in self.columns):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            raise TypeError("columns must be ProjectedColumnWidth instances")
        if not self.policy_version:
            raise ValueError("policy_version is required")


@dataclass(frozen=True)
class ValidatedStatement:
    """A statement a validator admitted, with the parameters bound to it.

    Only ``admit()`` creates one. The generated ``__init__`` always raises, so direct
    construction, ``dataclasses.replace`` and ``copy.replace`` all fail: each would
    let a caller change ``sql`` while keeping the admitted status. ``admit()`` builds
    the instance without ``__init__``. This seam is what the boundary invariant rests
    on: the statement the validator admitted is the statement that reaches the wire,
    and nothing else can be dressed up as one. Python cannot make this unforgeable;
    the seam makes every construction site explicit and auditable, and M3 adds a
    test that only validators call ``admit()``.

    ``result_width_proof`` travels with the statement because the size of what comes
    back has to be known before a connection is taken out, not after the bytes have
    arrived.
    """

    sql: str
    parameters: tuple[BoundParameter, ...]
    validator_version: str
    checks_passed: tuple[str, ...]
    result_width_proof: ResultWidthProof

    def __post_init__(self) -> None:
        raise TypeError("ValidatedStatement may only be created by admit()")


def admit(
    sql: str,
    parameters: tuple[BoundParameter, ...],
    validator_version: str,
    checks_passed: tuple[str, ...],
    result_width_proof: ResultWidthProof,
) -> ValidatedStatement:
    """The only sanctioned constructor of ``ValidatedStatement``.

    To be called by a ``SqlValidator`` implementation after validation passed, and
    by nothing else. It checks the shape of what it is handed; it validates no SQL.

    A statement is admitted only with a result-width proof. The proof's own
    constructor is what makes every bound in it finite and positive, so there is no
    way to hand a complete-looking proof here whose bounds are not: an unbounded
    projection cannot be turned into a ``ResultWidthProof`` in the first place.
    """
    if not isinstance(sql, str) or not sql.strip():  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
        raise ValueError("sql is required")
    if not validator_version:
        raise ValueError("validator_version is required")
    checks = tuple(checks_passed)
    if not checks:
        raise ValueError("checks_passed must name at least one validation check")
    if not isinstance(result_width_proof, ResultWidthProof):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
        raise TypeError("a statement is admitted only with a complete result-width proof")
    bound = tuple(parameters)
    if not all(isinstance(parameter, BoundParameter) for parameter in bound):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
        raise TypeError("parameters must be BoundParameter instances")
    positions = sorted(parameter.position for parameter in bound)
    if positions != list(range(1, len(positions) + 1)):
        raise ValueError("parameter positions must be exactly $1..$n")
    statement = object.__new__(ValidatedStatement)
    for name, value in (
        ("sql", sql),
        ("parameters", bound),
        ("validator_version", validator_version),
        ("checks_passed", checks),
        ("result_width_proof", result_width_proof),
    ):
        object.__setattr__(statement, name, value)
    return statement


@dataclass(frozen=True)
class ColumnType:
    """One column of a result: the name it came back under and the type it came back at.

    ``declared_type`` is the engine's own name for the type, spelled as that engine
    spells it, and it is read in the namespace of the engine the record's session
    settings name once. A column therefore carries no engine of its own: two columns
    whose ``declared_type`` reads the same come from records that state the same engine,
    or from two records a comparison already refused to make.
    """

    name: str
    declared_type: str


@dataclass(frozen=True)
class ExecutionResult:
    """Rows, column types, backend identity and the limits actually in force.

    ``truncated`` is True when ``rows`` is a bounded representation of what the
    statement returned rather than the whole of it. The bound is the caller's, not a
    limit stated here: ``limits_in_force`` is the timeout the session held, and an
    executor that returns every row it fetched says ``False``. Two results compare as
    equal only when they agree on this, so a bounded result is never mistaken for a
    complete one that happens to hold the same rows.
    """

    columns: tuple[ColumnType, ...]
    rows: tuple[tuple[object, ...], ...]
    backend_identity: str
    limits_in_force: ExecutionLimits
    truncated: bool

    def __post_init__(self) -> None:
        width = len(self.columns)
        for index, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(f"row {index} has {len(row)} values for {width} columns")


@dataclass(frozen=True)
class ValidationRejected(Exception):
    """Raised by a ``SqlValidator`` that did not admit the statement.

    ``check`` names the validation check that rejected it; ``reason`` says why.
    """

    check: str
    reason: str

    def __str__(self) -> str:
        return f"{self.check}: {self.reason}"

    def __reduce__(self) -> tuple[type, tuple[str, str]]:
        # A frozen dataclass exception cannot be restored through the default
        # pickle path (it assigns attributes); rebuild it through the constructor.
        return (type(self), (self.check, self.reason))


@dataclass(frozen=True)
class KernelVersions:
    """What ``KernelIdentity`` reports: versions or hashes, and the limit set.

    ``parser`` is ``None`` for a kernel that does not parse, which a validator over a
    pinned statement registry does not. Every kernel has a validator, an executor and a
    server, so those three are never absent.

    The absence is stated rather than filled. An empty string cannot be constructed
    here, so a component that exists always carries its own identity, and one that does
    not is never given a value of another kind standing in for it.
    """

    validator: str
    executor: str
    parser: str | None
    server: str
    limits: ExecutionLimits

    def __post_init__(self) -> None:
        for name in ("validator", "executor", "parser", "server"):
            if getattr(self, name) == "":
                raise ValueError(f"{name} is empty; a component this kernel lacks is None")
