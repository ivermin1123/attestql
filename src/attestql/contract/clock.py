"""Fixed evaluation clock and relative-window resolution (brief section 4.1).

Every relative time window in the canonical question set resolves against
``EVALUATION_CLOCK``, never against wall-clock time at execution. The
resolution table in this module is the brief's table and nothing else: a phrase
that is not in it raises ``UnknownWindow``. This module never guesses.

All bounds are half-open UTC intervals: start inclusive, end exclusive.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum

EVALUATION_CLOCK = datetime(2026, 7, 15, 0, 0, 0, tzinfo=UTC)
"""The fixed instant every relative window resolves against: 2026-07-15T00:00:00Z."""


class UnknownWindow(LookupError):
    """The phrase is not in the brief's resolution table. The caller must not guess."""


class Grain(Enum):
    """A period grain the brief speaks of when a window is made of complete periods."""

    CALENDAR_MONTH = "calendar_month"
    ISO_WEEK = "iso_week"


def require_utc(value: datetime, name: str) -> None:
    """Reject anything that is not an aware UTC datetime. Shared by every contract type."""
    if not isinstance(value, datetime):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
        raise TypeError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an aware UTC datetime, got {value!r}")


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(month_start: datetime, months: int) -> datetime:
    years, month_index = divmod(month_start.month - 1 + months, 12)
    return month_start.replace(year=month_start.year + years, month=month_index + 1)


def _quarter_start(value: datetime) -> datetime:
    first_month_of_quarter = ((value.month - 1) // 3) * 3 + 1
    return _month_start(value).replace(month=first_month_of_quarter)


def _iso_week_start(value: datetime) -> datetime:
    monday = value - timedelta(days=value.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _on_boundary(value: datetime, grain: Grain) -> bool:
    if grain is Grain.CALENDAR_MONTH:
        return value == _month_start(value)
    return value == _iso_week_start(value)


def _next_boundary(boundary: datetime, grain: Grain) -> datetime:
    if grain is Grain.CALENDAR_MONTH:
        return _add_months(boundary, 1)
    return boundary + timedelta(weeks=1)


@dataclass(frozen=True)
class Window:
    """A half-open UTC interval: ``start`` is inclusive, ``end`` is exclusive."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        require_utc(self.start, "start")
        require_utc(self.end, "end")
        if not self.start < self.end:
            raise ValueError(f"window start must precede end: {self.start!r} >= {self.end!r}")

    def periods(self, grain: Grain) -> tuple[Window, ...]:
        """The complete periods of ``grain`` that exactly tile ``[start, end)``.

        Raises ``ValueError`` when either bound is not on a period boundary, because
        a window that is not made of complete periods has no such decomposition and
        the brief forbids mixing partial periods with complete ones.
        """
        if not _on_boundary(self.start, grain):
            raise ValueError(f"{self.start!r} is not a {grain.value} boundary")
        periods: list[Window] = []
        cursor = self.start
        while cursor < self.end:
            following = _next_boundary(cursor, grain)
            if following > self.end:
                raise ValueError(f"{self.end!r} is not a {grain.value} boundary")
            periods.append(Window(cursor, following))
            cursor = following
        return tuple(periods)


@dataclass(frozen=True)
class TrendRule:
    """Resolution of the brief's "per month (trend)" row.

    The brief fixes the grain (complete calendar months only) and the exclusive
    upper bound (the incomplete month containing the clock is excluded). It states
    no lower bound: that comes from the question, not from the phrase. A trend rule
    is therefore not a ``Window`` and must not be read as one; a consumer that needs
    a lower bound must take it from the question's other constraints or refuse.
    """

    grain: Grain
    end: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.grain, Grain):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
            raise TypeError("grain must be a Grain")
        require_utc(self.end, "end")
        if not _on_boundary(self.end, self.grain):
            raise ValueError(f"{self.end!r} is not a {self.grain.value} boundary")


def _last_30_days(clock: datetime) -> Window:
    return Window(clock - timedelta(days=30), clock)


def _last_month(clock: datetime) -> Window:
    this_month = _month_start(clock)
    return Window(_add_months(this_month, -1), this_month)


def _current_month(clock: datetime) -> Window:
    return Window(_month_start(clock), clock)


def _last_quarter(clock: datetime) -> Window:
    this_quarter = _quarter_start(clock)
    return Window(_add_months(this_quarter, -3), this_quarter)


def _last_12_weeks(clock: datetime) -> Window:
    this_week = _iso_week_start(clock)
    return Window(this_week - timedelta(weeks=12), this_week)


def _the_last_two_months(clock: datetime) -> Window:
    """Two complete calendar months; ``.periods(Grain.CALENDAR_MONTH)`` yields each."""
    this_month = _month_start(clock)
    return Window(_add_months(this_month, -2), this_month)


def _per_month_trend(clock: datetime) -> TrendRule:
    return TrendRule(Grain.CALENDAR_MONTH, _month_start(clock))


def _the_last_year(clock: datetime) -> Window:
    try:
        start = clock.replace(year=clock.year - 1)
    except ValueError as exc:
        raise ValueError("'the last year' is undefined for a 29 February clock") from exc
    return Window(start, clock)


def _the_last_12_complete_months(clock: datetime) -> Window:
    """Twelve complete calendar months; ``.periods(Grain.CALENDAR_MONTH)`` yields each.

    Both bounds are month starts by construction, as in ``_the_last_two_months``, rather
    than by arithmetic that happens to land on one. "the last year" spans the same length
    and is **not** month aligned: it runs from the clock instant, so ``periods`` refuses
    it. A question that needs complete months takes this phrase, not that one.
    """
    this_month = _month_start(clock)
    return Window(_add_months(this_month, -12), this_month)


_RESOLVERS: dict[str, Callable[[datetime], Window | TrendRule]] = {
    "last 30 days": _last_30_days,
    "last month": _last_month,
    "current month": _current_month,
    "last quarter": _last_quarter,
    "last 12 weeks": _last_12_weeks,
    "the last two months": _the_last_two_months,
    "per month (trend)": _per_month_trend,
    "the last year": _the_last_year,
    "the last 12 complete months": _the_last_12_complete_months,
}

WINDOW_PHRASES: frozenset[str] = frozenset(_RESOLVERS)
"""Exactly the phrases in the brief's resolution table."""


def _normalize(phrase: str) -> str:
    return " ".join(phrase.split()).casefold()


def resolve_window(phrase: str, clock: datetime = EVALUATION_CLOCK) -> Window | TrendRule:
    """Resolve a phrase from the brief's table against ``clock``.

    Returns a ``Window`` for every row that states bounds, and a ``TrendRule`` for
    "per month (trend)", whose row states a grain and an end but no start. Any
    other phrase raises ``UnknownWindow``. A naive or non-UTC clock raises
    ``ValueError``.
    """
    if not isinstance(phrase, str):  # pyright: ignore[reportUnnecessaryIsInstance]  # runtime guard for callers outside the type system
        raise TypeError("phrase must be a str")
    require_utc(clock, "clock")
    resolver = _RESOLVERS.get(_normalize(phrase))
    if resolver is None:
        raise UnknownWindow(f"not in the brief's resolution table: {phrase!r}")
    return resolver(clock)
