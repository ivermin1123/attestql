"""``attestql audit``: one command over a question file and a database.

ADR-0013 point 2. A stranger loads the BIRD Mini-Dev PostgreSQL dump, runs this against
it, and gets one line per question, a directory per disagreement or fired smell, a
summary line and ``summary.json``. The line and the file also count the statements that
ran past ``--statement-timeout``, the gold's apart from the prediction's, so that a run
whose bound was too short says so rather than leaving it in the error list. With
``--predictions`` each prediction is compared with its gold under the gold's own replay
rule; without them the gold-only smells run alone.

**Which prediction answers which question.** A predictions file written for this tool is
keyed by question id. BIRD's own ``predict_*.json`` is keyed by the position of an entry
in the question file, because its evaluation pairs prediction ``i`` with gold line ``i``,
and ``--predictions-keyed-by position`` is what reads one; the two readings pair different
statements, so a file whose keys are the positions of a question file that is not keyed by
them is refused rather than guessed at. A file that holds one statement per line and no key
at all is read by ``--predictions-format lines``, where a line's position is its key, so
that reading is position keying and asking for the other one there is refused. Where each file came from is recorded and never
inferred: the path and the digest are measured, and ``--questions-origin``,
``--questions-date``, ``--predictions-origin`` and ``--predictions-date`` are what the run
was told, in the summary and in every record.

**What a verdict means.** NOT_EQUAL says the gold and the prediction disagree on this
data under this rule. It never says which of them is wrong, and neither does a smell,
which is a heuristic and says so in its own evidence. Exit status follows ADR-0013:
0 when nothing disagreed, 1 when something did, 2 when this tool could not run at all.
The counts live in the summary and never in the exit code, and ``--fail-on-smell`` is
for whoever wants a heuristic to block a pipeline.

**The credential is never here.** The DSN is libpq keyword form. A URI is refused
whatever it holds, because a URI is where a password is written, and so is a keyword DSN
that names one; the password comes from ``PGPASSWORD`` or ``~/.pgpass`` through the
driver, is never read by this module, and appears in no line, file or error.

**What aborts a run is the tool failing to start, and a write it cannot make.** Failing to
start is reading the question file, reading the predictions file, making the output
directory and clearing the run before it out of it, and asking the backend what it is. After
that one thing still stops the run: a question directory or a summary that cannot be
written. A run that cannot write its evidence has failed as a tool whatever it found, so it
is a ``ToolError`` and exit 2 rather than a traceback and exit 1. A gold that does not parse,
a statement that times out, a table this database does not hold, a value with no rendering, a
server that went away between two questions: each is that question's ``ERROR`` line with the
message, an entry in the summary's ``errors``, and the run goes on to the next question and
still writes ``summary.json``.

**An error is not the exit status.** ADR-0013 point 2 fixes 0 for no disagreement, 1 for
at least one NOT_EQUAL and 2 for a tool error, and a question the run could not answer is
none of the three: the tool ran, the other questions were audited, and their verdicts are
what the status states. The exception is a run that answered no question at all, which
produced no audit and is therefore the tool failing after all: it exits 2, with the
summary naming every question it could not answer written first.

The module holds three things and nothing else: reading what the command was given,
``run_audit``, which a test drives with a scripted backend, and ``main``, which builds
the PostgreSQL one. Everything printed goes through a writer, so a test reads the lines
rather than a captured stream.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from attestql.audit.cli.errors import ToolError
from attestql.audit.cli.inputs import (
    BIRD_PREDICTION_SUFFIX,
    JSON_PREDICTIONS,
    LINE_PREDICTIONS,
    POSITION_KEYING,
    QUESTION_ID_KEYING,
    QUESTION_ID_LIMIT,
    NoStatement,
    Prediction,
    Question,
    QuestionSet,
    ResolvedPredictions,
    read_predictions,
    read_questions,
    resolve_predictions,
)
from attestql.audit.cli.parser import (
    AUDIT,
    DEMO,
    PROGRAM,
    SERIALIZATION,
    AuditOptions,
    build_parser,
    parse_arguments,
)
from attestql.audit.cli.run import (
    DEMO_AUDIT_DIRECTORY,
    MARKER_FILE,
    MARKER_TEXT,
    QUESTION_DIRECTORY,
    RERUN_PREFIX,
    audit,
    connect_and_audit,
    report,
    run_audit,
    run_demo,
)
from attestql.audit.cli.summary import (
    ERROR,
    GOLD_ONLY,
    SMELLS_FILE,
    SUMMARY_FILE,
    SUMMARY_FORMAT,
    ConsoleWriter,
    Credited,
    QuestionError,
    Summary,
    Writer,
)
from attestql.audit.postgres import DEFAULT_SCRATCH_SCHEMA
from attestql.report import REPORT


def main(argv: Sequence[str] | None = None) -> int:
    """The command line, and then the command it asked for. The exit status is the answer.

    Which subcommand was asked for is read here and its options are read by the function that
    runs it: the demo takes none of the audit's, and it reaches the audit through the same
    ``parse_arguments`` every other run does, over a command line it builds and then prints.
    """
    parsed = build_parser().parse_args(argv)
    writer = ConsoleWriter(sys.stdout)
    if parsed.command == DEMO:
        return run_demo(cast("Path", parsed.out), writer)
    if parsed.command == REPORT:
        return report(cast("Path", parsed.audit), cast("Path | None", parsed.out), writer)
    return connect_and_audit(parse_arguments(argv), writer)


__all__ = [
    "AUDIT",
    "BIRD_PREDICTION_SUFFIX",
    "DEFAULT_SCRATCH_SCHEMA",
    "DEMO",
    "DEMO_AUDIT_DIRECTORY",
    "ERROR",
    "GOLD_ONLY",
    "JSON_PREDICTIONS",
    "LINE_PREDICTIONS",
    "MARKER_FILE",
    "MARKER_TEXT",
    "POSITION_KEYING",
    "PROGRAM",
    "QUESTION_DIRECTORY",
    "QUESTION_ID_KEYING",
    "QUESTION_ID_LIMIT",
    "REPORT",
    "RERUN_PREFIX",
    "SERIALIZATION",
    "SMELLS_FILE",
    "SUMMARY_FILE",
    "SUMMARY_FORMAT",
    "AuditOptions",
    "ConsoleWriter",
    "Credited",
    "NoStatement",
    "Prediction",
    "Question",
    "QuestionError",
    "QuestionSet",
    "ResolvedPredictions",
    "Summary",
    "ToolError",
    "Writer",
    "audit",
    "build_parser",
    "connect_and_audit",
    "main",
    "parse_arguments",
    "read_predictions",
    "read_questions",
    "report",
    "resolve_predictions",
    "run_audit",
    "run_demo",
]
