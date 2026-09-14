"""The files a run is pointed at, and what this tool will read out of them.

A question file, a prediction file, and the rules that decide which prediction answers
which question. Every refusal here is a refusal before the run starts: the file is wrong
about a question, and a run over it would be a run over something nobody stated.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from attestql.audit.cli.errors import ToolError
from attestql.audit.fixture import file_digest
from attestql.contract.document import JsonValue
from attestql.evidence.types import (
    StatementSource,
)

NAMED_IN_A_REFUSAL = 20
"""How many of a kind a refusal names before it says how many more there are.

A message is read by a person looking for the one they mistyped, and a file naming five
hundred unknown ids would otherwise print five hundred numbers at them."""

QUESTION_ID_LIMIT = 10**9
"""One past the largest question id this tool audits, because an id is also a name.

Every question's evidence goes in a directory called ``q<id>``, and the rerun that empties
the output directory again finds those directories by the pattern above. Both of those make
an id something narrower than an integer. Below zero the name does not match the pattern, so
a rerun left ``q-1`` standing beside a fresh run, which breaks the one thing the output
directory promises: that it holds this run and no other. Far above, the name stops being one
a filesystem will take, and a three-hundred digit id reached ``mkdir`` and came back as an
``OSError`` traceback and exit 1 where the contract says a tool error is exit 2.

Nine digits is the bound because it is far past every id any published BIRD file holds (the
largest is 1533) and past the six-digit synthetic ids the packaged demo audits, and short
enough that ``q<id>`` is a name every filesystem can hold. What matters is not the number: it
is that an id outside it is refused before the backend opens, by a message naming the entry,
rather than by a traceback in the middle of a run. ``connect_and_audit`` reads the question
file before it connects for that reason."""

BIRD_PREDICTION_SUFFIX = "\t----- bird -----\t"
"""What BIRD's own ``predict_dev.json`` appends to each statement: a tab, a marker and
the database it was written for. The statement is what comes before it."""

JSON_PREDICTIONS = "json"
"""A predictions file that is one JSON object, keyed by question id or by position."""

LINE_PREDICTIONS = "lines"
"""A predictions file that is one statement per line, keyed by the line's position.

Which is how most published prediction files ship. The reading is the shape and nothing
else: the tab suffix BIRD's own files append is taken off here as it is under ``json``,
and an edit only one publisher's file needs, such as a comment cut or a database name
appended to the statement, is prepared outside this tool rather than guessed at inside it.
"""

QUESTION_ID_KEYING = "question-id"
"""A key of the predictions file is the id of the question its prediction answers, which
is what a file written for this tool holds."""

POSITION_KEYING = "position"
"""A key is the position of an entry of the question file in file order, which is what
BIRD's own prediction files hold: its evaluation pairs prediction ``i`` with gold line
``i``, so the file is keyed ``"0"`` to ``"499"`` and carries no question id at all."""


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


def _question(entry: JsonValue, path: Path, index: int) -> Question:
    """One entry as a question, or a refusal naming the field that was not one.

    Every field is read at the type the file states it at rather than converted to the type
    this tool wants. ``int(True)`` is 1 and ``str(None)`` is ``"None"``, so a file holding
    either used to be audited under an identity it never stated, and a record then said that
    identity was what was measured. A field of the wrong type is the file being wrong about
    a question, which is a refusal, and the message names the field so that the person who
    wrote the file can find it.
    """
    if not isinstance(entry, dict):
        raise ToolError(f"{path} entry {index} is {type(entry).__name__} and not an object")
    fields = entry
    where = f"{path} entry {index}"
    return Question(
        question_id=_question_id(fields, where),
        db_id=_required_text(fields, "db_id", where),
        difficulty=_optional_text(fields, "difficulty", where),
        question=_required_text(fields, "question", where),
        evidence=_optional_text(fields, "evidence", where),
        sql=_required_text(fields, "SQL", where),
    )


def _question_id(fields: Mapping[str, object], where: str) -> int:
    """The id of one entry: a whole number this tool can also use as a directory name.

    ``bool`` is excluded explicitly because it is an ``int`` in Python and nowhere else: a
    file stating ``true`` under ``question_id`` was audited as question 1.
    """
    if "question_id" not in fields:
        raise ToolError(f"{where} is not a question: it states no question_id")
    stated = fields["question_id"]
    if not isinstance(stated, int) or isinstance(stated, bool):
        raise ToolError(
            f"{where} states question_id as {type(stated).__name__} and not a whole number; "
            f"an id is the name of the directory this question's evidence goes in"
        )
    if not 0 <= stated < QUESTION_ID_LIMIT:
        raise ToolError(
            f"{where} states question_id {stated}, which is outside 0 to "
            f"{QUESTION_ID_LIMIT - 1}: an id is the name of the directory this question's "
            f"evidence goes in, and a rerun of this output directory finds those directories "
            f"by that name"
        )
    return stated


def _required_text(fields: Mapping[str, object], name: str, where: str) -> str:
    """One field a question cannot be read without, at the type the file states it."""
    if name not in fields:
        raise ToolError(f"{where} is not a question: it states no {name}")
    return _text_field(fields[name], name, where)


def _optional_text(fields: Mapping[str, object], name: str, where: str) -> str:
    """One field a question may leave out, refused when it is there at the wrong type."""
    if name not in fields or fields[name] is None:
        return ""
    return _text_field(fields[name], name, where)


def _text_field(stated: object, name: str, where: str) -> str:
    if not isinstance(stated, str):
        raise ToolError(
            f"{where} states {name} as {type(stated).__name__} and not text; "
            f"nothing this tool records is a value it converted for the file"
        )
    return stated


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


def read_predictions(
    path: Path, *, shape: str = JSON_PREDICTIONS
) -> Mapping[int, str | NoStatement]:
    """The predictions by the number the file keys them under, whatever that number is.

    ``shape`` is which of the two files this is: one JSON object, or one statement per line.

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
    if shape == LINE_PREDICTIONS:
        return _predictions_from_lines(path)
    document = _read_json(path, "the predictions file")
    if not isinstance(document, dict):
        raise ToolError(f"{path} holds {type(document).__name__} and predictions are an object")
    predictions: dict[int, str | NoStatement] = {}
    for key, value in document.items():
        try:
            keyed_under = int(key)
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


def _predictions_from_lines(path: Path) -> Mapping[int, str | NoStatement]:
    """One statement per line, by the position of its line, counting from zero.

    The positions are the ones ``--predictions-keyed-by position`` pairs with, because that
    is what a line's place in a file is: the first line answers the first question of the
    question file. A line that is empty once the BIRD suffix is off is the file saying the
    model produced nothing for that question, as the number ``0`` is under the JSON shape.

    A line ends at a line feed and at nothing else, and the carriage return of a CRLF file
    is taken off the end of the line it terminates. ``str.splitlines`` is not what splits
    them: it also breaks at a form feed, a vertical tab and two Unicode separators, any of
    which inside a statement would push every later line onto the wrong question.

    The newline that ends the last line is not a line of its own and is dropped. Every other
    empty line is kept, at the end of the file as well as between statements: it is the file
    saying the model produced nothing for the question at that position, and a reader that
    dropped it would report that question as one nothing was written for.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as unreadable:
        raise ToolError(f"the predictions file {path} cannot be read: {unreadable}") from unreadable
    except ValueError as undecodable:
        raise ToolError(
            f"the predictions file {path} is not UTF-8 text: {undecodable}"
        ) from undecodable
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    predictions: dict[int, str | NoStatement] = {}
    for position, line in enumerate(lines):
        ended = line[:-1] if line.endswith("\r") else line
        statement = ended.partition(BIRD_PREDICTION_SUFFIX)[0].strip()
        predictions[position] = statement or NoStatement("an empty line")
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

    Raises ``ToolError`` for a position no entry of the question file has, for a key no
    question of the file has under question-id keying, and for a file keyed by question id
    whose keys are exactly the positions of a question file whose ids are not: those two
    readings pair different statements, and guessing between them would be this tool
    comparing golds with predictions written for other questions.
    """
    if keyed_by == QUESTION_ID_KEYING:
        _refuse_positions_read_as_ids(predictions, question_set)
        _refuse_ids_the_question_file_does_not_hold(predictions, question_set)
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


def _refuse_ids_the_question_file_does_not_hold(
    predictions: Mapping[int, str | NoStatement], question_set: QuestionSet
) -> None:
    """Refuse a prediction whose key names no question of the file, under question-id keying.

    Such a prediction was dropped without a word: the question it was written for was audited
    gold-only, and the run's own line and summary said GOLD-ONLY, which is what a question
    with no prediction looks like. One mistyped digit therefore read as an audit of a
    prediction that was never compared with anything.

    Against the whole file and not against what ``--ids`` kept. A run auditing one database
    out of a prediction file written for eleven compares none of the keys for the other ten,
    and each of those keys still names a real question of the file. What is refused is a key
    naming no question at all, which no filter explains.

    Position keying has its own account of what was left over, in ``positions_unused``, and a
    position outside the file is already refused above.
    """
    held = set(question_set.entry_ids)
    unknown = sorted(key for key in predictions if key not in held)
    if not unknown:
        return
    named = ", ".join(str(key) for key in unknown[:NAMED_IN_A_REFUSAL])
    rest = (
        ""
        if len(unknown) <= NAMED_IN_A_REFUSAL
        else f" and {len(unknown) - NAMED_IN_A_REFUSAL} more"
    )
    raise ToolError(
        f"the predictions file names {len(unknown)} ids no question of {question_set.path} "
        f"has: {named}{rest}. Under question-id keying a key is a question id, so each of "
        f"these is a prediction this run would leave out while reporting the question "
        f"it was meant for as having none. A file BIRD's own evaluation wrote is keyed by "
        f"position and needs --predictions-keyed-by position"
    )


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


def _question_entries(raw: JsonValue, path: Path) -> list[JsonValue]:
    """The list of question entries, bare as Mini-Dev ships it or wrapped in an object.

    A wrapped file is ``{"source": ..., "questions": [...]}``: a bare list cannot carry an
    attribution, and a fixture that reproduces a benchmark's questions has to, so the list may
    sit under ``questions`` beside the fields that say where it came from.
    """
    kind = type(raw).__name__
    if isinstance(raw, dict):
        wrapped = raw.get("questions")
        if isinstance(wrapped, list):
            return wrapped
    if isinstance(raw, list):
        return raw
    raise ToolError(
        f"{path} holds {kind} and a question file is a list, "
        "or an object whose 'questions' field is one"
    )


def _read_json(path: Path, what: str) -> JsonValue:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as unreadable:
        raise ToolError(f"{what} {path} cannot be read: {unreadable}") from unreadable
    except ValueError as broken:
        raise ToolError(f"{what} {path} is not JSON: {broken}") from broken
