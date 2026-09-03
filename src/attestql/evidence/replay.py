"""Replay-equality contract.

Three outcomes. ``EQUAL`` and ``NOT_EQUAL`` are the result of a comparison whose
preconditions all matched; ``NOT_COMPARABLE`` means a precondition differed: the second
execution is a different experiment, and that is not a disagreement about the answer.

Both comparisons return a ``ComparabilityVerdict`` and not a bare outcome. The
names of what differed are the caller's answer to "why", and a function that
computed them and returned only the enum would leave a reviewer to rediscover
them. Carrying them in the same value is what makes them impossible to drop.

What blocks a comparison is now what ADR-0013 point 6 names, and nothing else. The
fixture digest, because two answers about different data are not evidence about each
other; and the five session settings that change rendered bytes or row order. Every
other field is recorded and never blocks: a record whose validator, question set or
server version differs is still a record of the same data, and calling that pair
incomparable would hide the disagreement the audit exists to report.

The fixture is compared on its schema digest and its row counts always, and on its
content digests only when both records carry them. A record computed with content
digests and one computed without them are not two measurements that disagree; the
second simply did not take that measurement, and reporting the absence as a mismatch
would make the cheap mode incomparable with the thorough one for no observation.

Beyond the preconditions, a comparison is also refused when the two records disagree
on the rule the comparison would be performed under: the serialization descriptor for
both rules, the canonical ordering for R-ORD, and the declared replay rule itself.
These are not preconditions and ``PRECONDITION_FIELDS`` does not hold them; they are
named in the same verdict beside the precondition names. Rendering one record's result
under the other record's rules would let one record's rules decide the other's
evidence, and reporting the difference as ``NOT_EQUAL`` would call a change of rules a
failure of the statement under test.

A projection is compared by position and by declared type, and never by name. The
benchmark this tool audits compares result tuples by position and never sees a name, so a
prediction that aliases a column differently is the same answer, and a verdict that turned
on an alias would be an artifact of this tool rather than an observation about the data.
The names are recorded on both results and are shown beside the verdict where the two
disagree; the canonical rendering a record hashes still states them, so two results
identical by value under different aliases carry different result hashes and the same
verdict.

Calling the function that does not match the rule both records declare is a caller
error and raises, because the caller chose the wrong rule; it is not an outcome a
comparison can have.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from enum import Enum

from attestql.evidence.record import EvidenceRecord
from attestql.evidence.serialize import (
    SerializationDescriptor,
    canonical_serialize,
    typed_row,
)
from attestql.evidence.types import FixtureDigest, ReplayRule  # imported, never redefined
from attestql.kernel.types import ColumnType, ExecutionResult

__all__ = [
    "PRECONDITION_FIELDS",
    "RULE_FIELDS",
    "SESSION_PRECONDITIONS",
    "ComparabilityResult",
    "ComparabilityVerdict",
    "ReplayRule",
    "compare_r_ord",
    "compare_r_set",
    "compare_results",
    "precondition_mismatches",
    "preconditions_match",
]


class ComparabilityResult(Enum):
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    NOT_COMPARABLE = "not_comparable"


SESSION_PRECONDITIONS: tuple[str, ...] = (
    "time_zone",
    "date_style",
    "interval_style",
    "extra_float_digits",
    "database_collation",
)
"""The settings of ``session_settings_in_force`` that must match, by their field names.

Exactly the five ADR-0013 point 6 names: the ones that change rendered bytes or row
order. Everything else the session reported lives in ``recorded`` and blocks nothing."""

PRECONDITION_FIELDS: tuple[str, ...] = (
    "fixture",
    *(f"session_settings_in_force.{setting}" for setting in SESSION_PRECONDITIONS),
)
"""The values that must all match before equality is required at all, by the name a
verdict reports. A session setting is named through the field that holds it, so a reader
of a verdict is told which setting differed and not merely that one did."""

RULE_FIELDS: tuple[str, ...] = ("replay_rule", "serialization", "canonical_ordering")
"""What the comparison would be performed under. Not preconditions, and named in a
verdict on the same footing: a re-run under other rules is another experiment too.
``canonical_ordering`` is read only under R-ORD, where the ordering is half of what
equality means; under R-SET a record carries none by construction."""


@dataclass(frozen=True)
class ComparabilityVerdict:
    """One comparison's outcome and the names of everything that made it incomparable."""

    result: ComparabilityResult
    mismatched: tuple[str, ...]

    def __post_init__(self) -> None:
        incomparable = self.result is ComparabilityResult.NOT_COMPARABLE
        if incomparable != bool(self.mismatched):
            raise ValueError(
                "a NOT_COMPARABLE verdict names what differed and no other verdict names "
                f"anything; got {self.result} with {self.mismatched}"
            )


def _same_fixture(a: FixtureDigest, b: FixtureDigest) -> bool:
    """The schema and the row counts always; the content digests only when both have them."""
    if a.schema_digest != b.schema_digest or dict(a.row_counts) != dict(b.row_counts):
        return False
    if not a.content_digests or not b.content_digests:
        return True
    return dict(a.content_digests) == dict(b.content_digests)


def precondition_mismatches(a: EvidenceRecord, b: EvidenceRecord) -> tuple[str, ...]:
    """Names of the precondition fields on which ``a`` and ``b`` differ."""
    mismatched: list[str] = []
    if not _same_fixture(a.fixture, b.fixture):
        mismatched.append("fixture")
    for setting in SESSION_PRECONDITIONS:
        left = getattr(a.session_settings_in_force, setting)
        right = getattr(b.session_settings_in_force, setting)
        if left != right:
            mismatched.append(f"session_settings_in_force.{setting}")
    return tuple(mismatched)


def preconditions_match(a: EvidenceRecord, b: EvidenceRecord) -> bool:
    """True only when the fixture digest and the five named session settings all match."""
    return not precondition_mismatches(a, b)


def _require_the_declared_rule(a: EvidenceRecord, b: EvidenceRecord, rule: ReplayRule) -> None:
    """Refuse a comparison under a rule neither record declared."""
    if a.replay_rule is b.replay_rule and a.replay_rule is not rule:
        raise ValueError(
            f"both records declare {a.replay_rule.value} and this is the {rule.value} "
            "comparison; the caller chose the wrong rule"
        )


def _incomparable(a: EvidenceRecord, b: EvidenceRecord, *, ordered: bool) -> tuple[str, ...]:
    """Every precondition and every rule field the two records disagree on, in order."""
    mismatched = list(precondition_mismatches(a, b))
    if a.replay_rule is not b.replay_rule:
        mismatched.append("replay_rule")
    if a.serialization != b.serialization:
        mismatched.append("serialization")
    if ordered and a.canonical_ordering != b.canonical_ordering:
        mismatched.append("canonical_ordering")
    return tuple(mismatched)


def _verdict(equal: bool) -> ComparabilityVerdict:
    outcome = ComparabilityResult.EQUAL if equal else ComparabilityResult.NOT_EQUAL
    return ComparabilityVerdict(outcome, ())


def _row_multiset(result: ExecutionResult) -> Counter[tuple[tuple[str, object], ...]]:
    """The rows as a multiset of typed rows: how many times each row occurs, no order.

    A ``Counter`` is the whole of the representation. Two results whose rows differ
    only in order build the same counts from the same keys, so they are equal under
    it without anything being sorted, and a row that occurs twice in one result and
    once in the other is not equal, which a set would have lost.

    The keys are the shared ones, which is where the type tag and the rule for a NaN
    are stated: the smells key a row the same way, and two keyings would be one too many.
    """
    return Counter(typed_row(row) for row in result.rows)


def _declared_types(result: ExecutionResult) -> tuple[str, ...]:
    """The declared type at each position: what a projection is when two answers meet."""
    return tuple(column.pg_type for column in result.columns)


def _same_projection(a: ExecutionResult, b: ExecutionResult) -> bool:
    """The declared types in order, and whether the rows are all of them.

    Compared beside the multiset, not folded into it: a row carries neither the types it
    was returned at nor whether it is all of them, so two results holding the same values
    at different types, or one bounded and one complete, would otherwise compare equal.

    The names are not read. A column renamed is the same answer under another label, and
    a type at a position that differs is what it has always been: not equal.
    """
    return _declared_types(a) == _declared_types(b) and a.truncated == b.truncated


def _by_position(result: ExecutionResult) -> ExecutionResult:
    """The same result with every column named by the position it occupies.

    The canonical rendering states each column's name beside its declared type, so two
    results differing only in an alias render to different bytes. Renaming both sides to
    their positions before they are rendered takes the names out of the comparison and
    leaves the types, the bound, the order and every value in it. Nothing is dropped: the
    records keep the names they were built with, and only the verdict stops reading them.
    """
    return replace(
        result,
        columns=tuple(
            ColumnType(name=str(position), pg_type=column.pg_type)
            for position, column in enumerate(result.columns)
        ),
    )


def compare_results(
    a: ExecutionResult,
    b: ExecutionResult,
    *,
    rule: ReplayRule,
    serialization: SerializationDescriptor,
) -> ComparabilityVerdict:
    """Two results compared under one rule, with no preconditions left to check.

    For a caller that made both executions itself, in one session, against one fixture,
    under one serialization: the smells re-run a gold with a key cast, with the bound
    removed, or over a shuffled copy of the same data, and every precondition a record
    comparison would check is the same value on both sides by construction. So the
    verdict here is only ever ``EQUAL`` or ``NOT_EQUAL``.

    It is the same equality both record comparisons apply, and they apply it by calling
    this: two definitions of what R-ORD or R-SET means would be one too many.
    """
    if rule is ReplayRule.R_ORD:
        return _verdict(
            canonical_serialize(_by_position(a), serialization)
            == canonical_serialize(_by_position(b), serialization)
        )
    return _verdict(_same_projection(a, b) and _row_multiset(a) == _row_multiset(b))


def compare_r_ord(a: EvidenceRecord, b: EvidenceRecord) -> ComparabilityVerdict:
    """R-ORD: byte-identical canonical rendering under the recorded ordering and
    serialization, with each column named by its position so an alias is not part of the
    bytes. The verdict is ``NOT_COMPARABLE``, naming what differed, when a precondition or
    a rule field differs; otherwise the renderings are compared byte for byte, in the order
    each result holds its rows."""
    _require_the_declared_rule(a, b, ReplayRule.R_ORD)
    mismatched = _incomparable(a, b, ordered=True)
    if mismatched:
        return ComparabilityVerdict(ComparabilityResult.NOT_COMPARABLE, mismatched)
    return compare_results(a.result, b.result, rule=ReplayRule.R_ORD, serialization=a.serialization)


def compare_r_set(a: EvidenceRecord, b: EvidenceRecord) -> ComparabilityVerdict:
    """R-SET: typed semantic equality of the row multiset, order disregarded. The
    verdict is ``NOT_COMPARABLE``, naming what differed, when a precondition or a rule
    field differs; otherwise the projections, by position and declared type, and the typed
    row multisets are compared.

    The values are compared as the result returned them and are not first rendered at
    the descriptor's scale. Owner decision of 2026-08-31: a rounding step must not
    decide membership of a row set."""
    _require_the_declared_rule(a, b, ReplayRule.R_SET)
    mismatched = _incomparable(a, b, ordered=False)
    if mismatched:
        return ComparabilityVerdict(ComparabilityResult.NOT_COMPARABLE, mismatched)
    return compare_results(a.result, b.result, rule=ReplayRule.R_SET, serialization=a.serialization)
