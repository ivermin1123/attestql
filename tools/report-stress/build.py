#!/usr/bin/env python3
"""Build an audit directory that holds every state a report page has to render.

The sandbox `attestql demo` audits is small and calm: six questions, three of which
disagree, none of them long. A page that renders it well is a page nobody has stressed. So
this builds a second directory, outside the repository, whose questions are chosen for what
they make a page do rather than for what they say about a benchmark, and the note file it
leaves says exactly that.

Nothing here writes an artifact by hand. The fixture is `attestql.demo`'s own, with tables
and rows of this file's own on top of it; the questions and the predictions are two files
like any other pair; and what makes the directory is `attestql audit --engine sqlite` over
those three, so every JSON in it came from the tool's own writers. The one question the
command line cannot produce, NOT_COMPARABLE, is built from two records the recorder wrote
against two fixtures that differ, compared by the library's own comparison and written by
the audit's own writer; no record is edited, trimmed or reissued anywhere in this file.

What the directory ends up holding, and why each is here:

    a result of 10,000 rows      the record that dominates a page's size and its render time
    a 600-character statement    a statement that has to wrap without pushing the page
    a 16-column projection       a table that has to escape the prose measure
    a timestamp column           a cell whose text is long and whose column is dense
    a 200-character origin       an unbroken string that has to wrap somewhere
    a NULL-heavy result          the state a cell is rather than a value it has
    one question of each state   EQUAL, the five NOT_EQUAL classes, both kinds of ERROR,
                                 timed out, projection names, GOLD-ONLY with a fired probe,
                                 duplicate ids, prediction positions unused, missing tables

Three states of the design spec's table are not here, and are not faked. `result.truncated`
is written by no backend this tool has (both set it False), `unreadable_tables` is always
empty on a file, which has no grants, and a hand classification is phase 4's file with no
renderer to read it yet. The verification report names all three.

Run it with `uv run python tools/report-stress/build.py <directory>`; the directory is made
if it is not there, and rebuilt from nothing if it is. Nothing is written inside the
repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from attestql.audit.backend import Backend
from attestql.audit.cli import DEFAULT_SCRATCH_SCHEMA, SERIALIZATION
from attestql.audit.cli import main as audit_main
from attestql.audit.compare import (
    Comparison,
    bird_ex,
    record_statement,
    test_suite_ex,
    write_comparison,
)
from attestql.audit.engines import engine_named
from attestql.audit.parse import ParsedStatement
from attestql.audit.smells import QuestionText, SmellSettings, all_smells, smells_json
from attestql.demo import build_fixture
from attestql.evidence.record import EvidenceRecord
from attestql.evidence.render import result_digest, row_difference, write_json
from attestql.evidence.replay import ReplayRule, compare_r_ord
from attestql.evidence.types import QuestionMetadata, StatementSource
from attestql.report.render import GOLD_RECORD_FILE, SECOND_RECORD_FILE, SMELLS_FILE, SUMMARY_FILE

REPOSITORY = Path(__file__).resolve().parents[2]
"""Where this file lives, so the guard below can refuse to write inside it. The module's
docstring promises the directory is outside the repository; this is what keeps the promise."""

WIDE_ROWS = 10_000
"""How many rows the widest table holds, and therefore how many a record does. The bound the
audit runs under is higher, so this is the size a page has to render rather than a limit
anything reached."""

PARTS = 5
PART_USES = 103
"""Five rows that become a hundred and three through a join: the multiplicity class, at the
size the design spec's own example states it."""

SEQUENCE_ROWS = 40
"""Long enough that a slope chart draws its bound of twenty-five of them and says so."""

ORIGIN = "https://example.invalid/benchmarks/stress/" + "q" * 158
"""A 200-character origin with nowhere to break, recorded beside the question file's digest
and rendered on every record. What it is for is the wrapping."""

NOT_COMPARABLE_ID = 800014
"""The question built outside the run, from two records against two fixtures."""

FIXTURE_SQL = """
CREATE TABLE part (
    id  INTEGER PRIMARY KEY,
    tag TEXT NOT NULL
);

CREATE TABLE part_use (
    id      INTEGER PRIMARY KEY,
    part_id INTEGER NOT NULL REFERENCES part (id),
    used    TEXT NOT NULL
);

CREATE TABLE sequence (
    n     INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE wide (
    id          INTEGER PRIMARY KEY,
    recorded_at TEXT,
    region      TEXT,
    operator    TEXT,
    batch       TEXT,
    reading     REAL,
    tolerance   REAL,
    retries     INTEGER,
    flagged     INTEGER,
    station     TEXT,
    sensor      TEXT,
    unit        TEXT,
    note        TEXT,
    checked_by  TEXT,
    source_url  TEXT,
    comment     TEXT
);
"""
"""The tables this file adds to the packaged fixture. Sixteen columns on `wide` because a
sixteen-column projection is what a table has to escape the prose measure to show, and a
text column for the timestamp because SQLite has no timestamp type: a file holds the text,
and the record tags the cell `str`, which is the truth about this engine."""

LONG_STATEMENT = (
    "SELECT w.id, w.recorded_at, w.region, w.operator, w.batch, w.reading, w.tolerance, "
    "w.retries, w.flagged, w.station, w.sensor, w.unit, w.note, w.checked_by, "
    "w.source_url, w.comment FROM wide AS w WHERE w.id <= 4 AND (w.region IS NULL OR "
    "w.region IN ('north', 'south', 'east', 'west')) AND (w.batch IS NULL OR "
    "w.batch <> 'withdrawn') AND (w.station IS NULL OR w.station NOT IN "
    "('station-99', 'station-98', 'station-97', 'station-96', 'station-95')) AND "
    "(w.checked_by IS NULL OR w.checked_by <> 'checker-99') AND (w.unit IS NULL OR "
    "w.unit IN ('mm', 'cm', 'm')) ORDER BY w.id ASC"
)
"""The sixteen-column projection, and the statement whose length a page has to hold: 600
characters, which is the longest gold in BIRD Mini-Dev rounded up. Every predicate in it is
true of the fixture, so what it measures is the rendering and not the filtering."""

SECOND_LONG_STATEMENT = LONG_STATEMENT.replace("w.id <= 4", "w.id BETWEEN 5 AND 8")

QUESTIONS: tuple[tuple[int, str, str, str], ...] = (
    (
        800001,
        "Which tags are on the parts, in order?",
        "the tag refers to part.tag",
        "SELECT tag FROM part ORDER BY tag ASC",
    ),
    (
        800002,
        "Which tags are on the parts that were used?",
        "a use refers to a row of part_use",
        "SELECT tag FROM part ORDER BY tag ASC",
    ),
    (
        800003,
        "What are the numbers of the sequence, smallest first?",
        "the number refers to sequence.n",
        "SELECT n FROM sequence ORDER BY n ASC",
    ),
    (
        800004,
        "What are the first twenty numbers of the sequence?",
        "the first refers to the smallest",
        "SELECT n FROM sequence ORDER BY n ASC LIMIT 20",
    ),
    (
        800005,
        "What are the three smallest numbers of the sequence?",
        "",
        "SELECT n FROM sequence ORDER BY n ASC LIMIT 3",
    ),
    (
        800006,
        "Which tags are on the parts that were logged first?",
        "logged first refers to the lowest ids",
        "SELECT tag FROM part WHERE id <= 2 ORDER BY tag ASC",
    ),
    (
        800007,
        "Which parts are there?",
        "",
        "DELETE FROM part WHERE id = 1",
    ),
    (
        800008,
        "What did the withdrawn batches read?",
        "",
        "SELECT name FROM a_table_this_database_does_not_hold ORDER BY name",
    ),
    (
        800009,
        "How many readings are there, counted three ways?",
        "",
        "SELECT count(*) FROM wide AS a, wide AS b, wide AS c",
    ),
    (
        800010,
        "Which tag is on the part that was logged first?",
        "",
        "SELECT tag AS label FROM part WHERE id <= 2 ORDER BY tag ASC",
    ),
    (
        800011,
        "Who holds the highest score?",
        "the highest score refers to MAX(score)",
        "SELECT name FROM scores ORDER BY score DESC LIMIT 1",
    ),
    (
        800012,
        "What was recorded for the first four readings?",
        "a reading refers to a row of wide",
        LONG_STATEMENT,
    ),
    (
        800013,
        "What are the ids of every reading, smallest first?",
        "",
        "SELECT id FROM wide ORDER BY id ASC",
    ),
    (
        NOT_COMPARABLE_ID,
        "What are the numbers of the sequence?",
        "",
        "SELECT n FROM sequence ORDER BY n ASC",
    ),
)
"""The question set, in file order. Every id but the last is audited by the run; the last is
the one built against a second fixture below, and it is in the file so that the question a
reader opens is stated in the same place as the others."""

PREDICTIONS: dict[int, str] = {
    800001: "SELECT p.tag FROM part AS p ORDER BY p.tag ASC",
    800002: (
        "SELECT p.tag FROM part AS p JOIN part_use AS u ON u.part_id = p.id ORDER BY p.tag ASC"
    ),
    800003: "SELECT n FROM sequence ORDER BY label ASC",
    800004: "SELECT n FROM sequence ORDER BY n ASC LIMIT 8",
    800005: "SELECT CAST(n AS TEXT) FROM sequence ORDER BY n ASC LIMIT 3",
    800006: "SELECT tag FROM part WHERE id >= 4 ORDER BY tag ASC",
    800007: "SELECT tag FROM part ORDER BY tag ASC",
    800008: "SELECT tag FROM part ORDER BY tag ASC",
    800009: "SELECT count(*) FROM wide",
    800010: "SELECT tag AS name FROM part WHERE id >= 4 ORDER BY tag ASC",
    800012: SECOND_LONG_STATEMENT,
    800013: "SELECT id FROM wide ORDER BY id DESC",
}
"""One prediction per question, by question id here and written to the file by position: the
file the run reads is keyed the way BIRD's own predict files are keyed. 800011 has none, so
it is the GOLD-ONLY question, and the last question is not the run's."""

NOTE = """This directory is a rendering fixture.

It was built by tools/report-stress/build.py so that `attestql report` could be rendered and
measured against every state a page has: a ten-thousand-row record, a six-hundred-character
statement, a sixteen-column projection, an unbroken two-hundred-character origin, a
NULL-heavy result and one question of each verdict, mechanism, error and probe state.

The questions in it were written to make a page do something. They are not a benchmark, they
are not evidence about one, and the numbers in them say nothing about BIRD, about any model's
predictions or about any published result. The data they run against is this repository's own
synthetic fixture.
"""

NOTE_FILE = "THIS-IS-NOT-EVIDENCE.txt"
STRESS = "stress"
SECOND_FIXTURE = "fixture-second.sqlite"
"""The directory the run writes into, and the second file the NOT_COMPARABLE question's other
record was recorded against: one row more than the first, which is a precondition the two
records disagree on and the reason the library refuses to compare them."""


def build(out: Path) -> int:
    """Build the fixture, run the audit over it, add the one question a run cannot make."""
    out = out.expanduser().resolve()
    if out == REPOSITORY or REPOSITORY in out.parents:
        # The same rule tools/audit-sandbox-sqlite/build.py holds, for the same reason, and
        # here it is load bearing: the first thing this does to the directory it is given is
        # remove it.
        print(f"the output directory must be outside the repository: {out}", file=sys.stderr)
        return 2
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    fixture = _fixtures(out)
    questions, predictions = _inputs(out)
    audit = out / STRESS
    status = audit_main(
        [
            "audit",
            "--engine",
            "sqlite",
            "--dsn",
            str(fixture),
            "--questions",
            str(questions),
            "--predictions",
            str(predictions),
            "--predictions-keyed-by",
            "position",
            "--questions-origin",
            ORIGIN,
            "--questions-date",
            "2026-09-07",
            "--statement-timeout",
            "2",
            "--ids",
            ",".join(str(question_id) for question_id, *_ in QUESTIONS[:-1]),
            "--out",
            str(audit),
        ]
    )
    _not_comparable(out, audit)
    for beside in (out, audit):
        # Beside the directory and inside it. A person renders the audit directory, and moves
        # or publishes it; the note has to travel with it. `attestql report` reads the five
        # files it names and ignores everything else, so this changes no page.
        (beside / NOTE_FILE).write_text(NOTE, encoding="utf-8")
    _measure(audit)
    print(f"the audit is {audit}, and the run exited {status}")
    return 0


def _fixtures(out: Path) -> Path:
    """Both fixtures, and the path of the one the run audits.

    The packaged sandbox is built once and copied, and this file's own tables go into both
    copies. The second holds one row more, in a table no question reads: enough for the two
    fixture digests to differ, which is the precondition two records have to disagree on for
    the library to refuse to compare them, and no answer to any question changes.
    """
    built = build_fixture(out)
    shutil.copyfile(built, out / SECOND_FIXTURE)
    _extend(built, extra_row=False)
    _extend(out / SECOND_FIXTURE, extra_row=True)
    return built


def _extend(path: Path, *, extra_row: bool) -> None:
    """This file's own tables and rows, on top of a built sandbox."""
    connection = sqlite3.connect(path)
    try:
        with connection:
            connection.executescript(FIXTURE_SQL)
            connection.executemany(
                "INSERT INTO part (id, tag) VALUES (?, ?)",
                [(index, f"tag-{index:02d}") for index in range(1, PARTS + 1)],
            )
            connection.executemany(
                "INSERT INTO part_use (id, part_id, used) VALUES (?, ?, ?)",
                [
                    (index, (index % PARTS) + 1, f"2026-09-0{(index % 7) + 1}")
                    for index in range(1, PART_USES + 1)
                ],
            )
            connection.executemany(
                "INSERT INTO sequence (n, label) VALUES (?, ?)",
                [
                    (number, f"{(number * 17) % SEQUENCE_ROWS:03d}")
                    for number in range(1, SEQUENCE_ROWS + 1)
                ],
            )
            connection.executemany(
                "INSERT INTO wide VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [_wide_row(index) for index in range(1, WIDE_ROWS + 1)],
            )
            if extra_row:
                # The one row the two fixtures differ by, in the table the NOT_COMPARABLE
                # question reads: a fixture digest covers the tables a statement names, so a
                # row anywhere else would leave the two records comparable.
                connection.execute(
                    "INSERT INTO sequence (n, label) VALUES (?, ?)",
                    (SEQUENCE_ROWS + 1, f"{((SEQUENCE_ROWS + 1) * 17) % SEQUENCE_ROWS:03d}"),
                )
    finally:
        connection.close()


def _wide_row(index: int) -> tuple[object, ...]:
    """One row of the sixteen-column table: about a third of every cell is NULL.

    The NULLs are placed by the row's own number rather than at random, so two builds of
    this fixture hold the same rows and two renderings of it are the same page.
    """
    empty = index % 3 == 0
    later = index % 5 == 0
    return (
        index,
        f"2026-09-07T{index % 24:02d}:{index % 60:02d}:{(index * 7) % 60:02d}+00:00",
        None if empty else ("north", "south", "east", "west")[index % 4],
        None if later else f"operator-{index % 11:02d}",
        None if empty else f"batch-{index % 23:03d}",
        None if later else round(index / 7, 3),
        None if empty else 0.25,
        None if later else index % 4,
        None if empty else index % 2,
        f"station-{index % 37:02d}",
        None if later else f"sensor-{index % 13:02d}",
        None if empty else ("mm", "cm", "m")[index % 3],
        None if later else f"reading {index} taken on the {index % 28 + 1}th",
        None if empty else f"checker-{index % 5:02d}",
        f"https://example.invalid/readings/{index:07d}",
        None if later else "recorded by the stress fixture, not by any benchmark",
    )


def _inputs(out: Path) -> tuple[Path, Path]:
    """The question file and the prediction file, written as any other pair would be.

    The question file holds 800001 twice, at its own position and again at the end. That is
    the duplicate ids a run reports, and, because the prediction file is keyed by position
    the way BIRD's own predict files are, it is also the prediction position that loses to a
    lower one naming the same question and is reported as unused.
    """
    entries = [
        {
            "question_id": question_id,
            "db_id": "stress",
            "question": text,
            "evidence": evidence,
            "SQL": sql,
            "difficulty": "simple",
        }
        for question_id, text, evidence, sql in QUESTIONS
    ]
    entries.append(dict(entries[0]))
    questions = out / "questions.json"
    questions.write_text(
        json.dumps(
            {
                "source": {
                    "what": f"a rendering fixture, not a benchmark: see {NOTE_FILE}",
                    "written_by": "tools/report-stress/build.py",
                },
                "questions": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    by_position = {
        str(position): PREDICTIONS[entry["question_id"]]
        for position, entry in enumerate(entries)
        if entry["question_id"] in PREDICTIONS
    }
    predictions = out / "predictions.json"
    predictions.write_text(json.dumps(by_position, indent=2) + "\n", encoding="utf-8")
    return questions, predictions


def _not_comparable(out: Path, audit: Path) -> None:
    """The one verdict a single run cannot reach, from two records against two fixtures.

    Both records of a comparison come from one session, so one `attestql audit` never
    writes a NOT_COMPARABLE: its two records agree on every precondition by construction.
    Two runs against two fixtures do not, and that is what this builds. Both records are
    the recorder's own, the verdict is the library's own comparison of them, and the
    directory is written by the audit's own writer; nothing is edited afterwards.
    """
    engine = engine_named("sqlite")
    question_id, text, evidence, sql = QUESTIONS[-1]
    metadata = QuestionMetadata(
        question_id=str(question_id),
        question_set="questions",
        question_text=text,
        evidence_text=evidence,
    )
    parsed = engine.parse(sql)
    questions = out / "questions.json"
    # The digest of the file the statement was read from, in the form the audit's own writer
    # states it. Without it the one record built outside the run would carry a stand-in where
    # every other record on the page carries the sha256 a reader can take again themselves.
    digest = f"sha256:{hashlib.sha256(questions.read_bytes()).hexdigest()}"
    source = StatementSource(path=str(questions), digest=digest, origin=ORIGIN, date="2026-09-07")
    gold, second = (
        _record(
            engine.connect(str(out / name), scratch=DEFAULT_SCRATCH_SCHEMA),
            metadata,
            parsed,
            source,
            out,
            digest,
        )
        for name in ("fixture.sqlite", SECOND_FIXTURE)
    )
    verdict = compare_r_ord(gold, second)
    comparison = Comparison(
        question=metadata,
        replay_rule=ReplayRule.R_ORD,
        verdict=verdict,
        gold=gold,
        second=second,
        gold_result_hash=result_digest(gold.result, SERIALIZATION),
        second_result_hash=result_digest(second.result, SERIALIZATION),
        differing_rows=row_difference(gold.result.rows, second.result.rows),
        gold_ordering=parsed.ordering,
        second_ordering=parsed.ordering,
        bird_ex=bird_ex(gold.result, second.result, engine="sqlite"),
        test_suite_ex=test_suite_ex(gold.result, second.result, sql, engine="sqlite"),
        mechanism=None,
    )
    found = all_smells(
        parsed,
        engine.connect(str(out / "fixture.sqlite"), scratch=DEFAULT_SCRATCH_SCHEMA),
        gold.result,
        settings=SmellSettings(serialization=SERIALIZATION, statement_timeout_seconds=2),
        question=QuestionText(text, evidence),
        no_shuffle="this question was recorded outside a run, and no copy was prepared",
    )
    directory = audit / f"q{question_id}"
    directory.mkdir(parents=True, exist_ok=True)
    write_comparison(comparison, directory)
    write_json(directory / SMELLS_FILE, smells_json(found))
    print(f"q{question_id} is {verdict.result.name}, mismatched: {', '.join(verdict.mismatched)}")


def _record(
    backend: Backend,
    metadata: QuestionMetadata,
    parsed: ParsedStatement,
    source: StatementSource,
    out: Path,
    question_set_version: str,
) -> EvidenceRecord:
    """One statement recorded against one fixture, by the recorder every other record uses.

    ``source_digest`` is empty because the run's own records hold it empty: it is the digest
    of the file the data was loaded from, and this sandbox is given no ``--data-file``.
    Filling it here would state a provenance no record in this directory has.
    """
    return record_statement(
        question=metadata,
        question_set_version=question_set_version,
        statement_source=source,
        parsed=parsed,
        backend=backend,
        serialization=SERIALIZATION,
        session_settings=backend.session_settings(),
        run_id="stress-not-comparable",
        directory=out / "cache",
        data_as_of=datetime(2026, 9, 7, tzinfo=UTC),
        statement_timeout_seconds=2,
        with_content_digests=False,
        source_digest="",
    ).record


def _measure(audit: Path) -> None:
    """What the largest record costs: its bytes on disk, and the seconds a page takes.

    Both numbers go into the verification report, and both are measured here rather than
    stated: the record is the term that dominates a page's size, and the render is the one
    thing a reader waits for.
    """
    from attestql.report import render_report

    records = sorted(audit.rglob(GOLD_RECORD_FILE)) + sorted(audit.rglob(SECOND_RECORD_FILE))
    largest = max(records, key=lambda path: path.stat().st_size)
    started = time.perf_counter()
    report = render_report(audit, audit.parent / "report")
    elapsed = time.perf_counter() - started
    pages = sorted(report.out.rglob("index.html"), key=lambda path: path.stat().st_size)
    print(f"the largest record is {largest.relative_to(audit)} at {largest.stat().st_size:,} bytes")
    print(
        f"the largest page is {pages[-1].relative_to(report.out)} at "
        f"{pages[-1].stat().st_size:,} bytes"
    )
    print(f"{len(report.pages)} pages rendered in {elapsed:.2f} s")
    print(f"the summary is {(audit / SUMMARY_FILE).stat().st_size:,} bytes")


def run(argv: list[str] | None = None) -> int:
    """The command line: one optional directory, outside the repository by default."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "out",
        type=Path,
        nargs="?",
        default=Path(os.environ.get("TMPDIR", "/tmp")) / "attestql-report-stress",  # noqa: S108
        help="the directory the fixture, the inputs and the audit are written into",
    )
    return build(parser.parse_args(argv).out)


if __name__ == "__main__":
    sys.exit(run())
