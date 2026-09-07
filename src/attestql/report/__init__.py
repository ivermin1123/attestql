"""``attestql report``: an audit directory as pages, rendered from its own JSON.

The audit writes a run's ``summary.json`` and, per question, a counterexample, one or two
evidence records and the probes. This package turns a directory of them into HTML: one
page for the run and one for each question, with the JSON copied beside every page, so a
reader who doubts a sentence opens the file it was rendered from.

What it imports is the whole of the guarantee. The evidence package, Jinja2 and the
standard library, and nothing that reaches a database or parses SQL: a directory produced
on another machine, by another engine, is enough to render, and
``tests/test_report_imports_no_engine.py`` walks the import graph to keep it that way.
"""

from attestql.report.cli import (
    REPORT,
    REPORT_DESCRIPTION,
    REPORT_HELP,
    add_report_arguments,
)
from attestql.report.render import Report, ReportRefused, default_out, render_report

__all__ = [
    "REPORT",
    "REPORT_DESCRIPTION",
    "REPORT_HELP",
    "Report",
    "ReportRefused",
    "add_report_arguments",
    "default_out",
    "render_report",
]
