"""What a page is made of: the values a template is handed and nothing that builds them.

Every dataclass here is read by a template and by the tests that assert what a page says. They
hold no path, open no file and know nothing about where their values came from, which is what
lets a page be built from a directory this machine did not produce.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from attestql.report.figures import Figure

NOT_EQUAL = "NOT_EQUAL"
"""The verdict the first filter is about, spelled as the summary and the pages spell it."""

ROWS_ON_A_PAGE = 50
"""How many rows of one record's result a question page holds.

The record itself holds every row its result had, up to the bound the audit wrote it under,
and is copied beside the page: what this decides is the size of the document a browser has
to lay out, not what a reader can reach. Fifty is more than a reader reads before opening
the JSON and small enough that a result of ten thousand rows is a page like any other."""

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
        return count_in_words(self.row_count)


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
    within: str = ""
    """Where this run sits, in the words of whoever published it: a benchmark and, where the
    run is one of a group, the name of the prediction file the group is.

    Empty for a report ``attestql report`` wrote, which is one run and knows of no other. A
    site renders the same question under seventeen prediction runs, and the title of a page
    is what a search result, a browser tab and a bookmark are: measured on the build of
    2026-09-08, 673 pages carried 584 distinct titles and ``q1435 NOT_EQUAL`` was seventeen
    of them."""

    @property
    def title(self) -> str:
        """Short enough to survive a search result, and distinct within one site."""
        stated = f"q{self.question_id} {self.verdict}"
        return f"{stated}, {self.within}" if self.within else stated

    @property
    def description(self) -> str:
        """What this page is, for a reader who meets it as a search result and not as a link."""
        asked = self.question_text or "a question of this run"
        where = f" in {self.within}" if self.within else ""
        return f"q{self.question_id}{where}: {self.verdict} under {self.replay_rule}. {asked}"


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
    within: str = ""
    """Where the run this restricts sits, in the words of whoever published it, or nothing.

    The same context the run page and the question pages carry. Without it the title fell back
    to the run's UUID, which is 42 characters of nothing a reader can read, and a filter page
    was the longest title on the site."""

    @property
    def root(self) -> str:
        """What this page puts in front of a path the run page states relative to itself."""
        return "../" * (self.slug.count("/") + 1)

    @property
    def title(self) -> str:
        """The restriction first, then the run, in the shape a question page's title has.

        The restriction leads because it is what tells two of these apart, and because a tab
        and a search result show the front of a title and cut the rest. Where the publisher
        said which run this is, that is what follows; a report `attestql report` wrote knows
        of no other run and names its own UUID, as its run page does.
        """
        if self.within:
            return f"{self.heading}, {self.within}"
        return f"attestql run {self.run_id}: {self.heading}"

    @property
    def description(self) -> str:
        return self.restriction


@dataclass(frozen=True)
class Crumb:
    """One step of the way back up from a page: what it is called and where it is."""

    label: str
    href: str


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
    wrote: int | None = None
    """How many question directories the run says it wrote, where its summary says.

    What a selection is a selection of. ``published.json`` states the same number for a run a
    publisher archived, and this is the run's own answer for one nobody has; a summary written
    before the run stated it leaves this empty and the page says only that it is a selection."""
    verdict_figure: Figure | None = None
    probe_figure: Figure | None = None
    """The verdicts and the probes drawn, filled in after the page is built. ``counts``
    and ``probe_counts`` are the same numbers as the tables state them, and
    ``verdict_counts``, ``mechanism_counts`` and ``probe_fired`` are those numbers as
    numbers, which is what a bar is drawn from: the classes are counted from the question
    directories this run wrote, because ``summary.json`` counts a mechanism only for the
    credited rows. A count that is not a whole number is refused where it is read, the way
    every other number on this page is, rather than drawn as a zero nobody was told about."""

    within: str = ""
    """Where this run sits, in the words of whoever published it. Empty for a report
    ``attestql report`` wrote, which is one run and knows of no other."""
    breadcrumb: tuple[Crumb, ...] = ()
    """The way back up from this run, innermost last, or nothing.

    A reader arriving on a run page from a shared link had no link to the group or the
    benchmark it belongs to; the group and benchmark pages had one and the run did not. It is
    the publisher's to fill in, because a run knows nothing of what is above it, and a report
    of a single directory has nothing above it at all."""

    @property
    def title(self) -> str:
        """The run as a publisher names it, or as it names itself.

        `run_id` is a UUID, which is unique and unreadable, and the page states it either
        way. Where the publisher said which run this is, that is what a tab, a bookmark and
        a search result show instead.
        """
        return f"attestql run {self.within or self.run_id}"

    @property
    def description(self) -> str:
        where = f" of {self.within}" if self.within else ""
        return (
            f"The audit run{where}: {self.questions_audited} questions, "
            f"what disagreed, what fired, and the evidence for each."
        )


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


ALWAYS_TAGGED = ("text-bytes",)
"""Tags a cell carries even where every row of its column agrees.

A text value that did not decode is rendered as the hex of its bytes, and hex is text: a
column of them beside a column of text would show two readings of the same characters with
nothing to tell them apart, and the difference is what a verdict can turn on. Every other
tag is shown only where the rows disagree, because the payload already reads as itself.
"""


def count_in_words(value: int) -> str:
    """A number of rows, with the thousands separated: a page states counts, not digits."""
    return f"{value:,} {'row' if value == 1 else 'rows'}"
