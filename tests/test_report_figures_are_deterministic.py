"""The figures: the same bytes twice, a title, a text alternative, and one line per row.

A figure on these pages is a string built from integers the view model already holds, which
is what makes two renderings of one directory the same page. So the first thing asserted
here is that: build it twice from the same model and compare the bytes. A drawing that
reached a clock, a random number or the order a set happened to iterate in would fail here
and nowhere else, because it would still look right.

The rest is what the design spec asks of a figure: it names its data source in a ``<title>``,
it carries a text alternative stating the same numbers, and it points at that alternative so
a reader who does not see the drawing is told what it holds. A figure is never the only
carrier of a fact, and these three are how that is kept true.

The model is built here rather than audited, because a figure is a function of the model and
the interesting inputs are not the ones a small sandbox produces: a slope chart is about a
result whose rows moved, and this file states exactly which ones did.
``tests/test_report_renders_an_audit_directory.py`` is where the figures are asserted on the
pages of a real run.
"""

from __future__ import annotations

import re

import pytest

from attestql.report.figures import Figure, proportion_bar, question_figure, run_figures
from attestql.report.render import (
    Cell,
    Column,
    Fact,
    Mechanism,
    QuestionPage,
    Record,
    Row,
    Rows,
    RunPage,
    Side,
    Source,
)

MOVED: tuple[int, ...] = (3, 1, 5, 2, 4, 7, 6, 9, 8, 10)
"""A known ``order`` counterexample: ten rows, the prediction holding the gold's own rows in
this order. Only the tenth is where it was, so nine of the ten moved and a slope chart of it
draws ten lines, nine of them marked."""

TITLE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
LINE = re.compile(r'<line class="figure__line')


def rows(values: tuple[int, ...], source: str) -> Rows:
    """One single-column table of integers, as a result of that many rows."""
    return Rows(
        source=source,
        columns=(Column(name="n", declared_type="integer"),),
        rows=tuple(
            Row(
                cells=(Cell(tag="int", text=str(value), is_null=False, show_tag=False),),
                count=None,
                label="",
                glyph="",
            )
            for value in values
        ),
        row_count=len(values),
        rows_shown=len(values),
        truncated=False,
        counted=False,
        labelled=False,
    )


def record(side: str, result: Rows) -> Record:
    """One record with nothing on it but the result a figure reads."""
    return Record(
        file=f"evidence-{side}.json",
        side=side,
        executed_sql="SELECT n FROM sequence",
        source=Source(path="questions.json", digest="", origin="", date=""),
        identity=(),
        session=(),
        recorded=(),
        serialization=(),
        fixture=(),
        result=result,
        hashes=(),
        rerun_instruction="",
    )


def page(classification: str, gold: tuple[int, ...], second: tuple[int, ...]) -> QuestionPage:
    """A question page carrying two results and the class they were put in."""
    gold_rows = rows(gold, "evidence-gold.json")
    second_rows = rows(second, "evidence-second.json")
    return QuestionPage(
        slug="q1",
        question_id="1",
        question_set="questions",
        question_text="what are the numbers?",
        evidence_text="",
        replay_rule="R-ORD",
        verdict="NOT_EQUAL",
        verdict_reading="",
        mismatched=(),
        mechanism=Mechanism(classification=classification, reading="", facts=()),
        projection=None,
        backend_identity="",
        run_id="run",
        sides=(
            Side(
                side="gold",
                glyph="",
                tokens=(),
                ordering=(),
                result=gold_rows,
                result_hash="",
                record_file="evidence-gold.json",
            ),
            Side(
                side="second",
                glyph="",
                tokens=(),
                ordering=(),
                result=second_rows,
                result_hash="",
                record_file="evidence-second.json",
            ),
        ),
        differences=(),
        readings=(),
        probes=(),
        probes_reading="",
        records=(record("gold", gold_rows), record("second", second_rows)),
        files=(),
    )


def run_page() -> RunPage:
    """A run page carrying the counts the two run figures are drawn from."""
    return RunPage(
        run_id="audit-1",
        format="attestql/audit/summary/1",
        exit_status=1,
        questions_audited=13,
        counts=(),
        verdict_counts=(("EQUAL", 1), ("NOT_EQUAL", 8), ("ERROR", 3), ("GOLD-ONLY", 1)),
        mechanism_counts=(("other", 3), ("order", 2), ("multiplicity", 1), ("truncation", 1)),
        probe_counts=(Fact("arbitrary-cut", "1"), Fact("float-aggregate-order", "0")),
        credited=(),
        made_of=(),
        session=(),
        notes=(),
        entries=(),
        files=(),
    )


def every_figure() -> list[tuple[str, Figure]]:
    """One of each: the three a question can carry, the two a run does, and the landing bar."""
    ordered = page("order", tuple(range(1, 11)), MOVED)
    multiplicity = page("multiplicity", (1, 2, 3), (1, 1, 2, 2, 3, 3))
    truncation = page("truncation", (1, 2, 3, 4), (1, 2))
    verdicts, probes = run_figures(run_page())
    found = [
        ("order", question_figure(ordered)),
        ("multiplicity", question_figure(multiplicity)),
        ("truncation", question_figure(truncation)),
        ("verdicts", verdicts),
        ("probes", probes),
        (
            "landing",
            proportion_bar(
                "credited",
                (("credited", 164, False), ("of them NOT_EQUAL", 69, True)),
                title="the headline finding, from summary.json",
                whole="Of the predictions the benchmark credits",
            ),
        ),
    ]
    return [(name, figure) for name, figure in found if figure is not None]


FIGURES = every_figure()


@pytest.mark.parametrize("name", [name for name, _ in FIGURES], ids=lambda name: name)
def test_a_figure_is_the_same_bytes_twice(name: str) -> None:
    """The same model twice, the same SVG twice: no clock, no random, no set iteration."""
    first = dict(FIGURES)[name]

    second = dict(every_figure())[name]

    assert first.svg == second.svg
    assert first.alternative == second.alternative


@pytest.mark.parametrize(("name", "figure"), FIGURES, ids=lambda value: str(value))
def test_a_figure_names_its_data_source_and_states_its_numbers(name: str, figure: Figure) -> None:
    """A ``<title>`` naming the files, a text alternative, and the SVG pointing at it.

    The alternative is asserted to hold a number rather than to exist, because a figure
    whose description said "a bar chart" would satisfy the letter of the rule and none of
    what it is for.
    """
    stated = TITLE.search(figure.svg)

    assert stated is not None, f"the {name} figure states no title"
    assert stated.group(1) == figure.title
    assert re.search(r"\.json|summary", figure.title), f"{figure.title} names no file"
    assert re.search(r"\d", figure.alternative), f"{figure.alternative} states no number"
    assert f'aria-describedby="{figure.described_by}"' in figure.svg
    assert figure.svg.startswith("<svg ") and figure.svg.endswith("</svg>")


def test_the_slope_chart_draws_one_line_per_row_of_a_known_counterexample() -> None:
    """Ten rows in, ten lines out, and the nine that moved marked as the ones that did.

    The known counterexample is ``MOVED``, which is the prediction's rows in the prediction's
    order. Only the tenth row of the gold is where it was; the other nine are somewhere else,
    which is what the figure has to draw and what its own text has to say.
    """
    figure = question_figure(page("order", tuple(range(1, 11)), MOVED))

    assert figure is not None
    lines = LINE.findall(figure.svg)
    moved = figure.svg.count("figure__line--moved")

    assert len(lines) == len(MOVED)
    assert moved == sum(1 for place, value in enumerate(MOVED, start=1) if value != place)
    assert "9 are somewhere else in the prediction" in figure.alternative


def test_the_class_the_table_already_states_gets_no_figure() -> None:
    """``type`` has none: the declared type in the column header is where a reader sees it."""
    typed = page("type", (1, 2), (1, 2))
    other = page("other", (1, 2), (3, 4))

    assert question_figure(typed) is None
    assert question_figure(other) is None
