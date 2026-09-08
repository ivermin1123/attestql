"""The view model and the rendering: an audit's JSON files as pages.

Everything a page states is read out of the files the audit wrote, through the ``format``
strings they declare and never through the audit's own types. That is what makes the
command work over a directory another machine produced: this module imports the evidence
package and Jinja2 and nothing that reaches a database, so a directory is enough.

The model below is plain dataclasses, one per region of a page. It caps nothing of its
own. Two of the three artifacts are bounded where they were written -- the counterexample
shows twenty-five rows a side and a fired probe ten -- and the evidence records hold every
row, so the model carries ``row_count``, ``rows_shown`` and ``truncated`` through and each
table says which file it was read from and how much of it is on the page.

Nothing here decides anything either. The verdict, the mechanism, the readings and the
probes' meanings are the strings the JSON holds, rendered as they were written; the two
things this module computes are which SQL tokens the two statements differ in, which is a
comparison of two texts, and each record's two hashes taken again from the document, which
is the one check a reader cannot make by eye.
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from attestql.evidence.load import LoadedRecord, UnreadableRecord, load_record
from attestql.evidence.render import Json
from attestql.report.figures import Figure, question_figure, run_figures

TEMPLATES = Path(__file__).parent / "templates"
STATIC = Path(__file__).parent / "static"
"""Where the templates and the stylesheet are, found beside this file.

``importlib`` is forbidden repository-wide outside package metadata
(``tests/test_boundary.py``), and a package directory that ships its templates is a
directory this file can point at."""

SUMMARY_FILE = "summary.json"
QUESTIONS_FILE = "questions.json"
CLASSIFICATION_FILE = "classification.json"
CLASSIFICATION_SOURCE_FILE = "classification-source.json"
PUBLISHED_FILE = "published.json"
"""Three files a directory `attestql audit` wrote does not hold, which a publisher may put
beside its summary and which a page states when they are there.

`questions.json` names the database each question is about, which reaches no file the audit
writes; the two classification files are a maintainer's own reading of some of the questions,
kept apart from every verdict on the page; `published.json` is where the whole run was
uploaded. A directory without them renders exactly as it does today."""

COUNTEREXAMPLE_FILE = "counterexample.json"
GOLD_RECORD_FILE = "evidence-gold.json"
SECOND_RECORD_FILE = "evidence-second.json"
SMELLS_FILE = "smells.json"
"""The names of the files an audit directory holds.

Stated here rather than imported from the audit: this command reads a directory, which is
a layout, and the layout is what it is whoever wrote it. Importing the writer's constants
would put the audit's whole import graph -- both drivers and both parsers -- behind a
renderer that has to run where no engine is."""

QUESTION_DIRECTORY = re.compile(r"^q(\d+)$")
"""What a question's directory is called, and where its id is in the name."""

PAGE_COMMAND = "attestql audit"
"""What wrote the directory this command reads, as a refusal names it."""

PAGE_FILE = "index.html"
STATIC_DIRECTORY = "static"
OUT_SUFFIX = "-report"
"""What the default ``--out`` appends to the audit directory's own name. A sibling and
never a child: a rerun of the audit clears its own directory, and a report written inside
one would be left there, stale, beside a fresh run. A ``--out`` that names the audit
directory or a directory under it is refused for that reason, rather than half written and
then abandoned where the audit's own cleanup will meet it."""

NOT_EQUAL = "NOT_EQUAL"
"""The verdict the first filter is about, spelled as the summary and the pages spell it."""

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

MARKER_FILE = ".attestql-report"
"""What says an output directory is a render's own and may be cleared by the next one."""

MARKER_TEXT = (
    "written by attestql report: every rerun into this directory removes index.html, "
    "summary.json, the q<id>/ directories, not-equal/, by-mechanism/, by-probe/ and static/\n"
)
"""The one line the marker holds, so a reader who opens it learns why it is there."""

ASSET_SCHEME = "https://"
"""What the address in ``published.json`` has to begin with. It reaches an ``href`` on the run
page, where a ``javascript:`` value would run on a reader's click; autoescaping puts the text
safely inside the attribute and says nothing at all about what the scheme does."""

BIRD_READING = "BIRD's own check"
TEST_SUITE_READING = "the test-suite check"
"""What the two readings beside a verdict are called on a question page.

Named here rather than typed into the template because a page elsewhere states the same two
by name -- the site's method page lists what is computed beside every verdict -- and two
spellings of one thing would be a reader's question about whether they are one thing."""

GOLD = "gold"
SECOND = "second"
GOLD_ONLY = "GOLD-ONLY"
"""The two sides of a comparison, and the verdict of a question that had only the one."""

GOLD_GLYPH = "◀"
SECOND_GLYPH = "▶"
"""The left- and right-pointing triangles the two tints are paired with, so which side a
row came from survives grayscale and colour blindness."""

SQL_TOKEN = re.compile(r"\s+|\w+|[^\w\s]")
"""How a statement is cut up before the two are compared: runs of space, words, and single
characters of anything else. The comparison is of two texts and states nothing about
either statement; it marks where they differ so a reader's eye lands there first."""


class ReportRefused(Exception):
    """This directory cannot be rendered, and the message says what was looked for.

    The one error this command has. A directory that is not an audit's, a file that is not
    the JSON its name says, and a document that does not hold what its format states are
    all the same answer to a reader: nothing was rendered, and here is why.
    """


@dataclass(frozen=True)
class Cell:
    """One value of one row: its canonical type tag and the text it was written as."""

    tag: str
    text: str
    is_null: bool
    show_tag: bool


@dataclass(frozen=True)
class Column:
    """One column of a result: the name it came back under and its declared type."""

    name: str
    declared_type: str


@dataclass(frozen=True)
class Row:
    """One row of a table, with the label and the count the table it is in states."""

    cells: tuple[Cell, ...]
    count: int | None
    label: str
    glyph: str


@dataclass(frozen=True)
class Rows:
    """One table of rows and what the file it was read from says about how many there are.

    ``source`` names that file and its count, because a page shows rows from three
    different places -- a record, which holds every row, a counterexample's preview, and a
    fired probe's evidence -- and a reader who is not told which is looking at an unlabelled
    number.
    """

    source: str
    columns: tuple[Column, ...]
    rows: tuple[Row, ...]
    row_count: int
    rows_shown: int
    truncated: bool
    counted: bool
    labelled: bool

    @property
    def partial(self) -> bool:
        return self.rows_shown < self.row_count

    @property
    def total(self) -> str:
        """The count as a page states it: the thousands separated, and the word after it."""
        return _count(self.row_count)


@dataclass(frozen=True)
class Hash:
    """One hash as the document states it and as it was taken again from the document."""

    name: str
    stated: str
    recomputed: str
    match: bool


@dataclass(frozen=True)
class Fact:
    """One named value of a block a reader reads as a list: what it is and what it says."""

    name: str
    value: str
    detail: str = ""


@dataclass(frozen=True)
class Source:
    """Where one file came from: its path, its digest, and what the run was told about it."""

    path: str
    digest: str
    origin: str
    date: str


@dataclass(frozen=True)
class Token:
    """One piece of a statement, marked when the two statements differ there."""

    text: str
    differs: bool


@dataclass(frozen=True)
class Side:
    """One statement of a question: what ran, in what order, and what came back."""

    side: str
    glyph: str
    tokens: tuple[Token, ...]
    ordering: tuple[Fact, ...]
    result: Rows
    result_hash: str
    record_file: str


@dataclass(frozen=True)
class Difference:
    """One side of the row difference: the rows only that side holds, and how many there are."""

    label: str
    glyph: str
    heading: str
    rows: Rows
    total: int
    rows_shown_per_side: int


@dataclass(frozen=True)
class Reading:
    """What another evaluator's own check says about the same two results."""

    name: str
    value: int
    equal: bool
    method: str
    source: str
    counts: tuple[Fact, ...]


@dataclass(frozen=True)
class Mechanism:
    """What makes two results unequal under this rule, as the counterexample states it."""

    classification: str
    reading: str
    facts: tuple[Fact, ...]


@dataclass(frozen=True)
class Projection:
    """The two column lists, when the two statements named their columns differently."""

    gold: tuple[str, ...]
    second: tuple[str, ...]
    reading: str


@dataclass(frozen=True)
class Probe:
    """One probe that ran on one gold: whether it applied, whether it fired, and on what."""

    name: str
    fired: bool
    applicable: bool
    means: str
    reason: str
    evidence: str
    rows: Rows | None

    @property
    def state(self) -> str:
        if self.fired:
            return "fired"
        return "quiet" if self.applicable else "not applicable"


@dataclass(frozen=True)
class Record:
    """One evidence record as a page states it, with its two hashes taken again."""

    file: str
    side: str
    executed_sql: str
    source: Source
    identity: tuple[Fact, ...]
    session: tuple[Fact, ...]
    recorded: tuple[Fact, ...]
    serialization: tuple[Fact, ...]
    fixture: tuple[Fact, ...]
    result: Rows
    hashes: tuple[Hash, ...]
    rerun_instruction: str


@dataclass(frozen=True)
class HandReading:
    """What a maintainer recorded about one question, read out of a classification file.

    Never merged with the verdict. The tool's verdict is what a rule computed over two results
    and states nothing about which statement answers the question; this is a person's reading
    of the same question, in their own words, with the date of the file it was written in. They
    are two lines on the page and the page keeps them apart.
    """

    classification: str
    meaning: str
    """What that class means, in the words of the document that defines it, or nothing where
    the file beside the classification defines no such class. A page showing ``A`` and nothing
    else states a letter a reader has no way to read."""
    reason: str
    date: str
    source: str
    file: str


@dataclass(frozen=True)
class Published:
    """Where the whole run was uploaded, as the file beside the summary states it."""

    name: str
    url: str
    size: str
    digest: str
    directories: int | None = None
    """How many question directories the archive holds for this run, where the file states it.
    What a site shows is a selection; a page saying how many it shows without saying how many
    there are states a number a reader cannot use."""


@dataclass(frozen=True)
class QuestionPage:
    """One question directory as one page, in the order the design spec fixes."""

    slug: str
    question_id: str
    question_set: str
    question_text: str
    evidence_text: str
    replay_rule: str
    verdict: str
    verdict_reading: str
    mismatched: tuple[str, ...]
    mechanism: Mechanism | None
    projection: Projection | None
    backend_identity: str
    run_id: str
    sides: tuple[Side, ...]
    differences: tuple[Difference, ...]
    readings: tuple[Reading, ...]
    probes: tuple[Probe, ...]
    probes_reading: str
    records: tuple[Record, ...]
    files: tuple[Fact, ...]
    """The JSON this page was rendered from: each file's own name, and what it is. The
    names are what the renderer copies beside the page, so a page that states a file a
    reader can open is a page whose file is there."""
    figure: Figure | None = None
    """The drawing of this question's mechanism, where its class has one. Filled in after
    the page is built, because a figure is read off the page's own rows."""
    db_id: str = ""
    """Which database this question is about, out of the `questions.json` a publisher put
    beside the summary. It reaches no file the audit writes, and a directory without that file
    renders without it: the question set is named on its own, as it was before."""
    by_hand: HandReading | None = None
    """A maintainer's own reading of this question, where one of the two classification files
    beside the summary holds a row for it, and nothing where it does not."""

    @property
    def title(self) -> str:
        return f"q{self.question_id} {self.verdict}"


@dataclass(frozen=True)
class Entry:
    """One question on the run page's index: what it answered and where its page is."""

    question_id: str
    href: str
    verdict: str
    replay_rule: str
    mechanism: str
    probes: tuple[str, ...]
    question_text: str
    note: str


@dataclass(frozen=True)
class FilterPage:
    """The run page's index with rows left out, under an address of its own.

    Nothing is decided here that the run page did not decide: the rows are its own ``Entry``
    objects, kept or dropped by a field one of them already holds. ``slug`` is where the page
    goes under the report, and the number of steps in it is how far a question's own path has
    to climb to be reached from here.
    """

    slug: str
    heading: str
    restriction: str
    run_id: str
    of: int
    """How many rows the whole index holds, so the page states what it is a part of."""
    entries: tuple[Entry, ...]

    @property
    def root(self) -> str:
        """What this page puts in front of a path the run page states relative to itself."""
        return "../" * (self.slug.count("/") + 1)

    @property
    def title(self) -> str:
        return f"attestql run {self.run_id}: {self.heading}"


@dataclass(frozen=True)
class RunPage:
    """One audit directory's ``summary.json`` as the page a reader opens first."""

    run_id: str
    format: str
    exit_status: int
    questions_audited: int
    counts: tuple[Fact, ...]
    verdict_counts: tuple[tuple[str, int], ...]
    mechanism_counts: tuple[tuple[str, int], ...]
    probe_counts: tuple[Fact, ...]
    probe_fired: tuple[tuple[str, int], ...]
    credited: tuple[Fact, ...]
    made_of: tuple[Fact, ...]
    session: tuple[Fact, ...]
    notes: tuple[Fact, ...]
    entries: tuple[Entry, ...]
    files: tuple[Fact, ...]
    filters: tuple[FilterPage, ...] = ()
    """The pre-rendered restrictions of the index above, each a page of its own. Filled in
    after the page is built, because a filter is the index with rows dropped and the index is
    what the page is built from."""
    published: Published | None = None
    """Where the whole of this run was uploaded, out of the `published.json` a publisher put
    beside the summary. What a site shows of a run is a selection of its questions; this is the
    address of all of them, so that nothing is lost by the selection."""
    directories: int = 0
    """How many question directories this render found, which is how many of the run's
    questions have a page here. Counted rather than read, so it is what was rendered."""
    verdict_figure: Figure | None = None
    probe_figure: Figure | None = None
    """The verdicts and the probes drawn, filled in after the page is built. ``counts``
    and ``probe_counts`` are the same numbers as the tables state them, and
    ``verdict_counts``, ``mechanism_counts`` and ``probe_fired`` are those numbers as
    numbers, which is what a bar is drawn from: the classes are counted from the question
    directories this run wrote, because ``summary.json`` counts a mechanism only for the
    credited rows. A count that is not a whole number is refused where it is read, the way
    every other number on this page is, rather than drawn as a zero nobody was told about."""

    @property
    def title(self) -> str:
        return f"attestql run {self.run_id}"


@dataclass(frozen=True)
class Report:
    """What one rendering wrote: the pages, and the JSON files copied beside them."""

    out: Path
    pages: tuple[Path, ...]
    files: tuple[Path, ...]
    filters: tuple[Path, ...] = ()
    """The pre-rendered filters of the index, counted apart from ``pages`` because they hold
    no question a page above does not: a reader told the run wrote eleven pages and finding
    nineteen files would be counting the same questions twice."""

    @property
    def line(self) -> str:
        """The one line the command prints: how many pages, and where they were written."""
        questions = len(self.pages) - 1
        filtered = (
            ""
            if not self.filters
            else f" and {len(self.filters)} filtered "
            f"{'index' if len(self.filters) == 1 else 'indexes'}"
        )
        return (
            f"{len(self.pages)} pages ({questions} "
            f"{'question' if questions == 1 else 'questions'}){filtered} in {self.out.as_posix()}"
        )


def default_out(audit_directory: Path) -> Path:
    """Where a report goes when the command line does not say: the audit's own sibling."""
    resolved = audit_directory.resolve()
    return resolved.parent / f"{resolved.name}{OUT_SUFFIX}"


def render_report(
    audit_directory: Path, out: Path | None = None, *, banner: str = "", static_root: str = ""
) -> Report:
    """Render one audit directory into ``out``, or into its sibling when there is none.

    ``banner`` is a line put above every page written here, for a caller building a whole
    site out of several runs and needing to say something about all of them at once. It is
    empty for ``attestql report``, whose pages state what their own directory holds.

    ``static_root`` is for the same caller: the path from this report's own root to the
    directory holding the shared ``static/``, as ``../../../``. Empty, which is what
    ``attestql report`` passes, means this report carries its own copy of the stylesheet,
    the script and the three font files, so that the directory it wrote opens on its own from
    a file manager. A site is one tree and does not need a hundred and twenty of them: the
    fonts alone are 60 kB, and copied per run they would take a tenth of everything the site
    is allowed to weigh away from the evidence it is there to show.

    Every refusal comes before anything is written, and each names what was looked for: a
    directory holding no ``summary.json`` was not written by ``attestql audit``, an ``--out``
    inside the audit directory would be cleared by the audit's own rerun, and an output
    directory holding files this command did not write is a reader's own. A render that
    wrote a page and then refused would leave exactly the half-written directory these
    checks exist to prevent.
    """
    summary_path = audit_directory / SUMMARY_FILE
    if not summary_path.is_file():
        raise ReportRefused(
            f"{audit_directory} holds no {SUMMARY_FILE}, so it is not a directory "
            f"{PAGE_COMMAND} wrote"
        )
    destination = default_out(audit_directory) if out is None else out
    _refuse_an_out_inside_the_audit(audit_directory, destination)
    directories = _question_directories(audit_directory)
    try:
        summary = _document(summary_path)
        beside = _beside(audit_directory)
        questions = [_question_page(directory, beside) for directory in directories]
        run = _run_page(summary, questions, directories, beside.published, len(directories))
        verdicts, probes = run_figures(run)
        run = replace(
            run,
            verdict_figure=verdicts,
            probe_figure=probes,
            filters=_filters(run.entries, run.run_id),
        )
    except UnreadableRecord as unreadable:
        raise ReportRefused(f"{audit_directory}: {unreadable}") from unreadable
    _clear_the_render_before_this_one(destination)
    try:
        return _write(
            destination, run, questions, audit_directory, directories, banner, static_root
        )
    except OSError as unwritable:
        # Everything below writes files, and a write that fails is this command failing to
        # do what it was asked rather than a directory it could not read: it is the same
        # refusal and the same exit status as the checks above, and never a traceback.
        raise ReportRefused(f"{destination} could not be written: {unwritable}") from unwritable


def _refuse_an_out_inside_the_audit(audit_directory: Path, out: Path) -> None:
    """A report is written beside an audit and never into one.

    The audit's own rerun clears its directory, so a report written there is either removed
    by the next run or left stale beside it, and a report written *onto* it would copy the
    evidence over itself. Both resolved first, so a relative path, a symlink and a ``..``
    naming the same directory are the same answer.
    """
    inside = out.resolve()
    audit = audit_directory.resolve()
    if inside == audit or audit in inside.parents:
        raise ReportRefused(
            f"--out {out} is the audit directory {audit_directory} or a directory inside it, "
            f"and a report goes beside an audit: a rerun of the audit clears its own "
            f"directory, so nothing written in there survives it. Nothing was written."
        )


def _clear_the_render_before_this_one(out: Path) -> None:
    """Everything a previous render wrote here, gone before this one writes anything.

    The same rule the audit's own output directory follows, for the same reason: a reader
    opens this directory and reads it as one report, so a question page the render before
    wrote and this one does not is a page about a question that is not in this run.

    Only a directory this command wrote to is cleared, which is what ``MARKER_FILE`` says.
    One that is empty is taken over and marked, one that holds the marker is cleared and
    keeps it, and one that holds anything else is refused untouched: ``--out`` named a
    directory of the reader's own, and deleting from it would cost them files this command
    never wrote.
    """
    try:
        out.mkdir(parents=True, exist_ok=True)
        entries = sorted(out.iterdir())
    except OSError as unusable:
        raise ReportRefused(
            f"the output directory {out} cannot be made or read: {unusable}"
        ) from unusable
    if entries and not (out / MARKER_FILE).is_file():
        raise ReportRefused(
            f"the output directory {out} is not empty and holds no {MARKER_FILE}, the file "
            f"a report leaves in a directory of its own: nothing in it was removed. A render "
            f"writes into a directory that is empty, that is not there yet, or that an "
            f"earlier report wrote to."
        )
    try:
        for name in (PAGE_FILE, SUMMARY_FILE):
            (out / name).unlink(missing_ok=True)
        for child in entries:
            if child.is_dir() and (
                QUESTION_DIRECTORY.match(child.name)
                or child.name == STATIC_DIRECTORY
                or child.name in FILTER_DIRECTORIES
            ):
                shutil.rmtree(child)
        (out / MARKER_FILE).write_text(MARKER_TEXT, encoding="utf-8")
    except OSError as unwritable:
        raise ReportRefused(
            f"the output directory {out} cannot be cleared of the render before it: {unwritable}"
        ) from unwritable


def _write(
    out: Path,
    run: RunPage,
    questions: Sequence[QuestionPage],
    audit_directory: Path,
    directories: Sequence[Path],
    banner: str,
    static_root: str = "",
) -> Report:
    """The pages, the stylesheet and the script, and the JSON copied beside each page."""
    environment = _environment()
    pages: list[Path] = [
        _page(
            out / PAGE_FILE,
            environment,
            "run.html",
            page=run,
            root="",
            banner=banner,
            static_root=static_root,
        )
    ]
    files: list[Path] = [_copy(audit_directory / SUMMARY_FILE, out / SUMMARY_FILE)]
    files.extend(
        _copy(audit_directory / name, out / name)
        for name in (CLASSIFICATION_FILE, CLASSIFICATION_SOURCE_FILE)
        if (audit_directory / name).is_file()
    )
    for question, directory in zip(questions, directories, strict=True):
        beside = out / question.slug
        pages.append(
            _page(
                beside / PAGE_FILE,
                environment,
                "question.html",
                page=question,
                root="../",
                banner=banner,
                static_root=static_root,
            )
        )
        files.extend(
            _copy(directory / stated.name, beside / stated.name) for stated in question.files
        )
    filters = [
        _page(
            out / view.slug / PAGE_FILE,
            environment,
            "filter.html",
            page=view,
            root=view.root,
            banner=banner,
            static_root=static_root,
        )
        for view in run.filters
    ]
    if not static_root:
        for static in sorted(path for path in STATIC.rglob("*") if path.is_file()):
            # The whole tree, because the fonts are under a directory of their own: a stylesheet
            # copied without them would ask a reader's browser for a file that is not there.
            files.append(_copy(static, out / STATIC_DIRECTORY / static.relative_to(STATIC)))
    return Report(out=out, pages=tuple(pages), files=tuple(files), filters=tuple(filters))


def _environment() -> Environment:
    """Autoescaping on for every template, and an undefined name a template cannot swallow.

    SQL, engine messages and column names are untrusted text: they come from a question
    file, a prediction file and a server, and every one of them reaches a page. Escaping is
    therefore not a per-template decision. ``StrictUndefined`` is the same argument about
    the model: a template that reads a field the model does not have raises here rather
    than rendering an empty region nobody notices.
    """
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _page(
    path: Path,
    environment: Environment,
    template: str,
    *,
    page: object,
    root: str,
    banner: str = "",
    static_root: str = "",
) -> Path:
    """One page, with where the other pages are and where the stylesheet is told apart.

    ``root`` reaches this report's own root from this page; ``static`` reaches the directory
    holding ``static/``, which is that same root for a report that carries its own copy and a
    directory above the whole report for a site that shares one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = environment.get_template(template).render(
        page=page, root=root, banner=banner, static=root + static_root
    )
    path.write_text(rendered, encoding="utf-8")
    return path


def _copy(source: Path, destination: Path) -> Path:
    """One file beside the page that renders it, byte for byte and by copy, not by move."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def question_page(directory: Path) -> QuestionPage:
    """One question directory as the model a template renders, for a page built elsewhere.

    The second of the accessors this package exposes for the site: the site's landing shows
    one question's differing rows through the same macro the question page shows them
    through, and the rows it shows have to be the ones this module reads out of that
    directory. A second reader of ``counterexample.json`` written over there would be a
    second answer to what those rows are.
    """
    return _question_page(directory, _beside(directory.parent))


@dataclass(frozen=True)
class Beside:
    """The three files a publisher may put beside a summary, read once for the whole run.

    Read once because two of them are about the run rather than about one question: a
    question file of five hundred entries and a classification of a hundred and seventy rows
    read again for every question directory would be the same two documents parsed a hundred
    times over.
    """

    databases: Mapping[str, str]
    by_hand: Mapping[str, HandReading]
    published: Published | None


def _beside(audit_directory: Path) -> Beside:
    """What is beside the summary, or nothing, which is what a directory the audit wrote holds."""
    return Beside(
        databases=_databases(audit_directory),
        by_hand=_by_hand(audit_directory),
        published=_published(audit_directory),
    )


def _databases(audit_directory: Path) -> Mapping[str, str]:
    """Which database each question is about, out of the file beside the summary."""
    path = audit_directory / QUESTIONS_FILE
    if not path.is_file():
        return {}
    return {
        _as_text(entry.get("question_id")): _as_text(entry.get("db_id"))
        for entry in _entry_list(path)
    }


def _by_hand(audit_directory: Path) -> Mapping[str, HandReading]:
    """A maintainer's rows for this run, out of the classification and the note beside it.

    Two files, because the classification is a copy of a document written for a measurement
    and is kept byte for byte, and the note beside it says where that copy came from, what
    date it carries and which of its rows are this run's. Both have to be there: a
    classification with no note would be rows a page could not say the date of, and the date
    is what makes a reading a reading rather than an opinion.
    """
    classification = audit_directory / CLASSIFICATION_FILE
    note = audit_directory / CLASSIFICATION_SOURCE_FILE
    if not classification.is_file() or not note.is_file():
        return {}
    where = _document(note)
    rows = _classified(_document(classification), where)
    field = _optional_text(where, "reason_field") or "reason"
    classes = _object_or_none(where, "classes") or {}
    return {
        _as_text(row.get("question_id")): HandReading(
            classification=_optional_text(row, "class"),
            # The note's own words for that class, or nothing: a class the note does not define
            # is rendered as the value the row holds and nothing is invented beside it.
            meaning=_as_text(classes.get(_optional_text(row, "class")) or ""),
            reason=_optional_text(row, field),
            date=_optional_text(where, "date"),
            source=_optional_text(where, "source"),
            file=CLASSIFICATION_FILE,
        )
        for row in rows
    }


def _classified(document: Json, where: Json) -> list[Json]:
    """The rows of one classification this run's page shows, by the join the note states.

    Two shapes and no more, each named by the note: ``per_file`` is a document keyed by the
    prediction file, whose ``key`` is this run's, and ``rows`` is one list whose rows name the
    database they were read on. A note naming any other shape is refused rather than guessed
    at: a join this module invented would put a person's reading on a question they never read.
    """
    shape = _optional_text(where, "shape")
    key = _optional_text(where, "key")
    if shape == "per_file":
        files = _object(document, "per_file")
        stated = files.get(key)
        return [] if not isinstance(stated, dict) else _objects(cast("Json", stated), "rows")
    if shape == "rows":
        return [row for row in _objects(document, "rows") if _optional_text(row, "db") == key]
    raise UnreadableRecord(
        f"{CLASSIFICATION_SOURCE_FILE} states the shape {shape!r}, and the two this reads are "
        f"'per_file', keyed by the prediction file, and 'rows', naming the database of each row"
    )


def published_asset(directory: Path) -> Published | None:
    """Where the whole of one run or one group was uploaded, out of the file beside it.

    The third accessor this package exposes for the site: a group has a `published.json` of its
    own, holding the group's own count, and the group page is built over there. A second reader
    of that file written in the site would be a second answer to what it says.
    """
    return _published(directory)


def _published(audit_directory: Path) -> Published | None:
    """Where the whole of this run was uploaded, out of the file beside the summary."""
    path = audit_directory / PUBLISHED_FILE
    if not path.is_file():
        return None
    document = _document(path)
    url = _optional_text(document, "url")
    if not url.startswith(ASSET_SCHEME):
        raise ReportRefused(
            f"{path} states {url!r}, and this address is a link on the run page: it has to "
            f"begin with {ASSET_SCHEME}, so that what a reader clicks fetches a file"
        )
    stated = document.get("directories")
    return Published(
        name=_optional_text(document, "name"),
        url=url,
        size=f"{_integer(document, 'bytes'):,} bytes",
        digest=_optional_text(document, "sha256"),
        directories=(stated if isinstance(stated, int) and not isinstance(stated, bool) else None),
    )


def _question_directories(audit_directory: Path) -> tuple[Path, ...]:
    """Every ``q<id>/`` of the run, in the order their ids read as numbers.

    Sorted by the number rather than by the name, so q207 comes before q1029 and two
    renderings of one directory list the questions in one order.
    """
    found = [
        (int(match.group(1)), path)
        for path in audit_directory.iterdir()
        if path.is_dir() and (match := QUESTION_DIRECTORY.match(path.name)) is not None
    ]
    return tuple(path for _, path in sorted(found))


def _question_page(directory: Path, beside: Beside | None = None) -> QuestionPage:
    """One question directory as its page: a comparison when it holds one, a gold otherwise.

    The figure is attached here rather than inside the two builders because it is read off
    the finished page: the rows a slope chart draws are the rows the tables below it show.
    The database and a maintainer's reading come from beside the summary rather than from
    this directory, and are attached the same way and for the same reason.
    """
    counterexample = directory / COUNTEREXAMPLE_FILE
    smells = _document(directory / SMELLS_FILE)
    page = (
        _comparison_page(directory, _document(counterexample), smells)
        if counterexample.is_file()
        else _gold_only_page(directory, smells)
    )
    found = beside or Beside(databases={}, by_hand={}, published=None)
    return replace(
        page,
        figure=question_figure(page),
        db_id=found.databases.get(page.question_id, ""),
        by_hand=found.by_hand.get(page.question_id),
    )


def _comparison_page(directory: Path, counterexample: Json, smells: Json) -> QuestionPage:
    """A question that had a prediction: both statements, what differs, and both records."""
    question = _object(counterexample, "question")
    verdict = _object(counterexample, "verdict")
    gold = _object(counterexample, GOLD)
    second = _object(counterexample, SECOND)
    records = [
        _record(directory / GOLD_RECORD_FILE, GOLD),
        _record(directory / SECOND_RECORD_FILE, SECOND),
    ]
    hashes = _object(counterexample, "result_hashes")
    projection = _object_or_none(counterexample, "projection_names_differ")
    marked_gold, marked_second = mark_differences(
        _text(gold, "executed_sql"), _text(second, "executed_sql")
    )
    return QuestionPage(
        slug=directory.name,
        question_id=_text(question, "question_id"),
        question_set=_text(question, "question_set"),
        question_text=_text(question, "question_text"),
        evidence_text=_text(question, "evidence_text"),
        replay_rule=_text(counterexample, "replay_rule"),
        verdict=_text(verdict, "result").upper(),
        verdict_reading=_text(verdict, "reading"),
        mismatched=tuple(_strings(verdict, "mismatched")),
        mechanism=_mechanism(_object_or_none(counterexample, "mechanism")),
        projection=(
            None
            if projection is None
            else Projection(
                gold=tuple(_strings(projection, GOLD)),
                second=tuple(_strings(projection, SECOND)),
                reading=_text(projection, "reading"),
            )
        ),
        backend_identity=_text(counterexample, "backend_identity"),
        run_id=_text(counterexample, "run_id"),
        sides=(
            _side(GOLD, GOLD_GLYPH, gold, marked_gold, _text(hashes, GOLD), COUNTEREXAMPLE_FILE),
            _side(
                SECOND,
                SECOND_GLYPH,
                second,
                marked_second,
                _text(hashes, SECOND),
                COUNTEREXAMPLE_FILE,
            ),
        ),
        differences=_differences(counterexample, records),
        readings=(
            _reading(BIRD_READING, _object(counterexample, "bird_ex")),
            _reading(TEST_SUITE_READING, _object(counterexample, "test_suite_ex")),
        ),
        probes=_probes(smells),
        probes_reading=_text(smells, "reading"),
        records=tuple(record for record, _ in records),
        files=(
            Fact(COUNTEREXAMPLE_FILE, _text(counterexample, "format")),
            Fact(GOLD_RECORD_FILE, "the gold's evidence record"),
            Fact(SECOND_RECORD_FILE, "the prediction's evidence record"),
            Fact(SMELLS_FILE, _text(smells, "format")),
        ),
    )


def _gold_only_page(directory: Path, smells: Json) -> QuestionPage:
    """A question with no prediction: the gold's own record is what the probes are about."""
    record, document = _record(directory / GOLD_RECORD_FILE, GOLD)
    question = _object(document, "question")
    return QuestionPage(
        slug=directory.name,
        question_id=_text(question, "question_id"),
        question_set=_text(question, "question_set"),
        question_text=_text(question, "question_text"),
        evidence_text=_text(question, "evidence_text"),
        replay_rule=_text(document, "replay_rule"),
        verdict=GOLD_ONLY,
        verdict_reading=(
            "This question was audited without a prediction beside it, so there is nothing "
            "to compare the gold with. The probes below read the gold alone."
        ),
        mismatched=(),
        mechanism=None,
        projection=None,
        backend_identity=_text(document, "backend_identity_at_checkout"),
        run_id=_text(document, "run_id"),
        sides=(_record_side(document, record),),
        differences=(),
        readings=(),
        probes=_probes(smells),
        probes_reading=_text(smells, "reading"),
        records=(record,),
        files=(
            Fact(GOLD_RECORD_FILE, "the gold's evidence record"),
            Fact(SMELLS_FILE, _text(smells, "format")),
        ),
    )


def _side(
    side: str,
    glyph: str,
    stated: Json,
    tokens: tuple[Token, ...],
    result_hash: str,
    source: str,
) -> Side:
    """One statement of a counterexample: its SQL, its own ordering and its bounded result."""
    return Side(
        side=side,
        glyph=glyph,
        tokens=tokens,
        ordering=tuple(
            Fact(
                _text(key, "expression"),
                "descending" if bool(key.get("descending")) else "ascending",
                f"nulls {_text(key, 'nulls')}",
            )
            for key in _objects(stated, "own_ordering")
        ),
        result=_result_rows(_object(stated, "result"), source),
        result_hash=result_hash,
        record_file=_text(stated, "record"),
    )


def _record_side(document: Json, record: Record) -> Side:
    """The gold of a question that had no prediction, read from its record."""
    return Side(
        side=GOLD,
        glyph=GOLD_GLYPH,
        tokens=(Token(text=_text(document, "executed_sql"), differs=False),),
        ordering=tuple(
            Fact(_text(key, "column"), "descending" if bool(key.get("descending")) else "ascending")
            for key in _objects(document, "canonical_ordering")
        ),
        result=record.result,
        result_hash=record.hashes[0].stated,
        record_file=GOLD_RECORD_FILE,
    )


def _differences(
    counterexample: Json, records: Sequence[tuple[Record, Json]]
) -> tuple[Difference, ...]:
    """The two one-sided row differences, each under the columns of the side it came from."""
    stated = _object(counterexample, "differing_rows")
    per_side = _integer(stated, "rows_shown_per_side")
    sides = (
        (GOLD, GOLD_GLYPH, "in_gold_not_in_second", "in gold, not in the prediction"),
        (SECOND, SECOND_GLYPH, "in_second_not_in_gold", "in the prediction, not in gold"),
    )
    differences: list[Difference] = []
    for (label, glyph, key, heading), (record, _) in zip(sides, records, strict=True):
        groups = _objects(stated, key)
        total = _integer(stated, f"{key}_total")
        differences.append(
            Difference(
                label=label,
                glyph=glyph,
                heading=heading,
                rows=_grouped_rows(groups, record.result.columns, label, glyph, total, per_side),
                total=total,
                rows_shown_per_side=per_side,
            )
        )
    return tuple(differences)


def _grouped_rows(
    groups: Sequence[Json],
    columns: tuple[Column, ...],
    label: str,
    glyph: str,
    total: int,
    per_side: int,
) -> Rows:
    """The rows of one side of a difference, each with the number of times it occurred."""
    rows = tuple(
        Row(
            cells=_cells(_list(group, "row")),
            count=_integer(group, "count"),
            label=label,
            glyph=glyph,
        )
        for group in groups
    )
    return _tagged(
        Rows(
            source=(
                f"from {COUNTEREXAMPLE_FILE}, {_count(total)}, up to {per_side} shown per side"
            ),
            columns=columns,
            rows=rows,
            row_count=total,
            rows_shown=len(rows),
            truncated=False,
            counted=any((row.count or 0) > 1 for row in rows),
            labelled=True,
        )
    )


def _result_rows(result: Json, source: str) -> Rows:
    """A result block as a table: its columns, its rows, and what it says it left out."""
    rows = tuple(
        Row(cells=_cells(_list_of(row, "a row")), count=None, label="", glyph="")
        for row in _list(result, "rows")
    )
    row_count = _integer(result, "row_count")
    return _tagged(
        Rows(
            source=f"from {source}, {_count(row_count)}",
            columns=tuple(
                Column(name=_text(column, "name"), declared_type=_text(column, "declared_type"))
                for column in _objects(result, "columns")
            ),
            rows=rows,
            row_count=row_count,
            rows_shown=_optional_integer(result, "rows_shown", len(rows)),
            truncated=bool(result.get("truncated")),
            counted=False,
            labelled=False,
        )
    )


def _probe_rows(rows: Sequence[Json]) -> Rows:
    """The rows a fired probe carries. The probe names no columns for them, so nor does this."""
    built = tuple(
        Row(cells=_cells(_list_of(row, "a probe row")), count=None, label="", glyph="")
        for row in rows
    )
    return _tagged(
        Rows(
            source=f"from {SMELLS_FILE}, {_count(len(built))}",
            columns=(),
            rows=built,
            row_count=len(built),
            rows_shown=len(built),
            truncated=False,
            counted=False,
            labelled=False,
        )
    )


def _cells(row: Sequence[Json]) -> tuple[Cell, ...]:
    """One rendered row as its cells, each with the tag the value was written under."""
    return tuple(
        Cell(
            tag=_text(cell, "type"),
            text=_cell_text(cell),
            is_null=_text(cell, "type") == "null",
            show_tag=False,
        )
        for cell in (_object_of(value, "a cell") for value in row)
    )


def _tagged(rows: Rows) -> Rows:
    """The same table with a type tag on the cells of every column whose rows disagree.

    A column of a SQLite result holds whatever its cells came back as, so a page that
    showed only the declared type would state one type for a column holding two. The tag
    is put where the rows themselves disagree, which is where a reader has something to
    see, and nowhere else: it is read off the rows and states nothing about the engine.
    """
    if not rows.rows:
        return rows
    width = max(len(row.cells) for row in rows.rows)
    mixed = [
        len({row.cells[index].tag for row in rows.rows if index < len(row.cells)}) > 1
        for index in range(width)
    ]
    return Rows(
        source=rows.source,
        columns=rows.columns,
        rows=tuple(
            Row(
                cells=tuple(
                    Cell(
                        tag=cell.tag,
                        text=cell.text,
                        is_null=cell.is_null,
                        show_tag=mixed[index],
                    )
                    for index, cell in enumerate(row.cells)
                ),
                count=row.count,
                label=row.label,
                glyph=row.glyph,
            )
            for row in rows.rows
        ),
        row_count=rows.row_count,
        rows_shown=rows.rows_shown,
        truncated=rows.truncated,
        counted=rows.counted,
        labelled=rows.labelled,
    )


def _record(path: Path, side: str) -> tuple[Record, Json]:
    """One evidence record as a page states it, with its result and its two hashes retaken."""
    document = _document(path)
    loaded: LoadedRecord = load_record(document)
    settings = _object(document, "session_settings_in_force")
    result = _object(document, "result")
    fixture = _object(document, "fixture")
    source = _object(document, "statement_source")
    validation = _object(document, "validation_outcome")
    return (
        Record(
            file=path.name,
            side=side,
            executed_sql=_text(document, "executed_sql"),
            source=Source(
                path=_text(source, "path"),
                digest=_text(source, "digest"),
                origin=_optional_text(source, "origin"),
                date=_optional_text(source, "date"),
            ),
            identity=(
                Fact("run", _text(document, "run_id")),
                Fact("executed at", _text(document, "executed_at")),
                Fact("data as of", _text(document, "data_as_of")),
                Fact("backend at checkout", _text(document, "backend_identity_at_checkout")),
                Fact("backend that answered", _optional_text(result, "backend_identity")),
                Fact("database role", _text(document, "effective_database_role")),
                Fact("replay rule", _text(document, "replay_rule")),
                Fact("question set version", _text(document, "question_set_version")),
                Fact("validator", _text(document, "validator_version")),
                Fact("checks run", ", ".join(_strings(validation, "checks_run"))),
                Fact("statement timeout", f"{_optional_text(result, 'statement_timeout_ms')} ms"),
                Fact("rows", _count(_integer(document, "row_count"))),
            ),
            session=tuple(
                Fact(name, _optional_text(settings, name, absent="not stated by this engine"))
                for name in settings
                if name != "recorded"
            ),
            recorded=_facts(_object(settings, "recorded")),
            serialization=_facts(_object(document, "serialization")),
            fixture=(
                Fact("schema digest", _optional_text(fixture, "schema_digest")),
                Fact("source file sha256", _optional_text(fixture, "source_file_sha256")),
                *(
                    Fact(f"rows in {name}", _as_text(count))
                    for name, count in _object(fixture, "row_counts").items()
                ),
            ),
            result=_result_rows(result, path.name),
            hashes=(
                Hash(
                    name="result_hash",
                    stated=loaded.result_hash.stated,
                    recomputed=loaded.result_hash.recomputed,
                    match=loaded.result_hash.match,
                ),
                Hash(
                    name="record_hash",
                    stated=loaded.record_hash.stated,
                    recomputed=loaded.record_hash.recomputed,
                    match=loaded.record_hash.match,
                ),
            ),
            rerun_instruction=_text(document, "rerun_instruction"),
        ),
        document,
    )


def _mechanism(stated: Json | None) -> Mechanism | None:
    if stated is None:
        return None
    return Mechanism(
        classification=_text(stated, "class"),
        reading=_text(stated, "reading"),
        facts=tuple(
            Fact(name, _as_text(value))
            for name, value in stated.items()
            if name not in {"class", "reading"}
        ),
    )


def _reading(name: str, stated: Json) -> Reading:
    """One evaluator's own answer about the same two results, as its document states it."""
    return Reading(
        name=name,
        value=_integer(stated, "value"),
        equal=bool(stated.get("equal")),
        method=_text(stated, "method"),
        source=_text(stated, "source"),
        counts=tuple(
            Fact(key, _as_text(value))
            for key, value in stated.items()
            if key not in {"value", "equal", "method", "source"}
        ),
    )


def _probes(smells: Json) -> tuple[Probe, ...]:
    """Every probe that ran on this gold, fired, quiet and not applicable alike."""
    probes: list[Probe] = []
    for stated in _objects(smells, "smells"):
        evidence = _object(stated, "evidence")
        rows = _list(stated, "counterexample_rows")
        probes.append(
            Probe(
                name=_text(stated, "name"),
                fired=bool(stated.get("fired")),
                applicable=bool(stated.get("applicable")),
                means=_optional_text(evidence, "means"),
                reason=_optional_text(evidence, "reason"),
                evidence=json.dumps(
                    {key: value for key, value in evidence.items() if key != "means"},
                    indent=2,
                    ensure_ascii=False,
                ),
                rows=_probe_rows(rows) if rows else None,
            )
        )
    return tuple(probes)


def _run_page(
    summary: Json,
    questions: Sequence[QuestionPage],
    directories: Sequence[Path],
    published: Published | None = None,
    found: int = 0,
) -> RunPage:
    """``summary.json`` as the page a reader opens first: the counts, the run, the index."""
    question_set = _object(summary, "question_set")
    predictions = _object_or_none(summary, "predictions")
    fixture = _object(summary, "fixture")
    settings = _object(summary, "settings")
    shuffle = _object(summary, "shuffle")
    session = _object(summary, "session_settings")
    verdicts = _object(summary, "verdicts")
    return RunPage(
        published=published,
        directories=found,
        run_id=_text(summary, "run_id"),
        format=_text(summary, "format"),
        exit_status=_integer(summary, "exit_status"),
        questions_audited=_integer(question_set, "audited"),
        counts=(
            Fact("questions audited", _as_text(question_set.get("audited"))),
            *(Fact(name, _as_text(count)) for name, count in verdicts.items()),
            Fact("probes fired", _as_text(summary.get("smells_fired"))),
        ),
        verdict_counts=tuple(
            (name, value) for name, value in verdicts.items() if isinstance(value, int)
        ),
        mechanism_counts=_mechanism_counts(questions),
        probe_counts=_facts(_object(summary, "smells")),
        probe_fired=_probe_fired(_object(summary, "smells")),
        credited=_credited(_object_or_none(summary, "credited_but_not_equal")),
        made_of=(
            Fact("run", _text(summary, "run_id")),
            Fact("summary format", _text(summary, "format")),
            Fact(
                "question file",
                _text(question_set, "path"),
                _origin(question_set, _text(question_set, "digest")),
            ),
            Fact("questions in the file", _as_text(question_set.get("entries"))),
            *(
                ()
                if predictions is None
                else (
                    Fact(
                        "prediction file",
                        _text(predictions, "path"),
                        _origin(predictions, _text(predictions, "digest")),
                    ),
                    Fact("statements read", _as_text(predictions.get("statements"))),
                    Fact("keyed by", _text(predictions, "keyed_by")),
                )
            ),
            *_data_file(_object_or_none(fixture, "source")),
            Fact("server", _text(summary, "backend_identity")),
            Fact("database role", _text(summary, "effective_database_role")),
            Fact("engine", _text(session, "engine")),
            Fact("parser", ", ".join(f"{k} {v}" for k, v in _object(summary, "parser").items())),
            Fact("serialization", _text(settings, "serialization")),
            Fact("statement timeout", f"{_as_text(settings.get('statement_timeout_seconds'))} s"),
            Fact("fixture digest depth", _text(fixture, "depth")),
            Fact("schema digest", _optional_text(fixture, "schema_digest")),
            Fact("data as of", _text(summary, "data_as_of"), _text(summary, "data_as_of_source")),
            Fact(
                "shuffled copies",
                "prepared" if bool(shuffle.get("prepared")) else "not prepared",
                _optional_text(shuffle, "reason"),
            ),
            Fact("shuffle seed", _as_text(shuffle.get("seed"))),
            Fact("experimental probe", "on" if bool(settings.get("experimental_s2")) else "off"),
        ),
        session=_facts(_object(session, "recorded")),
        notes=_notes(summary, question_set, predictions, fixture, shuffle),
        entries=_entries(summary, questions, directories),
        files=(Fact(SUMMARY_FILE, _text(summary, "format")),),
    )


def _filters(entries: Sequence[Entry], run_id: str) -> tuple[FilterPage, ...]:
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


def _probe_fired(smells: Json) -> tuple[tuple[str, int], ...]:
    """Each probe and how many golds it fired on, as numbers, in the summary's own order.

    Read through ``_integer``, which is what every other number a page states goes through:
    a ``smells`` value that is not a whole number is a document this command cannot render,
    and refusing it names the key, where drawing it as a zero would state a count no file
    holds.
    """
    return tuple((name, _integer(smells, name)) for name in smells)


def _mechanism_counts(questions: Sequence[QuestionPage]) -> tuple[tuple[str, int], ...]:
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


def _credited(stated: Json | None) -> tuple[Fact, ...]:
    """What BIRD's own check credited and this comparison called NOT_EQUAL, by mechanism."""
    if stated is None:
        return ()
    return (
        Fact("credited by BIRD and NOT_EQUAL here", _as_text(stated.get("total"))),
        *(Fact(name, _as_text(count)) for name, count in _object(stated, "by_mechanism").items()),
        *(
            Fact(f"the test-suite check answered {name}", _as_text(count))
            for name, count in _object(stated, "by_test_suite_ex").items()
        ),
    )


def _data_file(source: Json | None) -> tuple[Fact, ...]:
    if source is None:
        return ()
    return (Fact("data file", _text(source, "path"), _origin(source, _text(source, "digest"))),)


def _notes(
    summary: Json,
    question_set: Json,
    predictions: Json | None,
    fixture: Json,
    shuffle: Json,
) -> tuple[Fact, ...]:
    """The states of the run that are a row rather than a page, stated only when they occurred."""
    notes: list[Fact] = []
    duplicates = _strings(question_set, "duplicate_ids")
    if duplicates:
        notes.append(Fact("ids the question file states twice", ", ".join(duplicates)))
    if predictions is not None:
        unused = _strings(predictions, "positions_unused")
        if unused:
            notes.append(Fact("prediction positions not compared", ", ".join(unused)))
    for key, name in (
        ("missing_tables", "tables the catalogue does not hold"),
        ("unreadable_tables", "tables this role may not read"),
    ):
        tables = _strings(fixture, key)
        if tables:
            notes.append(Fact(name, ", ".join(tables)))
    refused = _optional_text(fixture, "refused")
    if refused:
        notes.append(Fact("the fixture measurement was refused", refused))
    for name, reason in _object(shuffle, "not_reached_by_a_copy").items():
        notes.append(Fact(f"{name} was not reached by a shuffled copy", _as_text(reason)))
    bound = _as_text(_object(summary, "settings").get("statement_timeout_seconds"))
    for side, ids in _object(summary, "timed_out").items():
        stopped = [_as_text(value) for value in _list_of(ids, "timed_out")]
        if stopped:
            # The bound the run was given, beside the questions that reached it: the record of
            # a side that ran states the timeout it actually held, and a side that never
            # answered has none, so what a reader needs here is what the run asked for.
            notes.append(
                Fact(
                    f"stopped by the statement timeout, {side}",
                    ", ".join(stopped),
                    f"the run's bound was {bound} s",
                )
            )
    return tuple(notes)


def _entries(
    summary: Json, questions: Sequence[QuestionPage], directories: Sequence[Path]
) -> tuple[Entry, ...]:
    """The question index: one row per directory, then the questions that wrote none.

    A question whose statement could not be run has no directory to open, so it is a row
    of this table read from the summary's own error list, with the side that failed, the
    step it failed at and the engine's message.
    """
    entries = [
        Entry(
            question_id=question.question_id,
            href=f"{directory.name}/{PAGE_FILE}",
            verdict=question.verdict,
            replay_rule=question.replay_rule,
            mechanism="" if question.mechanism is None else question.mechanism.classification,
            probes=tuple(probe.name for probe in question.probes if probe.fired),
            question_text=question.question_text,
            note="",
        )
        for question, directory in zip(questions, directories, strict=True)
    ]
    entries.extend(
        Entry(
            question_id=_as_text(error.get("question_id")),
            href="",
            verdict="ERROR",
            replay_rule="",
            mechanism="",
            probes=(),
            question_text="",
            note=(f"{_text(error, 'side')}: {_text(error, 'step')}: {_text(error, 'message')}"),
        )
        for error in _objects(summary, "errors")
    )
    return tuple(entries)


def mark_differences(left: str, right: str) -> tuple[tuple[Token, ...], tuple[Token, ...]]:
    """The two statements cut into tokens, with the tokens they differ in marked.

    A comparison of two texts and nothing more. It states nothing about either statement:
    two statements that differ nowhere are two spellings of one, and two that differ
    everywhere may still return the same rows, which is what the verdict above is for.
    """
    left_tokens = SQL_TOKEN.findall(left)
    right_tokens = SQL_TOKEN.findall(right)
    marked_left = [False] * len(left_tokens)
    marked_right = [False] * len(right_tokens)
    matcher = difflib.SequenceMatcher(a=left_tokens, b=right_tokens, autojunk=False)
    for tag, left_from, left_to, right_from, right_to in matcher.get_opcodes():
        if tag == "equal":
            continue
        for index in range(left_from, left_to):
            marked_left[index] = True
        for index in range(right_from, right_to):
            marked_right[index] = True
    return (
        tuple(Token(text, differs) for text, differs in zip(left_tokens, marked_left, strict=True)),
        tuple(
            Token(text, differs) for text, differs in zip(right_tokens, marked_right, strict=True)
        ),
    )


def _document(path: Path) -> Json:
    """One JSON file of an audit directory, or a refusal naming the file and what was wrong."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError as unreadable:
        raise ReportRefused(f"{path} could not be read: {unreadable}") from unreadable
    except json.JSONDecodeError as unreadable:
        raise ReportRefused(f"{path} does not hold JSON: {unreadable}") from unreadable
    if not isinstance(loaded, dict):
        raise ReportRefused(f"{path} does not hold a JSON object")
    return cast("Json", loaded)


def _entry_list(path: Path) -> list[Json]:
    """One JSON file holding a list of objects, which `questions.json` is and no audit file."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except OSError as unreadable:
        raise ReportRefused(f"{path} could not be read: {unreadable}") from unreadable
    except json.JSONDecodeError as unreadable:
        raise ReportRefused(f"{path} does not hold JSON: {unreadable}") from unreadable
    if not isinstance(loaded, list):
        raise ReportRefused(f"{path} does not hold a JSON array")
    return [_object_of(entry, path.name) for entry in cast("list[object]", loaded)]


def _object(document: Json, key: str) -> Json:
    return _object_of(document.get(key), key)


def _object_of(value: object, what: str) -> Json:
    if not isinstance(value, dict):
        raise UnreadableRecord(f"{what} is not a JSON object: {value!r}")
    return cast("Json", value)


def _object_or_none(document: Json, key: str) -> Json | None:
    """A block the format states may be null, or absent when the run had nothing to say."""
    value = document.get(key)
    return None if value is None else _object_of(value, key)


def _list(document: Json, key: str) -> list[Json]:
    return _list_of(document.get(key), key)


def _list_of(value: object, what: str) -> list[Json]:
    if not isinstance(value, list):
        raise UnreadableRecord(f"{what} is not a JSON array: {value!r}")
    return cast("list[Json]", value)


def _objects(document: Json, key: str) -> list[Json]:
    return [_object_of(value, key) for value in _list(document, key)]


def _strings(document: Json, key: str) -> list[str]:
    return [_as_text(value) for value in _list(document, key)]


def _text(document: Json, key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise UnreadableRecord(f"{key} is not text: {value!r}")
    return value


def _optional_text(document: Json, key: str, *, absent: str = "") -> str:
    """A value the format states may be null, as the text a page shows for it."""
    value = document.get(key)
    return absent if value is None else _as_text(value)


def _integer(document: Json, key: str) -> int:
    value = document.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise UnreadableRecord(f"{key} is not a whole number: {value!r}")
    return value


def _optional_integer(document: Json, key: str, default: int) -> int:
    return default if document.get(key) is None else _integer(document, key)


def _facts(block: Json) -> tuple[Fact, ...]:
    return tuple(Fact(name, _as_text(value)) for name, value in block.items())


def _origin(source: Json, digest: str) -> str:
    """What the run was told about a file, after the digest it measured for itself."""
    origin = _optional_text(source, "origin", absent="origin not stated")
    date = _optional_text(source, "date")
    return f"{digest} | {origin}{f', {date}' if date else ''}"


def _as_text(value: object) -> str:
    """One JSON value as the text a page shows, with a null as the empty string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _cell_text(cell: Json) -> str:
    """One cell's payload as text. A null is the word, in the style the design gives it."""
    value = cell.get("value")
    return "NULL" if value is None else _as_text(value)


def _count(value: int) -> str:
    """A number of rows, with the thousands separated: a page states counts, not digits."""
    return f"{value:,} {'row' if value == 1 else 'rows'}"


__all__ = [
    "BIRD_READING",
    "BY_MECHANISM_DIRECTORY",
    "BY_PROBE_DIRECTORY",
    "COUNTEREXAMPLE_FILE",
    "FILTER_DIRECTORIES",
    "FILTER_SEGMENT",
    "GOLD_RECORD_FILE",
    "MARKER_FILE",
    "MARKER_TEXT",
    "NOT_EQUAL",
    "NOT_EQUAL_DIRECTORY",
    "PAGE_FILE",
    "SECOND_RECORD_FILE",
    "SMELLS_FILE",
    "STATIC",
    "SUMMARY_FILE",
    "TEMPLATES",
    "TEST_SUITE_READING",
    "Cell",
    "Column",
    "Difference",
    "Entry",
    "Fact",
    "Figure",
    "FilterPage",
    "Hash",
    "Mechanism",
    "Probe",
    "Projection",
    "QuestionPage",
    "Reading",
    "Record",
    "Report",
    "ReportRefused",
    "Row",
    "Rows",
    "RunPage",
    "Side",
    "Source",
    "Token",
    "default_out",
    "mark_differences",
    "question_page",
    "render_report",
]
