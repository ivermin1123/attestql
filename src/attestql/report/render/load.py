"""Reading an audit directory, and reconciling what it holds against what it states.

Every document a report reads was written by a run, possibly by an older release of this tool
and possibly on another machine, so every one of them is read at the type its format states
and refused by name when it is not that. The reconciliation is here too: a run states how many
question directories it wrote and this is what holds the directory to it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from attestql.contract.counts import whole_count
from attestql.contract.document import JsonObject, JsonValue, an_array, an_object
from attestql.evidence.load import UnreadableRecord
from attestql.report.render.errors import ReportRefused
from attestql.report.render.models import NOT_EQUAL, Fact, HandReading, Published

SUMMARY_FILE = "summary.json"
QUESTIONS_FILE = "questions.json"
CLASSIFICATION_FILE = "classification.json"
CLASSIFICATION_SOURCE_FILE = "classification-source.json"
PUBLISHED_FILE = "published.json"
"""Three files a directory `attestql audit` wrote does not hold, which a publisher may put
beside its summary and which a page states when they are there.

`questions.json` names the database each question is about, which reaches no file the audit
writes; the two classification files are a maintainer's own reading of some of the questions,
kept apart from every verdict on the page; `published.json` is where the whole run was
uploaded. A directory without them renders exactly as it does today."""

COUNTEREXAMPLE_FILE = "counterexample.json"
GOLD_RECORD_FILE = "evidence-gold.json"
SECOND_RECORD_FILE = "evidence-second.json"
SMELLS_FILE = "smells.json"
"""The names of the files an audit directory holds.

Stated here rather than imported from the audit: this command reads a directory, which is
a layout, and the layout is what it is whoever wrote it. Importing the writer's constants
would put the audit's whole import graph -- both drivers and both parsers -- behind a
renderer that has to run where no engine is."""

QUESTION_DIRECTORY = re.compile(r"^q(\d+)$")
"""What a question's directory is called, and where its id is in the name."""

NAMED_IN_A_REFUSAL = 20
"""How many question ids a refusal names before it counts the rest instead.

A run of a thousand questions that lost its directories would otherwise put a thousand ids in
one line on a terminal. Spelled here rather than imported from the command: a report is read
without the auditing side of the package, and two layers that happen to name the same number
are not one decision."""

ASSET_SCHEME = "https://"
"""What the address in ``published.json`` has to begin with. It reaches an ``href`` on the run
page, where a ``javascript:`` value would run on a reader's click; autoescaping puts the text
safely inside the attribute and says nothing at all about what the scheme does."""


def refuse_a_gap_nothing_explains(
    audit_directory: Path,
    summary: JsonObject,
    directories: Sequence[Path],
    published: Published | None,
) -> None:
    """Every question directory the run says it wrote, found here; and none it never wrote.

    The rows of the index come from the question directories, and until 2026-09-13 nothing
    compared them with the run. An audit that lost a directory rendered a report that looks
    whole: it states the run's real total at the top and is simply missing the question, with
    no page saying so anywhere. Removing ``q879`` from the demo rendered five questions under
    a total of six.

    What the run wrote is the list the summary names and never the number it audited. A
    question that agreed and fired no probe writes no directory, so the number audited is an
    upper bound and nothing more: reading it as the count of directories to expect refused
    every healthy run that held such a question, which is most of them.

    A selection is the other case. What a site publishes of a run is some of its questions and
    ``published.json`` is where the whole run is, so a directory the run wrote may be absent
    here; one the run never wrote may not, whichever kind of report this is.

    A summary that names no list was written before 2026-09-14, which every published run and
    every directory an earlier release wrote is. Nothing is claimed about those beyond what the
    counts allow, and what they allow is checked.
    """
    listed = listed_directories(summary)
    present = tuple(sorted(_question_ids(directories)))
    if listed is None:
        _refuse_a_count_that_cannot_be_right(audit_directory, summary, present, published)
        return
    named = set(listed)
    extra = tuple(sorted(set(present) - named))
    if extra:
        raise ReportRefused(
            f"{audit_directory} holds more question directories than its {SUMMARY_FILE} names: "
            f"{_ids(extra)} {'is' if len(extra) == 1 else 'are'} here and the run says it wrote "
            f"{len(listed)} directories, none of them {'that one' if len(extra) == 1 else 'those'}. "
            f"A report is rendered from an audit's own directory and shows what the run wrote."
        )
    if published is not None:
        return
    missing = tuple(sorted(named - set(present)))
    if missing:
        raise ReportRefused(
            f"{audit_directory} holds fewer question directories than its {SUMMARY_FILE} names: "
            f"the run says it wrote {len(listed)} and {_ids(missing)} "
            f"{'is' if len(missing) == 1 else 'are'} not here. A report rendered from it would "
            f"be missing {'that question' if len(missing) == 1 else 'those questions'} with no "
            f"page saying so. A selection of a run says where the whole run is, in "
            f"{PUBLISHED_FILE} beside the summary."
        )


def _refuse_a_count_that_cannot_be_right(
    audit_directory: Path,
    summary: JsonObject,
    present: Sequence[int],
    published: Published | None,
) -> None:
    """The two bounds a summary that names no directories still fixes.

    An errored question writes no directory and a question that agreed and fired no probe
    writes none either, so the number audited bounds the directories from above and nothing
    fixes them from below except the disagreements: every NOT_EQUAL was written. A selection
    holds some of the directories, so only the upper bound is about it.
    """
    audited = integer_at(object_at(summary, "question_set"), "audited")
    errors = len(objects_at(summary, "errors"))
    if len(present) + errors > audited:
        raise ReportRefused(
            f"{audit_directory} holds more than the questions its {SUMMARY_FILE} counts: the "
            f"summary says {audited} were audited and the directory holds {len(present)} "
            f"question directories beside {errors} errors, which is more questions than the "
            f"run had. A report rendered from it would state {audited} at the top and show "
            f"{len(present) + errors}."
        )
    not_equal = optional_integer(object_at(summary, "verdicts"), NOT_EQUAL, 0)
    if published is None and len(present) < not_equal:
        raise ReportRefused(
            f"{audit_directory} holds fewer question directories than its {SUMMARY_FILE} "
            f"counts {NOT_EQUAL}: the summary says {not_equal} questions disagreed and every "
            f"one of those was written, and {len(present)} question directories are here. A "
            f"report rendered from it would be missing a question that disagreed, with no page "
            f"saying so. A selection of a run says where the whole run is, in {PUBLISHED_FILE} "
            f"beside the summary."
        )


def listed_directories(summary: JsonObject) -> tuple[int, ...] | None:
    """The questions the run says it wrote a directory for, or ``None`` where it does not say.

    Absent is not empty. A summary written before this key existed says nothing about what
    was written, and reading that silence as "none" would refuse every run made before it.
    """
    stated = summary.get("question_directories")
    if stated is None:
        return None
    if not isinstance(stated, list):
        raise UnreadableRecord(f"question_directories is not a JSON array: {stated!r}")
    listed: list[int] = []
    for value in stated:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise UnreadableRecord(
                f"question_directories holds {value!r}, which is not a question id"
            )
        listed.append(value)
    return tuple(listed)


def _question_ids(directories: Sequence[Path]) -> tuple[int, ...]:
    """The id each ``q<id>/`` names, which is how the run named it."""
    return tuple(
        int(match.group(1))
        for path in directories
        if (match := QUESTION_DIRECTORY.match(path.name)) is not None
    )


def _ids(found: Sequence[int]) -> str:
    """A few question ids as a reader reads them, with the rest counted rather than listed."""
    shown = ", ".join(f"q{value}" for value in found[:NAMED_IN_A_REFUSAL])
    left = len(found) - NAMED_IN_A_REFUSAL
    return shown if left <= 0 else f"{shown} and {left} more"


@dataclass(frozen=True)
class Beside:
    """The three files a publisher may put beside a summary, read once for the whole run.

    Read once because two of them are about the run rather than about one question: a
    question file of five hundred entries and a classification of a hundred and seventy rows
    read again for every question directory would be the same two documents parsed a hundred
    times over.
    """

    databases: Mapping[str, str]
    by_hand: Mapping[str, HandReading]
    published: Published | None


def beside_the_run(audit_directory: Path) -> Beside:
    """What is beside the summary, or nothing, which is what a directory the audit wrote holds."""
    return Beside(
        databases=_databases(audit_directory),
        by_hand=_by_hand(audit_directory),
        published=_published(audit_directory),
    )


def _databases(audit_directory: Path) -> Mapping[str, str]:
    """Which database each question is about, out of the file beside the summary."""
    path = audit_directory / QUESTIONS_FILE
    if not path.is_file():
        return {}
    return {
        as_text(entry.get("question_id")): as_text(entry.get("db_id"))
        for entry in _entry_list(path)
    }


def _by_hand(audit_directory: Path) -> Mapping[str, HandReading]:
    """A maintainer's rows for this run, out of the classification and the note beside it.

    Two files, because the classification is a copy of a document written for a measurement
    and is kept byte for byte, and the note beside it says where that copy came from, what
    date it carries and which of its rows are this run's. Both have to be there: a
    classification with no note would be rows a page could not say the date of, and the date
    is what makes a reading a reading rather than an opinion.
    """
    classification = audit_directory / CLASSIFICATION_FILE
    note = audit_directory / CLASSIFICATION_SOURCE_FILE
    if not classification.is_file() or not note.is_file():
        return {}
    where = read_document(note)
    rows = _classified(read_document(classification), where)
    field = optional_text(where, "reason_field") or "reason"
    classes = object_or_none(where, "classes") or {}
    return {
        as_text(row.get("question_id")): HandReading(
            classification=optional_text(row, "class"),
            # The note's own words for that class, or nothing: a class the note does not define
            # is rendered as the value the row holds and nothing is invented beside it.
            meaning=as_text(classes.get(optional_text(row, "class")) or ""),
            reason=optional_text(row, field),
            date=optional_text(where, "date"),
            source=optional_text(where, "source"),
            file=CLASSIFICATION_FILE,
        )
        for row in rows
    }


def _classified(document: JsonObject, where: JsonObject) -> list[JsonObject]:
    """The rows of one classification this run's page shows, by the join the note states.

    Two shapes and no more, each named by the note: ``per_file`` is a document keyed by the
    prediction file, whose ``key`` is this run's, and ``rows`` is one list whose rows name the
    database they were read on. A note naming any other shape is refused rather than guessed
    at: a join this module invented would put a person's reading on a question they never read.
    """
    shape = optional_text(where, "shape")
    key = optional_text(where, "key")
    if shape == "per_file":
        files = object_at(document, "per_file")
        stated = files.get(key)
        return [] if not isinstance(stated, dict) else objects_at(stated, "rows")
    if shape == "rows":
        return [row for row in objects_at(document, "rows") if optional_text(row, "db") == key]
    raise UnreadableRecord(
        f"{CLASSIFICATION_SOURCE_FILE} states the shape {shape!r}, and the two this reads are "
        f"'per_file', keyed by the prediction file, and 'rows', naming the database of each row"
    )


def published_asset(directory: Path) -> Published | None:
    """Where the whole of one run or one group was uploaded, out of the file beside it.

    The third accessor this package exposes for the site: a group has a `published.json` of its
    own, holding the group's own count, and the group page is built over there. A second reader
    of that file written in the site would be a second answer to what it says.
    """
    return _published(directory)


def _published(audit_directory: Path) -> Published | None:
    """Where the whole of this run was uploaded, out of the file beside the summary."""
    path = audit_directory / PUBLISHED_FILE
    if not path.is_file():
        return None
    document = read_document(path)
    url = optional_text(document, "url")
    if not url.startswith(ASSET_SCHEME):
        raise ReportRefused(
            f"{path} states {url!r}, and this address is a link on the run page: it has to "
            f"begin with {ASSET_SCHEME}, so that what a reader clicks fetches a file"
        )
    stated = document.get("directories")
    return Published(
        name=optional_text(document, "name"),
        url=url,
        size=f"{integer_at(document, 'bytes'):,} bytes",
        digest=optional_text(document, "sha256"),
        directories=(stated if isinstance(stated, int) and not isinstance(stated, bool) else None),
    )


def question_directories(audit_directory: Path) -> tuple[Path, ...]:
    """Every ``q<id>/`` of the run, in the order their ids read as numbers.

    Sorted by the number rather than by the name, so q207 comes before q1029 and two
    renderings of one directory list the questions in one order.
    """
    found = [
        (int(match.group(1)), path)
        for path in audit_directory.iterdir()
        if path.is_dir() and (match := QUESTION_DIRECTORY.match(path.name)) is not None
    ]
    return tuple(path for _, path in sorted(found))


def read_document(path: Path) -> JsonObject:
    """One JSON file of an audit directory, or a refusal naming the file and what was wrong."""
    try:
        loaded: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except OSError as unreadable:
        raise ReportRefused(f"{path} could not be read: {unreadable}") from unreadable
    except json.JSONDecodeError as unreadable:
        raise ReportRefused(f"{path} does not hold JSON: {unreadable}") from unreadable
    if not isinstance(loaded, dict):
        raise ReportRefused(f"{path} does not hold a JSON object")
    return loaded


def _entry_list(path: Path) -> list[JsonObject]:
    """One JSON file holding a list of objects, which `questions.json` is and no audit file."""
    try:
        loaded: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except OSError as unreadable:
        raise ReportRefused(f"{path} could not be read: {unreadable}") from unreadable
    except json.JSONDecodeError as unreadable:
        raise ReportRefused(f"{path} does not hold JSON: {unreadable}") from unreadable
    if not isinstance(loaded, list):
        raise ReportRefused(f"{path} does not hold a JSON array")
    return [object_of(entry, path.name) for entry in loaded]


def object_at(document: JsonObject, key: str) -> JsonObject:
    return object_of(document.get(key), key)


def object_of(value: JsonValue, what: str) -> JsonObject:
    return an_object(value, what, UnreadableRecord)


def object_or_none(document: JsonObject, key: str) -> JsonObject | None:
    """A block the format states may be null, or absent when the run had nothing to say."""
    value = document.get(key)
    return None if value is None else object_of(value, key)


def array_at(document: JsonObject, key: str) -> list[JsonValue]:
    return array_of(document.get(key), key)


def array_of(value: JsonValue, what: str) -> list[JsonValue]:
    return an_array(value, what, UnreadableRecord)


def objects_at(document: JsonObject, key: str) -> list[JsonObject]:
    return [object_of(value, key) for value in array_at(document, key)]


def strings_at(document: JsonObject, key: str) -> list[str]:
    return [as_text(value) for value in array_at(document, key)]


def text_at(document: JsonObject, key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str):
        raise UnreadableRecord(f"{key} is not text: {value!r}")
    return value


def optional_text(document: JsonObject, key: str, *, absent: str = "") -> str:
    """A value the format states may be null, as the text a page shows for it."""
    value = document.get(key)
    return absent if value is None else as_text(value)


def integer_at(document: JsonObject, key: str) -> int:
    """One count, by the same rule the site builder and the selector read one under."""
    return whole_count(document, key, UnreadableRecord)


def optional_integer(document: JsonObject, key: str, default: int) -> int:
    return default if document.get(key) is None else integer_at(document, key)


def facts_of(block: JsonObject) -> tuple[Fact, ...]:
    return tuple(Fact(name, as_text(value)) for name, value in block.items())


def origin_of(source: JsonObject, digest: str) -> str:
    """What the run was told about a file, after the digest it measured for itself."""
    origin = optional_text(source, "origin", absent="origin not stated")
    date = optional_text(source, "date")
    return f"{digest} | {origin}{f', {date}' if date else ''}"


def as_text(value: object) -> str:
    """One JSON value as the text a page shows, with a null as the empty string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def cell_text(cell: JsonObject) -> str:
    """One cell's payload as text. A null is the word, in the style the design gives it."""
    value = cell.get("value")
    return "NULL" if value is None else as_text(value)
