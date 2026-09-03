"""The command, end to end, against a backend that answers from a script.

No server, no driver, no network: ``run_audit`` takes the backend, so these tests read
the lines the command printed, the files it wrote and the status it would exit with.

The three things the command has to get right and nothing else states are here: the line
format ADR-0013 point 2 writes down, which directory is written and which is not, and
what the exit status is in each of the four cases the ADR names.

Under "what does not stop a run" is the fourth: a run that meets a table nobody loaded, or
a server that goes away between two questions, still audits the questions it can and still
writes ``summary.json``. The fake backend is told to be missing a table or to have lost its
connection, which is the only way those two are reachable without a server.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.backend import BackendRefused, TextCensus
from attestql.audit.cli import (
    SMELLS_FILE,
    SUMMARY_FILE,
    AuditOptions,
    ToolError,
    audit,
    main,
    parse_arguments,
    read_predictions,
    read_questions,
    run_audit,
)
from attestql.audit.compare import COUNTEREXAMPLE_FILE, GOLD_RECORD_FILE, SECOND_RECORD_FILE
from attestql.audit.smells import DEFAULT_SHUFFLE_ROW_LIMIT, NUMERIC_TEXT
from attestql.audit.statements import parse_statement
from attestql.kernel.types import ExecutionResult
from tests.audit_fakes import FakeBackend, fake_result

FASTEST_LAP = (
    "SELECT t1.nationality FROM drivers AS t1 JOIN results AS t2 "
    "ON t1.driverid = t2.driverid ORDER BY t2.fastestlapspeed DESC LIMIT 1"
)
NUMERIC = parse_statement(FASTEST_LAP).with_ordering_key_cast_to_numeric(0)
UNBOUNDED = parse_statement(FASTEST_LAP).without_the_bound_and_projecting_its_keys()

ELEMENTS = "SELECT element FROM atom"
ELEMENTS_ONE_ROW = "SELECT element FROM atom LIMIT 1"
TWO_ROWS = "SELECT name FROM players LIMIT 2"
SEASONS = "SELECT year FROM seasons"
DRIVERS = "SELECT nationality FROM drivers"
BARE_SELECT = "SELECT"

NATIONALITY = (("nationality", "text"),)
NATIONALITY_AND_SPEED = (("nationality", "text"), ("attestql_ordering_key_0", "text"))
ELEMENT = (("element", "text"),)
NAME = (("name", "text"),)

COLUMN_TYPES = {
    "public.results": {"fastestlapspeed": "text", "laps": "bigint", "driverid": "bigint"},
    "public.drivers": {"driverid": "bigint", "nationality": "text"},
}
ALL_NUMERIC = TextCensus(
    rows=23_179, nulls=18_185, empty_strings=0, non_numeric=0, pattern=NUMERIC_TEXT
)


class Lines:
    """A writer that keeps what it was given, which is what a test reads."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def line(self, text: str) -> None:
        self.written.append(text)


def question(
    question_id: int, db_id: str, sql: str, *, text: str = "Which one?", evidence: str = ""
) -> dict[str, Any]:
    return {
        "question_id": question_id,
        "db_id": db_id,
        "question": text,
        "evidence": evidence,
        "SQL": sql,
        "difficulty": "simple",
    }


def write(path: Path, document: object) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def options(tmp_path: Path, **changed: Any) -> AuditOptions:
    stated: dict[str, Any] = {
        "dsn": "host=localhost dbname=bird",
        "questions": tmp_path / "questions.json",
        "out": tmp_path / "audit",
        **changed,
    }
    return AuditOptions(**stated)


def sha256_of(path: Path) -> str:
    """The digest of a file, computed here rather than with the tool's own helper: what a
    record and the summary state about a file is checked against the file itself."""
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def summary_of(tmp_path: Path) -> dict[str, Any]:
    document = json.loads((tmp_path / "audit" / SUMMARY_FILE).read_text(encoding="utf-8"))
    return cast("dict[str, Any]", document)


# the question file


def test_a_duplicated_id_with_the_same_entry_is_one_question(tmp_path: Path) -> None:
    """BIRD's own Mini-Dev file: 500 entries, 498 ids, 137 and 138 written twice."""
    entry = question(137, "financial", ELEMENTS)
    path = write(
        tmp_path / "questions.json", [entry, dict(entry), question(1, "toxicology", ELEMENTS)]
    )
    read = read_questions(path)
    assert [found.question_id for found in read.questions] == [137, 1]
    assert read.entries == 3
    assert read.duplicate_ids == (137,)


def test_two_different_questions_under_one_id_stop_the_run(tmp_path: Path) -> None:
    path = write(
        tmp_path / "questions.json",
        [question(137, "financial", ELEMENTS), question(137, "financial", "SELECT 1")],
    )
    with pytest.raises(ToolError, match=r"\[137\]"):
        read_questions(path)


def test_the_ids_filter_keeps_only_what_it_names(tmp_path: Path) -> None:
    path = write(
        tmp_path / "questions.json",
        [question(879, "formula_1", ELEMENTS), question(207, "toxicology", ELEMENTS)],
    )
    assert [found.question_id for found in read_questions(path, (207,)).questions] == [207]
    with pytest.raises(ToolError, match=r"\[3\]"):
        read_questions(path, (3,))


def test_a_question_file_that_is_not_a_list_is_refused(tmp_path: Path) -> None:
    path = write(tmp_path / "questions.json", {"question_id": 1})
    with pytest.raises(ToolError, match="a question file is a list"):
        read_questions(path)


# the predictions file


def test_predictions_are_read_in_both_of_the_forms_bird_writes(tmp_path: Path) -> None:
    path = write(
        tmp_path / "predictions.json",
        {
            "879": "SELECT nationality FROM drivers",
            207: "SELECT element FROM atom\t----- bird -----\ttoxicology",
        },
    )
    assert dict(read_predictions(path)) == {
        879: "SELECT nationality FROM drivers",
        207: "SELECT element FROM atom",
    }


def test_a_prediction_that_is_not_a_statement_is_refused(tmp_path: Path) -> None:
    path = write(tmp_path / "predictions.json", {"879": 12})
    with pytest.raises(ToolError, match="a prediction is SQL"):
        read_predictions(path)


# gold only


def _quiet_backend() -> FakeBackend:
    return FakeBackend({ELEMENTS: fake_result(ELEMENT, (("c",), ("o",)))}, row_counts={"atom": 2})


def test_a_gold_only_run_with_nothing_to_report_writes_no_directory(tmp_path: Path) -> None:
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    lines = Lines()
    summary = run_audit(options(tmp_path), _quiet_backend(), lines)
    assert lines.written[0] == "q207  toxicology  R-SET  GOLD-ONLY  smells=none"
    assert lines.written[1] == "1 questions: 0 NOT_EQUAL, 0 NOT_COMPARABLE, 0 smells fired"
    assert summary.exit_status == 0
    assert not (tmp_path / "audit" / "q207").exists()
    written = summary_of(tmp_path)
    assert written["verdicts"] == {"GOLD-ONLY": 1}
    assert written["data_as_of_source"] == "the instant the run started"
    assert written["fixture"]["row_counts"] == {"atom": 2}
    assert written["shuffle"]["prepared"] is True


def test_a_fired_smell_writes_the_gold_record_and_the_smells_beside_it(tmp_path: Path) -> None:
    write(tmp_path / "questions.json", [question(94, "european_football_2", TWO_ROWS)])
    backend = FakeBackend(
        {TWO_ROWS: fake_result(NAME, (("a",), ("b",)))},
        shuffled_results={TWO_ROWS: fake_result(NAME, (("c",), ("d",)))},
    )
    lines = Lines()
    summary = run_audit(options(tmp_path), backend, lines)
    assert "smells=arbitrary-cut,not-a-function-of-the-data" in lines.written[0]
    assert summary.exit_status == 0, "a heuristic does not fail a run by itself"
    assert summary.smells["arbitrary-cut"] == 1
    directory = tmp_path / "audit" / "q94"
    assert (directory / GOLD_RECORD_FILE).is_file()
    assert not (directory / COUNTEREXAMPLE_FILE).exists(), "there was no second statement"
    document = cast(
        "dict[str, Any]", json.loads((directory / SMELLS_FILE).read_text(encoding="utf-8"))
    )
    assert [entry["fired"] for entry in document["smells"]] == [False, True, True]
    assert document["smells"][1]["evidence"]["heuristic"] is True
    assert backend.dropped == 1, "the scratch copies outlived the run"


def test_a_scratch_schema_the_run_cannot_use_is_reported_and_audits_everything_else(
    tmp_path: Path,
) -> None:
    """The one thing this tool writes is the one thing it can do without: the run goes on,
    the summary says why the copies were not made, and the two smells that needed them say
    they were not asked rather than reading as quiet."""
    write(tmp_path / "questions.json", [question(94, "european_football_2", TWO_ROWS)])
    missing = "the scratch schema attestql_scratch does not exist and this tool creates none"
    backend = FakeBackend({TWO_ROWS: fake_result(NAME, (("a",), ("b",)))}, scratch_refusal=missing)
    lines = Lines()
    summary = run_audit(options(tmp_path), backend, lines)
    written = summary_of(tmp_path)

    assert summary.exit_status == 0
    assert lines.written[0] == "q94   european_football_2 R-SET  GOLD-ONLY  smells=none"
    assert written["shuffle"]["prepared"] is False
    assert written["shuffle"]["reason"] == f"prepare_shuffled_copies: {missing}"
    assert written["shuffle"]["scratch_schema"] == "attestql_scratch"
    assert backend.executed_shuffled == [], "a rerun ran against the tables themselves"
    assert not (tmp_path / "audit" / "q94").exists(), "nothing fired and nothing was written"


def test_fail_on_smell_is_what_makes_a_heuristic_fail_a_run(tmp_path: Path) -> None:
    write(tmp_path / "questions.json", [question(94, "european_football_2", TWO_ROWS)])
    backend = FakeBackend(
        {TWO_ROWS: fake_result(NAME, (("a",), ("b",)))},
        shuffled_results={TWO_ROWS: fake_result(NAME, (("c",), ("d",)))},
    )
    summary = run_audit(options(tmp_path, fail_on_smell=True), backend, Lines())
    assert summary.exit_status == 1
    assert summary.not_equal == 0


# with predictions


def _defect_backend(**also: Any) -> FakeBackend:
    """The q879 defect: the gold answers Italian and the numeric ordering answers otherwise."""
    return FakeBackend(
        {
            FASTEST_LAP: fake_result(NATIONALITY, (("Italian",),)),
            NUMERIC: fake_result(NATIONALITY, (("Brazilian",),)),
            UNBOUNDED: fake_result(
                NATIONALITY_AND_SPEED, (("Italian", "93.175"), ("Brazilian", "259.870"))
            ),
            **also,
        },
        row_counts={"drivers": 3, "results": 23_179},
        column_types=COLUMN_TYPES,
        censuses={("results", "fastestlapspeed"): ALL_NUMERIC},
    )


def test_the_line_of_a_disagreement_is_the_one_the_adr_writes_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``q879  formula_1   R-ORD  NOT_EQUAL  smells=ordering-over-numeric-text  audit/q879/``"""
    monkeypatch.chdir(tmp_path)
    write(tmp_path / "questions.json", [question(879, "formula_1", FASTEST_LAP)])
    write(tmp_path / "predictions.json", {"879": NUMERIC})
    lines = Lines()
    summary = run_audit(
        options(
            tmp_path,
            out=Path("audit"),
            predictions=tmp_path / "predictions.json",
        ),
        _defect_backend(),
        lines,
    )
    assert lines.written[0] == (
        "q879  formula_1   R-ORD  NOT_EQUAL  smells=ordering-over-numeric-text  audit/q879/"
    )
    assert lines.written[1] == "1 questions: 1 NOT_EQUAL, 0 NOT_COMPARABLE, 1 smells fired"
    assert summary.exit_status == 1


def test_a_disagreement_writes_the_counterexample_both_records_and_the_smells(
    tmp_path: Path,
) -> None:
    write(tmp_path / "questions.json", [question(879, "formula_1", FASTEST_LAP)])
    write(tmp_path / "predictions.json", {"879": NUMERIC})
    summary = run_audit(
        options(tmp_path, predictions=tmp_path / "predictions.json"),
        _defect_backend(),
        Lines(),
    )
    directory = tmp_path / "audit" / "q879"
    for name in (COUNTEREXAMPLE_FILE, GOLD_RECORD_FILE, SECOND_RECORD_FILE, SMELLS_FILE):
        assert (directory / name).is_file(), name
    counterexample = cast(
        "dict[str, Any]",
        json.loads((directory / COUNTEREXAMPLE_FILE).read_text(encoding="utf-8")),
    )
    assert counterexample["verdict"]["result"] == "not_equal"
    assert counterexample["bird_ex"]["value"] == 0
    assert "does not state which of them is wrong" in counterexample["verdict"]["reading"]
    written = summary_of(tmp_path)
    assert written["verdicts"] == {"NOT_EQUAL": 1}
    assert written["smells"]["ordering-over-numeric-text"] == 1
    assert written["predictions"]["statements"] == 1
    assert summary.exit_status == 1


def test_a_question_with_no_prediction_is_audited_gold_only_beside_one_that_has_it(
    tmp_path: Path,
) -> None:
    write(
        tmp_path / "questions.json",
        [question(879, "formula_1", FASTEST_LAP), question(207, "toxicology", ELEMENTS)],
    )
    write(tmp_path / "predictions.json", {"879": NUMERIC})
    backend = _defect_backend(**{ELEMENTS: fake_result(ELEMENT, (("c",),))})
    lines = Lines()
    summary = run_audit(
        options(tmp_path, predictions=tmp_path / "predictions.json"), backend, lines
    )
    assert "NOT_EQUAL" in lines.written[0]
    assert "GOLD-ONLY" in lines.written[1]
    assert summary.verdicts == {"NOT_EQUAL": 1, "GOLD-ONLY": 1}


# what does not stop a run


def test_a_gold_that_does_not_parse_is_one_error_line_and_not_the_end_of_the_run(
    tmp_path: Path,
) -> None:
    write(
        tmp_path / "questions.json",
        [question(1, "financial", "SELECT * FROM ;;"), question(207, "toxicology", ELEMENTS)],
    )
    lines = Lines()
    summary = run_audit(options(tmp_path), _quiet_backend(), lines)
    assert lines.written[0].startswith("q1    financial   ")
    assert "ERROR" in lines.written[0]
    assert "does not parse" in lines.written[0]
    assert "GOLD-ONLY" in lines.written[1]
    assert summary.verdicts == {"ERROR": 1, "GOLD-ONLY": 1}
    assert summary.exit_status == 0, "an error is not a disagreement"
    assert summary_of(tmp_path)["errors"][0]["question_id"] == 1


NO_COLUMNS = "the statement projects no column, so there is no answer to record or compare"


def test_a_prediction_that_projects_no_column_is_that_question_s_error_line(
    tmp_path: Path,
) -> None:
    """A bare ``SELECT`` is what BIRD's gpt-4-turbo predicted for q1481. PostgreSQL accepts
    it and answers one row of no columns, so the question is an error line and the question
    after it decides the status on its own."""
    write(
        tmp_path / "questions.json",
        [question(1481, "toxicology", ELEMENTS), question(879, "formula_1", FASTEST_LAP)],
    )
    write(tmp_path / "predictions.json", {"1481": BARE_SELECT, "879": NUMERIC})
    backend = _defect_backend(
        **{ELEMENTS: fake_result(ELEMENT, (("c",),)), BARE_SELECT: fake_result((), ((),))}
    )
    lines = Lines()
    summary = run_audit(
        options(tmp_path, predictions=tmp_path / "predictions.json"), backend, lines
    )
    written = summary_of(tmp_path)

    assert "ERROR" in lines.written[0]
    assert "projects no column" in lines.written[0]
    assert "NOT_EQUAL" in lines.written[1]
    assert summary.verdicts == {"ERROR": 1, "NOT_EQUAL": 1}
    assert written["errors"] == [{"question_id": 1481, "step": "statement", "message": NO_COLUMNS}]
    assert summary.exit_status == 1, "the question that disagreed decided it alone"


def test_a_gold_that_projects_no_column_is_that_question_s_error_line(tmp_path: Path) -> None:
    """The same refusal on the side nothing was predicted for."""
    write(
        tmp_path / "questions.json",
        [question(1, "financial", BARE_SELECT), question(207, "toxicology", ELEMENTS)],
    )
    backend = FakeBackend(
        {BARE_SELECT: fake_result((), ((),)), ELEMENTS: fake_result(ELEMENT, (("c",), ("o",)))},
        row_counts={"atom": 2},
    )
    lines = Lines()
    summary = run_audit(options(tmp_path), backend, lines)
    written = summary_of(tmp_path)

    assert "ERROR" in lines.written[0]
    assert "projects no column" in lines.written[0]
    assert lines.written[1] == "q207  toxicology  R-SET  GOLD-ONLY  smells=none"
    assert summary.verdicts == {"ERROR": 1, "GOLD-ONLY": 1}
    assert written["errors"] == [{"question_id": 1, "step": "statement", "message": NO_COLUMNS}]
    assert summary.exit_status == 0, "an error is not a disagreement"


class RefusingBackend(FakeBackend):
    """A backend that refuses one statement the way a server refuses a bad column."""

    def __init__(self, refuse: str, **stated: Any) -> None:
        super().__init__(**stated)
        self._refuse = refuse

    def execute(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        if sql == self._refuse:
            raise BackendRefused("execute", 'column "missing" does not exist')
        return super().execute(sql, statement_timeout_seconds=statement_timeout_seconds)


def test_a_statement_the_backend_refuses_is_recorded_and_the_run_goes_on(
    tmp_path: Path,
) -> None:
    refused = "SELECT missing FROM atom"
    write(
        tmp_path / "questions.json",
        [question(1, "financial", refused), question(207, "toxicology", ELEMENTS)],
    )
    backend = RefusingBackend(
        refused,
        results={
            refused: fake_result(ELEMENT, ()),
            ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))),
        },
        row_counts={"atom": 2},
    )
    lines = Lines()
    summary = run_audit(options(tmp_path), backend, lines)
    assert "ERROR" in lines.written[0]
    assert "does not exist" in lines.written[0]
    assert "GOLD-ONLY" in lines.written[1]
    assert summary.errors[0].step == "execute"
    assert summary.exit_status == 0
    assert summary_of(tmp_path)["errors"][0]["question_id"] == 1


class LinesThatTakeTheServerAway(Lines):
    """A writer that loses the connection as soon as the first question has been answered.

    A run's questions are answered one after another over one connection, so between two
    of them is where a server goes away, and a writer is what runs between two of them.
    """

    def __init__(self, backend: FakeBackend, gone: str) -> None:
        super().__init__()
        self._backend = backend
        self._gone = gone

    def line(self, text: str) -> None:
        super().line(text)
        if len(self.written) == 1:
            self._backend.refusing = self._gone


def test_a_server_that_goes_away_mid_run_errors_the_rest_and_still_writes_the_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The connection dies after the first line. The two questions after it are their own
    error lines, the run reaches its end, and the summary a reader opens is on disk."""
    write(
        tmp_path / "questions.json",
        [
            question(1, "toxicology", ELEMENTS),
            question(2, "formula_1", DRIVERS),
            question(3, "european_football_2", TWO_ROWS),
        ],
    )
    gone = "server closed the connection unexpectedly"
    backend = FakeBackend(
        {
            ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))),
            DRIVERS: fake_result(NATIONALITY, (("Italian",),)),
            TWO_ROWS: fake_result(NAME, (("a",), ("b",))),
        },
        row_counts={"atom": 2, "drivers": 3, "players": 2},
    )
    lines = LinesThatTakeTheServerAway(backend, gone)
    summary = run_audit(options(tmp_path), backend, lines)
    written = summary_of(tmp_path)

    assert "GOLD-ONLY" in lines.written[0]
    assert [gone in line for line in lines.written[1:3]] == [True, True]
    assert all("ERROR" in line for line in lines.written[1:3])
    assert summary.verdicts == {"GOLD-ONLY": 1, "ERROR": 2}
    assert [error.question_id for error in summary.errors] == [2, 3]
    assert [error.step for error in summary.errors] == ["schema_digest", "schema_digest"]
    assert [entry["question_id"] for entry in written["errors"]] == [2, 3]
    # One question was audited, so this run is not the run that audited nothing: an error
    # is neither a disagreement nor this tool failing, and the summary is where it is read.
    assert summary.exit_status == 0
    assert backend.dropped == 0, "a dead connection dropped the copies anyway"
    assert "the scratch copies were left behind" in capsys.readouterr().err


def test_a_run_that_answered_no_question_at_all_is_status_two(tmp_path: Path) -> None:
    """It produced no audit, which is what 2 means, and it says so in a summary it wrote."""
    write(tmp_path / "questions.json", [question(1, "toxicology", ELEMENTS)])
    backend = FakeBackend({}, refusing="the connection is closed")
    lines = Lines()
    summary = run_audit(options(tmp_path), backend, lines)
    written = summary_of(tmp_path)

    assert summary.exit_status == 2
    assert "ERROR" in lines.written[0]
    assert written["fixture"]["refused"] == "existing_tables: the connection is closed"
    assert written["fixture"]["schema_digest"] is None
    assert written["shuffle"]["prepared"] is False
    assert len(written["errors"]) == 1


def test_a_gold_naming_a_table_this_database_does_not_hold_is_that_question_s_error(
    tmp_path: Path,
) -> None:
    """The fixture is measured over what is there, the missing name is in the summary, and
    the question that used it fails on its own line with the message the server gives."""
    write(
        tmp_path / "questions.json",
        [question(1, "formula_1", SEASONS), question(207, "toxicology", ELEMENTS)],
    )
    backend = FakeBackend(
        {ELEMENTS: fake_result(ELEMENT, (("c",), ("o",)))},
        row_counts={"atom": 2},
        missing_tables=("seasons",),
    )
    lines = Lines()
    summary = run_audit(options(tmp_path), backend, lines)
    written = summary_of(tmp_path)

    assert "ERROR" in lines.written[0]
    assert 'relation "seasons" does not exist' in lines.written[0]
    assert lines.written[1] == "q207  toxicology  R-SET  GOLD-ONLY  smells=none"
    assert summary.exit_status == 0
    assert written["fixture"]["missing_tables"] == ["seasons"]
    assert written["fixture"]["measured_tables"] == ["atom"]
    assert written["fixture"]["row_counts"] == {"atom": 2}
    assert written["fixture"]["refused"] == ""
    assert backend.existing_table_calls == [("seasons", "atom")]
    assert backend.row_count_calls[0] == ("atom",), "the run measured a table that is not there"
    copied = [(("atom",), "1", DEFAULT_SHUFFLE_ROW_LIMIT)]
    assert backend.prepared == copied, "a table that is not there was copied"


# the exit statuses


def test_a_file_the_run_cannot_read_is_status_two(tmp_path: Path) -> None:
    status = audit(options(tmp_path), _quiet_backend(), Lines())
    assert status == 2


def test_a_dsn_that_names_a_password_is_refused_before_anything_runs() -> None:
    with pytest.raises(SystemExit) as refused:
        parse_arguments(
            [
                "audit",
                "--dsn",
                "host=localhost password=hunter2",
                "--questions",
                "q.json",
                "--out",
                "a",
            ]
        )
    assert refused.value.code == 2


def test_a_dsn_written_as_a_uri_is_refused_and_the_keyword_form_is_named(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``postgresql://user:secret@host/db`` carries the credential in the text itself, so
    the shape is refused rather than its contents inspected, and the refusal repeats none
    of it."""
    with pytest.raises(SystemExit) as refused:
        parse_arguments(
            [
                "audit",
                "--dsn",
                "postgresql://bird:hunter2@localhost:5432/bird",
                "--questions",
                "q.json",
                "--out",
                "a",
            ]
        )
    assert refused.value.code == 2
    message = capsys.readouterr().err
    assert "libpq keyword form" in message
    assert "PGPASSWORD" in message and "~/.pgpass" in message
    assert "hunter2" not in message, "the refusal repeated the credential"


def test_a_uri_that_carries_no_credential_at_all_is_refused_for_being_one() -> None:
    """The rule is the shape and not the contents: a URI is where a password is written."""
    with pytest.raises(SystemExit) as refused:
        parse_arguments(
            ["audit", "--dsn", "postgres://localhost/bird", "--questions", "q.json", "--out", "a"]
        )
    assert refused.value.code == 2


def test_a_scratch_schema_named_by_nothing_is_refused_before_anything_runs() -> None:
    with pytest.raises(SystemExit) as refused:
        parse_arguments(
            [
                "audit",
                "--dsn",
                "host=localhost dbname=bird",
                "--questions",
                "q.json",
                "--out",
                "a",
                "--scratch-schema",
                "   ",
            ]
        )
    assert refused.value.code == 2


def test_the_command_line_states_every_option_the_adr_names() -> None:
    parsed = parse_arguments(
        [
            "audit",
            "--dsn",
            "host=localhost dbname=bird",
            "--questions",
            "mini_dev_postgresql.json",
            "--predictions",
            "preds.json",
            "--out",
            "audit/",
            "--ids",
            "879,207",
            "--fixture-digest",
            "full",
            "--fail-on-smell",
            "--experimental-s2",
            "--plan-variant",
            "--shuffle-seed",
            "7",
            "--shuffle-row-limit",
            "1000",
            "--scratch-schema",
            "bench_scratch",
            "--statement-timeout",
            "60",
            "--data-as-of",
            "2026-09-02T00:00:00+00:00",
        ]
    )
    assert parsed.ids == (879, 207)
    assert parsed.with_content_digests is True
    assert (parsed.fail_on_smell, parsed.experimental_s2, parsed.plan_variant) == (True, True, True)
    assert (parsed.shuffle_seed, parsed.shuffle_row_limit) == (7, 1000)
    assert parsed.scratch_schema == "bench_scratch"
    assert parsed.statement_timeout_seconds == 60
    assert (
        parsed.data_as_of is not None
        and parsed.data_as_of.isoformat() == "2026-09-02T00:00:00+00:00"
    )


def test_the_stated_instant_is_the_one_the_records_carry(tmp_path: Path) -> None:
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    run_audit(
        options(tmp_path, data_as_of=parse_arguments_instant("2026-09-01T12:00:00+00:00")),
        _quiet_backend(),
        Lines(),
    )
    written = summary_of(tmp_path)
    assert written["data_as_of"] == "2026-09-01T12:00:00+00:00"
    assert written["data_as_of_source"] == "--data-as-of"


def parse_arguments_instant(value: str) -> Any:
    """The instant as the command line would have parsed it, through the parser itself."""
    parsed = parse_arguments(
        ["audit", "--dsn", "host=x", "--questions", "q.json", "--out", "a", "--data-as-of", value]
    )
    return parsed.data_as_of


def test_the_console_entry_point_is_the_main_this_module_states() -> None:
    assert callable(main)


# where the question file came from


ORIGIN = "https://example.org/bench/mini_dev_pg.json (commit f65faf4a, 2026-01-18)"
PREDICTIONS_ORIGIN = "https://example.org/runs/predict_mini_dev_gpt.json"


def test_the_stated_origin_of_the_question_file_is_in_the_summary_and_every_record(
    tmp_path: Path,
) -> None:
    """Two files of the same name from two places are two versions of a benchmark. The
    digest alone tells them apart only for someone who has both; the origin says which."""
    other = "SELECT element FROM atom WHERE element = 'c'"
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    write(tmp_path / "preds.json", {"207": other})
    backend = FakeBackend(
        {
            ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))),
            other: fake_result(ELEMENT, (("c",),)),
        },
        row_counts={"atom": 2},
    )
    summary = run_audit(
        options(tmp_path, predictions=tmp_path / "preds.json", questions_origin=ORIGIN),
        backend,
        Lines(),
    )
    assert summary.not_equal == 1
    assert summary_of(tmp_path)["question_set"]["origin"] == ORIGIN
    directory = tmp_path / "audit" / "q207"
    for name in (GOLD_RECORD_FILE, SECOND_RECORD_FILE, COUNTEREXAMPLE_FILE):
        assert ORIGIN in (directory / name).read_text(encoding="utf-8"), name
    record = json.loads((directory / GOLD_RECORD_FILE).read_text(encoding="utf-8"))
    assert record["question"]["question_set"] == f"questions from {ORIGIN}"


def test_without_a_stated_origin_the_summary_says_so_and_the_set_is_the_file_name(
    tmp_path: Path,
) -> None:
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    run_audit(options(tmp_path), _quiet_backend(), Lines())
    assert summary_of(tmp_path)["question_set"]["origin"] is None


def test_the_command_line_takes_the_origin_of_the_question_file() -> None:
    parsed = parse_arguments(
        [
            "audit",
            "--dsn",
            "host=h dbname=d",
            "--questions",
            "q.json",
            "--out",
            "o/",
            "--questions-origin",
            ORIGIN,
        ]
    )
    assert parsed.questions_origin == ORIGIN


def test_the_stated_date_of_the_question_file_is_in_the_summary(tmp_path: Path) -> None:
    """A dataset states a date beside the file it publishes, and the digest alone does not
    say when the copy that was audited was the current one."""
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    run_audit(options(tmp_path, questions_date="2026-01-18"), _quiet_backend(), Lines())
    assert summary_of(tmp_path)["question_set"]["date"] == "2026-01-18"
    run_audit(options(tmp_path), _quiet_backend(), Lines())
    assert summary_of(tmp_path)["question_set"]["date"] is None


def test_the_command_line_takes_the_origin_and_the_date_of_both_files() -> None:
    parsed = parse_arguments(
        [
            "audit",
            "--dsn",
            "host=h dbname=d",
            "--questions",
            "q.json",
            "--out",
            "o/",
            "--questions-origin",
            ORIGIN,
            "--questions-date",
            "2026-01-18",
            "--predictions",
            "p.json",
            "--predictions-origin",
            PREDICTIONS_ORIGIN,
            "--predictions-date",
            "2026-02-01T00:00:00+00:00",
            "--predictions-keyed-by",
            "position",
        ]
    )
    assert parsed.questions_date == "2026-01-18"
    assert parsed.predictions_origin == PREDICTIONS_ORIGIN
    assert parsed.predictions_date == "2026-02-01T00:00:00+00:00"
    assert parsed.predictions_keyed_by == "position"


@pytest.mark.parametrize("flag", ["--questions-date", "--predictions-date"])
def test_a_date_that_is_not_iso_8601_is_refused_before_anything_runs(flag: str) -> None:
    with pytest.raises(SystemExit) as refused:
        parse_arguments(
            ["audit", "--dsn", "host=h", "--questions", "q.json", "--out", "a", flag, "last week"]
        )
    assert refused.value.code == 2


def test_the_predictions_file_is_recorded_with_its_digest_origin_and_date(
    tmp_path: Path,
) -> None:
    """The gold and the prediction come out of two files, and each record names its own."""
    other = "SELECT element FROM atom WHERE element = 'c'"
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    predictions = write(tmp_path / "preds.json", {"207": other})
    backend = FakeBackend(
        {ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))), other: fake_result(ELEMENT, (("c",),))},
        row_counts={"atom": 2},
    )
    summary = run_audit(
        options(
            tmp_path,
            predictions=predictions,
            questions_origin=ORIGIN,
            questions_date="2026-01-18",
            predictions_origin=PREDICTIONS_ORIGIN,
            predictions_date="2026-02-01",
        ),
        backend,
        Lines(),
    )
    written = summary_of(tmp_path)["predictions"]

    assert summary.not_equal == 1
    assert written["path"] == str(predictions)
    assert written["digest"] == sha256_of(predictions)
    assert written["origin"] == PREDICTIONS_ORIGIN
    assert written["date"] == "2026-02-01"
    assert written["keyed_by"] == "question-id"
    assert written["positions_unused"] == []
    assert written["statements"] == 1

    directory = tmp_path / "audit" / "q207"
    gold = json.loads((directory / GOLD_RECORD_FILE).read_text(encoding="utf-8"))
    second = json.loads((directory / SECOND_RECORD_FILE).read_text(encoding="utf-8"))
    assert gold["statement_source"] == {
        "path": str(tmp_path / "questions.json"),
        "digest": sha256_of(tmp_path / "questions.json"),
        "origin": ORIGIN,
        "date": "2026-01-18",
    }
    assert second["statement_source"] == {
        "path": str(predictions),
        "digest": sha256_of(predictions),
        "origin": PREDICTIONS_ORIGIN,
        "date": "2026-02-01",
    }
    counterexample = json.loads((directory / COUNTEREXAMPLE_FILE).read_text(encoding="utf-8"))
    assert counterexample["sources"] == {
        "gold": gold["statement_source"],
        "second": second["statement_source"],
    }


def test_a_gold_only_record_names_the_question_file_as_the_source_of_its_statement(
    tmp_path: Path,
) -> None:
    """There is no second statement, so there is one file and the record names it."""
    questions = write(tmp_path / "questions.json", [question(94, "european_football_2", TWO_ROWS)])
    backend = FakeBackend(
        {TWO_ROWS: fake_result(NAME, (("a",), ("b",)))},
        shuffled_results={TWO_ROWS: fake_result(NAME, (("c",), ("d",)))},
    )
    run_audit(options(tmp_path), backend, Lines())
    record = json.loads((tmp_path / "audit" / "q94" / GOLD_RECORD_FILE).read_text(encoding="utf-8"))
    assert record["statement_source"]["path"] == str(questions)
    assert record["statement_source"]["digest"] == sha256_of(questions)
    assert record["statement_source"]["origin"] is None
    assert summary_of(tmp_path)["predictions"] is None


# predictions keyed by position


def _duplicated_question_file(tmp_path: Path) -> Path:
    """Three entries under two ids, which is the shape of BIRD's own Mini-Dev file: the
    entry of question 207 is written twice and every position still answers something."""
    entry = question(207, "toxicology", ELEMENTS)
    return write(
        tmp_path / "questions.json",
        [entry, question(94, "european_football_2", TWO_ROWS), dict(entry)],
    )


def _two_question_backend() -> FakeBackend:
    return FakeBackend(
        {
            ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))),
            ELEMENTS_ONE_ROW: fake_result(ELEMENT, (("c",),)),
            TWO_ROWS: fake_result(NAME, (("a",), ("b",))),
        },
        row_counts={"atom": 2, "players": 2},
    )


def test_a_prediction_file_keyed_by_position_is_paired_by_position(tmp_path: Path) -> None:
    """BIRD's own files hold "0" to "499": the position of the entry the prediction
    answers, not the question's id. Two positions name question 207 here, and the lower
    one is the prediction that is compared."""
    _duplicated_question_file(tmp_path)
    write(
        tmp_path / "preds.json",
        {"0": ELEMENTS_ONE_ROW, "1": TWO_ROWS, "2": "SELECT element FROM atom LIMIT 0"},
    )
    summary = run_audit(
        options(
            tmp_path,
            predictions=tmp_path / "preds.json",
            predictions_keyed_by="position",
        ),
        _two_question_backend(),
        Lines(),
    )
    written = summary_of(tmp_path)

    assert summary.verdicts == {"NOT_EQUAL": 1, "EQUAL": 1}
    assert written["predictions"]["keyed_by"] == "position"
    assert written["predictions"]["statements"] == 3
    assert written["predictions"]["positions_unused"] == [2]
    second = json.loads(
        (tmp_path / "audit" / "q207" / SECOND_RECORD_FILE).read_text(encoding="utf-8")
    )
    assert second["executed_sql"] == ELEMENTS_ONE_ROW, "position 0's prediction was compared"


def test_a_position_no_entry_of_the_question_file_has_stops_the_run(tmp_path: Path) -> None:
    _duplicated_question_file(tmp_path)
    write(tmp_path / "preds.json", {"3": ELEMENTS_ONE_ROW})
    with pytest.raises(ToolError, match="the key 3, which is no entry of"):
        run_audit(
            options(
                tmp_path,
                predictions=tmp_path / "preds.json",
                predictions_keyed_by="position",
            ),
            _two_question_backend(),
            Lines(),
        )


def test_keys_that_are_the_positions_of_a_file_keyed_otherwise_are_refused(
    tmp_path: Path,
) -> None:
    """Read as question ids, a BIRD file pairs its predictions with whichever questions
    happen to be numbered 0, 1, 2, and with nothing elsewhere. That is not a reading this
    tool guesses at."""
    _duplicated_question_file(tmp_path)
    write(tmp_path / "preds.json", {"0": ELEMENTS_ONE_ROW, "1": TWO_ROWS, "2": ELEMENTS})
    with pytest.raises(ToolError, match="--predictions-keyed-by position"):
        run_audit(
            options(tmp_path, predictions=tmp_path / "preds.json"),
            _two_question_backend(),
            Lines(),
        )


def test_a_question_file_whose_ids_are_the_positions_is_read_either_way(tmp_path: Path) -> None:
    """When the ids are 0 to N-1 the two readings pair the same statements, and the full
    BIRD dev set is numbered that way, so nothing is refused."""
    write(
        tmp_path / "questions.json",
        [question(0, "toxicology", ELEMENTS), question(1, "european_football_2", TWO_ROWS)],
    )
    write(tmp_path / "preds.json", {"0": ELEMENTS_ONE_ROW, "1": TWO_ROWS})
    summary = run_audit(
        options(tmp_path, predictions=tmp_path / "preds.json"),
        _two_question_backend(),
        Lines(),
    )
    assert summary.verdicts == {"NOT_EQUAL": 1, "EQUAL": 1}
    assert summary_of(tmp_path)["predictions"]["positions_unused"] == []
