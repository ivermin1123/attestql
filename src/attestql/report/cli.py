"""What ``attestql report`` is called and what it takes on the command line.

A subcommand of the existing command rather than a second console script. ``main`` already
reads which subcommand it was given and hands the rest to the function that runs it, so a
third one is a parser here, two lines there and no new entry point, no second ``--version``
and no second name for a reader to learn; a script of its own would have been all of those.

Only the argument parsing lives here. What the subcommand does is ``render_report`` in
``attestql.report.render``, which reads an audit directory and writes pages, and the
refusal it raises is what the command turns into its exit status.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPORT = "report"
"""The subcommand that renders a directory ``attestql audit`` wrote."""

REPORT_HELP = "render an audit directory as pages, one per question"

REPORT_DESCRIPTION = (
    "Read the JSON one audit wrote and write a page for the run and a page for each "
    "question, with the JSON each page was rendered from beside it. It reads the files "
    "and reaches no database, so a directory another machine produced is enough."
)

AUDIT_DIRECTORY_HELP = "the directory an audit wrote, the one holding summary.json"

OUT_HELP = (
    "where the pages are written; by default the audit directory's own sibling, "
    "<audit-dir>-report/, because a rerun of the audit clears the audit directory"
)


def add_report_arguments(parser: argparse.ArgumentParser) -> None:
    """The two arguments the subcommand takes: what to read, and where to write it."""
    parser.add_argument("audit", type=Path, help=AUDIT_DIRECTORY_HELP)
    parser.add_argument("--out", type=Path, default=None, help=OUT_HELP)


__all__ = [
    "AUDIT_DIRECTORY_HELP",
    "OUT_HELP",
    "REPORT",
    "REPORT_DESCRIPTION",
    "REPORT_HELP",
    "add_report_arguments",
]
