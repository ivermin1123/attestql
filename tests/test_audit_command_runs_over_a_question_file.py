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

import dataclasses
import hashlib
import importlib.metadata
import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.backend import (
    BackendRefused,
    PlannerStatistics,
    StatementTimedOut,
    TableName,
    TextCensus,
)
from attestql.audit.cli import (
    MARKER_FILE,
    SMELLS_FILE,
    SUMMARY_FILE,
    AuditOptions,
    NoStatement,
    ToolError,
    audit,
    main,
    parse_arguments,
    read_predictions,
    read_questions,
    run_audit,
)
from attestql.audit.compare import COUNTEREXAMPLE_FILE, GOLD_RECORD_FILE, SECOND_RECORD_FILE
from attestql.audit.engines import POSTGRESQL, SQLITE
from attestql.audit.fixture import CACHE_FILE
from attestql.audit.parse import ParsedStatement
from attestql.audit.smells import DEFAULT_SHUFFLE_ROW_LIMIT, NUMERIC_TEXT
from attestql.audit.statements import (
    GRAMMAR_VERSION,
    POSTGAST_VERSION,
    VALIDATOR_VERSION,
    parse_statement,
)
from attestql.kernel.types import ExecutionResult
from tests.audit_fakes import SETTINGS, FakeBackend, fake_result

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
SEALED = "SELECT secret FROM sealed"
DRIVERS = "SELECT nationality FROM drivers"
DRIVERS_ORDERED = "SELECT nationality FROM drivers ORDER BY nationality ASC"
BARE_SELECT = "SELECT"

NATIONALITY = (("nationality", "text"),)
NATIONALITY_AND_SPEED = (("nationality", "text"), ("attestql_ordering_key_0", "text"))
ELEMENT = (("element", "text"),)
NAME = (("name", "text"),)

ATOM_TABLE = TableName("", "atom")
DRIVERS_TABLE = TableName("", "drivers")
RESULTS_TABLE = TableName("", "results")
SEALED_TABLE = TableName("", "sealed")
SEASONS_TABLE = TableName("", "seasons")
"""The tables these questions name, as they name them. No gold here writes a schema, so
the catalogue is asked under the bare names and the summary states them bare."""

COLUMN_TYPES = {
    RESULTS_TABLE: {"fastestlapspeed": "text", "laps": "bigint", "driverid": "bigint"},
    DRIVERS_TABLE: {"driverid": "bigint", "nationality": "text"},
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


def test_an_entry_that_holds_no_statement_is_read_as_one_and_does_not_refuse_the_file(
    tmp_path: Path,
) -> None:
    """BIRD dev's own ``predict_dev.json`` writes the number 0 where the model produced
    nothing, and an empty string where it produced only the marker it appends. Both are
    questions the model did not answer and neither is a defect in the file, so the file is
    read and the two entries carry what they held.

    ``false`` is not the number 0, though Python counts a boolean as one: a file that wrote
    it wrote something this tool has no reading for, and it is refused with everything else
    that is not SQL."""
    path = write(
        tmp_path / "predictions.json",
        {
            "1481": 0,
            "879": "",
            "900": "\t----- bird -----\ttoxicology",
            "207": f"{ELEMENTS}\t----- bird -----\ttoxicology",
        },
    )

    assert dict(read_predictions(path)) == {
        1481: NoStatement("the number 0"),
        879: NoStatement("an empty string"),
        900: NoStatement("an empty string"),
        207: ELEMENTS,
    }
    refused = write(tmp_path / "boolean.json", {"879": False})
    with pytest.raises(ToolError, match="bool and a prediction is SQL"):
        read_predictions(refused)


# gold only


def _quiet_backend() -> FakeBackend:
    return FakeBackend({ELEMENTS: fake_result(ELEMENT, (("c",), ("o",)))}, row_counts={"atom": 2})


def test_a_gold_only_run_with_nothing_to_report_writes_no_directory(tmp_path: Path) -> None:
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    lines = Lines()
    summary = run_audit(options(tmp_path), _quiet_backend(), lines)
    assert lines.written[0] == "q207  toxicology  R-SET  GOLD-ONLY  smells=none"
    assert lines.written[1] == (
        "1 questions: 0 NOT_EQUAL, 0 smells fired, 0 timed out (0 gold, 0 prediction)"
    )
    assert summary.exit_status == 0
    assert not (tmp_path / "audit" / "q207").exists()
    written = summary_of(tmp_path)
    assert written["verdicts"] == {"GOLD-ONLY": 1}
    assert written["credited_but_not_equal"] is None, "nothing was compared with BIRD's reading"
    assert written["data_as_of_source"] == "the instant the run started"
    assert written["fixture"]["row_counts"] == {"atom": 2}
    assert written["shuffle"]["prepared"] is True
    assert written["timed_out"] == {"gold": [], "prediction": []}, (
        "the bound was in force over the one statement this run sent, and nothing reached it"
    )


def test_the_summary_states_the_planner_statistics_the_run_s_plans_were_chosen_from(
    tmp_path: Path,
) -> None:
    """Two runs of the shuffle probe over the same data can disagree because the planner's
    statistics moved between them, and the tool never runs ANALYZE. So the run records what
    the plans were chosen from, per measured table, and two summaries can be diffed."""
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    backend = FakeBackend(
        {ELEMENTS: fake_result(ELEMENT, (("c",), ("o",)))},
        row_counts={"atom": 2},
        planner_statistics={
            TableName("", "atom"): PlannerStatistics(
                last_analyze="2026-09-04 09:00:00+00",
                last_autoanalyze=None,
                n_mod_since_analyze=12,
            )
        },
    )
    run_audit(options(tmp_path), backend, Lines())
    written = summary_of(tmp_path)

    assert written["planner_statistics"] == {
        "atom": {
            "last_analyze": "2026-09-04 09:00:00+00",
            "last_autoanalyze": None,
            "n_mod_since_analyze": 12,
        }
    }
    assert backend.planner_statistics_calls == [(TableName("", "atom"),)] * 2, (
        "once with the fixture, for the summary, and again at smell time for the statement's own"
    )


def test_the_summary_names_the_session_and_the_grammar_the_run_was_judged_by(
    tmp_path: Path,
) -> None:
    """Two summaries that disagree were produced by some server and some grammar, and one
    that names neither leaves a reader with nothing to compare them by. The gather recorded
    here is the session's own: every statement runs with it off, and this says what the
    server would otherwise have been free to do."""
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    run_audit(options(tmp_path), _quiet_backend(), Lines())
    written = summary_of(tmp_path)
    settings = written["session_settings"]
    recorded = settings["recorded"]

    assert settings["engine"] == SETTINGS.engine
    assert set(settings) == {"engine", "recorded"}, (
        "the seven that decide comparability are on each record, under the engine that "
        "holds them; the summary states the session this run found and the engine it found it on"
    )
    assert written["settings"]["work_mem"] == SETTINGS.work_mem
    assert written["settings"]["hash_mem_multiplier"] == SETTINGS.hash_mem_multiplier
    assert recorded == dict(SETTINGS.recorded)
    assert recorded["max_parallel_workers_per_gather"] == "2"
    assert recorded["server_version"].startswith("16.4")
    assert recorded["server_version_num"] == "160004"
    assert written["parser"] == {
        "validator": VALIDATOR_VERSION,
        "postgast": POSTGAST_VERSION,
        "grammar_version": GRAMMAR_VERSION,
    }
    assert isinstance(written["parser"]["grammar_version"], int)
    assert re.fullmatch(r"\d+\.\d+.*", POSTGAST_VERSION), POSTGAST_VERSION


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
        censuses={(RESULTS_TABLE, "fastestlapspeed"): ALL_NUMERIC},
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
    assert lines.written[1] == (
        "1 questions: 1 NOT_EQUAL, 1 smells fired, 0 credited by BIRD but NOT_EQUAL "
        "(0 multiplicity, 0 type, 0 order, 0 truncation), 0 timed out (0 gold, 0 prediction)"
    )
    # Both records of a comparison are built from one session and one fixture, so no run
    # reaches NOT_COMPARABLE and the line does not count what cannot happen.
    assert "NOT_COMPARABLE" not in lines.written[1]
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


def _two_questions_with_predictions(tmp_path: Path) -> FakeBackend:
    """Two questions, each with a prediction: the shape that asks for the same thing twice."""
    write(
        tmp_path / "questions.json",
        [question(879, "formula_1", FASTEST_LAP), question(207, "toxicology", ELEMENTS)],
    )
    write(tmp_path / "predictions.json", {"879": NUMERIC, "207": ELEMENTS_ONE_ROW})
    return _defect_backend(
        **{
            ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))),
            ELEMENTS_ONE_ROW: fake_result(ELEMENT, (("c",),)),
        }
    )


def test_the_session_is_read_from_the_server_once_for_a_whole_run(tmp_path: Path) -> None:
    """The summary and every record state one read of the session and not one each.

    Two reads are two moments, and a run whose records disagree with its own summary about
    the session they ran under has said two things about one run.
    """
    backend = _two_questions_with_predictions(tmp_path)
    run_audit(options(tmp_path, predictions=tmp_path / "predictions.json"), backend, Lines())
    assert backend.settings_calls == 1, "the session was read again for every statement"


def test_every_statement_of_a_run_is_parsed_once_by_the_engine_the_run_chose(
    tmp_path: Path,
) -> None:
    """A parse is a function of its text, so a second one is not a second opinion.

    The golds are parsed before the data is measured, because the tables to measure are
    read off those parses, and each prediction is parsed where its comparison is asked for.
    Counted through an engine of the test's own, which is the seam a second engine arrives
    on: nothing below the options asks which engine is running.
    """
    parses: dict[str, int] = {}

    def counting(sql: str, /) -> ParsedStatement:
        parses[sql] = parses.get(sql, 0) + 1
        return parse_statement(sql)

    backend = _two_questions_with_predictions(tmp_path)
    run_audit(
        options(
            tmp_path,
            predictions=tmp_path / "predictions.json",
            engine=dataclasses.replace(POSTGRESQL, parse=counting),
        ),
        backend,
        Lines(),
    )
    assert parses == {FASTEST_LAP: 1, NUMERIC: 1, ELEMENTS: 1, ELEMENTS_ONE_ROW: 1}


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


def test_a_rerun_into_the_same_out_does_not_leave_the_run_before_it_to_be_read(
    tmp_path: Path,
) -> None:
    """The directory is one run's evidence: a question directory the run before it wrote and
    this one did not is gone, the cache it left is not, and neither is anything a reader put
    there."""
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    write(tmp_path / "predictions.json", {"207": ELEMENTS_ONE_ROW})
    backend = FakeBackend(
        {
            ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))),
            ELEMENTS_ONE_ROW: fake_result(ELEMENT, (("c",),)),
        },
        row_counts={"atom": 2},
    )
    first = run_audit(
        options(tmp_path, predictions=tmp_path / "predictions.json"), backend, Lines()
    )
    out = tmp_path / "audit"
    assert first.exit_status == 1
    assert (out / "q207" / COUNTEREXAMPLE_FILE).is_file()
    assert (out / MARKER_FILE).is_file(), "the run left nothing saying the directory is its own"
    schema_reads = len(backend.schema_digest_calls)

    notes = out / "notes.md"
    notes.write_text("a reader's own", encoding="utf-8")
    (out / "questions").mkdir()

    second = run_audit(options(tmp_path), backend, Lines())
    assert not (out / "q207").exists(), "the counterexample of the run before is still readable"
    assert second.verdicts == {"GOLD-ONLY": 1}
    written = summary_of(tmp_path)
    assert written["verdicts"] == {"GOLD-ONLY": 1}
    assert written["predictions"] is None
    assert notes.read_text(encoding="utf-8") == "a reader's own"
    assert (out / "questions").is_dir()
    assert (out / CACHE_FILE).is_file()
    assert (out / MARKER_FILE).is_file(), "the marker is gone after a rerun cleared the directory"
    assert backend.row_count_calls == [(ATOM_TABLE,)], "the data was measured twice"
    assert len(backend.schema_digest_calls) > schema_reads, (
        "the schema is read from the server every run"
    )


def test_a_directory_this_tool_never_wrote_to_is_refused_with_nothing_removed(
    tmp_path: Path,
) -> None:
    """A reader who points ``--out`` at a directory of their own keeps every file in it: the
    run is refused before anything is read, written or printed, and not after."""
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    out = tmp_path / "audit"
    (out / "q1").mkdir(parents=True)
    theirs = out / "q1" / "notes.txt"
    theirs.write_text("a reader's own working notes", encoding="utf-8")
    summary = write(out / SUMMARY_FILE, {"run_id": "not-this-tool's"})
    before = (theirs.read_bytes(), summary.read_bytes())

    backend = _quiet_backend()
    lines = Lines()
    with pytest.raises(ToolError) as refused:
        run_audit(options(tmp_path), backend, lines)

    assert str(out) in str(refused.value)
    assert MARKER_FILE in str(refused.value)
    assert (theirs.read_bytes(), summary.read_bytes()) == before
    assert sorted(child.name for child in out.iterdir()) == ["q1", SUMMARY_FILE]
    assert not (out / MARKER_FILE).exists()
    assert not (out / CACHE_FILE).exists()
    assert backend.executed == [], "the run reached the backend before it refused"
    assert lines.written == [], "the run printed a line before it refused"


def test_an_empty_directory_is_taken_over_and_marked_as_this_tool_s(tmp_path: Path) -> None:
    """An empty directory is as safe to write to as one that is not there yet, and the run
    leaves the marker that lets the next run clear it."""
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    out = tmp_path / "audit"
    out.mkdir()

    summary = run_audit(options(tmp_path), _quiet_backend(), Lines())

    assert summary.exit_status == 0
    assert summary_of(tmp_path)["verdicts"] == {"GOLD-ONLY": 1}
    marker = (out / MARKER_FILE).read_text(encoding="utf-8")
    assert marker.strip().splitlines() == [marker.strip()], "the marker is more than one line"
    assert SUMMARY_FILE in marker


class Watching(Lines):
    """A writer that says, at every line it prints, whether ``summary.json`` was on disk.

    The summary of the run before this one has to be gone before this one prints anything,
    and a writer is what runs while the questions are being answered.
    """

    def __init__(self, summary: Path) -> None:
        super().__init__()
        self._summary = summary
        self.summary_there: list[bool] = []

    def line(self, text: str) -> None:
        self.summary_there.append(self._summary.exists())
        super().line(text)


def test_the_summary_of_the_run_before_is_gone_before_this_one_prints_a_line(
    tmp_path: Path,
) -> None:
    """Removed when the run starts and not when it ends: a run that dies halfway leaves no
    summary of another run behind for a reader to open as its own."""
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    out = tmp_path / "audit"
    out.mkdir()
    (out / MARKER_FILE).write_text("written by an earlier audit\n", encoding="utf-8")
    write(out / SUMMARY_FILE, {"run_id": "audit-the-one-before"})
    writer = Watching(out / SUMMARY_FILE)
    run_audit(options(tmp_path), _quiet_backend(), writer)
    assert writer.summary_there[0] is False, "the summary of the run before outlived its start"
    assert summary_of(tmp_path)["run_id"] != "audit-the-one-before"


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
    assert "prediction: the statement projects no column" in lines.written[0]
    assert written["errors"] == [
        {"question_id": 1481, "side": "prediction", "step": "statement", "message": NO_COLUMNS}
    ]
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
    assert "gold: the statement projects no column" in lines.written[0]
    assert written["errors"] == [
        {"question_id": 1, "side": "gold", "step": "statement", "message": NO_COLUMNS}
    ]
    assert summary.exit_status == 0, "an error is not a disagreement"


HELD_NOTHING = "the predictions file holds {held} and no statement for this question"


def test_a_prediction_entry_that_holds_no_statement_is_that_question_s_error_line(
    tmp_path: Path,
) -> None:
    """The shape of BIRD dev's own ``predict_dev.json``: the number 0 where the model
    produced nothing, an empty string, and an entry that is the marker it appends and
    nothing before it. Each of those questions is one error line naming the side the file
    answers for and what it held there, and the question the file did predict for is
    compared and decides the status on its own.

    The whole file is not refused for any of them. A prediction file is a run of a model
    over a benchmark, and a tool that stopped at the first question the model skipped would
    report nothing about the ones it answered."""
    write(
        tmp_path / "questions.json",
        [
            question(1481, "toxicology", ELEMENTS_ONE_ROW),
            question(879, "formula_1", DRIVERS),
            question(900, "formula_1", SEASONS),
            question(207, "toxicology", ELEMENTS),
        ],
    )
    write(
        tmp_path / "predictions.json",
        {
            "1481": 0,
            "879": "",
            "900": "\t----- bird -----\ttoxicology",
            "207": DISTINCT_ELEMENTS,
        },
    )
    backend = FakeBackend(
        {
            ELEMENTS: fake_result(ELEMENT, (("c",), ("c",), ("o",))),
            DISTINCT_ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))),
        },
        row_counts={"atom": 3},
    )
    lines = Lines()
    summary = run_audit(
        options(tmp_path, predictions=tmp_path / "predictions.json"), backend, lines
    )
    written = summary_of(tmp_path)
    zero = HELD_NOTHING.format(held="the number 0")
    empty = HELD_NOTHING.format(held="an empty string")

    assert f"prediction: {zero}" in lines.written[0]
    assert [f"prediction: {empty}" in line for line in lines.written[1:3]] == [True, True]
    assert all("ERROR" in line for line in lines.written[:3])
    assert "NOT_EQUAL" in lines.written[3]
    assert summary.verdicts == {"ERROR": 3, "NOT_EQUAL": 1}
    assert written["errors"] == [
        {"question_id": 1481, "side": "prediction", "step": "statement", "message": zero},
        {"question_id": 879, "side": "prediction", "step": "statement", "message": empty},
        {"question_id": 900, "side": "prediction", "step": "statement", "message": empty},
    ]
    assert written["predictions"]["statements"] == 4, "every entry of the file was read"
    assert summary.exit_status == 1, "the question that was compared decided it alone"


def test_a_fixture_the_run_cannot_measure_names_the_run_and_not_either_statement(
    tmp_path: Path,
) -> None:
    """The measurement both records are made under is neither statement's, so the error line
    says so: an operator reading ``gold`` here would go and read a statement that never ran,
    where a GRANT on the table is what repairs it."""
    write(tmp_path / "questions.json", [question(2, "formula_1", SEALED)])
    write(tmp_path / "predictions.json", {"2": SEALED})
    backend = FakeBackend({}, unreadable_tables=(SEALED_TABLE,))
    lines = Lines()
    summary = run_audit(
        options(tmp_path, predictions=tmp_path / "predictions.json"), backend, lines
    )
    written = summary_of(tmp_path)

    assert "ERROR" in lines.written[0]
    assert "run: row_counts: permission denied for table sealed" in lines.written[0]
    assert summary.errors[0].side == "run"
    assert written["errors"][0]["side"] == "run"
    assert written["errors"][0]["step"] == "row_counts"


# what BIRD credits and this tool rejects


DISTINCT_ELEMENTS = "SELECT DISTINCT element FROM atom"


def test_a_record_states_the_timeout_its_statement_ran_under_and_the_summary_the_run_s(
    tmp_path: Path,
) -> None:
    """Two statements of one bound, and a question that ended in a cancellation needs both.

    The summary states what the run was given on the command line. Each record states what
    its own statement ran under, taken from the execution: the PostgreSQL backend reads that
    back inside the transaction and refuses to return rows when it is not what it set, which
    is why the two are one number here and why a record is worth reading for it.
    """
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    write(tmp_path / "predictions.json", {"207": DISTINCT_ELEMENTS})
    backend = FakeBackend(
        {
            ELEMENTS: fake_result(ELEMENT, (("c",), ("c",), ("o",)), timeout_ms=45_000),
            DISTINCT_ELEMENTS: fake_result(ELEMENT, (("c",), ("o",)), timeout_ms=45_000),
        },
        row_counts={"atom": 3},
    )
    run_audit(
        options(
            tmp_path,
            predictions=tmp_path / "predictions.json",
            statement_timeout_seconds=45,
        ),
        backend,
        Lines(),
    )

    for name in (GOLD_RECORD_FILE, SECOND_RECORD_FILE):
        record = json.loads((tmp_path / "audit" / "q207" / name).read_text(encoding="utf-8"))
        assert record["result"]["statement_timeout_ms"] == 45_000, name
    assert summary_of(tmp_path)["settings"]["statement_timeout_seconds"] == 45
    assert backend.executed[0] == (ELEMENTS, 45), "the bound the run was given is what was set"


def test_a_prediction_bird_credits_and_this_tool_rejects_is_counted_by_mechanism(
    tmp_path: Path,
) -> None:
    """``set(predicted) == set(gold)`` scores this pair 1 and the typed multiset does not:
    the gold holds one row twice and the prediction holds it once. The line and the file say
    how many of those a run found and what makes them, which is the whole point of running
    both readings over one pair of results. The file also says what the third reading makes
    of the same pair: the test-suite evaluator counts rows, so it refuses this one with the
    tool rather than crediting it with the benchmark."""
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    write(tmp_path / "predictions.json", {"207": DISTINCT_ELEMENTS})
    backend = FakeBackend(
        {
            ELEMENTS: fake_result(ELEMENT, (("c",), ("c",), ("o",))),
            DISTINCT_ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))),
        },
        row_counts={"atom": 3},
    )
    lines = Lines()
    summary = run_audit(
        options(tmp_path, predictions=tmp_path / "predictions.json"), backend, lines
    )
    written = summary_of(tmp_path)
    counterexample = json.loads(
        (tmp_path / "audit" / "q207" / COUNTEREXAMPLE_FILE).read_text(encoding="utf-8")
    )

    assert lines.written[1] == (
        "1 questions: 1 NOT_EQUAL, 0 smells fired, 1 credited by BIRD but NOT_EQUAL "
        "(1 multiplicity, 0 type, 0 order, 0 truncation), 0 timed out (0 gold, 0 prediction)"
    )
    assert summary.credited_but_not_equal is not None
    assert summary.credited_but_not_equal.total == 1
    assert written["credited_but_not_equal"] == {
        "total": 1,
        "by_mechanism": {
            "multiplicity": 1,
            "type": 0,
            "order": 0,
            "truncation": 0,
            "other": 0,
        },
        "by_test_suite_ex": {"1": 0, "0": 1},
    }
    assert counterexample["mechanism"]["class"] == "multiplicity"
    assert counterexample["bird_ex"]["value"] == 1
    assert counterexample["test_suite_ex"]["value"] == 0


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


PAST_THE_BOUND = "execute: the statement ran past its 30s timeout"
"""The step and the message a statement the bound stopped reaches the line under, in the
words the SQLite backend writes; PostgreSQL writes the server's own. Neither moves for the
count below: what the summary counts it by is the type the backend raised."""


class BackendPastItsBound(FakeBackend):
    """A backend whose bound runs out on the statements a test names, and on no other."""

    def __init__(self, past_the_bound: tuple[str, ...], **stated: Any) -> None:
        super().__init__(**stated)
        self._past_the_bound = set(past_the_bound)

    def execute(self, sql: str, *, statement_timeout_seconds: int) -> ExecutionResult:
        if sql in self._past_the_bound:
            raise StatementTimedOut(
                statement_timeout_seconds,
                f"the statement ran past its {statement_timeout_seconds}s timeout",
            )
        return super().execute(sql, statement_timeout_seconds=statement_timeout_seconds)


def test_a_statement_the_bound_stopped_is_counted_under_the_side_that_ran_it(
    tmp_path: Path,
) -> None:
    """A benchmark whose golds do not finish in the time given and one whose predictions do
    not are two findings, so the count is kept by side the way the error line is. Both are
    still error lines with the engine's own message: what a longer bound would have changed
    is which questions were compared, and that is what the last line now states."""
    write(
        tmp_path / "questions.json",
        [
            question(1, "formula_1", SEASONS),
            question(207, "toxicology", ELEMENTS),
            question(3, "formula_1", DRIVERS),
        ],
    )
    write(
        tmp_path / "predictions.json",
        {"1": SEASONS, "207": DISTINCT_ELEMENTS, "3": DRIVERS_ORDERED},
    )
    backend = BackendPastItsBound(
        (SEASONS, DISTINCT_ELEMENTS),
        results={
            ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))),
            DRIVERS: fake_result(NATIONALITY, (("Italian",), ("Kenyan",))),
            DRIVERS_ORDERED: fake_result(NATIONALITY, (("Italian",), ("Kenyan",))),
        },
        row_counts={"atom": 2, "drivers": 2, "seasons": 0},
    )
    lines = Lines()
    summary = run_audit(
        options(tmp_path, predictions=tmp_path / "predictions.json"), backend, lines
    )
    written = summary_of(tmp_path)

    assert f"gold: {PAST_THE_BOUND}" in lines.written[0]
    assert f"prediction: {PAST_THE_BOUND}" in lines.written[1]
    assert summary.timed_out == {"gold": (1,), "prediction": (207,)}
    assert summary.timed_out_total == 2
    assert lines.written[-1].endswith(", 2 timed out (1 gold, 1 prediction)")
    assert written["timed_out"] == {"gold": [1], "prediction": [207]}
    assert written["errors"] == [
        {"question_id": 1, "side": "gold", "step": "execute", "message": PAST_THE_BOUND},
        {"question_id": 207, "side": "prediction", "step": "execute", "message": PAST_THE_BOUND},
    ], "a question the bound stopped is an error line like any other, and says so twice"
    assert summary.verdicts == {"ERROR": 2, "EQUAL": 1}
    assert summary.exit_status == 0, "the question that was compared decided it alone"


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
        missing_tables=(SEASONS_TABLE,),
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
    assert backend.existing_table_calls == [(SEASONS_TABLE, ATOM_TABLE)]
    assert backend.row_count_calls[0] == (ATOM_TABLE,), "the run measured a table that is not there"
    copied = [((ATOM_TABLE,), "1", DEFAULT_SHUFFLE_ROW_LIMIT)]
    assert backend.prepared == copied, "a table that is not there was copied"


def test_a_gold_naming_a_table_this_login_may_not_read_is_not_one_that_is_not_there(
    tmp_path: Path,
) -> None:
    """A table nobody loaded is repaired in the question file and one nobody granted with a
    GRANT, so the summary names them under two words and the operator knows which to fix."""
    write(
        tmp_path / "questions.json",
        [
            question(1, "formula_1", SEASONS),
            question(2, "formula_1", SEALED),
            question(207, "toxicology", ELEMENTS),
        ],
    )
    backend = FakeBackend(
        {ELEMENTS: fake_result(ELEMENT, (("c",), ("o",)))},
        row_counts={"atom": 2},
        missing_tables=(SEASONS_TABLE,),
        unreadable_tables=(SEALED_TABLE,),
    )
    lines = Lines()
    summary = run_audit(options(tmp_path), backend, lines)
    written = summary_of(tmp_path)

    assert 'relation "seasons" does not exist' in lines.written[0]
    assert "permission denied for table sealed" in lines.written[1]
    assert lines.written[2] == "q207  toxicology  R-SET  GOLD-ONLY  smells=none"
    assert summary.exit_status == 0
    assert written["fixture"]["missing_tables"] == ["seasons"]
    assert written["fixture"]["unreadable_tables"] == ["sealed"]
    assert written["fixture"]["measured_tables"] == ["atom"]
    assert backend.row_count_calls[0] == (ATOM_TABLE,), "the run measured a table it cannot read"


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


@pytest.mark.parametrize(
    "path", ["/data/password/bird_dev.sqlite", "/data/http://mirror/bird_dev.sqlite"]
)
def test_a_sqlite_file_is_not_refused_for_what_would_carry_a_credential_in_a_dsn(
    path: str,
) -> None:
    """Under ``--engine sqlite`` the value is a path, so neither refusal above is about it: a
    directory called ``password`` is a directory somebody made, and ``://`` inside a path is
    not a connection string. The rule belongs to the engine, so it is asked of the engine the
    run named."""
    parsed = parse_arguments(
        ["audit", "--engine", "sqlite", "--dsn", path, "--questions", "q.json", "--out", "a"]
    )

    assert parsed.dsn == path
    assert parsed.engine is SQLITE


@pytest.mark.parametrize(
    "dsn", ["postgresql://bird:hunter2@localhost/bird", "host=localhost password=hunter2"]
)
def test_the_same_two_values_are_still_refused_when_the_run_names_postgresql(dsn: str) -> None:
    """The refusals move with the engine and are not weakened by the second one arriving."""
    with pytest.raises(SystemExit) as refused:
        parse_arguments(
            ["audit", "--engine", "postgresql", "--dsn", dsn, "--questions", "q.json", "--out", "a"]
        )

    assert refused.value.code == 2


def test_a_dsn_that_is_empty_is_refused_whichever_engine_was_named() -> None:
    """No engine is named by nothing, so this one is asked before the engine's own rule."""
    for engine in ("postgresql", "sqlite"):
        with pytest.raises(SystemExit) as refused:
            parse_arguments(
                ["audit", "--engine", engine, "--dsn", "  ", "--questions", "q.json", "--out", "a"]
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


def test_the_version_the_command_prints_is_the_release_that_is_installed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Read off the installed distribution rather than stated in the source, so that what a
    reader is told is the release the code they are running came from. It is what the command
    was asked for and not a refusal, so it ends the process with status 0."""
    with pytest.raises(SystemExit) as asked:
        main(["--version"])

    assert asked.value.code == 0
    assert capsys.readouterr().out == f"attestql {importlib.metadata.version('attestql')}\n"


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


# where the data the server holds came from


DATA_ORIGIN = "https://example.org/bench/mini_dev_postgresql.dump"
DUMP = "CREATE TABLE atom (element text);\nCOPY atom FROM stdin;\nc\no\n\\.\n"


def _dump(tmp_path: Path) -> Path:
    path = tmp_path / "mini_dev.dump"
    path.write_text(DUMP, encoding="utf-8")
    return path


def _differing(tmp_path: Path) -> tuple[Path, FakeBackend]:
    """A run whose gold and prediction disagree, so both records are written and read."""
    other = "SELECT element FROM atom WHERE element = 'c'"
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    predictions = write(tmp_path / "preds.json", {"207": other})
    backend = FakeBackend(
        {ELEMENTS: fake_result(ELEMENT, (("c",), ("o",))), other: fake_result(ELEMENT, (("c",),))},
        row_counts={"atom": 2},
    )
    return predictions, backend


def test_the_data_file_is_recorded_with_its_digest_origin_and_date(tmp_path: Path) -> None:
    """A run over a stale dump is the failure this tool exists to catch, and the server
    cannot say which file it was loaded from: the operator names it and the run states it."""
    predictions, backend = _differing(tmp_path)
    dump = _dump(tmp_path)
    run_audit(
        options(
            tmp_path,
            predictions=predictions,
            data_file=dump,
            data_origin=DATA_ORIGIN,
            data_date="2026-03-01",
        ),
        backend,
        Lines(),
    )

    assert summary_of(tmp_path)["fixture"]["source"] == {
        "path": str(dump),
        "digest": sha256_of(dump),
        "origin": DATA_ORIGIN,
        "date": "2026-03-01",
    }
    directory = tmp_path / "audit" / "q207"
    for name in (GOLD_RECORD_FILE, SECOND_RECORD_FILE, COUNTEREXAMPLE_FILE):
        written = json.loads((directory / name).read_text(encoding="utf-8"))
        assert written["fixture"]["source_file_sha256"] == sha256_of(dump), name


def test_without_a_data_file_the_summary_says_so_and_no_record_states_a_digest(
    tmp_path: Path,
) -> None:
    """The absence is stated: nobody named a file, rather than a file that hashed to nothing."""
    predictions, backend = _differing(tmp_path)
    run_audit(options(tmp_path, predictions=predictions), backend, Lines())

    assert summary_of(tmp_path)["fixture"]["source"] is None
    directory = tmp_path / "audit" / "q207"
    for name in (GOLD_RECORD_FILE, SECOND_RECORD_FILE, COUNTEREXAMPLE_FILE):
        written = json.loads((directory / name).read_text(encoding="utf-8"))
        assert written["fixture"]["source_file_sha256"] == "", name


def test_a_data_file_that_cannot_be_read_stops_the_run(tmp_path: Path) -> None:
    """The digest is the whole point of naming it, so a file that is not there is not a run."""
    write(tmp_path / "questions.json", [question(207, "toxicology", ELEMENTS)])
    with pytest.raises(ToolError, match="cannot be read"):
        run_audit(options(tmp_path, data_file=tmp_path / "gone.dump"), _quiet_backend(), Lines())


def test_the_command_line_takes_the_data_file_with_its_origin_and_date(tmp_path: Path) -> None:
    dump = _dump(tmp_path)
    parsed = parse_arguments(
        [
            "audit",
            "--dsn",
            "host=h dbname=d",
            "--questions",
            "q.json",
            "--out",
            "o/",
            "--data-file",
            str(dump),
            "--data-origin",
            DATA_ORIGIN,
            "--data-date",
            "2026-03-01",
        ]
    )
    assert parsed.data_file == dump
    assert parsed.data_origin == DATA_ORIGIN
    assert parsed.data_date == "2026-03-01"


@pytest.mark.parametrize(
    ("flag", "value"), [("--data-origin", DATA_ORIGIN), ("--data-date", "2026-03-01")]
)
def test_stating_where_the_data_came_from_without_naming_the_file_is_refused(
    flag: str, value: str
) -> None:
    """There is nothing to digest, so the run would record an origin for a file it never read."""
    with pytest.raises(SystemExit) as refused:
        parse_arguments(
            ["audit", "--dsn", "host=h", "--questions", "q.json", "--out", "a", flag, value]
        )
    assert refused.value.code == 2


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


def test_a_position_keyed_entry_that_holds_no_statement_errors_the_question_at_that_position(
    tmp_path: Path,
) -> None:
    """BIRD's own files are keyed by position and are the files that hold the number 0, so
    the pairing and the reading of an entry that holds nothing have to meet: position 0 is
    question 207 here, and it is that question's error line rather than the file's."""
    _duplicated_question_file(tmp_path)
    write(tmp_path / "preds.json", {"0": 0, "1": TWO_ROWS})
    lines = Lines()
    summary = run_audit(
        options(
            tmp_path,
            predictions=tmp_path / "preds.json",
            predictions_keyed_by="position",
        ),
        _two_question_backend(),
        lines,
    )

    assert summary.verdicts == {"ERROR": 1, "EQUAL": 1}
    assert [error.question_id for error in summary.errors] == [207]
    assert summary.errors[0].side == "prediction"
    assert "the predictions file holds the number 0" in lines.written[0]


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
