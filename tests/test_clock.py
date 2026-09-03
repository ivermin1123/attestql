"""Brief section 4.1: every phrase resolves to the stated half-open UTC bounds."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta, timezone

import pytest

from attestql.contract.clock import (
    EVALUATION_CLOCK,
    WINDOW_PHRASES,
    Grain,
    TrendRule,
    UnknownWindow,
    Window,
    resolve_window,
)


def utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


# The brief's table, verbatim, for every row that states bounds.
STATED_BOUNDS = {
    "last 30 days": (utc(2026, 6, 15), utc(2026, 7, 15)),
    "last month": (utc(2026, 6, 1), utc(2026, 7, 1)),
    "current month": (utc(2026, 7, 1), utc(2026, 7, 15)),
    "last quarter": (utc(2026, 4, 1), utc(2026, 7, 1)),
    "last 12 weeks": (utc(2026, 4, 20), utc(2026, 7, 13)),
    "the last two months": (utc(2026, 5, 1), utc(2026, 7, 1)),
    "the last year": (utc(2025, 7, 15), utc(2026, 7, 15)),
    # Added to the table by ADR-0011 on 2026-08-30, for Q13's trend lower bound.
    "the last 12 complete months": (utc(2025, 7, 1), utc(2026, 7, 1)),
}
TREND_PHRASE = "per month (trend)"


def test_evaluation_clock_is_the_brief_instant() -> None:
    assert datetime(2026, 7, 15, 0, 0, 0, tzinfo=UTC) == EVALUATION_CLOCK
    assert EVALUATION_CLOCK.utcoffset() == timedelta(0)


def test_table_contains_exactly_the_brief_phrases() -> None:
    assert frozenset(STATED_BOUNDS) | {TREND_PHRASE} == WINDOW_PHRASES


@pytest.mark.parametrize("phrase", sorted(STATED_BOUNDS))
def test_phrase_resolves_to_the_stated_bounds(phrase: str) -> None:
    window = resolve_window(phrase)
    assert isinstance(window, Window)
    assert (window.start, window.end) == STATED_BOUNDS[phrase]


@pytest.mark.parametrize("phrase", sorted(STATED_BOUNDS))
def test_bounds_are_aware_utc(phrase: str) -> None:
    window = resolve_window(phrase)
    assert isinstance(window, Window)
    for bound in (window.start, window.end):
        assert bound.tzinfo is not None
        assert bound.utcoffset() == timedelta(0)


def test_the_last_two_months_is_two_complete_calendar_months() -> None:
    window = resolve_window("the last two months")
    assert isinstance(window, Window)
    assert window.periods(Grain.CALENDAR_MONTH) == (
        Window(utc(2026, 5, 1), utc(2026, 6, 1)),
        Window(utc(2026, 6, 1), utc(2026, 7, 1)),
    )


def test_the_last_12_complete_months_is_twelve_complete_calendar_months() -> None:
    window = resolve_window("the last 12 complete months")
    assert isinstance(window, Window)
    assert (window.start, window.end) == (utc(2025, 7, 1), utc(2026, 7, 1))
    months = window.periods(Grain.CALENDAR_MONTH)
    assert len(months) == 12
    assert months[0].start == utc(2025, 7, 1)
    assert months[-1].end == utc(2026, 7, 1)
    assert all(month.start.day == 1 for month in months)


def test_the_last_year_is_unchanged_and_still_does_not_decompose() -> None:
    """The two phrases span the same length and only one is month aligned."""
    window = resolve_window("the last year")
    assert isinstance(window, Window)
    assert (window.start, window.end) == (utc(2025, 7, 15), utc(2026, 7, 15))
    with pytest.raises(ValueError):
        window.periods(Grain.CALENDAR_MONTH)


def test_last_12_weeks_is_twelve_complete_iso_weeks_ending_on_the_stated_monday() -> None:
    window = resolve_window("last 12 weeks")
    assert isinstance(window, Window)
    weeks = window.periods(Grain.ISO_WEEK)
    assert len(weeks) == 12
    assert all(week.start.weekday() == 0 for week in weeks)
    assert all(week.end - week.start == timedelta(weeks=1) for week in weeks)
    assert weeks[-1].end == utc(2026, 7, 13)


def test_per_month_trend_is_a_rule_that_excludes_the_incomplete_month() -> None:
    rule = resolve_window(TREND_PHRASE)
    assert isinstance(rule, TrendRule)
    assert rule.grain is Grain.CALENDAR_MONTH
    assert rule.end == utc(2026, 7, 1)
    assert not isinstance(rule, Window)
    assert not hasattr(rule, "start")


@pytest.mark.parametrize(
    "phrase",
    ["last week", "yesterday", "last 7 days", "this quarter", "year to date", "last 2 months", ""],
)
def test_unknown_phrase_raises_instead_of_guessing(phrase: str) -> None:
    with pytest.raises(UnknownWindow):
        resolve_window(phrase)


def test_phrase_matching_ignores_case_and_surrounding_whitespace_only() -> None:
    assert resolve_window("  Last Month ") == resolve_window("last month")
    with pytest.raises(UnknownWindow):
        resolve_window("last months")


def test_naive_clock_is_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_window("last month", clock=datetime(2026, 7, 15))


def test_non_utc_clock_is_rejected() -> None:
    offset = timezone(timedelta(hours=2))
    with pytest.raises(ValueError):
        resolve_window("last month", clock=datetime(2026, 7, 15, tzinfo=offset))


def test_resolution_is_relative_to_the_clock_including_year_rollover() -> None:
    clock = utc(2026, 1, 15)
    assert resolve_window("last month", clock) == Window(utc(2025, 12, 1), utc(2026, 1, 1))
    assert resolve_window("last quarter", clock) == Window(utc(2025, 10, 1), utc(2026, 1, 1))
    assert resolve_window("the last two months", clock) == Window(utc(2025, 11, 1), utc(2026, 1, 1))
    assert resolve_window("current month", clock) == Window(utc(2026, 1, 1), utc(2026, 1, 15))
    assert resolve_window("the last year", clock) == Window(utc(2025, 1, 15), utc(2026, 1, 15))
    assert resolve_window(TREND_PHRASE, clock) == TrendRule(Grain.CALENDAR_MONTH, utc(2026, 1, 1))


def test_window_is_frozen_and_validated() -> None:
    window = Window(utc(2026, 6, 1), utc(2026, 7, 1))
    with pytest.raises(dataclasses.FrozenInstanceError):
        window.start = utc(2026, 5, 1)  # type: ignore[misc]
    with pytest.raises(ValueError):
        Window(utc(2026, 7, 1), utc(2026, 6, 1))
    with pytest.raises(ValueError):
        Window(utc(2026, 6, 1), utc(2026, 6, 1))
    with pytest.raises(ValueError):
        Window(datetime(2026, 6, 1), utc(2026, 7, 1))


def test_periods_rejects_bounds_that_are_not_on_a_period_boundary() -> None:
    with pytest.raises(ValueError):
        Window(utc(2026, 6, 15), utc(2026, 7, 15)).periods(Grain.CALENDAR_MONTH)
    with pytest.raises(ValueError):
        Window(utc(2026, 6, 1), utc(2026, 7, 15)).periods(Grain.CALENDAR_MONTH)
    with pytest.raises(ValueError):
        Window(utc(2026, 4, 21), utc(2026, 7, 13)).periods(Grain.ISO_WEEK)
