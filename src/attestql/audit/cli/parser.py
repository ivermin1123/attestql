"""The argument grammar, and the options one run is given.

What a person may type and what that becomes: every flag, its default, the converters that
refuse a value the grammar cannot use, and ``AuditOptions``, which is the whole of what the
run below is told. Nothing here reads a file or opens anything.
"""

from __future__ import annotations

import argparse
import importlib.metadata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from attestql.audit.cli.inputs import (
    JSON_PREDICTIONS,
    LINE_PREDICTIONS,
    POSITION_KEYING,
    QUESTION_ID_KEYING,
)
from attestql.audit.compare import (
    DEFAULT_STATEMENT_TIMEOUT_SECONDS,
)
from attestql.audit.engines import DEFAULT_ENGINE, ENGINES, Engine, engine_named
from attestql.audit.postgres import DEFAULT_SCRATCH_SCHEMA
from attestql.audit.smells import (
    DEFAULT_SHUFFLE_ROW_LIMIT,
    DEFAULT_SHUFFLE_SEED,
)
from attestql.evidence.serialize import SerializationDescriptor
from attestql.report import (
    REPORT,
    REPORT_DESCRIPTION,
    REPORT_HELP,
    add_report_arguments,
)

PROGRAM = "attestql"

AUDIT = "audit"
"""The subcommand that audits a question file against a database."""

DEMO = "demo"
"""The subcommand that writes the packaged sandbox somewhere and audits that.

Named beside the audit rather than under it because it takes none of the audit's options: it
builds the run it then makes, and what it is for is a person who installed the wheel and has
no question file, no prediction file and no database to point the audit at."""

SERIALIZATION = SerializationDescriptor(
    version="attestql/audit/4",
    numeric_scale=6,
    timestamp_format="%Y-%m-%dT%H:%M:%S.%fZ",
    timezone="UTC",
    null_rendering="NULL",
    encoding="utf-8",
)
"""What every result of an audit is rendered under, stated in every record it writes.

One descriptor for the whole tool: two records rendered under different rules are not
comparable, and a run that let its rendering be configured would produce records that
cannot be compared with anyone else's.

``version`` is what a reader compares two records' layout under, so it moves with the
layout and with the set of value types a record can hold, and with nothing else (ADR-0014,
ADR-0015). It read ``2`` from the session settings gaining the engine and a column's type
becoming its declared type; it reads ``3`` since a text value that does not decode is
recorded as its bytes rather than refused. The rendering rules below have not changed at
any of it, and neither have the bytes the serializer makes of a record written before it:
a record states the version it was written under and is re-rendered under that one."""


@dataclass(frozen=True)
class AuditOptions:
    """Everything the command was asked for, with the credential deliberately absent."""

    dsn: str
    questions: Path
    out: Path
    predictions: Path | None = None
    questions_origin: str | None = None
    questions_date: str | None = None
    predictions_origin: str | None = None
    predictions_date: str | None = None
    predictions_keyed_by: str = QUESTION_ID_KEYING
    predictions_format: str = JSON_PREDICTIONS
    data_file: Path | None = None
    data_origin: str | None = None
    data_date: str | None = None
    ids: tuple[int, ...] = ()
    fixture_digest: str = "counts"
    fail_on_smell: bool = False
    experimental_s2: bool = False
    plan_variant: bool = False
    shuffle_seed: int = DEFAULT_SHUFFLE_SEED
    shuffle_row_limit: int = DEFAULT_SHUFFLE_ROW_LIMIT
    scratch_schema: str = DEFAULT_SCRATCH_SCHEMA
    statement_timeout_seconds: int = DEFAULT_STATEMENT_TIMEOUT_SECONDS
    data_as_of: datetime | None = None
    engine: Engine = DEFAULT_ENGINE

    @property
    def with_content_digests(self) -> bool:
        return self.fixture_digest == "full"


def _schema(value: str) -> str:
    """A schema name the copies can be written into: one name, and not an empty one.

    Whether it exists and whether this role may create in it is the server's answer and is
    asked at the moment the copies are made, so what is refused here is only what no server
    could be asked about.
    """
    name = value.strip()
    if not name:
        raise argparse.ArgumentTypeError("the scratch schema is named by nothing")
    return name


def _ids(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(found) for found in value.split(",") if found.strip())
    except ValueError as unreadable:
        raise argparse.ArgumentTypeError(f"{value!r} is not a comma separated list of ids") from (
            unreadable
        )


def _instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as unreadable:
        raise argparse.ArgumentTypeError(f"{value!r} is not an ISO 8601 instant") from unreadable
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError(
            f"{value!r} states no offset; an instant a record carries states one"
        )
    return parsed.astimezone(UTC)


def _stated_date(value: str) -> str:
    """A date or an instant as the origin states it, kept as the text that was given.

    Parsed only to refuse what is not ISO 8601. A dataset states its own date in its own
    words, and a run that rewrote them into a normal form would record something the place
    it came from does not say.
    """
    try:
        datetime.fromisoformat(value)
    except ValueError as unreadable:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not an ISO 8601 date or instant"
        ) from unreadable
    return value


def _positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError as unreadable:
        raise argparse.ArgumentTypeError(f"{value!r} is not a whole number") from unreadable
    if number < 1:
        raise argparse.ArgumentTypeError(f"{value!r} is not at least one")
    return number


def build_parser() -> argparse.ArgumentParser:
    """The command line, as ADR-0013 point 2 states it.

    ``--version`` is on this parser and not on the subcommand, because what a reader asks
    for when they type it is which release is installed and not what one of its commands
    does. The number is read off the installed distribution here, once per invocation, so it
    is the release the code being run came from rather than a string this file states about
    itself and could be wrong about.
    """
    parser = argparse.ArgumentParser(
        prog=PROGRAM, description="Audit text-to-SQL gold statements and predictions."
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROGRAM} {importlib.metadata.version(PROGRAM)}",
        help="print the installed release and exit",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    audit = subcommands.add_parser(
        AUDIT,
        help="compare golds and predictions on one database and record what differs",
        description=(
            "Run each gold statement, and each prediction beside it, against one "
            "PostgreSQL or SQLite database; report where they disagree and which golds "
            "smell wrong."
        ),
    )
    audit.add_argument(
        "--engine",
        choices=sorted(ENGINES),
        default=DEFAULT_ENGINE.name,
        help="which database engine to audit on; it decides the backend and the parser",
    )
    audit.add_argument(
        "--dsn",
        required=True,
        help=(
            "where the database is: a libpq keyword DSN without a password on PostgreSQL, "
            "where PGPASSWORD or ~/.pgpass supplies it, and the path to the file on SQLite"
        ),
    )
    audit.add_argument(
        "--questions", required=True, type=Path, help="the BIRD Mini-Dev question file"
    )
    audit.add_argument(
        "--predictions", type=Path, help="a JSON object of question id to predicted SQL"
    )
    audit.add_argument(
        "--questions-origin",
        default=None,
        help=(
            "where the question file came from, a URL or a note, recorded beside its digest so a "
            "reader knows which version of the benchmark was audited"
        ),
    )
    audit.add_argument(
        "--questions-date",
        type=_stated_date,
        default=None,
        help="the date that origin states for the question file, ISO 8601",
    )
    audit.add_argument(
        "--predictions-origin",
        default=None,
        help="where the predictions file came from, a URL or a note, recorded beside its digest",
    )
    audit.add_argument(
        "--predictions-date",
        type=_stated_date,
        default=None,
        help="the date that origin states for the predictions file, ISO 8601",
    )
    audit.add_argument(
        "--predictions-keyed-by",
        choices=(QUESTION_ID_KEYING, POSITION_KEYING),
        default=None,
        help=(
            "what a key of the predictions file is: a question id, or the position of an entry "
            "in the question file, which is what BIRD's own predict_*.json files hold; the "
            f"default is {QUESTION_ID_KEYING} for a JSON file and {POSITION_KEYING} for a file "
            "read line by line"
        ),
    )
    audit.add_argument(
        "--predictions-format",
        choices=(JSON_PREDICTIONS, LINE_PREDICTIONS),
        default=JSON_PREDICTIONS,
        help=(
            "the shape of the predictions file: one JSON object, or one statement per line, "
            "which is how most published prediction files ship. A publisher's own edit, such "
            "as a comment cut or a database name appended to the statement, is prepared before "
            "the file reaches this tool"
        ),
    )
    audit.add_argument(
        "--data-file",
        type=Path,
        help=(
            "the dump or SQL file the data was loaded from; it is digested and never read, "
            "so that a record states which file the server was loaded from"
        ),
    )
    audit.add_argument(
        "--data-origin",
        default=None,
        help="where the data file came from, a URL or a note, recorded beside its digest",
    )
    audit.add_argument(
        "--data-date",
        type=_stated_date,
        default=None,
        help="the date that origin states for the data file, ISO 8601",
    )
    audit.add_argument(
        "--out", required=True, type=Path, help="the directory the evidence is written to"
    )
    audit.add_argument("--ids", type=_ids, default=(), help="audit only these question ids")
    audit.add_argument(
        "--fixture-digest",
        choices=("counts", "full"),
        default="counts",
        help="how deep the data is measured: schema and row counts, or every row",
    )
    audit.add_argument(
        "--fail-on-smell", action="store_true", help="exit 1 when any smell fired as well"
    )
    audit.add_argument(
        "--experimental-s2",
        action="store_true",
        help="run the experimental direction-against-question smell",
    )
    audit.add_argument(
        "--plan-variant", action="store_true", help="also rerun each gold under another plan"
    )
    audit.add_argument(
        "--shuffle-seed",
        type=int,
        default=DEFAULT_SHUFFLE_SEED,
        help="the seed the shuffled copies are ordered by",
    )
    audit.add_argument(
        "--scratch-schema",
        type=_schema,
        default=DEFAULT_SCRATCH_SCHEMA,
        help=(
            "on PostgreSQL only: an existing schema this role may create tables in, where "
            "the shuffled copies are made; this tool creates no schema and drops none"
        ),
    )
    audit.add_argument(
        "--shuffle-row-limit",
        type=_positive,
        default=DEFAULT_SHUFFLE_ROW_LIMIT,
        help="a table with more rows than this is not copied for the shuffle",
    )
    audit.add_argument(
        "--statement-timeout",
        type=_positive,
        default=DEFAULT_STATEMENT_TIMEOUT_SECONDS,
        help="how long one statement may run, in seconds",
    )
    audit.add_argument(
        "--data-as-of", type=_instant, help="what instant the data is as of; the run's by default"
    )
    demo = subcommands.add_parser(
        DEMO,
        help="build the packaged sandbox and audit it",
        description=(
            "Write this package's own SQLite sandbox into a directory, audit it, and print "
            "the audit command over the files that were written."
        ),
    )
    demo.add_argument(
        "--out",
        required=True,
        type=Path,
        help="the directory the sandbox and its audit are written into",
    )
    add_report_arguments(
        subcommands.add_parser(REPORT, help=REPORT_HELP, description=REPORT_DESCRIPTION)
    )
    return parser


def parse_arguments(argv: Sequence[str] | None = None) -> AuditOptions:
    """The command line as options, or an argparse exit for anything it refuses.

    ``--version`` exits here too, with status 0 and the release on stdout: it is what the
    command was asked to do and not a refusal, and letting argparse end the process is what
    keeps the two apart without this function having a second kind of answer to return.
    """
    parser = build_parser()
    parsed = parser.parse_args(argv)
    engine = engine_named(cast("str", parsed.engine))
    dsn = cast("str", parsed.dsn)
    if not dsn.strip():
        parser.error("the DSN is empty")
    # What may stand there is the engine's to say: a libpq keyword string on one, a file
    # path on the other, and a rule written for one of them is wrong about the other.
    refused = engine.refuse_target(dsn)
    if refused is not None:
        parser.error(refused)
    if parsed.data_file is None and (parsed.data_origin, parsed.data_date) != (None, None):
        parser.error(
            "--data-origin and --data-date state where the data file came from; "
            "name that file with --data-file"
        )
    predictions_format = cast("str", parsed.predictions_format)
    keyed_by = cast("str | None", parsed.predictions_keyed_by)
    if keyed_by is None:
        keyed_by = POSITION_KEYING if predictions_format == LINE_PREDICTIONS else QUESTION_ID_KEYING
    elif predictions_format == LINE_PREDICTIONS and keyed_by == QUESTION_ID_KEYING:
        parser.error(
            "a predictions file read line by line holds no question id, so its keys are "
            f"positions; drop --predictions-keyed-by or pass {POSITION_KEYING}"
        )
    return AuditOptions(
        dsn=dsn,
        questions=cast("Path", parsed.questions),
        questions_origin=cast("str | None", parsed.questions_origin),
        questions_date=cast("str | None", parsed.questions_date),
        predictions=cast("Path | None", parsed.predictions),
        predictions_origin=cast("str | None", parsed.predictions_origin),
        predictions_date=cast("str | None", parsed.predictions_date),
        predictions_keyed_by=keyed_by,
        predictions_format=predictions_format,
        data_file=cast("Path | None", parsed.data_file),
        data_origin=cast("str | None", parsed.data_origin),
        data_date=cast("str | None", parsed.data_date),
        out=cast("Path", parsed.out),
        ids=cast("tuple[int, ...]", parsed.ids),
        fixture_digest=cast("str", parsed.fixture_digest),
        fail_on_smell=cast("bool", parsed.fail_on_smell),
        experimental_s2=cast("bool", parsed.experimental_s2),
        plan_variant=cast("bool", parsed.plan_variant),
        scratch_schema=cast("str", parsed.scratch_schema),
        shuffle_seed=cast("int", parsed.shuffle_seed),
        shuffle_row_limit=cast("int", parsed.shuffle_row_limit),
        statement_timeout_seconds=cast("int", parsed.statement_timeout),
        data_as_of=cast("datetime | None", parsed.data_as_of),
        engine=engine,
    )
