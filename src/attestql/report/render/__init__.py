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

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from attestql.evidence.load import UnreadableRecord
from attestql.report.figures import Figure, run_figures
from attestql.report.render.errors import ReportRefused
from attestql.report.render.indexes import (
    BY_MECHANISM_DIRECTORY,
    BY_PROBE_DIRECTORY,
    FILTER_DIRECTORIES,
    FILTER_SEGMENT,
    NOT_EQUAL_DIRECTORY,
    filter_pages,
)
from attestql.report.render.load import (
    COUNTEREXAMPLE_FILE,
    GOLD_RECORD_FILE,
    PUBLISHED_FILE,
    QUESTION_DIRECTORY,
    SECOND_RECORD_FILE,
    SMELLS_FILE,
    SUMMARY_FILE,
    beside_the_run,
    published_asset,
    question_directories,
    read_document,
    refuse_a_gap_nothing_explains,
)
from attestql.report.render.models import (
    BIRD_READING,
    NOT_EQUAL,
    ROWS_ON_A_PAGE,
    TEST_SUITE_READING,
    Cell,
    Column,
    Crumb,
    Difference,
    Entry,
    Fact,
    FilterPage,
    Hash,
    Mechanism,
    Probe,
    Projection,
    Published,
    QuestionPage,
    Reading,
    Record,
    Report,
    Row,
    Rows,
    RunPage,
    Side,
    Source,
    Token,
)
from attestql.report.render.pages import (
    MARKER_FILE,
    MARKER_TEXT,
    PAGE_COMMAND,
    PAGE_FILE,
    STATIC,
    STATIC_DIRECTORY,
    TEMPLATES,
    clear_the_render_before_this_one,
    default_out,
    mark_differences,
    question_page,
    question_page_beside,
    refuse_an_out_inside_the_audit,
    run_page,
    write_pages,
)


def render_report(
    audit_directory: Path,
    out: Path | None = None,
    *,
    banner: str = "",
    static_root: str = "",
    within: str = "",
    breadcrumb: Sequence[Crumb] = (),
    address: str = "",
    icon: str = "",
) -> Report:
    """Render one audit directory into ``out``, or into its sibling when there is none.

    ``banner`` is a line put above every page written here, for a caller building a whole
    site out of several runs and needing to say something about all of them at once. It is
    empty for ``attestql report``, whose pages state what their own directory holds.

    ``within`` and ``breadcrumb`` are for that caller too, and are what one run knows nothing
    of: where it sits among the others, which is in every page's title, and the way back up,
    which is on the run page. Both are empty for ``attestql report``, which renders one
    directory and has nothing above it.

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
    refuse_an_out_inside_the_audit(audit_directory, destination)
    directories = question_directories(audit_directory)
    try:
        summary = read_document(summary_path)
        beside = beside_the_run(audit_directory)
        refuse_a_gap_nothing_explains(audit_directory, summary, directories, beside.published)
        questions = [
            replace(question_page_beside(directory, beside), within=within)
            for directory in directories
        ]
        run = run_page(
            summary,
            questions,
            directories,
            beside.published,
            len(directories),
            within=within,
            breadcrumb=tuple(breadcrumb),
        )
        verdicts, probes = run_figures(run)
        run = replace(
            run,
            verdict_figure=verdicts,
            probe_figure=probes,
            filters=filter_pages(run.entries, run.run_id, within=within),
        )
    except UnreadableRecord as unreadable:
        raise ReportRefused(f"{audit_directory}: {unreadable}") from unreadable
    clear_the_render_before_this_one(destination)
    try:
        return write_pages(
            destination,
            run,
            questions,
            audit_directory,
            directories,
            banner,
            static_root,
            address,
            icon,
        )
    except OSError as unwritable:
        # Everything below writes files, and a write that fails is this command failing to
        # do what it was asked rather than a directory it could not read: it is the same
        # refusal and the same exit status as the checks above, and never a traceback.
        raise ReportRefused(f"{destination} could not be written: {unwritable}") from unwritable


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
    "PUBLISHED_FILE",
    "QUESTION_DIRECTORY",
    "ROWS_ON_A_PAGE",
    "SECOND_RECORD_FILE",
    "SMELLS_FILE",
    "STATIC",
    "STATIC_DIRECTORY",
    "SUMMARY_FILE",
    "TEMPLATES",
    "TEST_SUITE_READING",
    "Cell",
    "Column",
    "Crumb",
    "Difference",
    "Entry",
    "Fact",
    "Figure",
    "FilterPage",
    "Hash",
    "Mechanism",
    "Probe",
    "Projection",
    "Published",
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
    "published_asset",
    "question_page",
    "render_report",
]
