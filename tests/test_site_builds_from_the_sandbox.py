"""`tools/site/build.py` over the packaged sandbox: what the built site holds, and its budget.

The build has no data to render until the runs are published, so it audits the sandbox the
package carries and shows that, with a banner on every page saying so. That is exactly the
state these tests run in, which makes them a test of the stand-in as well as of the build: the
banner is there without data and gone with it, and the pages under `runs/` are rendered from an
audit the build made while it ran rather than from a fixture written for the test.

What is asserted is the rule the phase sets for the landing, which is that nothing on it is
typed by hand that an artifact states: the sentence is `pyproject.toml`'s description, the
install line is the one `README.md` holds, the links at the foot are the ones
`site/index.html` carries, and where the aggregate is missing there is no number at all. The
method page is asserted against the package's own accessors for the same reason, and the three
budgets are asserted by building over them.
"""

from __future__ import annotations

import io
import json
import tomllib
from contextlib import redirect_stdout
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast

import build as site
import pytest

from attestql.audit.postgres import session_preconditions
from attestql.audit.smells import probe_meanings
from attestql.report.render import PAGE_FILE

REPOSITORY = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.sandbox_sqlite


class _Read(HTMLParser):
    """One page as a reader meets it: the text with the markup gone, and every href."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[str] = []
        self.titles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        stated = dict(attrs)
        if tag == "a" and stated.get("href"):
            self.links.append(str(stated["href"]))
        if stated.get("title"):
            self.titles.append(str(stated["title"]))

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def read(path: Path) -> _Read:
    parser = _Read()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def build(out: Path) -> site.Built:
    """The build with its printed line kept rather than written over the test's own output."""
    printed = io.StringIO()
    with redirect_stdout(printed):
        built = site.build(out)
    return built


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One build, for the readings that only look at what it wrote."""
    out = tmp_path_factory.mktemp("site") / "site"
    assert build(out).files > 0
    return out


def test_the_build_renders_the_sandbox_as_a_benchmark_with_every_page_under_it(
    built: Path,
) -> None:
    """A run, its questions and its filters, under the benchmark the stand-in is called."""
    run = built / site.RUNS_DIRECTORY / site.SANDBOX_BENCHMARK / site.SANDBOX_RUN

    assert (built / PAGE_FILE).is_file()
    assert (built / site.METHOD_DIRECTORY / PAGE_FILE).is_file()
    assert (built / site.RUNS_DIRECTORY / PAGE_FILE).is_file()
    assert (built / site.RUNS_DIRECTORY / site.SANDBOX_BENCHMARK / PAGE_FILE).is_file()
    assert (run / PAGE_FILE).is_file()
    assert (run / site.DEMO_QUESTION / PAGE_FILE).is_file()
    assert (run / "not-equal" / PAGE_FILE).is_file()
    assert (built / "static" / "report.css").is_file()
    assert (built / "static" / "method.svg").is_file()


def test_the_landing_states_nothing_it_did_not_read_out_of_an_artifact(built: Path) -> None:
    """The sentence, the install line and the links are the ones the three files hold."""
    page = read(built / PAGE_FILE)
    stated = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
    description = cast("dict[str, Any]", stated["project"])["description"]
    install = next(
        line.strip()
        for line in (REPOSITORY / "README.md").read_text(encoding="utf-8").splitlines()
        if "pip install attestql" in line
    )
    text = " ".join("".join(page.text).split())

    assert description in text
    assert " ".join(install.split()) in text, "the README's own line, its runs of space collapsed"
    assert site.PRINCIPLE in text
    for href, words in site.live_links():
        assert href in page.links, href
        assert words in text, words
    assert "attestql demo --out demo" in text
    assert "demo/audit/q879/" in text, "the command's own output, with the paths it printed"


def test_the_landing_shows_the_rows_of_the_question_it_names(built: Path) -> None:
    """The differing rows of q879, out of that run's own counterexample and not retyped."""
    page = read(built / PAGE_FILE)
    text = " ".join("".join(page.text).split())
    counterexample = json.loads(
        (
            built
            / site.RUNS_DIRECTORY
            / site.SANDBOX_BENCHMARK
            / site.SANDBOX_RUN
            / site.DEMO_QUESTION
            / "counterexample.json"
        ).read_text(encoding="utf-8")
    )
    rows = cast("dict[str, Any]", counterexample["differing_rows"])

    for side in ("in_gold_not_in_second", "in_second_not_in_gold"):
        for row in cast("list[list[Any]]", rows[side]):
            for cell in row:
                assert str(cell) in text, cell
    assert f"{site.RUNS_DIRECTORY}/{site.SANDBOX_BENCHMARK}" in " ".join(page.links)


def test_the_landing_shows_no_number_while_the_aggregate_is_not_there(built: Path) -> None:
    """The three headline numbers are the aggregate's, so without it there is no number.

    The one thing a page of this project may not do is state a number nobody can open the
    file behind, so the absence is stated in words and the figure that draws the three is not
    drawn either.
    """
    markup = (built / PAGE_FILE).read_text(encoding="utf-8")
    page = read(built / PAGE_FILE)

    assert not (site.DATA / site.AGGREGATE_FILE).exists(), "phase 4 writes it; this is before"
    assert site.NO_NUMBERS in " ".join("".join(page.text).split())
    assert "figure--headline" not in markup
    assert not page.titles, "a number carries its source in a title, and there is no number"


def test_the_landing_renders_the_three_numbers_and_the_bar_when_the_aggregate_is_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the file, each number is rendered with the file it was read from beside it."""
    data = tmp_path / "data"
    data.mkdir()
    (data / site.AGGREGATE_FILE).write_text(
        json.dumps(
            {
                "credited_but_not_equal": {"value": 164, "source": "minidev-pg/aggregate.json"},
                "classified_by_hand": {"value": 69, "source": "minidev-pg/classification.json"},
                "bird_dev_classified_by_hand": {
                    "value": 23,
                    "source": "bird-dev-sqlite/classification.json",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(site, "DATA", data)
    out = tmp_path / "site"

    build(out)

    page = read(out / PAGE_FILE)
    markup = (out / PAGE_FILE).read_text(encoding="utf-8")
    text = " ".join("".join(page.text).split())
    assert "164" in text
    assert "minidev-pg/aggregate.json" in page.titles
    assert "figure--headline" in markup, "the bar is drawn only where the aggregate is"
    assert site.NO_NUMBERS not in text


def test_the_method_page_states_every_probe_and_every_precondition(built: Path) -> None:
    """The two accessors the package exposes for this page, read back off the page."""
    text = " ".join("".join(read(built / site.METHOD_DIRECTORY / PAGE_FILE).text).split())

    for name, meaning in probe_meanings().items():
        assert name in text, name
        assert meaning in text, name
    for setting in session_preconditions():
        assert setting in text, setting
    assert "R-ORD" in text
    assert "R-SET" in text
    assert site.SERIALIZATION.version in text
    assert site.PRINCIPLE in text
    assert site.docs_url() in read(built / site.METHOD_DIRECTORY / PAGE_FILE).links


def test_the_banner_is_on_every_page_without_data_and_on_none_of_them_with_it(
    built: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A benchmark directory is what removes the banner, so publishing runs removes it.

    Not an edit to a template: phase 4 adds data and the sentence goes, which is the only way
    a line saying "this is a stand-in" cannot outlive the stand-in.
    """
    for page in built.rglob(PAGE_FILE):
        assert site.BANNER in page.read_text(encoding="utf-8"), page

    published = built / site.RUNS_DIRECTORY / site.SANDBOX_BENCHMARK / site.SANDBOX_RUN
    data = tmp_path / "data"
    (data / "a-benchmark" / "a-run").mkdir(parents=True)
    (data / "a-benchmark" / "a-run" / "summary.json").write_text(
        (published / "summary.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(site, "DATA", data)
    out = tmp_path / "site"

    build(out)

    assert site.benchmark_directories() != ()
    written = sorted(out.rglob(PAGE_FILE))
    assert written, "the build wrote pages"
    for page in written:
        assert site.BANNER not in page.read_text(encoding="utf-8"), page
    assert (out / site.RUNS_DIRECTORY / "a-benchmark" / "a-run" / PAGE_FILE).is_file()


def test_the_build_refuses_an_out_inside_the_live_page_s_directory(tmp_path: Path) -> None:
    """`site/` holds what attestql.com serves and belongs to another session."""
    with pytest.raises(site.BuildRefused, match="belongs to another session"):
        site.build(REPOSITORY / "site" / "built")
    with pytest.raises(site.BuildRefused, match="belongs to another session"):
        site.build(REPOSITORY / "site")
    assert not (REPOSITORY / "site" / "built").exists()


def test_the_build_is_under_its_three_budgets_and_says_what_it_measured(
    tmp_path: Path,
) -> None:
    """The build measures itself, and a build over any of the three fails naming the offender."""
    out = tmp_path / "site"
    measured = build(out)

    assert measured.files <= site.MAX_FILES
    assert measured.bytes_written <= site.MAX_BYTES
    assert f"{measured.files:,} files" in measured.line
    assert str(out.as_posix()) in measured.line
    biggest = max(path.stat().st_size for path in out.rglob("*.html"))
    assert biggest <= site.MAX_PAGE_BYTES


def test_a_budget_that_the_site_is_over_fails_the_build_and_names_the_offender(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checker never seen to fail is not known to work, so each of the three is failed."""
    monkeypatch.setattr(site, "MAX_FILES", 1)
    with pytest.raises(site.BuildRefused, match="files, over 1"):
        build(tmp_path / "files")

    monkeypatch.setattr(site, "MAX_FILES", 8_000)
    monkeypatch.setattr(site, "MAX_BYTES", 1_000)
    with pytest.raises(site.BuildRefused, match="bytes, over 1,000"):
        build(tmp_path / "bytes")

    monkeypatch.setattr(site, "MAX_BYTES", 40 * 1024 * 1024)
    monkeypatch.setattr(site, "MAX_PAGE_BYTES", 100)
    with pytest.raises(site.BuildRefused, match=r"pages over 100 bytes: .*index\.html at "):
        build(tmp_path / "pages")
