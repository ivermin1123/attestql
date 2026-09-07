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
them is refused rather than guessed at. Where each file came from is recorded and never
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

**Nothing aborts a run except the tool failing to start.** Failing to start is reading the
question file, reading the predictions file, making the output directory and clearing the
run before it out of it, and asking the backend what it is; nothing after that. A gold that
does not parse, a statement that times out, a table this database does not hold, a value
with no rendering, a server that went away between two questions: each is that question's
``ERROR`` line with the message, an entry in the summary's ``errors``, and the run goes on
to the next question and still writes ``summary.json``.

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

import argparse
import importlib.metadata
import json
import re
import shutil
import sys
import time
import uuid
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TextIO, cast

from attestql.audit.backend import (
    Backend,
    BackendRefused,
    PlannerStatistics,
    ShuffledCopies,
    StatementTimedOut,
    TableName,
    planner_statistics_json,
)
from attestql.audit.compare import (
    DEFAULT_STATEMENT_TIMEOUT_SECONDS,
    GOLD_RECORD_FILE,
    MECHANISM_CLASSES,
    MECHANISM_MULTIPLICITY,
    MECHANISM_ORDER,
    MECHANISM_TRUNCATION,
    MECHANISM_TYPE,
    SIDE_GOLD,
    SIDE_PREDICTION,
    SIDE_RUN,
    Comparison,
    SideFailed,
    compare_statements,
    record_statement,
    sided,
    write_comparison,
)
from attestql.audit.engines import DEFAULT_ENGINE, ENGINES, SQLITE, Engine, Parse, engine_named
from attestql.audit.fixture import CACHE_FILE, file_digest, fixture_digest
from attestql.audit.parse import ParsedStatement, StatementRefused
from attestql.audit.postgres import DEFAULT_SCRATCH_SCHEMA
from attestql.audit.smells import (
    DEFAULT_SHUFFLE_ROW_LIMIT,
    DEFAULT_SHUFFLE_SEED,
    SMELL_NAMES,
    QuestionText,
    Smell,
    SmellSettings,
    all_smells,
    smells_json,
)
from attestql.demo import FIXTURE_FILE, build_fixture, write_inputs
from attestql.evidence.record import EvidenceRecord
from attestql.evidence.render import Json, record_json, write_json
from attestql.evidence.replay import ComparabilityResult
from attestql.evidence.serialize import SerializationDescriptor
from attestql.evidence.types import (
    FixtureDigest,
    QuestionMetadata,
    SessionSettings,
    StatementSource,
)

PROGRAM = "attestql"

AUDIT = "audit"
"""The subcommand that audits a question file against a database."""

DEMO = "demo"
"""The subcommand that writes the packaged sandbox somewhere and audits that.

Named beside the audit rather than under it because it takes none of the audit's options: it
builds the run it then makes, and what it is for is a person who installed the wheel and has
no question file, no prediction file and no database to point the audit at."""

DEMO_AUDIT_DIRECTORY = "audit"
"""Where the demo's audit writes, under the directory the demo was given: the sandbox it
built is beside it, so one directory holds the run and everything the run read."""

RERUN_PREFIX = "rerun: "
"""What the demo's last line starts with, before the audit command it just ran."""

SUMMARY_FILE = "summary.json"
MARKER_FILE = ".attestql-run"
"""What says an output directory is an audit's own and may be cleared by the next run."""
MARKER_TEXT = (
    "written by attestql audit: every rerun into this directory removes summary.json "
    "and the q<id>/ directories\n"
)
"""The one line the marker holds, so a reader who opens it learns why it is there."""
QUESTION_DIRECTORY = re.compile(r"q\d+")
"""The name of a directory this tool writes a question's evidence to."""
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

SERIALIZATION = SerializationDescriptor(
    version="attestql/audit/2",
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
layout and with nothing else (ADR-0014). It reads ``2`` since the session settings a
record states gained the engine and a column's type became its declared type; the
rendering rules below, and the bytes the serializer makes of them, did not change."""

BIRD_PREDICTION_SUFFIX = "\t----- bird -----\t"
"""What BIRD's own ``predict_dev.json`` appends to each statement: a tab, a marker and
the database it was written for. The statement is what comes before it."""

QUESTION_ID_KEYING = "question-id"
"""A key of the predictions file is the id of the question its prediction answers, which
is what a file written for this tool holds."""

POSITION_KEYING = "position"
"""A key is the position of an entry of the question file in file order, which is what
BIRD's own prediction files hold: its evaluation pairs prediction ``i`` with gold line
``i``, so the file is keyed ``"0"`` to ``"499"`` and carries no question id at all."""


class ToolError(Exception):
    """This tool could not run at all, which is exit status 2 and not a finding."""


@dataclass(frozen=True)
class Question:
    """One row of the question file, as the file states it."""

    question_id: int
    db_id: str
    difficulty: str
    question: str
    evidence: str
    sql: str


@dataclass(frozen=True)
class QuestionSet:
    """The questions a run will audit, and what the file they came from held.

    ``entry_ids`` is the id of every entry in file order, duplicates included, so that a
    position in the file is one lookup away from the question it names.
    """

    questions: tuple[Question, ...]
    entries: int
    entry_ids: tuple[int, ...]
    duplicate_ids: tuple[int, ...]
    digest: str
    path: Path


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


@dataclass(frozen=True)
class _Measured:
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


def read_questions(path: Path, ids: Sequence[int] = ()) -> QuestionSet:
    """Every question of the file, deduplicated by id, filtered to ``ids`` when given.

    A duplicated id whose entry is identical is one question and is kept once: BIRD's own
    Mini-Dev file holds 500 entries with 498 distinct ids that way. A duplicated id whose
    entries differ is two questions with one name, which no run can answer, so the ids
    are named and the run does not start.
    """
    entries = _question_entries(_read_json(path, "the question file"), path)
    kept: dict[int, Question] = {}
    entry_ids: list[int] = []
    duplicates: list[int] = []
    conflicting: list[int] = []
    for index, entry in enumerate(entries):
        question = _question(entry, path, index)
        entry_ids.append(question.question_id)
        seen = kept.get(question.question_id)
        if seen is None:
            kept[question.question_id] = question
            continue
        duplicates.append(question.question_id)
        if seen != question:
            conflicting.append(question.question_id)
    if conflicting:
        raise ToolError(
            f"{path} states different questions under the same ids "
            f"{sorted(set(conflicting))}; no run can answer both"
        )
    wanted = tuple(kept[found] for found in ids if found in kept) if ids else tuple(kept.values())
    missing = [found for found in ids if found not in kept]
    if missing:
        raise ToolError(f"{path} holds no question with the ids {missing}")
    return QuestionSet(
        questions=wanted,
        entries=len(entries),
        entry_ids=tuple(entry_ids),
        duplicate_ids=tuple(sorted(set(duplicates))),
        digest=file_digest(path),
        path=path,
    )


def _question(entry: object, path: Path, index: int) -> Question:
    """One entry as a question, or a refusal naming the entry that was not one."""
    if not isinstance(entry, dict):
        raise ToolError(f"{path} entry {index} is {type(entry).__name__} and not an object")
    fields = cast("dict[str, Any]", entry)
    try:
        return Question(
            question_id=int(fields["question_id"]),
            db_id=str(fields["db_id"]),
            difficulty=str(fields.get("difficulty", "")),
            question=str(fields["question"]),
            evidence=str(fields.get("evidence", "")),
            sql=str(fields["SQL"]),
        )
    except (KeyError, TypeError, ValueError) as incomplete:
        raise ToolError(f"{path} entry {index} is not a question: {incomplete}") from incomplete


@dataclass(frozen=True)
class NoStatement:
    """An entry of a predictions file that holds no statement, and what it holds instead.

    BIRD dev's own ``predict_dev.json`` writes the number ``0`` where the model it was
    generated from produced nothing for a question, and an empty string is the other shape of
    the same thing. Neither is a defect in the file and neither is SQL: it is one question the
    model did not answer, so it is that question's error line rather than a refusal of the
    whole file, which would leave every question the file did answer unaudited.

    ``held`` is what the file has there, in words, because the error line names it: a file
    full of zeroes and a file full of empty strings are two different things to go and look
    at, and a message that spelled them the same way sent a reader to neither.

    A question the file does not name at all is not this. Nothing was predicted for it, and it
    is audited gold-only the way every question is in a run given no predictions file.
    """

    held: str


def read_predictions(path: Path) -> Mapping[int, str | NoStatement]:
    """The predictions by the number the file keys them under, whatever that number is.

    A key is a whole number written as a string or as a number. Which question it names is
    ``resolve_predictions``'s answer and not this one's: reading the file and pairing its
    predictions with questions are two steps, so a run refuses a pairing it cannot make
    before it has run anything. A value is the statement, and BIRD's own
    ``predict_dev.json`` appends a tab, a marker and the database name to it, which is
    stripped here so that one file works in both forms.

    The number ``0`` and a value that is empty once that suffix is off are the two ways that
    same file says the model produced nothing for a question, and they are read as
    ``NoStatement`` rather than refused: the file is a run of a model over a benchmark, and a
    run that stopped at the first question the model skipped would audit none of the rest.
    Every other value that is not a string is still refused, because it is a file this tool
    has no reading for at all.

    Raises ``ToolError`` for a file that is not an object, a key that is no whole number and a
    value of any other type: each is the file itself being something else, which is a run that
    cannot start rather than one question that cannot be answered.
    """
    document = _read_json(path, "the predictions file")
    if not isinstance(document, dict):
        raise ToolError(f"{path} holds {type(document).__name__} and predictions are an object")
    predictions: dict[int, str | NoStatement] = {}
    for key, value in cast("dict[object, object]", document).items():
        try:
            keyed_under = int(cast("int | str", key))
        except (TypeError, ValueError) as unreadable:
            raise ToolError(
                f"{path} has the key {key!r}, which is neither a question id nor a position"
            ) from unreadable
        if _is_the_number_zero(value):
            predictions[keyed_under] = NoStatement("the number 0")
            continue
        if not isinstance(value, str):
            raise ToolError(f"{path}[{key}] is {type(value).__name__} and a prediction is SQL")
        statement = value.partition(BIRD_PREDICTION_SUFFIX)[0].strip()
        predictions[keyed_under] = statement or NoStatement("an empty string")
    return predictions


def _is_the_number_zero(value: object) -> bool:
    """Whether the file wrote the JSON number ``0`` there and not something that resembles it.

    A boolean is not it. Python counts one as a whole number and ``False == 0``, so a file
    that wrote ``false`` there wrote a value this tool has no reading for, and it is refused
    with every other value that is not SQL rather than read as a prediction nobody made.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


@dataclass(frozen=True)
class Prediction:
    """One prediction: the statement to compare a gold with, and where its text came from.

    ``sql`` is what the file held for this question, which is a statement or the record that
    it held none: what makes a question with no prediction different from a question the file
    named and left empty is that this one is the file's answer, and a reader is told so on
    that question's line."""

    sql: str | NoStatement
    source: StatementSource


@dataclass(frozen=True)
class ResolvedPredictions:
    """The predictions a run will compare, by question id, and what was left over.

    ``positions_unused`` is empty under question-id keying. Under position keying it names
    every position that lost to a lower one naming the same question: the question file
    holds one entry twice, the lowest position is the prediction that is compared, and the
    rest are recorded here rather than silently dropped. A position whose question was
    left out by ``--ids`` is not listed; it was not compared, but nothing displaced it.
    """

    by_id: Mapping[int, str | NoStatement]
    positions_unused: tuple[int, ...]


def resolve_predictions(
    predictions: Mapping[int, str | NoStatement], question_set: QuestionSet, keyed_by: str
) -> ResolvedPredictions:
    """The predictions by question id, from a file keyed by question id or by position.

    Under ``position`` a key is the index of an entry of the question file in file order,
    which is what BIRD's own evaluation writes: its ``package_sqls`` pairs prediction ``i``
    with gold line ``i``, so the file holds ``"0"`` to ``"499"`` and no question id at all.

    Raises ``ToolError`` for a position no entry of the question file has, and for a file
    keyed by question id whose keys are exactly the positions of a question file whose ids
    are not: those two readings pair different statements, and guessing between them would
    be this tool comparing golds with predictions written for other questions.
    """
    if keyed_by == QUESTION_ID_KEYING:
        _refuse_positions_read_as_ids(predictions, question_set)
        return ResolvedPredictions(by_id=dict(predictions), positions_unused=())
    by_id: dict[int, str | NoStatement] = {}
    unused: list[int] = []
    for position in sorted(predictions):
        if not 0 <= position < question_set.entries:
            raise ToolError(
                f"the predictions file is keyed by position and has the key {position}, "
                f"which is no entry of {question_set.path}: it holds {question_set.entries} "
                f"entries, so a position is 0 to {question_set.entries - 1}"
            )
        question_id = question_set.entry_ids[position]
        if question_id in by_id:
            unused.append(position)
            continue
        by_id[question_id] = predictions[position]
    return ResolvedPredictions(by_id=by_id, positions_unused=tuple(unused))


def _refuse_positions_read_as_ids(
    predictions: Mapping[int, str | NoStatement], question_set: QuestionSet
) -> None:
    """Refuse a file whose keys are the positions of a question file that is not keyed by
    them, which is what BIRD's own prediction files are and what reading them as question
    ids would quietly compare the wrong pairs."""
    positions = tuple(range(question_set.entries))
    if set(predictions) != set(positions) or question_set.entry_ids == positions:
        return
    raise ToolError(
        f"the predictions file is keyed 0 to {question_set.entries - 1}, which are the "
        f"positions of the {question_set.entries} entries of {question_set.path} and not "
        "its question ids; a prediction file BIRD's own evaluation wrote is keyed by "
        "position and needs --predictions-keyed-by position"
    )


def _question_entries(raw: object, path: Path) -> list[object]:
    """The list of question entries, bare as Mini-Dev ships it or wrapped in an object.

    A wrapped file is ``{"source": ..., "questions": [...]}``: a bare list cannot carry an
    attribution, and a fixture that reproduces a benchmark's questions has to, so the list may
    sit under ``questions`` beside the fields that say where it came from.
    """
    kind = type(raw).__name__
    if isinstance(raw, dict):
        wrapped = cast("dict[str, object]", raw).get("questions")
        if isinstance(wrapped, list):
            return cast("list[object]", wrapped)
    if isinstance(raw, list):
        return cast("list[object]", raw)
    raise ToolError(
        f"{path} holds {kind} and a question file is a list, "
        "or an object whose 'questions' field is one"
    )


def _read_json(path: Path, what: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as unreadable:
        raise ToolError(f"{what} {path} cannot be read: {unreadable}") from unreadable
    except ValueError as broken:
        raise ToolError(f"{what} {path} is not JSON: {broken}") from broken


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


def _line(
    question: Question, rule: str, verdict: str, smells: Sequence[str], directory: str | None
) -> str:
    """One question's line: the id, the database, the rule, the verdict and the smells."""
    fired = ",".join(smells) if smells else NO_SMELL
    line = (
        f"{'q' + str(question.question_id):<5} {question.db_id:<11} "
        f"{rule:<6} {verdict:<10} smells={fired}"
    )
    return f"{line}  {directory}" if directory else line


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
        read_predictions(options.predictions) if options.predictions else {}
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
    summary = _summarise(options, counted, run_id=run_id, elapsed=phases.rounded())
    writer.line(_summary_line(summary))
    write_json(
        options.out / SUMMARY_FILE,
        _summary_json(
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


def _summary_line(summary: Summary) -> str:
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
            f"{counted[MECHANISM_ORDER]} order, {counted[MECHANISM_TRUNCATION]} truncation)"
        )
    return line + (
        f", {summary.timed_out_total} timed out "
        f"({len(summary.timed_out.get(SIDE_GOLD, ()))} gold, "
        f"{len(summary.timed_out.get(SIDE_PREDICTION, ()))} prediction)"
    )


def _clear_previous_run(out: Path) -> None:
    """Everything a previous run wrote here, gone before this one writes anything of its own.

    A reader opens this directory and reads it as one run, so a question directory the run
    before wrote and this one does not, or a summary of a run that is not the one whose
    lines are on screen, is evidence of nothing. The summary goes at the start and not at
    the end, so a run that dies halfway leaves none rather than another run's. The fixture
    cache is keyed by the server and the schema digest and is a speed decision, so it stays,
    and so does anything a reader put here that this tool does not write.

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


def _run_fixture(backend: Backend, tables: Sequence[TableName], options: AuditOptions) -> _Measured:
    """The digest of everything the run will read, over the tables it can read.

    A gold that names a table this database does not hold is a defect in the question file,
    which is one of the things this tool exists to find; a gold that names one this login
    was never granted is a defect in the grants. Measuring either would refuse, so the
    tables are asked for first and the measurement covers the ones that exist and can be
    read; the others are named in the summary, each under the word for what it is, and
    error on the lines of the questions that used them.

    Nothing here ends a run. A backend that will not answer at all leaves the run without a
    digest and with the reason recorded, and every question then fails on its own line with
    the server's message rather than the run stopping with nothing audited.
    """
    if not tables:
        return _Measured(None, (), (), (), "", {})
    try:
        lookup = backend.existing_tables(tables)
    except BackendRefused as refused:
        return _Measured(None, tuple(tables), (), (), _refusal(refused), {})
    present = lookup.present
    accounted = set(present) | set(lookup.unreadable)
    missing = tuple(name for name in tables if name not in accounted)
    if not present:
        return _Measured(None, (), missing, lookup.unreadable, "", {})
    try:
        digest = fixture_digest(
            backend,
            present,
            directory=options.out,
            with_content_digests=options.with_content_digests,
        )
    except BackendRefused as refused:
        return _Measured(None, present, missing, lookup.unreadable, _refusal(refused), {})
    return _Measured(
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


@dataclass
class _Counted:
    """The running counts of one audit, in the order the questions were answered."""

    verdicts: dict[str, int] = field(default_factory=dict[str, int])
    smells: dict[str, int] = field(default_factory=dict[str, int])
    errors: list[QuestionError] = field(default_factory=list[QuestionError])
    timed_out: dict[str, list[int]] = field(default_factory=dict[str, list[int]])
    """The questions the run's bound stopped, by side, in the order they were asked. Kept
    beside ``errors`` rather than read back out of them, because what makes one of them a
    timeout is the type the backend raised and not a phrase in a message an engine wrote."""
    questions: int = 0
    credited: int = 0
    credited_by_mechanism: dict[str, int] = field(default_factory=dict[str, int])
    credited_and_test_suite_ex: int = 0
    """How many of the credited comparisons the test-suite reading credits too. The rest of
    them are the ones it refuses, which is why one number carries both."""


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
) -> _Counted:
    """Every question in turn, each one's failure its own."""
    counted = _Counted()
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
            step = refusal.step if isinstance(refusal, BackendRefused) else "statement"
            message = " ".join(str(refusal).split())
            if isinstance(refusal, StatementTimedOut):
                counted.timed_out.setdefault(failed.side, []).append(question.question_id)
            counted.errors.append(QuestionError(question.question_id, failed.side, step, message))
            counted.verdicts[ERROR] = counted.verdicts.get(ERROR, 0) + 1
            writer.line(_line(question, "", ERROR, (), None) + f"  {failed.side}: {message}")
    return counted


def _audit_one(
    question: Question,
    options: AuditOptions,
    backend: Backend,
    writer: Writer,
    counted: _Counted,
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
        _count_credited(counted, comparison)
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
    writer.line(
        _line(
            question,
            parsed.replay_rule.value,
            verdict,
            fired,
            f"{options.out.as_posix()}/q{question.question_id}/" if written else None,
        )
    )


def _count_credited(counted: _Counted, comparison: Comparison) -> None:
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
    if comparison is not None:
        write_comparison(comparison, directory)
    else:
        write_json(directory / GOLD_RECORD_FILE, record_json(gold_record))
    write_json(directory / SMELLS_FILE, smells_json(found))


def _summarise(
    options: AuditOptions, counted: _Counted, *, run_id: str, elapsed: Mapping[str, float]
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
        timed_out=_timed_out(counted),
        elapsed_seconds=elapsed,
        exit_status=status,
    )


def _timed_out(counted: _Counted) -> Mapping[str, tuple[int, ...]]:
    """The questions the bound stopped, by side, with both statements' sides always named.

    A run that stopped nothing states two empty lists rather than an empty block, because a
    reader of one summary has to be able to tell a run whose golds all finished from a run
    that never counted. A side neither statement is, which is the measurement around the
    two, is named only when something there did reach the bound.
    """
    sides = dict.fromkeys((SIDE_GOLD, SIDE_PREDICTION, *counted.timed_out))
    return {side: tuple(counted.timed_out.get(side, ())) for side in sides}


def _summary_json(
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
    measured: _Measured,
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
            "PostgreSQL database; report where they disagree and which golds smell wrong."
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
        default=QUESTION_ID_KEYING,
        help=(
            "what a key of the predictions file is: a question id, or the position of an entry "
            "in the question file, which is what BIRD's own predict_*.json files hold"
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
    return AuditOptions(
        dsn=dsn,
        questions=cast("Path", parsed.questions),
        questions_origin=cast("str | None", parsed.questions_origin),
        questions_date=cast("str | None", parsed.questions_date),
        predictions=cast("Path | None", parsed.predictions),
        predictions_origin=cast("str | None", parsed.predictions_origin),
        predictions_date=cast("str | None", parsed.predictions_date),
        predictions_keyed_by=cast("str", parsed.predictions_keyed_by),
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
        backend = options.engine.connect(options.dsn, scratch=options.scratch_schema)
    except BackendRefused as refused:
        print(f"{PROGRAM}: the database could not be reached: {refused}", file=sys.stderr)
        return 2
    return audit(options, backend, writer)


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
    return connect_and_audit(parse_arguments(argv), writer)


__all__ = [
    "AUDIT",
    "DEMO",
    "DEMO_AUDIT_DIRECTORY",
    "ERROR",
    "GOLD_ONLY",
    "MARKER_FILE",
    "MARKER_TEXT",
    "POSITION_KEYING",
    "PROGRAM",
    "QUESTION_ID_KEYING",
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
    "resolve_predictions",
    "run_audit",
    "run_demo",
]
