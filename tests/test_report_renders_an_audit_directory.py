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
    COUNTEREXAMPLE_FILE,
    GOLD_RECORD_FILE,
    MARKER_FILE,
    PAGE_FILE,
    SECOND_RECORD_FILE,
    SMELLS_FILE,
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
        link for link in page.links if link.endswith(PAGE_FILE)
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
        [MARKER_FILE, PAGE_FILE, SUMMARY_FILE, "static"]
        + [directory.name for directory in rendered.audit.iterdir() if directory.is_dir()]
    )


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

    assert [path.name for path in first.pages] == [path.name for path in second.pages]
    for page, again in zip(first.pages, second.pages, strict=True):
        assert page.read_bytes() == again.read_bytes(), page.name


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


def test_the_method_page_s_two_accessors_state_what_the_private_tables_hold() -> None:
    """The two public accessors phase 1 adds for the pages of phase 3, which import nothing
    private: every probe's meaning by name, and the seven preconditions of a comparison."""
    meanings = probe_meanings()

    assert sorted(meanings) == sorted(SMELL_NAMES)
    assert all(meanings.values())
    assert len(session_preconditions()) == 7
    assert set(session_preconditions()) >= {"TimeZone", "work_mem", "datcollate"}
