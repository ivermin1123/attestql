"""What a run says about itself: the lines it prints and the summary it writes.

One line per question while it runs, the counts at the end, and ``summary.json``, whose
format is a public contract (``docs/audit-command.md``). The writer is a protocol so that
a test reads the lines rather than a captured stream.
"""

from __future__ import annotations

import time
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol, TextIO

from attestql.audit.backend import (
    PlannerStatistics,
    ShuffledCopies,
    TableName,
    planner_statistics_json,
)
from attestql.audit.cli.errors import ToolError
from attestql.audit.cli.inputs import Question, QuestionSet
from attestql.audit.cli.parser import SERIALIZATION, AuditOptions
from attestql.audit.compare import (
    MECHANISM_CLASSES,
    MECHANISM_MULTIPLICITY,
    MECHANISM_ORDER,
    MECHANISM_OTHER,
    MECHANISM_TRUNCATION,
    MECHANISM_TYPE,
    SIDE_GOLD,
    SIDE_PREDICTION,
    Comparison,
)
from attestql.audit.fixture import CACHE_FILE
from attestql.audit.smells import (
    SMELL_NAMES,
)
from attestql.evidence.render import Json, write_json
from attestql.evidence.replay import ComparabilityResult
from attestql.evidence.types import (
    FixtureDigest,
    SessionSettings,
    StatementSource,
)

SUMMARY_FILE = "summary.json"

SUMMARY_FORMAT = "attestql/audit/summary/2"
"""What the layout of ``summary.json`` is, for a reader who opens one.

It moves when a key a reader was reading changes meaning or leaves, and not when one is
added, for the reason ``COUNTEREXAMPLE_FORMAT`` states: ``credited_but_not_equal`` gaining
``by_test_suite_ex`` beside ``by_mechanism`` left it where it was, and so did the run
gaining ``timed_out`` beside ``errors``. It reads ``2`` because
what the session reported moved under ``session_settings`` beside the engine that reported
it."""

SMELLS_FILE = "smells.json"

GOLD_ONLY = "GOLD-ONLY"
"""The verdict column of a question that had no prediction to compare the gold with."""

ERROR = "ERROR"
"""The verdict column of a question whose statement could not be run and recorded."""

NO_SMELL = "none"


@dataclass(frozen=True)
class Measured:
    """What the run measured before the questions, and what it could not measure.

    ``missing`` are the names a gold used that this database does not hold and
    ``unreadable`` the ones it holds and this login was never granted; they are the
    summary's ``fixture.missing_tables`` and ``fixture.unreadable_tables`` and the reason
    the questions that use them will error. They are two fields because the first is
    repaired in the question file and the second with a GRANT. ``refused`` is filled when
    the measurement itself was refused, which leaves the run without a digest and every
    question to fail or succeed on its own.

    ``planner_statistics`` is what the plans over the measured tables were chosen from when
    the run started. The shuffle probe reruns a gold and reads the copies with whichever
    plan the planner picks, so two runs that disagree about that probe and agree about
    everything else are told apart by this and by nothing else in the summary.
    """

    digest: FixtureDigest | None
    present: tuple[TableName, ...]
    missing: tuple[TableName, ...]
    unreadable: tuple[TableName, ...]
    refused: str
    planner_statistics: Mapping[TableName, PlannerStatistics]


@dataclass(frozen=True)
class QuestionError:
    """One question this run could not answer, which side of it stopped, and what stopped it.

    ``side`` is the gold, the prediction, or the run around both, and it is the first thing
    the error line states: a benchmark whose golds do not run on this database and one whose
    predictions do not are two different findings, and the message alone tells them apart
    only for a reader who already knows which statement it came from.
    """

    question_id: int
    side: str
    step: str
    message: str


@dataclass(frozen=True)
class Credited:
    """The comparisons BIRD's own evaluator credits and this tool calls NOT_EQUAL.

    ``set(predicted) == set(gold)`` scores those pairs 1 and the typed comparison finds the
    two answers unequal, so this number is the size of the gap between the two readings on
    one run, and ``by_mechanism`` is what the gap is made of. A run given no predictions
    compared nothing and has none of this at all.

    ``by_test_suite_ex`` splits the same comparisons by the other published reading, the
    test-suite evaluator's: ``1`` counts the ones it credits with BIRD and ``0`` the ones it
    refuses with this tool, which is how much of the gap that reading closes on this run.
    The two always add up to ``total``.
    """

    total: int
    by_mechanism: Mapping[str, int]
    by_test_suite_ex: Mapping[str, int]


@dataclass(frozen=True)
class Summary:
    """What a run found, counted. The same numbers the summary line and the file state."""

    run_id: str
    questions: int
    verdicts: Mapping[str, int]
    smells: Mapping[str, int]
    credited_but_not_equal: Credited | None
    errors: tuple[QuestionError, ...]
    question_directories: tuple[int, ...]
    """The questions this run wrote a directory for, in the order they were asked.

    A question gets one when it disagreed, which is a NOT_EQUAL or a NOT_COMPARABLE, or when
    a probe fired over it; a question that agreed with nothing to say about it writes none,
    and neither does one that errored. Stated rather than left to be counted, because the
    number audited does not say which directories a reader should find and a run that lost
    one looked like a run that never wrote it.
    """
    timed_out: Mapping[str, tuple[int, ...]]
    """The questions whose statement ran past the run's bound, by the side it ran on.

    A subset of ``errors``, counted apart because it is a different finding: every other
    error is the database's or the parser's answer about a statement, and this one is the
    budget this run gave itself running out over a statement that was still going. The same
    questions under a longer ``--statement-timeout`` would have been compared.

    ``gold`` and ``prediction`` are always keys, with an empty tuple where nothing timed out,
    because a run that timed nothing out measured that and did not fail to measure it.
    """
    elapsed_seconds: Mapping[str, float]
    exit_status: int

    @property
    def not_equal(self) -> int:
        return self.verdicts.get(ComparabilityResult.NOT_EQUAL.name, 0)

    @property
    def smells_fired(self) -> int:
        return sum(self.smells.values())

    @property
    def timed_out_total(self) -> int:
        return sum(len(found) for found in self.timed_out.values())


class Writer(Protocol):
    """Where the command's lines go. One method, so a test can be one."""

    def line(self, text: str) -> None: ...


class ConsoleWriter:
    """The lines, to a stream, one per call."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def line(self, text: str) -> None:
        print(text, file=self._stream)


@dataclass
class Phases:
    """Wall time per phase of a run, accumulated across the questions."""

    elapsed: dict[str, float] = field(default_factory=dict[str, float])

    @contextmanager
    def timed(self, name: str) -> Generator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.elapsed[name] = self.elapsed.get(name, 0.0) + time.perf_counter() - start

    def rounded(self) -> Mapping[str, float]:
        return {name: round(value, 3) for name, value in sorted(self.elapsed.items())}


def question_line(
    question: Question, rule: str, verdict: str, smells: Sequence[str], directory: str | None
) -> str:
    """One question's line: the id, the database, the rule, the verdict and the smells."""
    fired = ",".join(smells) if smells else NO_SMELL
    line = (
        f"{'q' + str(question.question_id):<5} {question.db_id:<11} "
        f"{rule:<6} {verdict:<10} smells={fired}"
    )
    return f"{line}  {directory}" if directory else line


def summary_line(summary: Summary) -> str:
    """The last line of a run: what was audited, what disagreed, what fired, what timed out.

    The credited count is on the line only where there is something to count it over: a
    gold-only run compared nothing against BIRD's reading, and a zero there would read as
    a measurement rather than as the absence of one.

    The timeouts are on it always, a gold-only run included. A zero there is the opposite
    case: the bound was in force over every statement the run sent, so nothing having
    reached it is something this run measured, and two runs at two bounds are compared by
    reading this clause off both.
    """
    line = (
        f"{summary.questions} questions: {summary.not_equal} NOT_EQUAL, "
        f"{summary.smells_fired} smells fired"
    )
    credited = summary.credited_but_not_equal
    if credited is not None:
        counted = credited.by_mechanism
        line += (
            f", {credited.total} credited by BIRD but NOT_EQUAL "
            f"({counted[MECHANISM_MULTIPLICITY]} multiplicity, {counted[MECHANISM_TYPE]} type, "
            f"{counted[MECHANISM_ORDER]} order, {counted[MECHANISM_TRUNCATION]} truncation, "
            f"{counted[MECHANISM_OTHER]} other)"
        )
    return line + (
        f", {summary.timed_out_total} timed out "
        f"({len(summary.timed_out.get(SIDE_GOLD, ()))} gold, "
        f"{len(summary.timed_out.get(SIDE_PREDICTION, ()))} prediction)"
    )


@dataclass
class Counted:
    """The running counts of one audit, in the order the questions were answered."""

    verdicts: dict[str, int] = field(default_factory=dict[str, int])
    smells: dict[str, int] = field(default_factory=dict[str, int])
    errors: list[QuestionError] = field(default_factory=list[QuestionError])
    timed_out: dict[str, list[int]] = field(default_factory=dict[str, list[int]])
    """The questions the run's bound stopped, by side, in the order they were asked. Kept
    beside ``errors`` rather than read back out of them, because what makes one of them a
    timeout is the type the backend raised and not a phrase in a message an engine wrote."""
    questions: int = 0
    directories: list[int] = field(default_factory=list[int])
    """The questions this run wrote a directory for, in the order they were asked, which is
    what the summary states so that a reader of the directory knows which of them to expect."""
    credited: int = 0
    credited_by_mechanism: dict[str, int] = field(default_factory=dict[str, int])
    credited_and_test_suite_ex: int = 0
    """How many of the credited comparisons the test-suite reading credits too. The rest of
    them are the ones it refuses, which is why one number carries both."""


def count_credited(counted: Counted, comparison: Comparison) -> None:
    """One comparison BIRD's own evaluator credits and this tool calls NOT_EQUAL, by mechanism.

    Counted here because this is where every reading of one pair of results exists at once.
    A comparison carries a mechanism when and only when it is a NOT_EQUAL, so the two
    conditions the count is over are the two tests below, and the test-suite reading of the
    same pair is added up beside them rather than read off the files afterwards.
    """
    found = comparison.mechanism
    if found is None or comparison.bird_ex.value != 1:
        return
    counted.credited += 1
    counted.credited_by_mechanism[found.classification] = (
        counted.credited_by_mechanism.get(found.classification, 0) + 1
    )
    counted.credited_and_test_suite_ex += comparison.test_suite_ex.value


def write_summary(path: Path, document: Json) -> None:
    """The summary, written where a write that fails is this tool failing rather than a
    traceback: the same refusal and the same exit status as every other one."""
    try:
        write_json(path, document)
    except OSError as unwritable:
        raise ToolError(f"{path} could not be written: {unwritable}") from unwritable


def summarise(
    options: AuditOptions, counted: Counted, *, run_id: str, elapsed: Mapping[str, float]
) -> Summary:
    """The counts as one value, with the exit status ADR-0013 point 2 states.

    A question that errored moves nothing here: it is neither a disagreement nor this tool
    failing, and the summary is where a reader counts them. A run whose every question
    errored is the one case that is 2, because it audited nothing at all, and that is what
    2 means; a run with no questions to audit asked nothing and is not that case.
    """
    smells = {name: counted.smells.get(name, 0) for name in SMELL_NAMES}
    fired = sum(smells.values())
    not_equal = counted.verdicts.get(ComparabilityResult.NOT_EQUAL.name, 0)
    errored = counted.verdicts.get(ERROR, 0)
    if counted.questions and errored == counted.questions:
        status = 2
    else:
        status = 1 if not_equal or (options.fail_on_smell and fired) else 0
    return Summary(
        run_id=run_id,
        questions=counted.questions,
        verdicts=dict(counted.verdicts),
        smells=smells,
        credited_but_not_equal=(
            None
            if options.predictions is None
            else Credited(
                total=counted.credited,
                by_mechanism={
                    name: counted.credited_by_mechanism.get(name, 0) for name in MECHANISM_CLASSES
                },
                by_test_suite_ex={
                    "1": counted.credited_and_test_suite_ex,
                    "0": counted.credited - counted.credited_and_test_suite_ex,
                },
            )
        ),
        errors=tuple(counted.errors),
        question_directories=tuple(counted.directories),
        timed_out=_timed_out(counted),
        elapsed_seconds=elapsed,
        exit_status=status,
    )


def _timed_out(counted: Counted) -> Mapping[str, tuple[int, ...]]:
    """The questions the bound stopped, by side, with both statements' sides always named.

    A run that stopped nothing states two empty lists rather than an empty block, because a
    reader of one summary has to be able to tell a run whose golds all finished from a run
    that never counted. A side neither statement is, which is the measurement around the
    two, is named only when something there did reach the bound.
    """
    sides = dict.fromkeys((SIDE_GOLD, SIDE_PREDICTION, *counted.timed_out))
    return {side: tuple(counted.timed_out.get(side, ())) for side in sides}


def summary_json(
    options: AuditOptions,
    summary: Summary,
    *,
    question_set: QuestionSet,
    predictions_source: StatementSource | None,
    statements: int,
    positions_unused: tuple[int, ...],
    identity: str,
    role: str,
    scratch: str,
    session_settings: SessionSettings,
    measured: Measured,
    shuffled: ShuffledCopies | None,
    no_shuffle: str,
    data_as_of: datetime,
    data_digest: str,
) -> Json:
    """The whole run in one document: what was audited, on what, and what was found.

    The ``out`` it states is this run's directory and holds this run's evidence: the
    question directories and the summary of the run before it were removed before this
    one wrote anything.

    ``session_settings`` names the engine and holds the session as it was found, which
    blocks nothing. The two memory settings are under ``settings`` beside the serialization
    instead, because they are what this run held every statement to rather than what it
    found: a reader comparing two summaries reads them where the rest of this run's own
    choices are.
    """
    digest = measured.digest
    return {
        "format": SUMMARY_FORMAT,
        "run_id": summary.run_id,
        "backend_identity": identity,
        "effective_database_role": role,
        "session_settings": {
            "engine": session_settings.engine,
            "recorded": dict(session_settings.recorded),
        },
        "parser": options.engine.parser.json(),
        "question_set": {
            "path": str(question_set.path),
            "digest": question_set.digest,
            "origin": options.questions_origin,
            "date": options.questions_date,
            "entries": question_set.entries,
            "audited": summary.questions,
            "duplicate_ids": list(question_set.duplicate_ids),
            "ids": list(options.ids),
        },
        "predictions": (
            None
            if predictions_source is None
            else {
                "path": predictions_source.path,
                "digest": predictions_source.digest,
                "origin": predictions_source.origin,
                "date": predictions_source.date,
                "keyed_by": options.predictions_keyed_by,
                "format": options.predictions_format,
                "statements": statements,
                "positions_unused": list(positions_unused),
            }
        ),
        "verdicts": dict(summary.verdicts),
        "smells": dict(summary.smells),
        "smells_fired": summary.smells_fired,
        "credited_but_not_equal": (
            None
            if summary.credited_but_not_equal is None
            else {
                "total": summary.credited_but_not_equal.total,
                "by_mechanism": dict(summary.credited_but_not_equal.by_mechanism),
                "by_test_suite_ex": dict(summary.credited_but_not_equal.by_test_suite_ex),
            }
        ),
        "fixture": {
            "depth": options.fixture_digest,
            "cache": f"{options.out.as_posix()}/{CACHE_FILE}",
            "source": (
                None
                if options.data_file is None
                else {
                    "path": str(options.data_file),
                    "digest": data_digest,
                    "origin": options.data_origin,
                    "date": options.data_date,
                }
            ),
            "schema_digest": None if digest is None else digest.schema_digest,
            "row_counts": {} if digest is None else dict(digest.row_counts),
            "content_digests": {} if digest is None else dict(digest.content_digests),
            "measured_tables": [name.text for name in measured.present],
            "missing_tables": [name.text for name in measured.missing],
            "unreadable_tables": [name.text for name in measured.unreadable],
            "refused": measured.refused,
        },
        "planner_statistics": planner_statistics_json(measured.planner_statistics),
        "shuffle": {
            "seed": options.shuffle_seed,
            "row_limit": options.shuffle_row_limit,
            "scratch_schema": scratch,
            "prepared": shuffled is not None,
            "reason": no_shuffle,
            "copied": [] if shuffled is None else [name.text for name in shuffled.copied],
            "skipped": (
                {}
                if shuffled is None
                else {name.text: rows for name, rows in shuffled.skipped.items()}
            ),
            "not_reached_by_a_copy": (
                {}
                if shuffled is None
                else {name.text: reason for name, reason in shuffled.unreachable.items()}
            ),
        },
        "settings": {
            "statement_timeout_seconds": options.statement_timeout_seconds,
            "fail_on_smell": options.fail_on_smell,
            "experimental_s2": options.experimental_s2,
            "plan_variant": options.plan_variant,
            "out": options.out.as_posix(),
            "serialization": SERIALIZATION.version,
            "work_mem": session_settings.work_mem,
            "hash_mem_multiplier": session_settings.hash_mem_multiplier,
        },
        "data_as_of": data_as_of.isoformat(),
        "data_as_of_source": (
            "the instant the run started" if options.data_as_of is None else "--data-as-of"
        ),
        "elapsed_seconds": dict(summary.elapsed_seconds),
        "question_directories": list(summary.question_directories),
        "errors": [
            {
                "question_id": error.question_id,
                "side": error.side,
                "step": error.step,
                "message": error.message,
            }
            for error in summary.errors
        ],
        "timed_out": {side: list(found) for side, found in summary.timed_out.items()},
        "exit_status": summary.exit_status,
    }
