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
import shutil
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

assert Path(site.__file__ or "") == REPOSITORY / "tools" / "site" / "build.py", (
    "`build` is also the name of the git-ignored output directory, which resolves as a "
    "namespace package when the repository root comes first on the path: this asserts the "
    "module under test is the script and not that directory"
)

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
    """One build of the stand-in, for the readings that only look at what it wrote.

    With `data/` pointed at a directory that is not there, which is the state this module is
    about: what the build does when the published runs are not beside it. Since phase 4 that
    directory holds a hundred and twenty audit directories and forty megabytes, and a fixture
    that rebuilt them for every reading would be measuring the data rather than the build. The
    published runs have two readings of their own below: the budget, which is measured over
    them, and the two that put a run under `data/` themselves.
    """
    root = tmp_path_factory.mktemp("site")
    with pytest.MonkeyPatch.context() as without_data:
        without_data.setattr(site, "DATA", root / "not-published")
        out = root / "site"
        assert build(out).files > 0
    return out


@pytest.fixture
def without_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`data/` pointed at a directory that is not there, for a reading about the build alone."""
    monkeypatch.setattr(site, "DATA", tmp_path / "not-published")


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


def test_the_landing_shows_no_number_while_the_aggregate_is_not_there(
    built: Path, without_data: None
) -> None:
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
    # And the other half of the sentence: with no benchmark beside it, on every page.
    monkeypatch.setattr(site, "DATA", tmp_path / "not-published")
    empty = tmp_path / "empty-site"
    build(empty)
    for page in sorted(empty.rglob(PAGE_FILE)):
        assert site.BANNER in page.read_text(encoding="utf-8"), page


def test_a_benchmark_directory_holding_no_run_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One published run removes the banner, and an empty directory is not one.

    The failure this refuses is a site saying its runs have arrived while it holds none, which
    is what a banner keyed to the directory rather than to a run would do on the first `mkdir`
    of the next phase.
    """
    data = tmp_path / "data"
    (data / "a-benchmark").mkdir(parents=True)
    monkeypatch.setattr(site, "DATA", data)
    out = tmp_path / "site"

    build(out)

    assert site.benchmark_directories() != ()
    assert site.BANNER in (out / PAGE_FILE).read_text(encoding="utf-8")
    assert not (out / site.RUNS_DIRECTORY / "a-benchmark").exists()


def test_the_build_refuses_a_directory_it_did_not_write_and_takes_over_one_it_did(
    tmp_path: Path, without_data: None
) -> None:
    """`--out` is a path a person types, so a build empties only a directory of its own.

    The rule `attestql report` follows, for the reason it follows it: emptying whatever the
    flag was pointed at would cost somebody the files this build never wrote.
    """
    mine = tmp_path / "mine"
    mine.mkdir()
    (mine / "notes.md").write_text("mine", encoding="utf-8")

    with pytest.raises(site.BuildRefused, match="is not empty and holds no"):
        build(mine)

    assert [path.name for path in mine.iterdir()] == ["notes.md"]
    assert (mine / "notes.md").read_text(encoding="utf-8") == "mine"

    out = tmp_path / "site"
    build(out)
    assert (out / site.SITE_MARKER).is_file()
    # A directory an earlier build wrote holds the marker, so the next one takes it over.
    assert build(out).files > 0


def test_a_published_run_may_not_take_the_address_the_sandbox_goes_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, built: Path
) -> None:
    """Two runs at one address would mean the second silently overwrote the first."""
    data = tmp_path / "data" / site.SANDBOX_BENCHMARK / site.SANDBOX_RUN
    data.mkdir(parents=True)
    (data / "summary.json").write_text(
        (
            built / site.RUNS_DIRECTORY / site.SANDBOX_BENCHMARK / site.SANDBOX_RUN / "summary.json"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setattr(site, "DATA", tmp_path / "data")

    with pytest.raises(site.BuildRefused, match="which is where the sandbox"):
        build(tmp_path / "site")


def test_a_run_the_renderer_refuses_is_this_build_refusing_and_names_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, built: Path
) -> None:
    """A malformed file in one published run is a line and an exit status, not a traceback."""
    run = tmp_path / "data" / "a-benchmark" / "a-run"
    run.mkdir(parents=True)
    (run / "summary.json").write_text("not the JSON its name says", encoding="utf-8")
    monkeypatch.setattr(site, "DATA", tmp_path / "data")

    with pytest.raises(site.BuildRefused, match="could not be read as JSON"):
        build(tmp_path / "site")


def test_the_bar_is_one_whole_cut_into_two_parts_and_never_three_added_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bar states a proportion, so its parts are disjoint and add up to what it draws.

    The second number is a subset of the first and the third counts another benchmark's
    questions, so a bar over all three would double-count one and mix in the other. What is
    drawn is the first cut into the part classified by hand and the rest.
    """
    data = tmp_path / "data"
    data.mkdir()
    (data / site.AGGREGATE_FILE).write_text(
        json.dumps(
            {
                "credited_but_not_equal": {"value": 164, "source": "minidev-pg/aggregate.json"},
                "classified_by_hand": {"value": 69, "source": "minidev-pg/classification.json"},
                "bird_dev_classified_by_hand": {"value": 23, "source": "bird-dev/classify.json"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(site, "DATA", data)
    out = tmp_path / "site"

    build(out)

    page = read(out / PAGE_FILE)
    text = " ".join("".join(page.text).split())
    assert "69 " in text and "95 " in text, "the part and the rest, which add up to 164"
    assert "23" not in text.split("the rest")[-1][:80], "the other benchmark is not a segment"

    (data / site.AGGREGATE_FILE).write_text(
        json.dumps(
            {
                "credited_but_not_equal": {"value": 10, "source": "a.json"},
                "classified_by_hand": {"value": 11, "source": "b.json"},
                "bird_dev_classified_by_hand": {"value": 1, "source": "c.json"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(site.BuildRefused, match="a part larger than its whole"):
        build(tmp_path / "over")


def test_the_method_page_says_whose_preconditions_those_seven_are(built: Path) -> None:
    """They are PostgreSQL's, and the landing's own demo is a SQLite run.

    A reader told their run required agreement on seven settings that SQLite never checks
    would have been told something the tool does not do. Both sentences are the two backends'
    own.
    """
    text = " ".join("".join(read(built / site.METHOD_DIRECTORY / PAGE_FILE).text).split())

    assert "settings two postgresql records must agree on" in text.lower()
    assert "a SQLite record states no session setting that decides comparability" in text


def test_no_page_of_the_built_site_names_a_user_a_home_or_this_checkout(built: Path) -> None:
    """The pages are published, and the SQLite backend records the file it opened.

    That identity is the "server" fact on the run page and both "backend" facts on every
    question page, so wherever the demo is audited ends up on a public page. Audited under
    `build/` it published the builder's own home directory and repository layout and changed
    with every `--out`; the scratch directory is fixed and neutral for that reason.
    """
    for page in built.rglob("*.html"):
        markup = page.read_text(encoding="utf-8")
        for named in (str(REPOSITORY), str(Path.home()), "/Users/"):
            assert named not in markup, f"{page.relative_to(built)} names {named}"
    identity = (
        built / site.RUNS_DIRECTORY / site.SANDBOX_BENCHMARK / site.SANDBOX_RUN / PAGE_FILE
    ).read_text(encoding="utf-8")
    assert str(site.SANDBOX_SCRATCH.resolve()) in identity, "the neutral path is what it states"


def test_the_method_page_states_a_rule_and_not_the_notes_under_it(built: Path) -> None:
    """A rule is its docstring's opening paragraph; what follows is written for a maintainer.

    `compare_r_set`'s second paragraph records an owner's decision of a particular date about
    a rounding step, which is a note to whoever changes that code and not something a reader
    meeting this project on its method page has any use for.
    """
    text = " ".join("".join(read(built / site.METHOD_DIRECTORY / PAGE_FILE).text).split())

    assert "Owner decision" not in text
    assert "typed semantic equality of the row multiset, order disregarded" in text
    assert "byte-identical canonical rendering under the recorded ordering" in text


def test_a_name_under_data_that_cannot_be_a_url_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A benchmark and a run are the two segments of every URL a run has.

    `data/` is a maintainer's directory, so an unusable name is refused and named rather than
    left out of the site quietly, which is where this differs from the renderer's own rule
    over names it reads out of a document.
    """
    data = tmp_path / "data"
    (data / "a benchmark").mkdir(parents=True)
    monkeypatch.setattr(site, "DATA", data)

    with pytest.raises(site.BuildRefused, match="is not a name this site can publish"):
        build(tmp_path / "site")

    (data / "a benchmark").rmdir()
    (data / "fine" / "a run").mkdir(parents=True)
    with pytest.raises(site.BuildRefused, match="is not a name this site can publish"):
        build(tmp_path / "site")


def test_a_symlink_under_data_is_refused_rather_than_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Everything published is read out of `data/`, so nothing here points out of it."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    (data / "benchmark").symlink_to(elsewhere, target_is_directory=True)
    monkeypatch.setattr(site, "DATA", data)

    with pytest.raises(site.BuildRefused, match="is a symlink"):
        build(tmp_path / "site")


def test_a_count_below_zero_is_refused_rather_than_drawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two negatives satisfy the bar's part-no-larger-than-its-whole check and are drawn."""
    data = tmp_path / "data"
    data.mkdir()
    (data / site.AGGREGATE_FILE).write_text(
        json.dumps(
            {
                "credited_but_not_equal": {"value": -1, "source": "a.json"},
                "classified_by_hand": {"value": -5, "source": "b.json"},
                "bird_dev_classified_by_hand": {"value": 3, "source": "c.json"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(site, "DATA", data)

    with pytest.raises(site.BuildRefused, match="every number this page states is a count"):
        build(tmp_path / "site")


def test_the_install_line_is_a_command_and_the_links_are_the_first_nav_s(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two readings of two files the site does not own, each of which had a shape it took.

    The install line was any line holding `pip install attestql`, which a sentence of prose
    above the block satisfies; a page built from it would have offered a reader a paragraph
    to paste into a shell. The navigation merged every `nav` on the page and carried a link
    with no words on it, which on the built page is a link a reader cannot read.
    """
    readme = tmp_path / "README.md"
    readme.write_text(
        "Install it with `pip install attestql` if you prefer pip.\n\n"
        "```sh\nuv tool install attestql        # or: pip install attestql\n```\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(site, "README", readme)

    assert site.install_line() == "uv tool install attestql        # or: pip install attestql"

    page = tmp_path / "index.html"
    page.write_text(
        '<!DOCTYPE html><html lang="en"><body>'
        '<nav><a href="/one">One</a><a href="/two">Two</a></nav>'
        "<p>the page</p>"
        '<nav><a href="/three">Three</a></nav>'
        "</body></html>",
        encoding="utf-8",
    )
    monkeypatch.setattr(site, "LIVE_PAGE", page)

    assert site.live_links() == (("/one", "One"), ("/two", "Two")), "the first nav, whole"

    page.write_text(
        '<!DOCTYPE html><html lang="en"><body>'
        '<nav><a href="/one">One</a><a href="/icon"><img src="i.png" alt=""></a></nav>'
        "</body></html>",
        encoding="utf-8",
    )
    with pytest.raises(site.BuildRefused, match="with no words on it"):
        site.live_links()


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
    """The build measures itself, over what `data/` actually holds.

    The one reading here that builds the published runs rather than the stand-in, because the
    budget is about them: the answer to a site over one of the three is a narrower selection of
    questions, and this is where that is found out.
    """
    out = tmp_path / "site"
    measured = build(out)

    assert measured.files <= site.MAX_FILES
    assert measured.bytes_written <= site.MAX_BYTES
    assert f"{measured.files:,} files" in measured.line
    assert str(out.as_posix()) in measured.line
    biggest = max(path.stat().st_size for path in out.rglob("*.html"))
    assert biggest <= site.MAX_PAGE_BYTES


def test_a_budget_that_the_site_is_over_fails_the_build_and_names_the_offender(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, without_data: None
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


def _publish(data: Path, slug: str, source: Path) -> Path:
    """One published run at `slug` under `data`, copied from a rendered run's own directory.

    The summary and the question directories, because what a published run is, is a directory
    `attestql report` can render: a summary alone would test the index and not the pages under
    it, which is where the address of a run of a group is measured.
    """
    run = data / slug
    run.mkdir(parents=True)
    shutil.copyfile(source / "summary.json", run / "summary.json")
    for question in sorted(source.glob("q*")):
        if question.is_dir():
            shutil.copytree(question, run / question.name)
    return run


def test_a_benchmark_whose_runs_are_under_a_group_publishes_them_a_level_deeper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, built: Path
) -> None:
    """The shape a SQLite benchmark has: a prediction file is a group of one run per database.

    `--dsn` is one file there, so one prediction file is eleven invocations of the audit and
    the group is that file. The group is a level in the address, a page of its own and a line
    on the benchmark index; what it is never is a merged `summary.json`, because a summary no
    audit wrote would be this site's own invention.
    """
    source = built / site.RUNS_DIRECTORY / site.SANDBOX_BENCHMARK / site.SANDBOX_RUN
    data = tmp_path / "data"
    _publish(data, "grouped/a-model/first-db", source)
    _publish(data, "grouped/a-model/second-db", source)
    _publish(data, "flat/a-run", source)
    monkeypatch.setattr(site, "DATA", data)
    out = tmp_path / "site"

    build(out)

    runs = out / site.RUNS_DIRECTORY
    assert (runs / "grouped" / "a-model" / "first-db" / PAGE_FILE).is_file()
    assert (runs / "grouped" / "a-model" / "first-db" / site.DEMO_QUESTION / PAGE_FILE).is_file()
    assert (runs / "grouped" / "a-model" / PAGE_FILE).is_file(), "the group has a page"
    assert (runs / "flat" / "a-run" / PAGE_FILE).is_file()

    index = read(runs / "grouped" / PAGE_FILE)
    assert "runs/grouped/a-model/index.html" in [link.split("../")[-1] for link in index.links]
    assert "2 runs" in "".join(index.text)
    group = read(runs / "grouped" / "a-model" / PAGE_FILE)
    assert "12" in "".join(group.text), "six questions in each of the two runs, added up"


def test_the_static_directory_is_served_revalidated_on_every_load(built: Path) -> None:
    """A page is fresh on every load; its stylesheet has to be as fresh, or the two disagree.

    Pages keeps `static/` for four hours by default and a page for none, so a deploy that
    changed a rule left readers with the new page and the old stylesheet until the hour was
    up. The site tells Pages to revalidate the static directory on every load, as it does a
    page.
    """
    stated = (built / site.HEADERS_FILE).read_text(encoding="utf-8")

    assert stated.startswith("/static/*\n"), stated
    assert "max-age=0, must-revalidate" in stated


def test_every_page_takes_its_stylesheet_from_the_one_static_directory_of_the_site(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, built: Path
) -> None:
    """One `static/`, however deep a page is, and no copy of the fonts beside each run.

    The three font files are 60 kB. Copied per run, a site of a hundred and twenty runs would
    spend a tenth of everything it is allowed to weigh on the same eight files, which is weight
    taken off the evidence the site exists to show. So every page's link is resolved here
    against the page's own directory and has to land on the site's own copy.
    """
    source = built / site.RUNS_DIRECTORY / site.SANDBOX_BENCHMARK / site.SANDBOX_RUN
    data = tmp_path / "data"
    _publish(data, "grouped/a-model/first-db", source)
    _publish(data, "flat/a-run", source)
    monkeypatch.setattr(site, "DATA", data)
    out = tmp_path / "site"

    build(out)

    stylesheets = 0
    for page in sorted(out.rglob(PAGE_FILE)):
        for href in read(page).links:
            assert not (page.parent / href).is_dir(), href
        found = [
            line
            for line in page.read_text(encoding="utf-8").splitlines()
            if 'rel="stylesheet"' in line
        ]
        assert len(found) == 1, page
        href = found[0].split('href="')[1].split('"')[0]
        assert (page.parent / href).resolve() == (out / "static" / "report.css"), page
        stylesheets += 1
    assert stylesheets > 4
    assert sorted(path.name for path in out.rglob("static") if path.is_dir()) == ["static"]


def test_a_number_the_site_could_not_publish_whole_says_so_under_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What was found and what has a page are two questions, and the page states both.

    The number is what the runs and the classification hold, which no budget of this site may
    change; how many of them have a page here is a fact about the budget, and it is one line
    under the number. Where the two are the same there is nothing to say, and an aggregate
    written before they were told apart states one number and gets the same silence.
    """
    data = tmp_path / "data"
    data.mkdir()
    (data / site.AGGREGATE_FILE).write_text(
        json.dumps(
            {
                "credited_but_not_equal": {
                    "value": 164,
                    "published": 161,
                    "source": "minidev-pg/<run>/summary.json",
                },
                "classified_by_hand": {
                    "value": 69,
                    "published": 69,
                    "source": "minidev-pg/classification.json",
                },
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

    text = " ".join("".join(read(out / PAGE_FILE).text).split())
    assert "164" in text and "69" in text and "23" in text, "the numbers are what was found"
    assert "161 of them have a page here; the other 3 are whole in the release assets." in text
    assert "69 of them have a page here" not in text, "as many published as found"
    assert "23 of them have a page here" not in text, "a file that states the one number"


def test_a_group_published_as_one_archive_states_that_archive_on_the_group_s_own_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, built: Path
) -> None:
    """A group is what one prediction file was audited as, and one archive is what holds it.

    A reader on the group page is a level above the runs, so the sentence there is the group's
    sum against the archive's own count, and the link is the one archive both runs are in.
    """
    source = built / site.RUNS_DIRECTORY / site.SANDBOX_BENCHMARK / site.SANDBOX_RUN
    data = tmp_path / "data"
    first = _publish(data, "grouped/a-model/first-db", source)
    _publish(data, "grouped/a-model/second-db", source)
    published = json.dumps(
        {
            "name": "grouped-a-model.tar.gz",
            "url": "https://example.invalid/grouped-a-model.tar.gz",
            "bytes": 1234567,
            "sha256": "9" * 64,
            "directories": 400,
        }
    )
    (first.parent / "published.json").write_text(published, encoding="utf-8")
    monkeypatch.setattr(site, "DATA", data)
    out = tmp_path / "site"

    build(out)

    group = read(out / site.RUNS_DIRECTORY / "grouped" / "a-model" / PAGE_FILE)
    text = " ".join("".join(group.text).split())
    written = 2 * len(list(source.glob("q*")))
    assert f"This site holds {written} of the 400 question directories these 2 runs wrote" in text
    assert "https://example.invalid/grouped-a-model.tar.gz" in group.links
    assert "9" * 64 in text
