"""The figures a page carries: SVG written here, from the same model the templates read.

A figure is drawn only where a table cannot say the thing: rows that kept their values and
changed their places, one result that is the other one counted differently, one that is the
first rows of the other, and a run's verdicts side by side. Everything else on a page is a
table, because a table is the thing a reader can check.

No chart library and no script. What a figure is, is a string of SVG built from integers the
view model already holds, so the same directory renders the same bytes on any machine, and a
reader who reads the page with images off loses nothing: every figure states its data source
in its ``<title>``, and every number it draws is in the text beside it and in a table above
it. The marks carry classes and no colours of their own; ``report.css`` gives them the page's
tokens, which is what makes them hold in light, in dark and in print, because a ``var()``
inside an SVG presentation attribute is not a value SVG reads.

Only the standard library and this package are imported here, and the view model only for
its type names: a figure is arithmetic over numbers that were read out of JSON somewhere
else.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - imported for the type names alone
    from collections.abc import Sequence

    from attestql.report.render import QuestionPage, Rows, RunPage

WIDTH = 640
BAR_SPAN = 440
"""How wide a figure is, in px, and how much of that a bar at its full count fills.

The size is fixed rather than fluid, and the region a figure sits in scrolls sideways the
way a table's does. A figure scaled to its column would scale its text with it, and the
design spec puts the numbers on a figure at 13px: a slope chart shrunk to a phone would
state them at seven. The 200px the bars leave on the right is where their direct labels
are, which is why they carry no legend."""

BAR_HEIGHT = 24
BAR_GAP = 12
SLOPE_STEP = 18
"""One bar, the space under it, and one row of the slope chart.

The first two are on the spacing scale of the design spec, which is what keeps a bar
aligned with the text beside it. The third is not on it: 24 would make a twenty-five row
chart taller than a phone screen and 16 leaves a 13px numeral no room, because ``_room``
asks for 14px between two numbers it writes. 18 is the pitch of a line of numbers, not a
space between blocks, and it is the one measurement in this module that is neither."""

LABEL = 7.8
"""The advance of one character of Plex Mono at 13px, in these coordinates: 0.6em, the
family's own monospace advance. Used to keep two direct labels from overlapping, never to
place text a reader has to measure."""

MECHANISM_ORDER = "order"
MECHANISM_MULTIPLICITY = "multiplicity"
MECHANISM_TRUNCATION = "truncation"
"""The three classes that get a figure. ``type`` gets none: the declared type in the column
header is where a reader sees it, and ``other`` is the class for everything the four named
readings do not cover, which is not one shape."""

ROWS_IN_A_SLOPE = 25
"""How many rows of the gold a slope chart draws. The counterexample's own preview bound:
the figure is a reading of the opening of two results and says so, and a line for every row
of a ten-thousand-row result would be a black rectangle."""


@dataclass(frozen=True)
class Figure:
    """One figure: the markup, what it is about, and the same numbers as text.

    ``alternative`` is not a description of the picture. It is the figure's content in
    words, so that the page states the numbers twice and the drawing is never the only
    carrier of one of them.
    """

    name: str
    title: str
    alternative: str
    svg: str

    @property
    def described_by(self) -> str:
        """The id of the element holding the text alternative, which the SVG points at."""
        return f"figure-{self.name}-text"


def question_figure(page: QuestionPage) -> Figure | None:
    """The figure for this question's mechanism, or none where the table already says it."""
    if page.mechanism is None or len(page.sides) < 2:
        return None
    classification = page.mechanism.classification
    if classification == MECHANISM_ORDER:
        return _slope(page)
    if classification == MECHANISM_MULTIPLICITY:
        return _multiplicity(page)
    if classification == MECHANISM_TRUNCATION:
        return _truncation(page)
    return None


def run_figures(page: RunPage) -> tuple[Figure, ...]:
    """The run in one glance: the verdicts as one bar, and one bar per probe."""
    return (_verdicts(page), _probes(page))


def proportion_bar(
    name: str, parts: Sequence[tuple[str, int, bool]], *, title: str, whole: str
) -> Figure:
    """One bar cut into named parts, the marked ones in ``--warn``.

    The landing page's own figure, and the shape the run's verdict bar is drawn with. It is
    a function here and is placed nowhere: the page that carries it is the site's, and the
    site is built somewhere else.
    """
    total = sum(value for _, value, _ in parts)
    segments = _segments(parts, total)
    height = BAR_HEIGHT + BAR_GAP + 18 + segments.rows * 16
    body = [
        f'<rect class="figure__frame" x="0" y="0" width="{WIDTH}" height="{BAR_HEIGHT}"></rect>'
    ]
    body.extend(segments.marks)
    body.extend(segments.labels)
    alternative = (
        f"{whole}: " + ", ".join(f"{value:,} {label}" for label, value, _ in parts if value)
        if total
        else f"{whole}: nothing counted"
    )
    return _figure(name, title, alternative, height, body)


def _slope(page: QuestionPage) -> Figure:
    """Where each row of the gold is in the prediction: one line per row, the moved marked.

    Read off the two records, which hold every row, so a position is the row's place in the
    whole result and not in a preview of it. The rows drawn are the opening of the gold, up
    to ``ROWS_IN_A_SLOPE``, and both the title and the text below state how many of how many
    that is.
    """
    gold, second = _rows_of(page)
    places = _places(gold, second)
    drawn = places[:ROWS_IN_A_SLOPE]
    span = SLOPE_STEP * (max(len(drawn), 2) - 1)
    top = 30
    height = top + span + 24
    left, right = 88.0, WIDTH - 152.0
    moved = [place for place in drawn if place[1] is not None and place[1] != place[0]]
    absent = [here for here, there in drawn if there is None]

    def height_of(place: int, of: int) -> float:
        """One position as a height: the first row at the top, the last at the bottom.

        Both axes are the whole of their own result, so a row of the gold that is the last
        row of the prediction is drawn at the foot of the right-hand axis whether the
        prediction holds twenty rows or ten thousand.
        """
        return top + span * (place - 1) / max(of - 1, 1)

    body = [
        f'<text class="figure__label" x="{left}" y="16" text-anchor="end">gold</text>',
        f'<text class="figure__label" x="{right}" y="16" text-anchor="start">prediction</text>',
        f'<line class="figure__axis" x1="{left}" y1="{top}" x2="{left}" y2="{top + span}"></line>',
        f'<line class="figure__axis" x1="{right}" y1="{top}" x2="{right}" '
        f'y2="{top + span}"></line>',
    ]
    written: list[float] = []
    placed: list[float] = []
    for here, there in drawn:
        y = height_of(here, gold.row_count)
        if _room(y, placed):
            # The same rule on both axes: a position is written where there is room for it.
            # Twenty-five rows of a forty-row result stand closer together than the numbers
            # that name them, and a column of overlapping digits states nothing.
            body.append(
                f'<text class="figure__number" x="{left - 8}" y="{y + 4:.1f}" '
                f'text-anchor="end">{here}</text>'
            )
            placed.append(y)
        if there is None:
            body.append(
                f'<text class="figure__number figure__number--warn" x="{left + 8}" '
                f'y="{y + 4:.1f}" text-anchor="start">not in the prediction</text>'
            )
            continue
        target = height_of(there, second.row_count)
        marked = " figure__line--moved" if there != here else ""
        body.append(
            f'<line class="figure__line{marked}" x1="{left}" y1="{y:.1f}" '
            f'x2="{right}" y2="{target:.1f}"></line>'
        )
        if _room(target, written):
            body.append(
                f'<text class="figure__number" x="{right + 8}" y="{target + 4:.1f}" '
                f'text-anchor="start">{there}</text>'
            )
            written.append(target)
    title = (
        f"where each row of the gold is in the prediction, from {_source(page)}, "
        f"{len(drawn):,} of {gold.row_count:,} rows drawn"
    )
    alternative = _slope_text(drawn, moved, absent, gold.row_count)
    return _figure("slope", title, alternative, height, body)


def _room(y: float, taken: Sequence[float]) -> bool:
    """Whether a number can be written at that height without landing on one already there."""
    return all(abs(y - other) >= SLOPE_STEP - 4 for other in taken)


def _slope_text(
    drawn: Sequence[tuple[int, int | None]],
    moved: Sequence[tuple[int, int | None]],
    absent: Sequence[int],
    total: int,
) -> str:
    """The slope chart in words: how many rows moved, how many are not there, and which.

    A row the prediction does not hold is drawn as the absence it is, so the sentence has to
    say so too: a caption reading "in the same places" over three marks that say "not in the
    prediction" would make the drawing the only carrier of the fact, which is the one thing
    a figure in this module may not be.
    """
    opening = f"first {len(drawn):,} rows of the gold, of {total:,}"
    if not moved and not absent:
        return f"The {opening}, are in the same places in the prediction."
    if len(absent) == len(drawn):
        return f"None of the {opening}, is in the prediction."
    named = ", ".join(
        f"row {here} of the gold is row {there} in the prediction" for here, there in moved[:8]
    )
    ending = "" if len(moved) <= 8 else f", and {len(moved) - 8:,} more"
    missing = f"{len(absent):,} {_is_are(len(absent))} not in the prediction at all"
    if not moved:
        return f"Of the {opening}, {missing}; the rest are where they are in the gold."
    somewhere = f"{len(moved):,} {_is_are(len(moved))} somewhere else in the prediction: {named}"
    tail = "." if not absent else f", and {missing}."
    return f"Of the {opening}, {somewhere}{ending}{tail}"


def _is_are(count: int) -> str:
    """Which verb a count takes, so a figure's own sentence reads as English."""
    return "is" if count == 1 else "are"


def _multiplicity(page: QuestionPage) -> Figure:
    """Two results holding the same rows a different number of times, and the mark they share.

    The bars are the two row counts; the rule across them is how many rows both hold at
    least once, counted from the two records. A reader sees at once that the two bars grew
    from one set of rows.
    """
    gold, second = _rows_of(page)
    shared = len(_distinct(gold) & _distinct(second))
    widest = max(gold.row_count, second.row_count, 1)
    height = 2 * (BAR_HEIGHT + BAR_GAP) + 24
    bars = ((gold.row_count, "gold"), (second.row_count, "prediction"))
    body: list[str] = []
    for index, (count, label) in enumerate(bars):
        y = index * (BAR_HEIGHT + BAR_GAP)
        width = _scaled(count, widest)
        body.append(
            f'<rect class="figure__bar" x="0" y="{y}" width="{width}" height="{BAR_HEIGHT}"></rect>'
        )
        body.append(
            f'<text class="figure__number" x="{width + 8}" y="{y + 16}">{count:,} {label}</text>'
        )
    mark = _scaled(shared, widest)
    rule_end = 2 * BAR_HEIGHT + BAR_GAP
    body.append(
        f'<line class="figure__mark" x1="{mark}" y1="-4" x2="{mark}" y2="{rule_end + 4}"></line>'
    )
    body.append(
        f'<text class="figure__number figure__number--warn" x="{mark + 8}" '
        f'y="{rule_end + 20}">{shared:,} rows both results hold</text>'
    )
    title = f"how many rows each result holds, and how many rows both hold, from {_source(page)}"
    alternative = (
        f"The gold returned {gold.row_count:,} rows and the prediction {second.row_count:,}. "
        f"{shared:,} rows occur in both results at least once."
    )
    return _figure("multiplicity", title, alternative, height, body)


def _truncation(page: QuestionPage) -> Figure:
    """One result and the shorter one that is its first rows, drawn as a bar and its prefix."""
    gold, second = _rows_of(page)
    longer, shorter = (gold, second) if gold.row_count >= second.row_count else (second, gold)
    names = ("gold", "prediction") if gold.row_count >= second.row_count else ("prediction", "gold")
    widest = max(longer.row_count, 1)
    prefix = _scaled(shorter.row_count, widest)
    height = 2 * (BAR_HEIGHT + BAR_GAP) + 8
    body = [
        f'<rect class="figure__bar" x="0" y="0" width="{_scaled(longer.row_count, widest)}" '
        f'height="{BAR_HEIGHT}"></rect>',
        f'<rect class="figure__bar figure__bar--marked" x="0" y="0" width="{prefix}" '
        f'height="{BAR_HEIGHT}"></rect>',
        f'<text class="figure__number" x="{_scaled(longer.row_count, widest) + 8}" y="16">'
        f"{longer.row_count:,} {names[0]}</text>",
        f'<rect class="figure__bar figure__bar--marked" x="0" y="{BAR_HEIGHT + BAR_GAP}" '
        f'width="{prefix}" height="{BAR_HEIGHT}"></rect>',
        f'<text class="figure__number figure__number--warn" x="{prefix + 8}" '
        f'y="{BAR_HEIGHT + BAR_GAP + 16}">{shorter.row_count:,} {names[1]}</text>',
    ]
    title = f"one result and the shorter one that is its first rows, from {_source(page)}"
    alternative = (
        f"The {names[0]} returned {longer.row_count:,} rows and the {names[1]} "
        f"{shorter.row_count:,}, which are the first {shorter.row_count:,} rows of the "
        f"other one in the same order."
    )
    return _figure("truncation", title, alternative, height, body)


def _verdicts(page: RunPage) -> Figure:
    """The run's verdicts as one bar, NOT_EQUAL cut into the classes the questions were put in.

    The classes are counted from the question directories that are there, and the verdicts
    from ``summary.json``. Where the two agree, every NOT_EQUAL question has a directory and a
    class, and the cut is the run's; where they do not, some directories are not here, as on a
    site that shows a selection of a run, and a cut would draw the selection as if it were the
    run. Then NOT_EQUAL is one part, as the summary states it.
    """
    parts: list[tuple[str, int, bool]] = []
    for verdict, count in page.verdict_counts:
        if verdict != "NOT_EQUAL":
            parts.append((verdict, count, verdict not in {"EQUAL", "GOLD-ONLY"}))
            continue
        classes = [(name, value) for name, value in page.mechanism_counts if value]
        if classes and sum(value for _, value in classes) == count:
            parts.extend((name, value, True) for name, value in classes)
        else:
            parts.append(("NOT_EQUAL", count, True))
    return proportion_bar(
        "verdicts",
        parts,
        title=f"the verdicts of run {page.run_id}, from summary.json",
        whole="Of the questions this run audited",
    )


def _probes(page: RunPage) -> Figure:
    """One bar per probe, against the number of questions the run audited."""
    audited = max(page.questions_audited, 1)
    height = len(page.probe_fired) * (BAR_HEIGHT + BAR_GAP) + 4
    body: list[str] = []
    for index, (name, count) in enumerate(page.probe_fired):
        y = index * (BAR_HEIGHT + BAR_GAP)
        # Clamped to the span a full bar fills. The two numbers come from two keys of one
        # summary and nothing ties them together: a document stating more firings than
        # questions would otherwise draw a bar off the canvas and take its label with it.
        width = max(min(_scaled(count, audited), BAR_SPAN), 1)
        marked = " figure__bar--marked" if count else ""
        body.append(
            f'<rect class="figure__bar{marked}" x="0" y="{y}" width="{width}" '
            f'height="{BAR_HEIGHT}"></rect>'
        )
        body.append(
            f'<text class="figure__number" x="{width + 8}" y="{y + 16}">'
            f"{count:,} {escape(name)}</text>"
        )
    title = f"how many golds each probe fired on, of {page.questions_audited:,}, from summary.json"
    fired = [f"{name} on {count:,}" for name, count in page.probe_fired if count]
    alternative = (
        f"Of {page.questions_audited:,} golds this run read, the probes fired on: "
        + ("; ".join(fired) if fired else "none")
        + "."
    )
    return _figure("probes", title, alternative, height, body)


SWATCH = 10
"""The side of the square a legend entry carries, in the colour of its part."""


@dataclass(frozen=True)
class _Segments:
    """The marks of one cut bar and the legend that names them, in the bar's order."""

    marks: tuple[str, ...]
    labels: tuple[str, ...]
    rows: int


def _segments(parts: Sequence[tuple[str, int, bool]], total: int) -> _Segments:
    """One bar cut into its parts, and a legend under it naming each in the bar's order.

    The names are a legend and not labels placed under their parts: a part of one question
    among five hundred is a pixel wide, and three such parts side by side have nowhere under
    them for three names. The legend flows left to right, each entry a square in the part's
    colour and its count and name, and starts another row where the next entry would run off
    the right edge. The text under the figure states every number whatever the legend did.
    """
    marks: list[str] = []
    labels: list[str] = []
    x = 0.0
    pen = 0.0
    row = 0
    for label, value, warn in parts:
        if not value:
            continue
        width = WIDTH * value / total if total else 0.0
        marked = " figure__bar--marked" if warn else ""
        # A pixel of paper between one part and the next. Two parts the same colour are two
        # parts, and a bar drawn without the gap reads as one: three ERROR questions beside
        # eight NOT_EQUAL ones are both marked, and a reader has to be able to see the join.
        marks.append(
            f'<rect class="figure__bar{marked}" x="{x:.1f}" y="0" '
            f'width="{max(width - 1, 1):.1f}" height="{BAR_HEIGHT}"></rect>'
        )
        text = f"{value:,} {label}"
        room = SWATCH + 6 + LABEL * len(text)
        if pen and pen + room > WIDTH:
            row += 1
            pen = 0.0
        baseline = BAR_HEIGHT + BAR_GAP + 13 + row * 16
        labels.append(
            f'<rect class="figure__bar{marked}" x="{pen:.1f}" y="{baseline - SWATCH}" '
            f'width="{SWATCH}" height="{SWATCH}"></rect>'
        )
        labels.append(
            f'<text class="figure__number" x="{pen + SWATCH + 6:.1f}" y="{baseline}">'
            f"{escape(text)}</text>"
        )
        pen += room + 16
        x += width
    return _Segments(marks=tuple(marks), labels=tuple(labels), rows=row + 1)


def _figure(name: str, title: str, alternative: str, height: int, body: Sequence[str]) -> Figure:
    """The SVG around the marks: the box it is drawn in, its title and what describes it."""
    box = height + 16
    svg = (
        f'<svg class="figure__svg figure__svg--{name}" role="img" width="{WIDTH}" '
        f'height="{box}" viewBox="0 -8 {WIDTH} {box}" '
        f'aria-describedby="figure-{name}-text" xmlns="http://www.w3.org/2000/svg">'
        f"<title>{escape(title)}</title>" + "".join(body) + "</svg>"
    )
    return Figure(name=name, title=title, alternative=alternative, svg=svg)


def _rows_of(page: QuestionPage) -> tuple[Rows, Rows]:
    """The two results a figure is drawn from: the records', which hold every row."""
    if len(page.records) == 2:
        return page.records[0].result, page.records[1].result
    return page.sides[0].result, page.sides[1].result


def _source(page: QuestionPage) -> str:
    """Which files the figure's numbers were read from, for its ``<title>``.

    Unescaped: a title is escaped once, where it is put into the markup, and a name escaped
    here as well would reach the ``<title>`` as ``&amp;amp;`` and read as ``&amp;``.
    """
    if len(page.records) == 2:
        return f"{page.records[0].file} and {page.records[1].file}"
    return "counterexample.json"


def _values(rows: Rows) -> list[tuple[str, ...]]:
    """Each row as the text its cells were rendered as: what a figure compares two rows by."""
    return [tuple(cell.text for cell in row.cells) for row in rows.rows]


def _distinct(rows: Rows) -> set[tuple[str, ...]]:
    return set(_values(rows))


def _places(gold: Rows, second: Rows) -> list[tuple[int, int | None]]:
    """Each row of the gold, in order, with the place it holds in the second result.

    A row that occurs more than once takes its occurrences in order, so two equal rows are
    not both drawn to the first of them, and a row the second result does not hold is drawn
    as the absence it is.
    """
    taken: Counter[tuple[str, ...]] = Counter()
    where: dict[tuple[str, ...], list[int]] = {}
    for index, row in enumerate(_values(second), start=1):
        where.setdefault(row, []).append(index)
    places: list[tuple[int, int | None]] = []
    for index, row in enumerate(_values(gold), start=1):
        found = where.get(row, ())
        used = taken[row]
        places.append((index, found[used] if used < len(found) else None))
        taken[row] += 1
    return places


def _scaled(value: int, widest: int) -> int:
    """One count as a length in the figure's own coordinates, the widest filling the bar."""
    return round(BAR_SPAN * value / widest) if widest else 0


__all__ = ["Figure", "proportion_bar", "question_figure", "run_figures"]
