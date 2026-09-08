"""``attestql report`` over a directory the audit wrote: what the pages state, structurally.

The fixture is ``attestql demo``: it writes the packaged SQLite sandbox somewhere and audits
it, which needs no container and no credential, so these tests run wherever the suite does
and read the same six questions ``tests/test_demo_runs_the_packaged_sandbox.py`` reads.

What is observed is the page as a reader meets it, parsed with ``html.parser`` rather than
searched as a string: the run page's counts against ``summary.json``, a comparison page's two
statements, its verdict, its two differing-rows sections, both published readings and its four
JSON links, a gold-only page's record and its probes in all three states, and an ERROR
question, which has no directory, as a row of the run page with the side that stopped and the
engine's own message.

Where the pages go is asserted here too, because a render writes into a directory a reader
may also be keeping files in: an ``--out`` naming the audit directory or a directory inside
it is refused before anything is written, a rerun clears what the render before it wrote,
and a directory holding files this command did not write is refused untouched.

Two of the tests hand the renderer a document that has been changed after the audit wrote it,
because both cases are what a page is for: a statement holding ``<script>`` is escaped, and a
record whose bytes no longer hash to what it states says so beside the hash instead of
stating a match nobody checked.
"""

from __future__ import annotations

import io
import json
import re
import shutil
from contextlib import redirect_stdout
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.cli import main
from attestql.audit.postgres import session_preconditions
from attestql.audit.smells import SMELL_NAMES, probe_meanings
from attestql.report import ReportRefused, default_out, render_report
from attestql.report.render import (
    BY_MECHANISM_DIRECTORY,
    BY_PROBE_DIRECTORY,
    COUNTEREXAMPLE_FILE,
    FILTER_DIRECTORIES,
    GOLD_RECORD_FILE,
    MARKER_FILE,
    MARKER_TEXT,
    NOT_EQUAL_DIRECTORY,
    PAGE_FILE,
    SECOND_RECORD_FILE,
    SMELLS_FILE,
    STATIC,
    SUMMARY_FILE,
)

pytestmark = pytest.mark.sandbox_sqlite

DEMO_AUDIT = "audit"
"""Where ``attestql demo`` puts the audit it makes, under the directory it was given."""

MISSING_TABLE = "SELECT name FROM a_table_this_database_does_not_hold ORDER BY name"
"""A gold that reaches no table of the sandbox: the run answers the question with an error
line, counts it, and writes no directory for it, which is the state the run page has to
render from the summary alone."""


@dataclass
class Page:
    """One rendered page, read as a reader's browser would read it rather than as text.

    ``rows`` holds every table row as its cells, which is how the counts and the question
    index are asserted; ``links`` holds every href, which is how the JSON beside a page is;
    and ``text`` is what a reader sees, with the markup gone.
    """

    text: str
    links: tuple[str, ...]
    classes: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def row_of(self, name: str) -> tuple[str, ...]:
        found = [row for row in self.rows if row and row[0] == name]
        assert len(found) == 1, f"{name} is on {len(found)} rows"
        return found[0]


class _Read(HTMLParser):
    """The whole of the reading: the text, the hrefs, the classes and the table rows."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[str] = []
        self.classes: list[str] = []
        self.rows: list[tuple[str, ...]] = []
        self.cells: list[str] = []
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        stated = dict(attrs)
        if tag == "a" and stated.get("href"):
            self.links.append(str(stated["href"]))
        self.classes.extend(str(stated.get("class", "")).split())
        if tag == "tr":
            self.cells = []
        if tag in {"td", "th"}:
            self.cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None:
            self.cells.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr":
            self.rows.append(tuple(self.cells))

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)


def _is_a_question_row(row: tuple[str, ...]) -> bool:
    """One row of a question index rather than its header: the first cell is ``q<id>``."""
    return bool(row) and row[0].startswith("q") and row[0][1:].isdigit()


def read(path: Path) -> Page:
    parser = _Read()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return Page(
        text=" ".join("".join(parser.text).split()),
        links=tuple(parser.links),
        classes=tuple(parser.classes),
        rows=tuple(parser.rows),
    )


def document(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def write(path: Path, stated: dict[str, Any]) -> None:
    path.write_text(json.dumps(stated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(argv: list[str]) -> tuple[int, list[str]]:
    """The command, with the lines kept instead of printed."""
    printed = io.StringIO()
    with redirect_stdout(printed):
        status = main(argv)
    return status, printed.getvalue().splitlines()


@dataclass(frozen=True)
class Rendered:
    """One demo audit and the report rendered from it."""

    audit: Path
    out: Path
    summary: dict[str, Any]

    def page(self, *parts: str) -> Page:
        return read(self.out.joinpath(*parts, PAGE_FILE))


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Rendered:
    """One demo, audited and rendered once, for the readings that only look at it."""
    sandbox = tmp_path_factory.mktemp("demo") / "sandbox"
    status, _ = run(["demo", "--out", str(sandbox)])
    assert status == 1, "three of the packaged golds disagree with their corrections"
    audit = sandbox / DEMO_AUDIT
    out = sandbox / "report"
    assert run(["report", str(audit), "--out", str(out)])[0] == 0
    return Rendered(audit=audit, out=out, summary=document(audit / SUMMARY_FILE))


def test_the_run_page_states_the_counts_and_the_digests_of_its_summary(
    rendered: Rendered,
) -> None:
    """Every count on the run page is one ``summary.json`` states, and the file it was read
    from is named on the page and copied beside it."""
    page = rendered.page()
    summary = rendered.summary

    assert page.row_of("questions audited") == ("questions audited", "6")
    for verdict, count in cast("dict[str, int]", summary["verdicts"]).items():
        assert page.row_of(verdict) == (verdict, str(count))
    assert page.row_of("probes fired") == ("probes fired", str(summary["smells_fired"]))
    for probe, count in cast("dict[str, int]", summary["smells"]).items():
        assert page.row_of(probe) == (probe, str(count))
    assert summary["format"] in page.text
    assert cast("dict[str, str]", summary["question_set"])["digest"] in page.text
    assert cast("dict[str, str]", summary["predictions"])["digest"] in page.text
    assert cast("dict[str, str]", summary["fixture"])["schema_digest"] in page.text
    assert summary["run_id"] in page.text
    assert SUMMARY_FILE in page.links
    assert (rendered.out / SUMMARY_FILE).is_file()


def test_the_run_page_indexes_every_question_that_wrote_a_directory(
    rendered: Rendered,
) -> None:
    """One row per directory, each linking to the page rendered from it, in id order."""
    page = rendered.page()
    written = sorted(
        (int(directory.name[1:]), directory.name)
        for directory in rendered.audit.iterdir()
        if directory.is_dir()
    )

    assert [f"{name}/{PAGE_FILE}" for _, name in written] == [
        link for link in page.links if link.endswith(PAGE_FILE) and link.startswith("q")
    ]
    assert page.row_of("q879")[1:3] == ("R-ORD", "NOT_EQUAL")
    assert page.row_of("q900001")[2] == "GOLD-ONLY"
    assert page.row_of("q900005")[2] == "EQUAL"


def test_a_comparison_page_holds_both_statements_the_verdict_and_the_readings(
    rendered: Rendered,
) -> None:
    """The question page of q879, whole: what was asked, both statements, what came of the
    two results, and the four files it was rendered from, beside it."""
    page = rendered.page("q879")
    counterexample = document(rendered.audit / "q879" / COUNTEREXAMPLE_FILE)
    gold = cast("dict[str, Any]", counterexample["gold"])
    second = cast("dict[str, Any]", counterexample["second"])
    verdict = cast("dict[str, str]", counterexample["verdict"])
    mechanism = cast("dict[str, str]", counterexample["mechanism"])
    hashes = cast("dict[str, str]", counterexample["result_hashes"])

    assert str(gold["executed_sql"]) in page.text
    assert str(second["executed_sql"]) in page.text
    assert "NOT_EQUAL" in page.text
    assert counterexample["replay_rule"] == "R-ORD"
    assert "R-ORD" in page.text
    assert verdict["reading"] in page.text, "the JSON's own reading, verbatim"
    assert mechanism["class"] in page.text
    assert mechanism["reading"] in page.text
    assert "in gold, not in the prediction" in page.text
    assert "in the prediction, not in gold" in page.text
    assert str(cast("dict[str, str]", counterexample["bird_ex"])["method"]) in page.text
    assert str(cast("dict[str, str]", counterexample["test_suite_ex"])["method"]) in page.text
    assert hashes["gold"] in page.text
    assert hashes["second"] in page.text
    assert set(page.links) >= {
        COUNTEREXAMPLE_FILE,
        GOLD_RECORD_FILE,
        SECOND_RECORD_FILE,
        SMELLS_FILE,
    }
    for name in (COUNTEREXAMPLE_FILE, GOLD_RECORD_FILE, SECOND_RECORD_FILE, SMELLS_FILE):
        assert (rendered.out / "q879" / name).is_file(), name


def test_a_gold_only_page_holds_the_record_and_every_probe_that_ran(
    rendered: Rendered,
) -> None:
    """q900001 had no prediction: the gold's own record is the evidence, and the probes are
    rendered fired, quiet and not applicable alike, each with what the file says it means.

    Its three probes are one of each state, which is why this question and not another: a
    page that rendered only the fired ones would be a page a reader could not tell a quiet
    probe from a probe that never ran on."""
    page = rendered.page("q900001")
    record = document(rendered.audit / "q900001" / GOLD_RECORD_FILE)
    probes = cast(
        "list[dict[str, Any]]", document(rendered.audit / "q900001" / SMELLS_FILE)["smells"]
    )

    assert "GOLD-ONLY" in page.text
    assert str(record["executed_sql"]) in page.text
    assert str(record["record_hash"]) in page.text
    assert [probe["name"] for probe in probes] == [
        name for name in SMELL_NAMES if name in {probe["name"] for probe in probes}
    ], "the probes are on the page in the order the file lists them"
    for probe in probes:
        assert str(probe["name"]) in page.text
        assert str(cast("dict[str, str]", probe["evidence"])["means"]) in page.text
    states = {"fired": False, "quiet": False, "not applicable": False}
    for probe in probes:
        if probe["fired"]:
            states["fired"] = True
        elif probe["applicable"]:
            states["quiet"] = True
        else:
            states["not applicable"] = True
    assert all(states.values()), "this question exercises all three probe states"
    for state, seen in states.items():
        assert seen and state in page.text
    assert set(page.links) >= {GOLD_RECORD_FILE, SMELLS_FILE}
    assert not (rendered.out / "q900001" / COUNTEREXAMPLE_FILE).exists()


def test_every_record_on_every_page_carries_its_hashes_taken_again(
    rendered: Rendered,
) -> None:
    """The line the whole loader is for, on both records of every question that has two."""
    pages = [
        rendered.page(directory.name)
        for directory in sorted(rendered.out.iterdir())
        if directory.is_dir() and directory.name.startswith("q")
    ]

    assert len(pages) == 6
    for page in pages:
        records = [name for name in (GOLD_RECORD_FILE, SECOND_RECORD_FILE) if name in page.links]
        # Two hashes per record, and the same sentence beside each of them.
        assert page.text.count("recomputed from this JSON: match") == 2 * len(records)


def test_the_filter_pages_hold_the_rows_the_run_page_and_the_summary_state(
    rendered: Rendered,
) -> None:
    """Every filter is the index restricted, and the restriction is one the summary counts.

    A static host reads no query string, so a filtered view is a directory. What is asserted
    is that each one holds exactly the rows its rule keeps: the NOT_EQUAL page holds the
    summary's own NOT_EQUAL count, each probe page holds the golds the summary says that probe
    fired on, and every row of every filter is a row of the whole index.
    """
    whole = rendered.page()
    summary = rendered.summary
    every = {row[0] for row in whole.rows if _is_a_question_row(row)}

    not_equal = rendered.page(NOT_EQUAL_DIRECTORY)
    kept = [row for row in not_equal.rows if _is_a_question_row(row)]
    assert len(kept) == cast("dict[str, int]", summary["verdicts"])["NOT_EQUAL"]
    assert all(row[2] == "NOT_EQUAL" for row in kept)
    assert {row[0] for row in kept} <= every
    assert "The questions of this run whose verdict is NOT_EQUAL." in not_equal.text
    assert f"../{PAGE_FILE}" in not_equal.links, "a link back to the whole index"

    for probe, count in cast("dict[str, int]", summary["smells"]).items():
        page = rendered.out / BY_PROBE_DIRECTORY / probe / PAGE_FILE
        assert page.is_file() == bool(count), probe
        if count:
            rows = [row for row in read(page).rows if _is_a_question_row(row)]
            assert len(rows) == count, probe
            assert all(probe in row[4] for row in rows), probe
            assert f"../../{PAGE_FILE}" in read(page).links, probe

    for classification in {row[3] for row in whole.rows if _is_a_question_row(row) and row[3]}:
        rows = [
            row
            for row in read(rendered.out / BY_MECHANISM_DIRECTORY / classification / PAGE_FILE).rows
            if _is_a_question_row(row)
        ]
        assert rows, classification
        assert all(row[3] == classification for row in rows), classification


def test_a_filter_no_question_of_this_run_satisfies_is_not_written(
    rendered: Rendered,
) -> None:
    """A link to an empty index is a reader's wasted click, so the page is not written.

    ``multiplicity`` is a class of the tool that this sandbox produces no question in, and
    two of the five probes fire on none of its golds. Neither gets a directory, and the run
    page links to neither.
    """
    page = rendered.page()

    assert not (rendered.out / BY_MECHANISM_DIRECTORY / "multiplicity").exists()
    for quiet in ("float-aggregate-order", "direction-against-question"):
        assert not (rendered.out / BY_PROBE_DIRECTORY / quiet).exists(), quiet
    written = sorted(
        path.parent.relative_to(rendered.out).as_posix()
        for name in FILTER_DIRECTORIES
        for path in (rendered.out / name).rglob(PAGE_FILE)
    )
    assert written == sorted(
        link.removesuffix(f"/{PAGE_FILE}")
        for link in page.links
        if link.startswith(tuple(FILTER_DIRECTORIES))
    )


def test_a_class_or_a_probe_that_is_not_a_name_writes_no_directory_and_nothing_outside(
    tmp_path: Path,
) -> None:
    """The one place text out of a document becomes a path, and where it stops.

    This command is documented to render a directory another machine produced, so a
    ``mechanism.class`` and a probe ``name`` are untrusted text; both reach ``out / slug``.
    Before the guard, a class of ``../../..`` wrote a page outside the ``--out`` the caller
    chose, which a template engine does not prevent because a path is not markup. The name is
    still a chip on both pages: what is dropped is a pre-rendered view, not a fact.
    """
    sandbox = tmp_path / "sandbox"
    assert run(["demo", "--out", str(sandbox)])[0] == 1
    audit = sandbox / DEMO_AUDIT
    escape = "../../../../../../" + tmp_path.name + "-escaped"
    counterexample = document(audit / "q879" / COUNTEREXAMPLE_FILE)
    cast("dict[str, Any]", counterexample["mechanism"])["class"] = escape
    write(audit / "q879" / COUNTEREXAMPLE_FILE, counterexample)
    smells = document(audit / "q879" / SMELLS_FILE)
    for probe in cast("list[dict[str, Any]]", smells["smells"]):
        if probe["fired"]:
            probe["name"] = escape
    write(audit / "q879" / SMELLS_FILE, smells)
    out = tmp_path / "report"

    render_report(audit, out)

    assert not list(tmp_path.parent.glob(f"{tmp_path.name}-escaped")), "nothing outside --out"
    assert sorted(path.name for path in (out / BY_MECHANISM_DIRECTORY).iterdir()) == [
        "other",
        "truncation",
    ], "q1029 is still an `other`; q879's class is not a name and got no directory"
    assert escape not in {path.name for path in (out / BY_PROBE_DIRECTORY).iterdir()}
    assert not any(".." in path.as_posix() for path in out.rglob("*")), (
        "no path this render wrote climbs out of the directory it was given"
    )
    page = read(out / PAGE_FILE)
    assert escape in page.text, "the class the document states is still on the run page"
    assert not [link for link in page.links if "escaped" in link], "and reaches no link"


def test_an_error_question_is_a_row_of_the_run_page_and_has_no_page(tmp_path: Path) -> None:
    """A statement the engine could not run wrote no directory, so the run page states it
    from the summary's own error list: the side that stopped and the message it stopped with.
    """
    sandbox = tmp_path / "sandbox"
    assert run(["demo", "--out", str(sandbox)])[0] == 1
    questions = tmp_path / "questions.json"
    write(
        questions,
        cast(
            "dict[str, Any]",
            [
                {
                    "question_id": 900301,
                    "db_id": "synthetic",
                    "question": "What does a table that is not there hold?",
                    "evidence": "",
                    "SQL": MISSING_TABLE,
                    "difficulty": "simple",
                }
            ],
        ),
    )
    audit = tmp_path / "audit"
    status, _ = run(
        [
            "audit",
            "--engine",
            "sqlite",
            "--dsn",
            str(sandbox / "fixture.sqlite"),
            "--questions",
            str(questions),
            "--out",
            str(audit),
        ]
    )
    assert status == 2, "this run answered no question at all"
    out = tmp_path / "report"
    assert run(["report", str(audit), "--out", str(out)])[0] == 0

    page = read(out / PAGE_FILE)
    error = cast("list[dict[str, str]]", document(audit / SUMMARY_FILE)["errors"])[0]

    assert page.row_of("q900301")[2] == "ERROR"
    assert error["side"] in page.text
    assert error["message"] in page.text
    assert not (out / "q900301").exists(), "a question that errored wrote no directory"
    assert not [link for link in page.links if link.endswith(PAGE_FILE)]


def test_an_out_inside_the_audit_directory_is_refused_with_nothing_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A report goes beside an audit and never into one.

    The audit's own rerun clears its directory, so a report written there is removed by the
    next run or left stale beside it, and a report written onto it would copy the evidence
    over itself. Both paths are resolved first, so the directory named through ``..`` is the
    same answer as the directory named directly. Nothing is written in any of the three.
    """
    sandbox = tmp_path / "sandbox"
    assert run(["demo", "--out", str(sandbox)])[0] == 1
    audit = sandbox / DEMO_AUDIT
    before = sorted(path.name for path in audit.iterdir())

    for out in (audit, audit / "pages", Path(f"{audit}/../{DEMO_AUDIT}")):
        status, lines = run(["report", str(audit), "--out", str(out)])

        assert status == 2, out
        assert lines == []
        assert "is the audit directory" in capsys.readouterr().err
        assert sorted(path.name for path in audit.iterdir()) == before, out
        assert not (audit / PAGE_FILE).exists()


def test_a_rerun_clears_the_render_before_it(rendered: Rendered, tmp_path: Path) -> None:
    """A reader opens the output directory and reads it as one report.

    A question page an earlier render wrote and this one does not is a page about a question
    that is not in this run, so the rerun removes what it wrote before writing again: the
    marker says which directory that rule applies to.
    """
    out = tmp_path / "report"
    render_report(rendered.audit, out)
    stale = out / "q999" / PAGE_FILE
    stale.parent.mkdir()
    stale.write_text("a page for a question this run does not hold", encoding="utf-8")
    (out / "static" / "stale.css").write_text("body {}", encoding="utf-8")

    render_report(rendered.audit, out)

    assert not stale.exists()
    assert not stale.parent.exists()
    assert not (out / "static" / "stale.css").exists()
    assert (out / MARKER_FILE).is_file()
    assert sorted(path.name for path in out.iterdir()) == sorted(
        [MARKER_FILE, PAGE_FILE, SUMMARY_FILE, "static", *FILTER_DIRECTORIES]
        + [directory.name for directory in rendered.audit.iterdir() if directory.is_dir()]
    )


def test_a_rerun_clears_a_filter_the_run_before_it_wrote(
    rendered: Rendered, tmp_path: Path
) -> None:
    """The filters are cleared by the same rule the question directories are.

    A mechanism the run before held and this one does not is a filter page listing questions
    that are not in this run, which is the state the clear exists to prevent.
    """
    out = tmp_path / "report"
    render_report(rendered.audit, out)
    stale = out / BY_MECHANISM_DIRECTORY / "a-class-no-run-holds" / PAGE_FILE
    stale.parent.mkdir(parents=True)
    stale.write_text("a filter for a class this run does not hold", encoding="utf-8")

    render_report(rendered.audit, out)

    assert not stale.exists()
    assert not stale.parent.exists()
    assert (out / NOT_EQUAL_DIRECTORY / PAGE_FILE).is_file()
    assert MARKER_TEXT.count(BY_MECHANISM_DIRECTORY) == 1, "the marker says what is removed"


def test_a_directory_this_command_did_not_write_is_refused_untouched(
    rendered: Rendered, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--out`` named a directory of the reader's own: deleting from it would cost them
    files this command never wrote, so it is refused with nothing in it removed."""
    mine = tmp_path / "mine"
    mine.mkdir()
    (mine / "notes.md").write_text("mine", encoding="utf-8")

    status, lines = run(["report", str(rendered.audit), "--out", str(mine)])

    assert status == 2
    assert lines == []
    assert f"holds no {MARKER_FILE}" in capsys.readouterr().err
    assert [path.name for path in mine.iterdir()] == ["notes.md"]
    assert (mine / "notes.md").read_text(encoding="utf-8") == "mine"


def test_an_empty_directory_and_a_directory_that_is_not_there_are_both_taken_over(
    rendered: Rendered, tmp_path: Path
) -> None:
    """The two cases a first render meets, both written into and both marked."""
    empty = tmp_path / "empty"
    empty.mkdir()
    missing = tmp_path / "missing" / "under it"

    for out in (empty, missing):
        assert render_report(rendered.audit, out).out == out
        assert (out / PAGE_FILE).is_file(), out
        assert (out / MARKER_FILE).read_text(encoding="utf-8").startswith("written by attestql")


def test_a_question_the_budget_stopped_is_a_row_of_the_run_page_with_the_bound(
    rendered: Rendered, tmp_path: Path
) -> None:
    """The other state the summary lists without a directory of its own.

    Nothing in either sandbox reaches the bound, so the summary is given the shape a run that
    did reach it writes: the ids under the side that stopped. The page states them with the
    bound the run was given, because the record of a side that never answered holds none.
    """
    audit = tmp_path / "audit"
    shutil.copytree(rendered.audit, audit)
    summary = document(audit / SUMMARY_FILE)
    summary["timed_out"] = {"gold": [879], "prediction": []}
    write(audit / SUMMARY_FILE, summary)

    render_report(audit, tmp_path / "report")
    page = read(tmp_path / "report" / PAGE_FILE)

    assert "stopped by the statement timeout, gold" in page.text
    assert "879 the run's bound was 30 s" in page.text
    assert "stopped by the statement timeout, prediction" not in page.text


def test_a_statement_holding_markup_is_escaped(rendered: Rendered, tmp_path: Path) -> None:
    """SQL is text from a question file and a prediction file, and reaches the page as text.

    The counterexample is changed after the audit wrote it, which is what an untrusted
    document is: whatever it holds, the page states it and does not become it.
    """
    audit = tmp_path / "audit"
    shutil.copytree(rendered.audit, audit)
    counterexample = document(audit / "q879" / COUNTEREXAMPLE_FILE)
    cast("dict[str, Any]", counterexample["gold"])["executed_sql"] = "SELECT <script>alert(1)"
    write(audit / "q879" / COUNTEREXAMPLE_FILE, counterexample)

    rendered_page = tmp_path / "report" / "q879" / PAGE_FILE
    render_report(audit, tmp_path / "report")
    markup = rendered_page.read_text(encoding="utf-8")

    assert "<script>alert(1)" not in markup
    assert "&lt;" in markup, "the angle brackets are escaped where the statement is rendered"
    # The tokens the two statements differ in are marked one by one, so the escaped text is
    # spread over several elements; what a reader sees is what the parser reads back.
    assert "SELECT <script>alert(1)" in read(rendered_page).text


def test_a_record_whose_bytes_changed_states_both_hashes(
    rendered: Rendered, tmp_path: Path
) -> None:
    """The other half of the recomputed line: a record that no longer hashes to what it
    states has the two values beside each other rather than a match nobody checked."""
    audit = tmp_path / "audit"
    shutil.copytree(rendered.audit, audit)
    record = document(audit / "q879" / GOLD_RECORD_FILE)
    record["executed_sql"] = f"{record['executed_sql']} -- changed after the audit wrote it"
    write(audit / "q879" / GOLD_RECORD_FILE, record)

    render_report(audit, tmp_path / "report")
    page = read(tmp_path / "report" / "q879" / PAGE_FILE)

    assert "recomputed from this JSON: match" in page.text, "the prediction's record is intact"
    assert f"and this file states {record['record_hash']}" in page.text


def test_rendering_the_same_directory_twice_writes_the_same_bytes(
    rendered: Rendered, tmp_path: Path
) -> None:
    """No clock is read and no generation time is written, so a rerun changes nothing."""
    first = render_report(rendered.audit, tmp_path / "first")
    second = render_report(rendered.audit, tmp_path / "second")

    for one, other in ((first.pages, second.pages), (first.filters, second.filters)):
        assert [path.name for path in one] == [path.name for path in other]
        for page, again in zip(one, other, strict=True):
            assert page.read_bytes() == again.read_bytes(), page.name
    assert first.filters, "the demo holds a NOT_EQUAL row, so it has at least one filter"


def test_the_report_goes_beside_the_audit_when_the_command_line_does_not_say(
    tmp_path: Path,
) -> None:
    """The default ``--out`` is the audit directory's sibling and never a directory inside
    it, which the audit's own rerun would clear."""
    sandbox = tmp_path / "sandbox"
    assert run(["demo", "--out", str(sandbox)])[0] == 1
    audit = sandbox / DEMO_AUDIT

    assert run(["report", str(audit)])[0] == 0

    beside = default_out(audit)
    assert beside == audit.resolve().parent / f"{DEMO_AUDIT}-report"
    assert (beside / PAGE_FILE).is_file()
    assert not (audit / PAGE_FILE).exists()


def test_a_directory_that_is_not_an_audit_s_is_refused_with_the_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit status 2 and a line naming what was looked for: nothing was rendered."""
    empty = tmp_path / "not-an-audit"
    empty.mkdir()

    status, lines = run(["report", str(empty)])

    assert status == 2
    assert lines == []
    assert f"attestql: {empty} holds no {SUMMARY_FILE}" in capsys.readouterr().err
    with pytest.raises(ReportRefused, match=SUMMARY_FILE):
        render_report(empty)


def test_the_run_page_draws_its_verdicts_and_its_probes_from_the_counts_it_states(
    rendered: Rendered,
) -> None:
    """Two figures on the run page, each naming its file and stating its numbers as text.

    The rule the design spec sets for every figure, asserted on a real one: a reader who
    does not see the drawing reads the same counts in the caption under it, and the counts
    themselves are in the table above it whatever happens to either.
    """
    page = rendered.page()
    markup = (rendered.out / PAGE_FILE).read_text(encoding="utf-8")
    summary = rendered.summary
    audited = cast("dict[str, Any]", summary["question_set"])["audited"]

    assert markup.count("<svg ") == 2
    assert f"the verdicts of run {summary['run_id']}, from {SUMMARY_FILE}" in markup
    assert f"how many golds each probe fired on, of {audited:,}, from {SUMMARY_FILE}" in markup
    for verdict, count in cast("dict[str, int]", summary["verdicts"]).items():
        if verdict != "NOT_EQUAL":
            assert f"{count:,} {verdict}" in page.text
    assert 'aria-describedby="figure-verdicts-text"' in markup
    assert 'id="figure-verdicts-text"' in markup
    assert "fill=" not in markup, "a figure carries classes and takes its colours from the page"


def test_a_question_page_draws_the_class_its_counterexample_states(
    rendered: Rendered,
) -> None:
    """A figure where the mechanism has one, and none where the table already says it.

    q207 is a ``truncation`` on this sandbox and q1029 an ``other``: the first is drawn as a
    bar and the prefix of it that the shorter result is, and the second is not drawn at all,
    because ``other`` is not one shape.
    """
    truncation = (rendered.out / "q207" / PAGE_FILE).read_text(encoding="utf-8")
    other = (rendered.out / "q1029" / PAGE_FILE).read_text(encoding="utf-8")

    assert "<svg " in truncation
    assert "one result and the shorter one that is its first rows" in truncation
    assert "rows of the other one in the same order" in truncation
    assert "<svg " not in other


def test_the_fonts_are_beside_the_pages_with_the_licence_that_lets_them_be(
    rendered: Rendered,
) -> None:
    """Every file the stylesheet asks for is written beside it, and so are its terms.

    The fonts are under a directory of their own, which the copy has to walk into: a
    stylesheet copied without them is a page that asks a reader's browser for a file that is
    not there, and there is no request to a network to fall back on.
    """
    stylesheet = (rendered.out / "static" / "report.css").read_text(encoding="utf-8")
    asked_for = re.findall(r'url\("(fonts/[^"]+)"\)', stylesheet)

    assert len(asked_for) == 3, "three faces: the sans at two weights and the mono at one"
    for name in asked_for:
        assert (rendered.out / "static" / name).is_file(), name
        assert (STATIC / name).read_bytes() == (rendered.out / "static" / name).read_bytes()
    assert "font-display: swap" in stylesheet
    for beside in ("OFL.txt", "provenance.txt"):
        assert (rendered.out / "static" / "fonts" / beside).is_file(), beside


def test_the_method_page_s_two_accessors_state_what_the_private_tables_hold() -> None:
    """The two public accessors phase 1 adds for the pages of phase 3, which import nothing
    private: every probe's meaning by name, and the seven preconditions of a comparison."""
    meanings = probe_meanings()

    assert sorted(meanings) == sorted(SMELL_NAMES)
    assert all(meanings.values())
    assert len(session_preconditions()) == 7
    assert set(session_preconditions()) >= {"TimeZone", "work_mem", "datcollate"}


def _copy_audit(rendered: Rendered, tmp_path: Path) -> Path:
    """The demo's audit directory, copied so that files can be put beside its summary."""
    audit = tmp_path / DEMO_AUDIT
    shutil.copytree(rendered.audit, audit)
    return audit


def test_the_strip_names_the_database_when_a_questions_file_is_beside_the_summary(
    rendered: Rendered, tmp_path: Path
) -> None:
    """`db_id` reaches no file the audit writes, so a publisher may put it beside the summary.

    A directory the audit wrote holds no such file and renders as it did before: the question
    set alone. One that has it states the database in front of the set, and nothing else on
    the page changes.
    """
    audit = _copy_audit(rendered, tmp_path)
    (audit / "questions.json").write_text(
        json.dumps([{"question_id": "879", "db_id": "formula_1", "question": "..."}]),
        encoding="utf-8",
    )

    render_report(audit, tmp_path / "with")
    render_report(rendered.audit, tmp_path / "without")

    with_file = read(tmp_path / "with" / "q879" / PAGE_FILE)
    without = read(tmp_path / "without" / "q879" / PAGE_FILE)
    assert "formula_1" in with_file.text
    assert "formula_1" not in without.text
    # The one question the file names, and no other: a page states the database of its own.
    assert "formula_1" not in read(tmp_path / "with" / "q207" / PAGE_FILE).text


def test_a_question_a_maintainer_read_states_that_reading_beside_the_verdict_and_never_in_it(
    rendered: Rendered, tmp_path: Path
) -> None:
    """The row is on the question that has one, with the date of the file it was written in.

    Two lines that never merge: the verdict's own words are what a rule computed over two
    results, and the reading is a person's own. Both are on the page, and the reading is on
    the one question the classification holds a row for.
    """
    audit = _copy_audit(rendered, tmp_path)
    (audit / "classification.json").write_text(
        json.dumps(
            {
                "per_file": {
                    "a-model": {
                        "rows": [
                            {
                                "question_id": 879,
                                "class": "A",
                                "reason": "the gold orders speeds as text",
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (audit / "classification-source.json").write_text(
        json.dumps(
            {
                "source": "plans/reports/a-measurement/classification.json",
                "date": "2026-09-04",
                "shape": "per_file",
                "key": "a-model",
                "reason_field": "reason",
                "keys": "per_file[<prediction file>].rows[]",
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "report"

    render_report(audit, out)

    page = read(out / "q879" / PAGE_FILE)
    assert "read by hand, 2026-09-04" in page.text
    assert "the gold orders speeds as text" in page.text
    assert "../classification.json" in page.links
    assert (out / "classification.json").is_file(), "the file the row was read from is beside it"
    assert document(audit / "classification.json") == document(out / "classification.json")
    # The verdict's own reading is still there and is a paragraph of its own.
    assert "It does not state which of them is wrong." in page.text
    assert "read by hand" not in read(out / "q207" / PAGE_FILE).text


def test_a_run_published_as_a_release_asset_states_where_the_whole_of_it_is(
    rendered: Rendered, tmp_path: Path
) -> None:
    """What a site shows is a selection; this is the address of every question directory."""
    audit = _copy_audit(rendered, tmp_path)
    (audit / "published.json").write_text(
        json.dumps(
            {
                "name": "a-benchmark-a-run.tar.gz",
                "url": "https://example.invalid/a-benchmark-a-run.tar.gz",
                "bytes": 1234567,
                "sha256": "9" * 64,
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "report"

    render_report(audit, out)

    page = read(out / PAGE_FILE)
    assert "https://example.invalid/a-benchmark-a-run.tar.gz" in page.links
    assert "1,234,567 bytes" in page.text
    assert "9" * 64 in page.text
    assert "release asset" not in read(rendered.out / PAGE_FILE).text


def _published(directories: int | None = None, url: str | None = None) -> str:
    """One ``published.json`` as the selection writes it, with the count where there is one."""
    stated: dict[str, Any] = {
        "name": "a-benchmark-a-run.tar.gz",
        "url": url or "https://example.invalid/a-benchmark-a-run.tar.gz",
        "bytes": 1234567,
        "sha256": "9" * 64,
    }
    if directories is not None:
        stated["directories"] = directories
    return json.dumps(stated)


def test_a_published_run_says_how_many_of_its_question_directories_have_a_page_here(
    rendered: Rendered, tmp_path: Path
) -> None:
    """A page that states how many questions it shows and not how many there are says nothing.

    The run wrote a directory per question it has evidence for; a site shows the ones its
    budget fits. Both numbers are on the page: the one counted here as the pages were written,
    and the one the archive holds, which is the manifest's and reaches the page through
    ``published.json``. A file written before that number existed still renders, without it.
    """
    audit = _copy_audit(rendered, tmp_path)
    written = len(list(audit.glob("q*")))
    assert written > 1, "the demo writes a directory per question it has evidence for"

    (audit / "published.json").write_text(_published(directories=218), encoding="utf-8")
    render_report(audit, tmp_path / "counted")
    (audit / "published.json").write_text(_published(), encoding="utf-8")
    render_report(audit, tmp_path / "uncounted")

    counted = read(tmp_path / "counted" / PAGE_FILE).text
    assert f"This site holds {written} of the 218 question directories this run wrote" in counted
    assert "the archive holds every one" in counted
    uncounted = read(tmp_path / "uncounted" / PAGE_FILE).text
    assert "of the 218 question directories" not in uncounted
    assert "The pages here are a selection of this run's questions." in uncounted


def test_a_release_asset_the_page_could_not_fetch_is_refused_rather_than_linked(
    rendered: Rendered, tmp_path: Path
) -> None:
    """The address becomes an ``href`` a reader clicks, so what it is is checked, not escaped.

    Autoescaping puts the value safely inside the attribute and says nothing about what the
    scheme does when the link is followed: a ``javascript:`` value would run on that click.
    """
    audit = _copy_audit(rendered, tmp_path)
    (audit / "published.json").write_text(_published(url="javascript:alert(1)"), encoding="utf-8")

    with pytest.raises(ReportRefused, match="has to begin with https://"):
        render_report(audit, tmp_path / "report")


def _classify(audit: Path, stated: dict[str, Any], note: dict[str, Any]) -> None:
    """One hand classification and the note beside it, for the question the demo has at 879."""
    (audit / "classification.json").write_text(
        json.dumps({"per_file": {"a-model": {"rows": [stated]}}}), encoding="utf-8"
    )
    (audit / "classification-source.json").write_text(
        json.dumps(
            {
                "source": "plans/reports/a-measurement/classification.json",
                "date": "2026-09-04",
                "shape": "per_file",
                "key": "a-model",
                "reason_field": "reason",
                "keys": "per_file[<prediction file>].rows[]",
                **note,
            }
        ),
        encoding="utf-8",
    )


def test_the_class_a_maintainer_recorded_is_read_with_what_its_own_source_says_it_means(
    rendered: Rendered, tmp_path: Path
) -> None:
    """``A`` on its own is a letter, and a letter is not a reading.

    The note beside the classification carries the meaning of each class in the words of the
    document that defines it, and the row states the letter and then those words. A class the
    note does not define is rendered as the value the row holds, with nothing invented beside
    it, which is what an older note written before the meanings existed leaves.
    """
    audit = _copy_audit(rendered, tmp_path)
    meaning = "a wrong answer the benchmark credited: another table or projection"
    row: dict[str, Any] = {"question_id": 879, "class": "A", "reason": "orders speeds as text"}
    _classify(audit, row, {"classes": {"A": meaning}, "classes_source": "the report's legend"})
    render_report(audit, tmp_path / "defined")
    _classify(audit, row, {})
    render_report(audit, tmp_path / "undefined")

    defined = read(tmp_path / "defined" / "q879" / PAGE_FILE).text
    assert f"A {meaning}" in defined
    undefined = read(tmp_path / "undefined" / "q879" / PAGE_FILE).text
    assert meaning not in undefined
    assert "read by hand, 2026-09-04: A" in undefined
