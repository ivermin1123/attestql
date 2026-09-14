"""The filtered indexes a reader navigates by: not equal, by mechanism, by probe.

One page per filter, built from the entries a run page already holds, so an index states
exactly what the run page states and cannot drift from it. What a filter is named and where it
is written are here with the counting that fills it.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence

from attestql.contract.document import JsonObject
from attestql.report.render.load import (
    as_text,
    integer_at,
    object_at,
    origin_of,
    text_at,
)
from attestql.report.render.models import NOT_EQUAL, Entry, Fact, FilterPage, QuestionPage

NOT_EQUAL_DIRECTORY = "not-equal"
BY_MECHANISM_DIRECTORY = "by-mechanism"
BY_PROBE_DIRECTORY = "by-probe"
FILTER_DIRECTORIES: tuple[str, ...] = (
    NOT_EQUAL_DIRECTORY,
    BY_MECHANISM_DIRECTORY,
    BY_PROBE_DIRECTORY,
)
"""Where the pre-rendered filters of the index go, and the three names the clear below
removes. A static host reads no query string and this project ships no script that filters,
so a filtered view of the index is a directory with an address of its own: one for the
NOT_EQUAL rows, one per mechanism the run holds under ``by-mechanism/``, one per probe that
fired under ``by-probe/``. A filter no row satisfies is not written, because a page listing
nothing is a page a reader followed a link to for nothing."""

FILTER_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
"""What a mechanism class or a probe name has to look like to become a directory.

The one place in this command where text out of a document becomes a path. The class is read
from a counterexample's ``mechanism`` and the probe name from ``smells.json``, both of which
are files this command is documented to read from another machine, and both reach
``out / slug``. Without this a ``class`` of ``../../etc`` would write a page outside the
``--out`` the caller chose, because a path is not a string a template engine escapes.

A name that does not match gets no filter page: the leading character must be alphanumeric,
so ``.`` and ``..`` are out and nothing empty passes, and the rest allows only the characters
this tool's own classes and probe names use. Skipped rather than refused, because the name is
still a chip on the run page and on the question page, so nothing a document states is lost;
what is lost is a pre-rendered view of rows a reader can already see."""


def filter_pages(
    entries: Sequence[Entry], run_id: str, *, within: str = ""
) -> tuple[FilterPage, ...]:
    """The restrictions of the index that this run has rows for, in a fixed order.

    Every one is a subset of the rows above it and states its own rule in a sentence: no
    filter here reads a file the run page did not, and none of them counts anything. Which
    filters exist is the run's own business -- a mechanism no question was classified under
    and a probe that fired on nothing get no page, because a link to an empty index is a
    reader's wasted click -- and the order is fixed so that two renders of one directory
    write the same bytes.
    """
    of = len(entries)

    def view(slug: str, heading: str, restriction: str, rows: list[Entry]) -> FilterPage:
        return FilterPage(
            slug=slug,
            heading=heading,
            restriction=restriction,
            run_id=run_id,
            of=of,
            entries=tuple(rows),
            within=within,
        )

    views: list[FilterPage] = [
        view(
            NOT_EQUAL_DIRECTORY,
            NOT_EQUAL,
            f"The questions of this run whose verdict is {NOT_EQUAL}.",
            [entry for entry in entries if entry.verdict == NOT_EQUAL],
        )
    ]
    views.extend(
        view(
            f"{BY_MECHANISM_DIRECTORY}/{classification}",
            f"class {classification}",
            f"The questions this run's counterexamples classified as {classification}.",
            [entry for entry in entries if entry.mechanism == classification],
        )
        for classification in _nameable(entry.mechanism for entry in entries)
    )
    views.extend(
        view(
            f"{BY_PROBE_DIRECTORY}/{probe}",
            f"probe {probe}",
            f"The questions whose gold statement fired the probe {probe}.",
            [entry for entry in entries if probe in entry.probes],
        )
        for probe in _nameable(probe for entry in entries for probe in entry.probes)
    )
    return tuple(kept for kept in views if kept.entries)


def _nameable(names: Iterable[str]) -> list[str]:
    """The names of a set that can be a directory, once each and in one order.

    Both filters below the run page put a name out of a document into a path, so this is
    where a name that is not a name stops. See ``FILTER_SEGMENT`` for what is allowed and
    why a name outside it is dropped rather than refused."""
    return sorted({name for name in names if name and FILTER_SEGMENT.fullmatch(name)})


def probe_fired(smells: JsonObject) -> tuple[tuple[str, int], ...]:
    """Each probe and how many golds it fired on, as numbers, in the summary's own order.

    Read through ``integer_at``, which is what every other number a page states goes through:
    a ``smells`` value that is not a whole number is a document this command cannot render,
    and refusing it names the key, where drawing it as a zero would state a count no file
    holds.
    """
    return tuple((name, integer_at(smells, name)) for name in smells)


def mechanism_counts(questions: Sequence[QuestionPage]) -> tuple[tuple[str, int], ...]:
    """How many questions were put in each class, counted from the directories the run wrote.

    ``summary.json`` counts a class only for the rows another evaluator credited, so a run
    with no prediction file states none at all: the classes on the page are the ones its own
    question directories hold. Largest first, then by name, so two renderings of one
    directory draw the bar in one order.
    """
    counted = Counter(
        page.mechanism.classification for page in questions if page.mechanism is not None
    )
    return tuple(sorted(counted.items(), key=lambda pair: (-pair[1], pair[0])))


def credited(stated: JsonObject | None) -> tuple[Fact, ...]:
    """What BIRD's own check credited and this comparison called NOT_EQUAL, by mechanism."""
    if stated is None:
        return ()
    return (
        Fact("credited by BIRD and NOT_EQUAL here", as_text(stated.get("total"))),
        *(Fact(name, as_text(count)) for name, count in object_at(stated, "by_mechanism").items()),
        *(
            Fact(f"the test-suite check answered {name}", as_text(count))
            for name, count in object_at(stated, "by_test_suite_ex").items()
        ),
    )


def data_file(source: JsonObject | None) -> tuple[Fact, ...]:
    if source is None:
        return ()
    return (
        Fact("data file", text_at(source, "path"), origin_of(source, text_at(source, "digest"))),
    )
