#!/usr/bin/env python3
"""Build the whole site: the published runs, a landing page and a page about the method.

The renderer inside the package turns one audit directory into pages. This turns a tree of
audit directories into a site, and adds the two pages that are the site's own: the landing,
which is what a link to attestql.com opens, and the method, which is what the tool computes.
Both extend the package's base template and take its stylesheet, its script and its fonts, so
there is one design here and not two.

Nothing on either page is typed by hand that an artifact states. The one sentence is the
package description out of `pyproject.toml`; the opening command and its output are produced
by running `attestql demo` while the build runs; the rows under it are that run's own
`counterexample.json`, read through the same accessor the question page reads it through; the
install line is the line `README.md` holds, so the two cannot drift; the run table is each
run's `summary.json`; the links at the foot are the ones `site/index.html` carries, read out
of that file and never edited; and the method page's rules, preconditions, probes and readings
are the strings the package itself holds. What is left, and it is short, is the connective
prose in the two templates.

Until phase 4 publishes the real runs there is nothing under `tools/site/data/`, so the build
audits the packaged sandbox and shows that instead, under the benchmark `sandbox` and the run
`demo`, with a banner on every page of the site saying so. The banner is dropped by the
presence of a benchmark directory and not by an edit, so publishing the runs removes it.

Run it with `uv run python tools/site/build.py`; `--out` defaults to `build/site/`, which git
ignores, and an `--out` inside `site/` is refused, because that directory is the live page's
and belongs to another session.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import sys
import time
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from contextlib import chdir, redirect_stdout
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import cast

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, StrictUndefined

from attestql.audit.cli import SERIALIZATION
from attestql.audit.cli import main as audit_main
from attestql.audit.compare import (
    BIRD_EX_METHOD,
    BIRD_EX_SOURCE,
    MECHANISM_CLASSES,
    MECHANISM_READING,
    TEST_SUITE_EX_METHOD,
    TEST_SUITE_EX_SOURCE,
    VERDICT_READING,
)
from attestql.audit.postgres import session_preconditions
from attestql.audit.smells import SMELLS_READING, probe_meanings
from attestql.evidence.replay import compare_r_ord, compare_r_set
from attestql.report.figures import Figure, proportion_bar
from attestql.report.render import (
    BIRD_READING,
    PAGE_FILE,
    STATIC,
    STATIC_DIRECTORY,
    SUMMARY_FILE,
    TEMPLATES,
    TEST_SUITE_READING,
    Fact,
    QuestionPage,
    question_page,
    render_report,
)

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parent.parent
DATA = HERE / "data"
SITE_TEMPLATES = HERE / "templates"
DEFAULT_OUT = REPOSITORY / "build" / "site"
LIVE_PAGE = REPOSITORY / "site" / "index.html"
README = REPOSITORY / "README.md"
PYPROJECT = REPOSITORY / "pyproject.toml"

RUNS_DIRECTORY = "runs"
METHOD_DIRECTORY = "method"
AGGREGATE_FILE = "aggregate.json"
DATA_README = "README.md"
"""Where the runs go under the built site, and what the two extra files under `data/` are
called. `aggregate.json` is phase 4's, and its shape is stated in `data/README.md`."""

MAX_FILES = 8_000
MAX_BYTES = 40 * 1024 * 1024
MAX_PAGE_BYTES = 2 * 1024 * 1024
"""The build's own budget, under the Free plan's limits (20,000 files a site, 25 MiB a file,
owner 2026-09-07), so that a run can be added to a passing build without a re-plan. A build
over any of the three fails and prints what pushed it over; the answer to that is a narrower
selection and never a larger budget."""

HEADLINE: tuple[tuple[str, str], ...] = (
    ("credited_but_not_equal", "credited by BIRD's own check and NOT_EQUAL here"),
    (
        "classified_by_hand",
        "of those, classified by hand as a gold that does not answer its question",
    ),
    ("bird_dev_classified_by_hand", "BIRD dev golds classified by hand the same way"),
)
"""The three numbers the landing shows, their keys in `aggregate.json` and the words beside
each. The words are this file's and the numbers are the aggregate's: a page of this project
states no number an artifact does not, and `data/README.md` states the shape of the file the
next phase writes. The order is the order they are read in and is not the file's."""

SANDBOX_BENCHMARK = "sandbox"
SANDBOX_RUN = "demo"
DEMO_QUESTION = "q879"
"""The stand-in, and the question the landing shows the rows of. q879 is a gold BIRD ships
that sorts a text column holding numbers, so its disagreement is one sentence long."""

BANNER = (
    "The runs on this site are the sandbox the package carries, audited while this site was "
    "built. The published runs of the benchmarks arrive with the next phase; nothing here is "
    "a measurement of a benchmark yet."
)
"""What every page says while `tools/site/data/` holds no benchmark. Dropped by the data and
not by an edit: a directory under `data/` is what makes it empty."""

PRINCIPLE = "NOT_EQUAL never means the gold is wrong."
"""The sentence the design spec names as the site's principle and allows verbatim. It is a
value here and not a literal in a template, which is where the copy rule forbids the words it
holds; the rule exists to stop a page adding a judgement of its own, and this sentence is the
refusal of one."""

NO_NUMBERS = (
    "The three headline numbers are rendered from the aggregate the next phase writes. It is "
    "not in this build, so no number is shown: a number typed here by hand would be the one "
    "thing this site is against."
)
"""What stands where the three numbers go while `aggregate.json` is not there."""


class BuildRefused(Exception):
    """This site cannot be built, and the message says what was looked for or what is over."""


@dataclass(frozen=True)
class Run:
    """One audit directory to render, and where it goes under the built site."""

    benchmark: str
    name: str
    audit: Path
    summary: Mapping[str, object]
    command: str = ""
    output: str = ""
    """The command that made this run and what it printed, filled in for the sandbox alone:
    the published runs were made by hand, months of machine time apart, and the landing states
    a command a reader can run rather than one it watched run."""

    @property
    def slug(self) -> str:
        return f"{RUNS_DIRECTORY}/{self.benchmark}/{self.name}"

    @property
    def facts(self) -> tuple[Fact, ...]:
        """What the run table on the landing states about this run, out of its summary."""
        question_set = _mapping(self.summary, "question_set")
        return (
            Fact("date", _string(self.summary, "data_as_of")),
            Fact("engine", _string(_mapping(self.summary, "session_settings"), "engine")),
            Fact("question set", _string(question_set, "origin") or _string(question_set, "path")),
            Fact("question set digest", _string(question_set, "digest")),
        )


@dataclass(frozen=True)
class Runs:
    """The index over every benchmark: what the site published, one row per run."""

    benchmarks: tuple[Benchmark, ...]

    title = "attestql: the published runs"


@dataclass(frozen=True)
class Benchmark:
    """One benchmark and the runs under it, as the two indexes state them."""

    name: str
    runs: tuple[Run, ...]

    @property
    def title(self) -> str:
        return f"attestql: the runs of {self.name}"

    @property
    def slug(self) -> str:
        return f"{RUNS_DIRECTORY}/{self.name}"


@dataclass(frozen=True)
class Number:
    """One headline number, and the file it was read out of."""

    name: str
    value: int
    source: str


@dataclass(frozen=True)
class Landing:
    """Everything the landing page states, each field read out of an artifact."""

    sentence: str
    command: str
    output: str
    run_id: str
    executed_at: str
    question: QuestionPage
    question_href: str
    principle: str
    numbers: tuple[Number, ...]
    no_numbers: str
    bar: Figure | None
    install: str
    benchmarks: tuple[Benchmark, ...]
    links: tuple[tuple[str, str], ...]

    title = "AttestQL"


@dataclass(frozen=True)
class Rule:
    """One replay rule, named as the tool names it and read out of the tool's own text."""

    name: str
    reading: str


@dataclass(frozen=True)
class Method:
    """Everything the method page states, each field read out of the package."""

    figure: str
    figure_text: str
    rules: tuple[Rule, ...]
    serialization: tuple[Fact, ...]
    preconditions: tuple[str, ...]
    probes: tuple[Fact, ...]
    probes_reading: str
    readings: tuple[Rule, ...]
    verdict_reading: str
    mechanism_reading: str
    classes: tuple[str, ...]
    principle: str
    docs: str

    title = "AttestQL: the method"


@dataclass(frozen=True)
class Built:
    """What one build wrote, and what it measured of itself."""

    out: Path
    files: int
    bytes_written: int
    seconds: float

    @property
    def line(self) -> str:
        return (
            f"{self.files:,} files, {self.bytes_written:,} bytes, "
            f"{self.seconds:.1f} s in {self.out.as_posix()}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """The command: build the site, print what it measured, and say why if it refused."""
    parser = argparse.ArgumentParser(description=_docstring(sys.modules[__name__]))
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"where the site is written; by default {DEFAULT_OUT.relative_to(REPOSITORY)}",
    )
    parsed = parser.parse_args(argv)
    try:
        print(build(cast("Path", parsed.out)).line)
    except BuildRefused as refused:
        print(f"attestql-site: {refused}", file=sys.stderr)
        return 2
    return 0


def build(out: Path) -> Built:
    """Render every run, then the two pages of the site's own, then measure the result."""
    started = time.perf_counter()
    _refuse_an_out_inside_the_live_page(out)
    scratch = out.parent / f"{out.name}-sandbox"
    _clear(out)
    _clear(scratch)
    try:
        banner = "" if benchmark_directories() else BANNER
        runs = _runs(scratch)
        benchmarks = _benchmarks(runs)
        for run in runs:
            render_report(run.audit, out / run.slug, banner=banner)
        environment = _environment()
        for benchmark in benchmarks:
            _write(
                out / benchmark.slug / PAGE_FILE,
                environment,
                "benchmark.html",
                page=benchmark,
                root="../../",
                banner=banner,
            )
        _write(
            out / RUNS_DIRECTORY / PAGE_FILE,
            environment,
            "runs.html",
            page=Runs(benchmarks=tuple(benchmarks)),
            root="../",
            banner=banner,
        )
        _write(
            out / PAGE_FILE,
            environment,
            "landing.html",
            page=_landing(runs, benchmarks),
            root="",
            banner=banner,
        )
        _write(
            out / METHOD_DIRECTORY / PAGE_FILE,
            environment,
            "method.html",
            page=_method(),
            root="../",
            banner=banner,
        )
        for static in sorted(path for path in STATIC.rglob("*") if path.is_file()):
            _copy(static, out / STATIC_DIRECTORY / static.relative_to(STATIC))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return _measure(out, time.perf_counter() - started)


def _refuse_an_out_inside_the_live_page(out: Path) -> None:
    """`site/` is the live page's directory and another session's; a build never writes there.

    Resolved first, so a relative path, a symlink and a `..` naming that directory are the
    same answer. The check is the reason this script has an `--out` at all: the default is
    already outside it, and what is refused is a hand that points it back in.
    """
    inside = out.resolve()
    live = LIVE_PAGE.parent.resolve()
    if inside == live or live in inside.parents:
        raise BuildRefused(
            f"--out {out} is {live} or a directory inside it, which holds the page "
            f"attestql.com serves and belongs to another session. Nothing was written."
        )


def _clear(directory: Path) -> None:
    """The directory this build writes into, empty before it writes anything."""
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True, exist_ok=True)


def benchmark_directories() -> tuple[Path, ...]:
    """Every benchmark under `data/`, which is what says the published runs have arrived."""
    if not DATA.is_dir():
        return ()
    return tuple(sorted(path for path in DATA.iterdir() if path.is_dir()))


def _runs(scratch: Path) -> tuple[Run, ...]:
    """Every run to render: the sandbox this build audits, and then the published ones.

    The sandbox is always made and always rendered, because the landing opens with the demo
    command, what it printed, and the rows of one of its questions, and those rows have to be
    a page on this site rather than a quotation of one. A published run is a directory holding
    a `summary.json` two levels under `data/`; while there are none the sandbox is the whole
    site, which is what the banner says.
    """
    audit, command, output = _demo(scratch)
    sandbox = Run(
        benchmark=SANDBOX_BENCHMARK,
        name=SANDBOX_RUN,
        audit=audit,
        summary=_document(audit / SUMMARY_FILE),
        command=command,
        output=output,
    )
    published = [
        Run(
            benchmark=benchmark.name,
            name=run.name,
            audit=run,
            summary=_document(run / SUMMARY_FILE),
        )
        for benchmark in benchmark_directories()
        for run in sorted(path for path in benchmark.iterdir() if path.is_dir())
        if (run / SUMMARY_FILE).is_file()
    ]
    return (sandbox, *published)


def _demo(scratch: Path) -> tuple[Path, str, str]:
    """`attestql demo` run here: the audit it wrote, the command, and what it printed.

    The output is the command's own, unedited and not reformatted: the landing shows what a
    reader will see on their own machine, and the one thing that will differ is the run id and
    the time, which the page says are this build's. It is run from inside the scratch
    directory and told `--out demo`, so the paths it prints are the relative ones a reader
    following the command would see rather than this machine's own.
    """
    printed = io.StringIO()
    with chdir(scratch), redirect_stdout(printed):
        status = audit_main([SANDBOX_RUN, "--out", SANDBOX_RUN])
    if status != 1:
        raise BuildRefused(
            f"attestql {SANDBOX_RUN} exited {status}; it exits 1, because three of the golds "
            f"it carries disagree with their corrections, which is what it is there to show"
        )
    return (
        scratch / SANDBOX_RUN / "audit",
        f"attestql {SANDBOX_RUN} --out {SANDBOX_RUN}",
        printed.getvalue(),
    )


def _benchmarks(runs: Sequence[Run]) -> tuple[Benchmark, ...]:
    """The runs grouped under the benchmark each belongs to, in the order they were found."""
    names = list(dict.fromkeys(run.benchmark for run in runs))
    return tuple(
        Benchmark(name=name, runs=tuple(run for run in runs if run.benchmark == name))
        for name in names
    )


def _landing(runs: Sequence[Run], benchmarks: Sequence[Benchmark]) -> Landing:
    """The landing page, in the order the phase fixes, every field read out of an artifact."""
    demo = next((run for run in runs if run.command), runs[0])
    numbers, source = _numbers()
    return Landing(
        sentence=_description(),
        command=demo.command,
        output=demo.output,
        run_id=_string(demo.summary, "run_id"),
        executed_at=_string(demo.summary, "data_as_of"),
        question=question_page(demo.audit / DEMO_QUESTION),
        question_href=f"{demo.slug}/{DEMO_QUESTION}/{PAGE_FILE}",
        principle=PRINCIPLE,
        numbers=numbers,
        no_numbers="" if numbers else NO_NUMBERS,
        bar=_bar(numbers, source),
        install=_install_line(),
        benchmarks=tuple(benchmarks),
        links=live_links(),
    )


def _description() -> str:
    """The one sentence: the package description, out of `pyproject.toml`."""
    stated = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = cast("Mapping[str, object]", stated["project"])
    return _string(project, "description")


def docs_url() -> str:
    """Where the flags are written, on the repository `pyproject.toml` names."""
    stated = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    urls = cast("Mapping[str, object]", cast("Mapping[str, object]", stated["project"])["urls"])
    return f"{_string(urls, 'Repository')}/blob/main/docs/audit-command.md"


def _install_line() -> str:
    """The install line `README.md` holds, so the page and the README cannot drift.

    The line and not a paraphrase of it: what a reader copies off this page is what a reader
    copies off the README, and if that line changes there this page changes with it.
    """
    for line in README.read_text(encoding="utf-8").splitlines():
        if "pip install attestql" in line:
            return line.strip()
    raise BuildRefused(
        f"{README} holds no line with `pip install attestql`, which is the install line this "
        f"page is built from rather than typing one of its own"
    )


def live_links() -> tuple[tuple[str, str], ...]:
    """The links the live page carries today, read out of it and never edited.

    `site/index.html` belongs to another session. This reads its navigation so the built site
    offers the same destinations, and a link added there arrives here on the next build.
    """
    found = _Links()
    found.feed(LIVE_PAGE.read_text(encoding="utf-8"))
    found.close()
    if not found.links:
        raise BuildRefused(f"{LIVE_PAGE} holds no navigation links to carry over")
    return tuple(found.links)


class _Links(HTMLParser):
    """The `nav` of the live page: each link's target and the words on it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.inside = False
        self.href = ""
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "nav":
            self.inside = True
        if tag == "a" and self.inside:
            self.href = str(dict(attrs).get("href") or "")
            self.text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.inside and self.href:
            self.links.append((self.href, "".join(self.text).strip()))
            self.href = ""
        if tag == "nav":
            self.inside = False

    def handle_data(self, data: str) -> None:
        if self.href:
            self.text.append(data)


def _numbers() -> tuple[tuple[Number, ...], str]:
    """The three headline numbers, out of the aggregate, or none while it is not there.

    Each carries the file it was read from, which the page states in a title attribute, and
    the shape of the file is `data/README.md`'s. Nothing is computed here: a number this build
    worked out would be a number with no artifact behind it.
    """
    aggregate = DATA / AGGREGATE_FILE
    if not aggregate.is_file():
        return (), ""
    stated = _document(aggregate)
    missing = [key for key, _ in HEADLINE if key not in stated]
    if missing:
        raise BuildRefused(
            f"{aggregate} holds no {', '.join(missing)}; the landing renders the three numbers "
            f"`data/README.md` names and shows none of them where one is not in the file"
        )
    numbers = tuple(
        Number(
            name=words,
            value=_integer(_mapping(stated, key), "value"),
            source=_string(_mapping(stated, key), "source"),
        )
        for key, words in HEADLINE
    )
    return numbers, AGGREGATE_FILE


def _bar(numbers: Sequence[Number], source: str) -> Figure | None:
    """The three numbers as one bar, drawn only where the aggregate put numbers there."""
    if not numbers:
        return None
    return proportion_bar(
        "headline",
        [(number.name, number.value, index == 0) for index, number in enumerate(numbers)],
        title=f"the three headline numbers, from {source}",
        whole="the published runs",
    )


def _method() -> Method:
    """The method page, out of the strings the package holds and out of nothing else.

    Every field here is read from the module that owns the thing it describes: the two rules
    from the two comparisons' own docstrings, the descriptor from the one the audit renders
    every result under, the preconditions and the probes from the two accessors the package
    exposes, and the two benchmark readings from the tables the audit computes them with. A
    page that restated any of them would be a page that could disagree with the tool.
    """
    figure, alternative = _figure()
    return Method(
        figure=figure,
        figure_text=alternative,
        rules=(
            Rule(name="R-ORD", reading=_docstring(compare_r_ord)),
            Rule(name="R-SET", reading=_docstring(compare_r_set)),
        ),
        serialization=(
            Fact("version", SERIALIZATION.version),
            Fact("numeric scale", str(SERIALIZATION.numeric_scale)),
            Fact("timestamp format", SERIALIZATION.timestamp_format),
            Fact("timezone", SERIALIZATION.timezone),
            Fact("null rendering", SERIALIZATION.null_rendering),
            Fact("encoding", SERIALIZATION.encoding),
        ),
        preconditions=session_preconditions(),
        probes=tuple(Fact(name, meaning) for name, meaning in sorted(probe_meanings().items())),
        probes_reading=SMELLS_READING,
        readings=(
            Rule(name=BIRD_READING, reading=_per_engine(BIRD_EX_METHOD, BIRD_EX_SOURCE)),
            Rule(
                name=TEST_SUITE_READING,
                reading=_per_engine(TEST_SUITE_EX_METHOD, TEST_SUITE_EX_SOURCE),
            ),
        ),
        verdict_reading=VERDICT_READING,
        mechanism_reading=MECHANISM_READING,
        classes=MECHANISM_CLASSES,
        principle=PRINCIPLE,
        docs=docs_url(),
    )


def _figure() -> tuple[str, str]:
    """`method.svg` and the words inside it: the drawing, and the same thing said in text."""
    svg = (STATIC / "method.svg").read_text(encoding="utf-8")
    opened = svg.index("<desc")
    start = svg.index(">", opened) + 1
    return svg, " ".join(svg[start : svg.index("</desc>")].split())


def _docstring(of: object) -> str:
    """One function's own docstring as one paragraph, which is where its rule is written.

    The doubled backticks are the source's own markup for a name and are dropped: what is
    wanted here is the sentence, and nothing else about it is changed.
    """
    return " ".join((of.__doc__ or "").replace("``", "").split())


def _per_engine(method: Mapping[str, str], source: str) -> str:
    """One reading's rule on each engine it is read on, and where the rule was read from."""
    return (
        "; ".join(f"on {engine}, {rule}" for engine, rule in sorted(method.items()))
        + f". Read from {source}"
    )


def _environment() -> Environment:
    """The site's templates first, the package's behind them, autoescaping on for both.

    The package's directory is on the loader so that `landing.html` and `method.html` extend
    the same base page and call the same macros the report's own pages do: one design, and
    every markup rule for a table of rows written once.
    """
    return Environment(
        loader=ChoiceLoader([FileSystemLoader(SITE_TEMPLATES), FileSystemLoader(TEMPLATES)]),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _write(
    path: Path, environment: Environment, template: str, *, page: object, root: str, banner: str
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        environment.get_template(template).render(page=page, root=root, banner=banner),
        encoding="utf-8",
    )
    return path


def _copy(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def _measure(out: Path, seconds: float) -> Built:
    """What the build wrote, against the three budgets, with the offenders named.

    Measured after the fact rather than predicted: the size of a site is the size of the
    records in it, and those are whatever the runs wrote. A build over a budget names what
    pushed it over, because the answer is a narrower selection of questions and the person
    making it needs to know which ones are large.
    """
    files = sorted(path for path in out.rglob("*") if path.is_file())
    total = sum(path.stat().st_size for path in files)
    heavy = [
        path for path in files if path.suffix == ".html" and path.stat().st_size > MAX_PAGE_BYTES
    ]
    over: list[str] = []
    if len(files) > MAX_FILES:
        over.append(f"{len(files):,} files, over {MAX_FILES:,}")
    if total > MAX_BYTES:
        over.append(f"{total:,} bytes, over {MAX_BYTES:,}")
    if heavy:
        over.append(
            f"{len(heavy)} pages over {MAX_PAGE_BYTES:,} bytes: "
            + ", ".join(
                f"{path.relative_to(out).as_posix()} at {path.stat().st_size:,}"
                for path in _largest(heavy)
            )
        )
    if over:
        raise BuildRefused("the site is over its budget: " + "; ".join(over))
    return Built(out=out, files=len(files), bytes_written=total, seconds=seconds)


def _largest(paths: Iterable[Path]) -> list[Path]:
    """The offenders worst first, and at most ten of them, which is a readable line."""
    return sorted(paths, key=lambda path: path.stat().st_size, reverse=True)[:10]


def _document(path: Path) -> Mapping[str, object]:
    """One JSON file as a mapping, refused by name when it is not one."""
    try:
        stated = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as unreadable:
        raise BuildRefused(f"{path} could not be read as JSON: {unreadable}") from unreadable
    if not isinstance(stated, dict):
        raise BuildRefused(f"{path} holds {type(stated).__name__} where an object was expected")
    return cast("Mapping[str, object]", stated)


def _mapping(document: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise BuildRefused(f"{key} is {type(value).__name__} where an object was expected")
    return cast("Mapping[str, object]", value)


def _string(document: Mapping[str, object], key: str) -> str:
    value = document.get(key)
    return "" if value is None else str(value)


def _integer(document: Mapping[str, object], key: str) -> int:
    value = document.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise BuildRefused(f"{key} is {type(value).__name__} where a whole number was expected")
    return value


if __name__ == "__main__":
    sys.exit(main())
