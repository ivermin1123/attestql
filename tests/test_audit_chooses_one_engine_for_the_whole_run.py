"""One engine brings both halves of an audit: the database it reaches and the parser.

ADR-0014 points 2 and 3 put a second engine behind two protocols rather than behind a
branch. What is observed here is that the seam is really the only way through: an engine
the test builds itself, with its own way of connecting and its own parser, runs a whole
audit, and nothing under the options asks which engine it is. The engine the record names
is the backend's answer and not this record's name, which is why a fake engine may call
itself anything at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.backend import Backend
from attestql.audit.cli import SUMMARY_FILE, AuditOptions, connect_and_audit
from attestql.audit.engines import DEFAULT_ENGINE, ENGINES, Engine, engine_named
from attestql.audit.parse import ParsedStatement, ParserIdentity
from attestql.audit.sqlite_statements import PARSER as SQLITE_PARSER
from attestql.audit.sqlite_statements import parse_statement as parse_sqlite_statement
from attestql.audit.statements import PARSER, parse_statement
from attestql.evidence.types import ENGINE_POSTGRESQL, ENGINE_SQLITE
from tests.audit_fakes import FakeBackend, fake_result

ELEMENTS = "SELECT DISTINCT element FROM atom"
ELEMENT = (("element", "text"),)


class Lines:
    """A writer that keeps what was written instead of printing it."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def line(self, text: str) -> None:
        self.written.append(text)


def _questions(tmp_path: Path) -> Path:
    path = tmp_path / "questions.json"
    path.write_text(
        json.dumps(
            [
                {
                    "question_id": 207,
                    "db_id": "toxicology",
                    "question": "Which elements are there?",
                    "evidence": "",
                    "SQL": ELEMENTS,
                    "difficulty": "simple",
                }
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_the_postgresql_backend_and_parser_fill_the_two_protocols_in() -> None:
    """Assignability is the assertion: the type checker reads every member of both."""
    backend: Backend = FakeBackend({ELEMENTS: fake_result(ELEMENT, (("c",),))})
    parsed: ParsedStatement = parse_statement(ELEMENTS)
    parser: ParserIdentity = parsed.parser

    assert backend.session_settings().engine == ENGINE_POSTGRESQL
    assert parsed.sql == ELEMENTS
    assert parser is PARSER
    assert parser.json()["validator"] == PARSER.validator


def test_the_registry_holds_the_engines_the_flag_offers() -> None:
    assert DEFAULT_ENGINE.name == ENGINE_POSTGRESQL
    assert engine_named(ENGINE_POSTGRESQL) is DEFAULT_ENGINE
    assert set(ENGINES) == {ENGINE_POSTGRESQL, ENGINE_SQLITE}
    assert DEFAULT_ENGINE.parse is parse_statement
    assert DEFAULT_ENGINE.parser is PARSER, (
        "the summary and every record of a run name one parser, not two"
    )


def test_each_engine_brings_its_own_parser_and_never_the_other_one_s() -> None:
    """The two seams are filled in per engine, so a run reads its statements with the
    grammar of the engine it is running on and a record cannot name the other parser."""
    assert engine_named(ENGINE_SQLITE).parser is SQLITE_PARSER
    assert engine_named(ENGINE_SQLITE).parse is parse_sqlite_statement
    assert SQLITE_PARSER.validator != PARSER.validator


def test_an_engine_nobody_registered_is_refused_by_name() -> None:
    with pytest.raises(KeyError, match="no engine named 'duckdb'"):
        engine_named("duckdb")


def test_a_whole_audit_runs_through_an_engine_the_test_built(tmp_path: Path) -> None:
    """Connect, parse, audit: all three reached through one record the options carry."""
    backend = FakeBackend(
        {ELEMENTS: fake_result(ELEMENT, (("c",), ("o",)))}, row_counts={"atom": 2}
    )
    opened: list[tuple[str, str]] = []
    parsed: list[str] = []

    def connect(target: str, /, *, scratch: str) -> Backend:
        opened.append((target, scratch))
        return backend

    def parse(sql: str, /) -> ParsedStatement:
        parsed.append(sql)
        return parse_statement(sql)

    engine = Engine(name="an-engine-of-the-test's-own", connect=connect, parse=parse, parser=PARSER)
    options = AuditOptions(
        dsn="host=nowhere dbname=none",
        questions=_questions(tmp_path),
        out=tmp_path / "audit",
        engine=engine,
    )
    writer = Lines()

    assert connect_and_audit(options, writer) == 0
    assert opened == [("host=nowhere dbname=none", options.scratch_schema)]
    assert parsed == [ELEMENTS]
    assert writer.written[-1] == "1 questions: 0 NOT_EQUAL, 0 smells fired"

    document = cast(
        "dict[str, Any]",
        json.loads((tmp_path / "audit" / SUMMARY_FILE).read_text(encoding="utf-8")),
    )
    assert document["parser"] == PARSER.json()
    assert document["session_settings"]["engine"] == ENGINE_POSTGRESQL, (
        "the record's engine is what the backend reported, not what the engine called itself"
    )
