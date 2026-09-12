"""What the byte budget takes out of a selection, which until 2026-09-12 could be a whole benchmark.

`select_questions.py` cut the selection to the site's budget by dropping the largest question of
the whole selection until it fit. That settles the site on one size threshold for every benchmark,
and the threshold fell between two benchmarks' distributions: on 2026-09-12, with the
`duplicate-full-row` probe adding 613 question directories, `minidev-sqlite` came out of 99 runs
with 0 question pages while `bird-dev-sqlite` kept 79, because the smallest question `minidev-sqlite`
has is 52 KB where `bird-dev-sqlite`'s is 28 KB. The published site of 2026-09-08 had 60 of them.

The cut now takes the largest question of whichever benchmark still holds the most, so the
benchmarks end with as equal a number of pages as the cut reaches. The budget itself is unchanged:
the answer to a build over budget is a narrower selection and never a larger budget.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
import select_questions as selection


def run(benchmark: str, name: str) -> selection.Run:
    return selection.Run(benchmark=benchmark, group="", name=name, audit=Path(name), summary={})


def question(
    where: selection.Run, index: int, data_bytes: int, *, reasons: frozenset[str] | None = None
) -> selection.Question:
    return selection.Question(
        run=where,
        directory=where.audit / f"q{index}",
        question_id=f"q{index}",
        files=("question.json", "result.json"),
        data_bytes=data_bytes,
        reasons=reasons if reasons is not None else frozenset({"probe"}),
    )


def kept_per_benchmark(
    runs: list[selection.Run], questions: list[selection.Question]
) -> Counter[str]:
    kept, _ = selection.trim(runs, questions)
    return Counter(one.run.benchmark for one in kept)


def two_benchmarks() -> tuple[list[selection.Run], list[selection.Question]]:
    """The shape that starved a benchmark: one holds more questions than the budget can take,
    and every question of the other is larger than every question of that one."""
    small, large = run("small-records", "a"), run("large-records", "b")
    questions = [question(small, index, 20_000) for index in range(1_500)]
    questions += [question(large, index, 40_000) for index in range(400)]
    return [small, large], questions


def test_a_benchmark_whose_questions_run_larger_still_publishes_its_own() -> None:
    kept = kept_per_benchmark(*two_benchmarks())
    assert kept["large-records"] > 0
    assert kept["small-records"] > 0


def test_the_benchmarks_are_left_as_equal_as_the_cut_reaches() -> None:
    kept = kept_per_benchmark(*two_benchmarks())
    assert abs(kept["small-records"] - kept["large-records"]) <= 1


def test_a_question_read_by_hand_is_kept_however_large_it_is() -> None:
    one = run("bench", "a")
    by_hand = question(one, 0, 900_000, reasons=frozenset({"hand"}))
    questions = [by_hand] + [question(one, index, 200_000) for index in range(1, 400)]
    kept, dropped = selection.trim([one], questions)
    assert by_hand in kept
    assert {"over-budget"} <= set().union(*(one.reasons for one in dropped))


def test_a_page_over_its_own_budget_goes_first_and_being_read_by_hand_does_not_save_it() -> None:
    one = run("bench", "a")
    too_wide = question(one, 0, selection.MAX_PAGE_BYTES * 2, reasons=frozenset({"hand"}))
    kept, dropped = selection.trim([one], [too_wide, question(one, 1, 10_000)])
    assert too_wide not in kept
    assert any("over-page" in one.reasons for one in dropped)


def test_a_selection_the_questions_read_by_hand_alone_cannot_hold_is_refused() -> None:
    one = run("bench", "a")
    questions = [question(one, index, 900_000, reasons=frozenset({"hand"})) for index in range(60)]
    with pytest.raises(selection.SelectionRefused, match="do not fit on their own"):
        selection.trim([one], questions)


def test_the_cut_makes_the_same_selection_twice() -> None:
    """Two benchmarks of equal-sized questions: the tie is broken by name and by question."""
    first, second = run("alpha", "a"), run("beta", "b")
    questions = [question(first, index, 30_000) for index in range(300)]
    questions += [question(second, index, 30_000) for index in range(300)]
    once, _ = selection.trim([first, second], questions)
    again, _ = selection.trim([first, second], questions)
    assert [one.directory for one in once] == [one.directory for one in again]
