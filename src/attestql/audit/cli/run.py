"""The run itself: what it does in order, and the directory it leaves behind.

Connect, measure the fixture once, read the golds, audit each question, write what
disagreed, and write the summary. The output directory's lifecycle is here too, because
what a rerun may empty is part of what a run is.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from attestql.audit.backend import (
    READ_THROUGH_PRIVATE_COPY,
    Backend,
    BackendRefused,
    ContentDigestRefused,
    PlannerStatistics,
    ShuffledCopies,
    StatementTimedOut,
    TableName,
)
from attestql.audit.cli.errors import ToolError
from attestql.audit.cli.inputs import (
    NoStatement,
    Prediction,
    Question,
    QuestionSet,
    read_predictions,
    read_questions,
    resolve_predictions,
)
from attestql.audit.cli.parser import (
    AUDIT,
    PROGRAM,
    SERIALIZATION,
    AuditOptions,
    parse_arguments,
)
from attestql.audit.cli.summary import (
    ERROR,
    GOLD_ONLY,
    SMELLS_FILE,
    SUMMARY_FILE,
    Counted,
    Measured,
    Phases,
    QuestionError,
    Summary,
    Writer,
    count_credited,
    question_line,
    summarise,
    summary_json,
    summary_line,
    write_summary,
)
from attestql.audit.compare import (
    GOLD_RECORD_FILE,
    SIDE_GOLD,
    SIDE_PREDICTION,
    SIDE_RUN,
    Comparison,
    ComparisonRefused,
    SideFailed,
    compare_statements,
    record_statement,
    sided,
    write_comparison,
)
from attestql.audit.engines import SQLITE, Parse
from attestql.audit.fixture import file_digest, fixture_digest
from attestql.audit.parse import ParsedStatement, StatementRefused
from attestql.audit.smells import (
    QuestionText,
    Smell,
    SmellSettings,
    all_smells,
    smells_json,
)
from attestql.demo import FIXTURE_FILE, build_fixture, write_inputs
from attestql.evidence.record import EvidenceRecord
from attestql.evidence.render import PARTIAL_SUFFIX, record_json, write_json
from attestql.evidence.replay import ComparabilityResult
from attestql.evidence.types import (
    QuestionMetadata,
    SessionSettings,
    StatementSource,
)
from attestql.report import (
    ReportRefused,
    render_report,
)

DEMO_AUDIT_DIRECTORY = "audit"
"""Where the demo's audit writes, under the directory the demo was given: the sandbox it
built is beside it, so one directory holds the run and everything the run read."""

RERUN_PREFIX = "rerun: "
"""What the demo's last line starts with, before the audit command it just ran."""
MARKER_FILE = ".attestql-run"
"""What says an output directory is an audit's own and may be cleared by the next run."""
MARKER_TEXT = (
    "written by attestql audit: every rerun into this directory removes summary.json "
    "and the q<id>/ directories\n"
)
"""The one line the marker holds, so a reader who opens it learns why it is there."""
QUESTION_DIRECTORY = re.compile(r"q\d+")
"""The name of a directory this tool writes a question's evidence to."""


def _question_set_name(question_set: QuestionSet, options: AuditOptions) -> str:
    """The file's stem, and its stated origin when there is one."""
    if options.questions_origin is None:
        return question_set.path.stem
    return f"{question_set.path.stem} from {options.questions_origin}"


def _question_metadata(question: Question, question_set: str) -> QuestionMetadata:
    """``question_set`` names the set as the file's stem and, when the run was told where the
    file came from, that origin after it: two files of the same name from two places are two
    versions of a benchmark, and the record has to say which one it audited."""
    return QuestionMetadata(
        question_id=str(question.question_id),
        question_set=question_set,
        question_text=question.question,
        evidence_text=question.evidence,
    )


def _prepare_shuffle(
    backend: Backend, tables: Sequence[TableName], options: AuditOptions
) -> tuple[ShuffledCopies | None, str]:
    """The shuffled copies for the run, or the reason there are none."""
    if not tables:
        return None, "no gold statement named a table to copy"
    try:
        return (
            backend.prepare_shuffled_copies(
                tables, seed=str(options.shuffle_seed), row_limit=options.shuffle_row_limit
            ),
            "",
        )
    except BackendRefused as refused:
        # A backend that will not make the copies is not a backend that cannot audit:
        # every other smell and every comparison still runs, and the summary says which
        # measurement was not taken.
        return None, _refusal(refused)


def _parsed_golds(
    questions: Sequence[Question], parse: Parse
) -> tuple[ParsedStatement | StatementRefused, ...]:
    """Every gold read once, by the engine's parser, in the order the questions are asked.

    The tables this run measures are read off these parses and so is every record written
    from them, and a parse is a function of its text: asking for a second one buys nothing
    a run does not already hold. A gold this audit cannot read keeps its refusal here and
    raises it when the run reaches that question, which is where a reader is told.
    """
    parsed: list[ParsedStatement | StatementRefused] = []
    for question in questions:
        try:
            parsed.append(parse(question.sql))
        except StatementRefused as refused:
            parsed.append(refused)
    return tuple(parsed)


def _referenced_tables(
    golds: Sequence[ParsedStatement | StatementRefused],
) -> tuple[TableName, ...]:
    """Every table the golds name, for the one fixture measurement and the copies.

    A gold that did not parse names nothing here and is reported as its own question's
    error when the run reaches it. A table two golds spelled two ways is two names here
    and one table underneath: what the backend does with the two spellings is its own,
    and what a summary states is what the golds wrote.
    """
    tables: dict[TableName, None] = {}
    for gold in golds:
        if isinstance(gold, StatementRefused):
            continue
        for table in gold.tables:
            tables[table] = None
    return tuple(tables)


def run_audit(options: AuditOptions, backend: Backend, writer: Writer) -> Summary:
    """Audit every question the options name, on that backend, and write what was found.

    Raises ``ToolError`` when the run cannot start: an unreadable file, a question file
    that states two different questions under one id, an output directory that cannot be
    made, that holds files no audit wrote, or that cannot be cleared of the run before it,
    or a backend that will not say what it is. Everything a single question can fail at is
    that question's error line.
    """
    phases = Phases()
    run_id = f"audit-{uuid.uuid4()}"
    data_as_of = options.data_as_of or datetime.now(UTC)
    question_set = read_questions(options.questions, options.ids)
    questions_source = StatementSource(
        path=str(options.questions),
        digest=question_set.digest,
        origin=options.questions_origin,
        date=options.questions_date,
    )
    keyed: Mapping[int, str | NoStatement] = (
        read_predictions(options.predictions, shape=options.predictions_format)
        if options.predictions
        else {}
    )
    resolved = resolve_predictions(keyed, question_set, options.predictions_keyed_by)
    predictions_source = _predictions_source(options)
    data_digest = _data_digest(options)
    predictions = (
        {}
        if predictions_source is None
        else {
            question_id: Prediction(sql, predictions_source)
            for question_id, sql in resolved.by_id.items()
        }
    )
    try:
        options.out.mkdir(parents=True, exist_ok=True)
    except OSError as unwritable:
        raise ToolError(f"the output directory {options.out} cannot be made: {unwritable}") from (
            unwritable
        )
    _clear_previous_run(options.out)
    try:
        identity = backend.identity()
        role = backend.effective_database_role()
        settings = backend.session_settings()
    except BackendRefused as refused:
        raise ToolError(f"the backend will not state what it is: {refused}") from refused
    golds = _parsed_golds(question_set.questions, options.engine.parse)
    tables = _referenced_tables(golds)
    with phases.timed("fixture"):
        measured = _run_fixture(backend, tables, options)
    with phases.timed("shuffle"):
        shuffled, no_shuffle = _prepare_shuffle(backend, measured.present, options)
    try:
        counted = _audit_questions(
            options,
            backend,
            writer,
            phases,
            question_set=question_set,
            golds=golds,
            questions_source=questions_source,
            predictions=predictions,
            session_settings=settings,
            run_id=run_id,
            data_as_of=data_as_of,
            data_digest=data_digest,
            shuffled=shuffled,
            no_shuffle=no_shuffle,
        )
    finally:
        # The copies are this tool's own and outlive nothing: dropped whether the run
        # ended, failed or was interrupted.
        _drop_shuffle(backend)
    summary = summarise(options, counted, run_id=run_id, elapsed=phases.rounded())
    writer.line(summary_line(summary))
    write_summary(
        options.out / SUMMARY_FILE,
        summary_json(
            options,
            summary,
            question_set=question_set,
            predictions_source=predictions_source,
            statements=len(keyed),
            positions_unused=resolved.positions_unused,
            identity=identity,
            role=role,
            scratch=backend.scratch,
            session_settings=settings,
            measured=measured,
            shuffled=shuffled,
            no_shuffle=no_shuffle,
            data_as_of=data_as_of,
            data_digest=data_digest,
        ),
    )
    return summary


def _clear_previous_run(out: Path) -> None:
    """Everything a previous run wrote here, gone before this one writes anything of its own.

    A reader opens this directory and reads it as one run, so a question directory the run
    before wrote and this one does not, or a summary of a run that is not the one whose
    lines are on screen, is evidence of nothing. The summary goes at the start and not at
    the end, so a run that dies halfway leaves none rather than another run's. The fixture
    cache is keyed by the server and the schema digest and is a speed decision, so it stays,
    and so does anything a reader put here that this tool does not write.

    A write in progress this tool never finished goes too. ``write_json`` writes beside its
    destination and moves the file into place, and removes the partial one if either step
    fails; a process killed between them leaves it behind, named with ``PARTIAL_SUFFIX``. It
    is this tool's own file and is evidence of nothing, so a rerun takes it with the rest.

    Only a directory this tool wrote to is cleared, which is what ``MARKER_FILE`` says. One
    that is empty is taken over and marked, one that holds the marker is cleared and keeps
    it, and one that holds anything else is refused untouched: ``--out`` named a directory
    of the reader's own, and deleting from it would cost them files this tool never wrote.

    Raises ``ToolError`` when the directory holds files no audit wrote, and when something
    cannot be read or removed: the run would otherwise write its evidence beside evidence
    it did not produce.
    """
    try:
        entries = sorted(out.iterdir())
    except OSError as unreadable:
        raise ToolError(f"the output directory {out} cannot be read: {unreadable}") from unreadable
    if entries and not (out / MARKER_FILE).is_file():
        raise ToolError(
            f"the output directory {out} is not empty and holds no {MARKER_FILE}, the file "
            f"an audit leaves in a directory of its own: nothing in it was removed. A run "
            f"writes into a directory that is empty, that is not there yet, or that an "
            f"earlier audit wrote to."
        )
    try:
        (out / SUMMARY_FILE).unlink(missing_ok=True)
        for child in entries:
            if child.is_dir() and QUESTION_DIRECTORY.fullmatch(child.name):
                shutil.rmtree(child)
            elif child.name.startswith(".") and child.name.endswith(PARTIAL_SUFFIX):
                child.unlink(missing_ok=True)
        (out / MARKER_FILE).write_text(MARKER_TEXT, encoding="utf-8")
    except OSError as unwritable:
        raise ToolError(
            f"the output directory {out} cannot be cleared of the run before it: {unwritable}"
        ) from unwritable


def _predictions_source(options: AuditOptions) -> StatementSource | None:
    """The file the predictions were read from, or nothing when the run was given none.

    The digest is taken here, once, after the file has been read: every record of a
    prediction states it, and hashing it per question would state the same thing again.
    """
    if options.predictions is None:
        return None
    return StatementSource(
        path=str(options.predictions),
        digest=file_digest(options.predictions),
        origin=options.predictions_origin,
        date=options.predictions_date,
    )


def _data_digest(options: AuditOptions) -> str:
    """The digest of the file the data was loaded from, or the empty string for no file.

    Taken here, once, for the same reason the predictions file's is: every record states
    it, and a dump is a gigabyte whose sha256 costs seconds a pass. The file is never read
    for anything else; what the data is, is measured on the server.

    Raises ``ToolError`` when it cannot be read: the operator named a file to have it
    stated, and a run that recorded an origin for a file it never hashed would state less
    than it was asked to.
    """
    if options.data_file is None:
        return ""
    try:
        return file_digest(options.data_file)
    except (OSError, ValueError) as unreadable:
        raise ToolError(f"the data file {options.data_file} cannot be read: {unreadable}") from (
            unreadable
        )


def _run_fixture(backend: Backend, tables: Sequence[TableName], options: AuditOptions) -> Measured:
    """The digest of everything the run will read, over the tables it can read.

    A gold that names a table this database does not hold is a defect in the question file,
    which is one of the things this tool exists to find; a gold that names one this login
    was never granted is a defect in the grants. Measuring either would refuse, so the
    tables are asked for first and the measurement covers the ones that exist and can be
    read; the others are named in the summary, each under the word for what it is, and
    error on the lines of the questions that used them.

    Nothing here ends a run except one thing. A backend that will not answer at all leaves the
    run without a digest and with the reason recorded, and every question then fails on its own
    line with the server's message rather than the run stopping with nothing audited. The
    exception is a table the content digest cannot read inside the row budget: the operator
    asked for a digest of every row and there is no such digest to give, no question to attach
    the refusal to, and the default digest over the same tables still exists, so that is a tool
    error before anything has run rather than a line under every question.
    """
    if not tables:
        return Measured(None, (), (), (), "", {})
    try:
        lookup = backend.existing_tables(tables)
    except BackendRefused as refused:
        return Measured(None, tuple(tables), (), (), _refusal(refused), {})
    present = lookup.present
    accounted = set(present) | set(lookup.unreadable)
    missing = tuple(name for name in tables if name not in accounted)
    if not present:
        return Measured(None, (), missing, lookup.unreadable, "", {})
    try:
        digest = fixture_digest(
            backend,
            present,
            directory=options.out,
            with_content_digests=options.with_content_digests,
        )
    except ContentDigestRefused as refused:
        raise ToolError(str(refused)) from refused
    except BackendRefused as refused:
        return Measured(None, present, missing, lookup.unreadable, _refusal(refused), {})
    return Measured(
        digest, present, missing, lookup.unreadable, "", _planner_statistics(backend, present)
    )


def _planner_statistics(
    backend: Backend, tables: Sequence[TableName]
) -> Mapping[TableName, PlannerStatistics]:
    """What the run's plans were chosen from, or nothing where the backend would not say.

    Taken once, beside the fixture, because the summary states one measurement per run and
    not one per question. A refusal leaves the block empty rather than ending the run: the
    statistics say why two runs differ and are never what a run is for.
    """
    try:
        return backend.planner_statistics(tables)
    except BackendRefused:
        return {}


def _refusal(refused: BackendRefused) -> str:
    """One refusal as the one line a summary states it in."""
    return f"{refused.step}: {refused.detail}"


def _drop_shuffle(backend: Backend) -> None:
    """Remove the scratch copies, whether the run made them, failed halfway or made none.

    Asked unconditionally, because what a backend made is the backend's to know: a run
    that prepared nothing drops nothing, and one that was interrupted after copying part
    of the tables still clears what it copied.
    """
    try:
        backend.drop_shuffled_copies()
    except BackendRefused as refused:
        # Nothing left to unwind: the run is over and what is being reported is its
        # result, not the state of a scratch schema a reader can drop by hand. A run whose
        # connection died is where this happens, and it is said on stderr so that the
        # summary the run still writes is not the place a reader learns it.
        print(f"{PROGRAM}: the scratch copies were left behind: {refused}", file=sys.stderr)


def _audit_questions(
    options: AuditOptions,
    backend: Backend,
    writer: Writer,
    phases: Phases,
    *,
    question_set: QuestionSet,
    golds: Sequence[ParsedStatement | StatementRefused],
    questions_source: StatementSource,
    predictions: Mapping[int, Prediction],
    session_settings: SessionSettings,
    run_id: str,
    data_as_of: datetime,
    data_digest: str,
    shuffled: ShuffledCopies | None,
    no_shuffle: str,
) -> Counted:
    """Every question in turn, each one's failure its own."""
    counted = Counted()
    settings = SmellSettings(
        serialization=SERIALIZATION,
        statement_timeout_seconds=options.statement_timeout_seconds,
        shuffle_seed=options.shuffle_seed,
        shuffle_row_limit=options.shuffle_row_limit,
        plan_variant=options.plan_variant,
        experimental_s2=options.experimental_s2,
    )
    for question, gold in zip(question_set.questions, golds, strict=True):
        counted.questions += 1
        try:
            with phases.timed("questions"), sided(SIDE_RUN):
                if isinstance(gold, StatementRefused):
                    # Read before the data was measured and raised here, so that a gold
                    # this audit cannot read is one question's line and not the run's end.
                    raise SideFailed(SIDE_GOLD, gold)
                _audit_one(
                    question,
                    options,
                    backend,
                    writer,
                    counted,
                    question_set=question_set,
                    parsed=gold,
                    questions_source=questions_source,
                    prediction=predictions.get(question.question_id),
                    session_settings=session_settings,
                    run_id=run_id,
                    data_as_of=data_as_of,
                    data_digest=data_digest,
                    shuffled=shuffled,
                    no_shuffle=no_shuffle,
                    settings=settings,
                )
        except SideFailed as failed:
            # Everything a question can fail at runs under a side, and the outermost one
            # is the run: a refusal that named nothing narrower came from around the two
            # statements rather than from either of them.
            refusal = failed.failed
            named = (BackendRefused, ComparisonRefused)
            step = refusal.step if isinstance(refusal, named) else "statement"
            message = " ".join(str(refusal).split())
            if isinstance(refusal, StatementTimedOut):
                counted.timed_out.setdefault(failed.side, []).append(question.question_id)
            counted.errors.append(QuestionError(question.question_id, failed.side, step, message))
            counted.verdicts[ERROR] = counted.verdicts.get(ERROR, 0) + 1
            writer.line(
                question_line(question, "", ERROR, (), None) + f"  {failed.side}: {message}"
            )
    return counted


def _audit_one(
    question: Question,
    options: AuditOptions,
    backend: Backend,
    writer: Writer,
    counted: Counted,
    *,
    question_set: QuestionSet,
    parsed: ParsedStatement,
    questions_source: StatementSource,
    prediction: Prediction | None,
    session_settings: SessionSettings,
    run_id: str,
    data_as_of: datetime,
    data_digest: str,
    shuffled: ShuffledCopies | None,
    no_shuffle: str,
    settings: SmellSettings,
) -> None:
    """One question: the gold, the prediction when there is one, then the smells.

    The gold arrives parsed, because the tables this run measured were read off that same
    parse. The prediction is parsed here, which is the only place that needs it.
    """
    metadata = _question_metadata(question, _question_set_name(question_set, options))
    directory = options.out / f"q{question.question_id}"
    comparison: Comparison | None = None
    if prediction is None:
        with sided(SIDE_GOLD):
            gold = record_statement(
                question=metadata,
                question_set_version=question_set.digest,
                statement_source=questions_source,
                parsed=parsed,
                backend=backend,
                serialization=SERIALIZATION,
                session_settings=session_settings,
                run_id=run_id,
                directory=options.out,
                data_as_of=data_as_of,
                statement_timeout_seconds=options.statement_timeout_seconds,
                with_content_digests=options.with_content_digests,
                source_digest=data_digest,
            ).record
        verdict = GOLD_ONLY
    else:
        with sided(SIDE_PREDICTION):
            if isinstance(prediction.sql, NoStatement):
                # The file named this question and held no statement for it, which is this
                # question's error under the side the file answers for, exactly like a
                # prediction that does not parse.
                raise StatementRefused(
                    f"the predictions file holds {prediction.sql.held} "
                    "and no statement for this question"
                )
            second_parsed = options.engine.parse(prediction.sql)
        comparison = compare_statements(
            question=metadata,
            question_set_version=question_set.digest,
            gold_parsed=parsed,
            gold_source=questions_source,
            second_parsed=second_parsed,
            second_source=prediction.source,
            backend=backend,
            serialization=SERIALIZATION,
            session_settings=session_settings,
            run_id=run_id,
            directory=options.out,
            data_as_of=data_as_of,
            statement_timeout_seconds=options.statement_timeout_seconds,
            with_content_digests=options.with_content_digests,
            source_digest=data_digest,
        )
        gold = comparison.gold
        verdict = comparison.verdict.result.name
        count_credited(counted, comparison)
    found = all_smells(
        parsed,
        backend,
        gold.result,
        settings=settings,
        question=QuestionText(question.question, question.evidence),
        shuffled=shuffled,
        no_shuffle=no_shuffle,
    )
    fired = [smell.name for smell in found if smell.fired]
    counted.verdicts[verdict] = counted.verdicts.get(verdict, 0) + 1
    for name in fired:
        counted.smells[name] = counted.smells.get(name, 0) + 1
    disagreed = verdict in {
        ComparabilityResult.NOT_EQUAL.name,
        ComparabilityResult.NOT_COMPARABLE.name,
    }
    written = disagreed or bool(fired)
    if written:
        _write_question(directory, comparison, gold_record=gold, found=found)
        counted.directories.append(question.question_id)
    writer.line(
        question_line(
            question,
            parsed.replay_rule.value,
            verdict,
            fired,
            f"{options.out.as_posix()}/q{question.question_id}/" if written else None,
        )
    )


def _write_question(
    directory: Path,
    comparison: Comparison | None,
    *,
    gold_record: EvidenceRecord,
    found: Sequence[Smell],
) -> None:
    """The directory a reader opens: the counterexample when there is one, and the smells.

    Without a prediction there is no counterexample to write and the gold's own record is
    what the fired smell is evidence about, so the directory holds that and the smells.
    """
    try:
        if comparison is not None:
            write_comparison(comparison, directory)
        else:
            write_json(directory / GOLD_RECORD_FILE, record_json(gold_record))
        write_json(directory / SMELLS_FILE, smells_json(found))
    except OSError as unwritable:
        # A run that could not write its evidence has failed as a tool, whatever it found
        # about the question: the contract says a tool error is exit 2, and an OSError let
        # out of here was a traceback and exit 1.
        raise ToolError(f"{directory} could not be written: {unwritable}") from unwritable


def audit(options: AuditOptions, backend: Backend, writer: Writer) -> int:
    """One audit's exit status: what it found, or 2 when it could not run at all.

    The status is the whole of what this returns, as ADR-0013 point 2 states: the counts
    are in the summary, and a run that found nothing and a run that could not start are
    told apart here rather than by reading them.
    """
    try:
        return run_audit(options, backend, writer).exit_status
    except ToolError as failed:
        print(f"{PROGRAM}: {failed}", file=sys.stderr)
        return 2


def connect_and_audit(options: AuditOptions, writer: Writer) -> int:
    """Open the engine the options name and audit through it. The exit status is the answer.

    The engine brings both halves: the backend opened here and the parser every statement
    of the run is read by. Nothing below this line asks which engine it is, so a second
    engine is a second entry in the registry and a branch nowhere.
    """
    try:
        read_questions(options.questions, options.ids)
    except ToolError as unusable:
        # Read before anything is opened, and read again by the run for itself. The read
        # needs no backend and the file is where a run is refused most often, so a question
        # file this run cannot use is its own refusal rather than a session opened, a copy of
        # the data made and a scratch schema locked for a run that then refuses. What is
        # carried past this line is nothing: the run reads the file itself, so there is no
        # second reading of it for a caller to have to keep in step with the first.
        print(f"{PROGRAM}: {unusable}", file=sys.stderr)
        return 2
    try:
        backend = options.engine.connect(options.dsn, scratch=options.scratch_schema)
        _say_what_was_copied(backend, options.dsn)
    except BackendRefused as refused:
        print(f"{PROGRAM}: the database could not be reached: {refused}", file=sys.stderr)
        return 2
    try:
        return audit(options, backend, writer)
    finally:
        # Given back rather than left to the process exit. A command survives without this
        # and a caller that is not a command does not: an unclosed backend is a session
        # still open on the server and a file handle still held, and the copies the run
        # made go with it.
        backend.close()


def _say_what_was_copied(backend: Backend, dsn: str) -> None:
    """One line on stderr when the data could only be read through a private copy.

    A copy costs what the data weighs and is made without being asked for, so a run says it
    where a person sees it rather than only in the records it writes. Which backends can
    need one is not asked here: the setting is the interface's, and a backend that read the
    data where it lives states nothing. The record states the fact and this line states the
    disk, which is what a person watching a run needs and what a published record should not
    carry.
    """
    if not backend.session_settings().recorded.get(READ_THROUGH_PRIVATE_COPY, ""):
        return
    source = Path(dsn)
    weight = source.stat().st_size if source.is_file() else 0
    print(
        f"{PROGRAM}: the data could not be read where it is, so this run reads a private "
        f"copy of {dsn} ({weight} bytes) under {tempfile.gettempdir()}, removed when the "
        "run ends",
        file=sys.stderr,
    )


def report(audit_directory: Path, out: Path | None, writer: Writer) -> int:
    """One rendering's exit status: the pages it wrote, or 2 when it could not render.

    The two statuses of ADR-0013 point 2 that a command which audits nothing can have. A
    directory that is not an audit's, a file that is not the JSON its name says and a
    document that does not hold what its format states are each this tool failing to run
    over what it was given, which is 2; anything it rendered is 0, because rendering states
    nothing about what the run found and the run's own status is on the page.
    """
    try:
        writer.line(render_report(audit_directory, out).line)
    except ReportRefused as refused:
        print(f"{PROGRAM}: {refused}", file=sys.stderr)
        return 2
    return 0


def run_demo(out: Path, writer: Writer) -> int:
    """Write the packaged sandbox into that directory, audit it, and say how to rerun it.

    What a person who installed the wheel has and nothing else: the fixture is built from the
    packaged ``fixture.sql``, the questions and the predictions are copied out beside it, and
    the audit that follows is the ordinary one over those three files. It exits 1 here because
    three of the golds disagree with their corrections on this data, which is the finding and
    not a failure of the command.

    The files are written every time, so a second demo into one directory is a clean rerun:
    the sandbox is rebuilt, and the audit's own directory follows the marker rule that governs
    every other run. The command line is built once and used twice, for the run and for the
    last line, so what a reader is told to type is the run whose lines are above it rather than
    a sentence about it, over paths as the command line gave them: a relative ``--out`` stays
    relative and every path on that line is one the reader can type where they are standing.
    The line is printed whatever the audit answered, because it names the run either way.
    """
    try:
        # The built path is resolved and names the same file as the one below; the audit is
        # given the paths the command line was given, and those are what its lines state.
        build_fixture(out)
        questions, predictions = write_inputs(out)
    except OSError as unwritable:
        print(f"{PROGRAM}: the demo cannot be written into {out}: {unwritable}", file=sys.stderr)
        return 2
    arguments = [
        AUDIT,
        "--engine",
        SQLITE.name,
        "--dsn",
        str(out / FIXTURE_FILE),
        "--questions",
        str(questions),
        "--predictions",
        str(predictions),
        "--out",
        str(out / DEMO_AUDIT_DIRECTORY),
    ]
    status = connect_and_audit(parse_arguments(arguments), writer)
    writer.line(f"{RERUN_PREFIX}{PROGRAM} {' '.join(arguments)}")
    return status
