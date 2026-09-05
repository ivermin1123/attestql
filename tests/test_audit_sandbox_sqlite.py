"""The audit end to end on the SQLite sandbox: the same three defects, without a container.

The sibling of ``tests/test_audit_end_to_end.py``, and the reason it exists twice: that one
runs the command against a pinned PostgreSQL server that ``tools/audit-sandbox/run.sh``
starts in Docker, and this one runs it against a file. A SQLite database is a file, so the
whole sandbox is ``fixture.sql`` written into ``tmp_path``. There is nothing to start, no port
to hold, no login to create and no credential anywhere, which is why these tests are marked
and are never skipped: the gate runs them wherever it runs the suite.

What is observed is that the three disagreements survive the whole path on the second engine
too (parse with sqlglot, execute read-only against the file, measure the data, compare under
the rule the gold's own ORDER BY chooses), that the gold-only probes fire on the same shapes,
and that the summary a maintainer reads states which engine and which parser produced it.

The golds are Mini-Dev's own SQLite copy rather than translations of the PostgreSQL sandbox's,
and one of them is a shape the PostgreSQL sandbox cannot show: q879's SQLite gold states no
NULLS placement, because SQLite puts a null last under DESC without being told, and the parse
says so rather than reporting the placement as the statement's own.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from build import PREDICTIONS_FILE, QUESTIONS_FILE, build_fixture

from attestql.audit.cli import (
    MARKER_FILE,
    SMELLS_FILE,
    SUMMARY_FILE,
    AuditOptions,
    Summary,
    ToolError,
    run_audit,
)
from attestql.audit.compare import COUNTEREXAMPLE_FILE, GOLD_RECORD_FILE, SECOND_RECORD_FILE
from attestql.audit.engines import SQLITE
from attestql.audit.smells import (
    ARBITRARY_CUT,
    NOT_A_FUNCTION_OF_THE_DATA,
    ORDERING_OVER_NUMERIC_TEXT,
)
from attestql.audit.sqlite import QUALIFIED_NAME_IS_NOT_REACHED
from attestql.audit.sqlite_statements import PARSER, VALIDATOR_VERSION
from attestql.evidence.replay import ComparabilityResult
from attestql.evidence.types import ENGINE_SQLITE

pytestmark = pytest.mark.sandbox_sqlite

DEFECTS = ("1029", "879", "207")
"""The three questions whose shipped gold and correction disagree on this data."""

GOLD_ONLY_LINE = "6 questions: 0 NOT_EQUAL, 5 smells fired"
PREDICTION_LINE = (
    "6 questions: 3 NOT_EQUAL, 5 smells fired, "
    "0 credited by BIRD but NOT_EQUAL (0 multiplicity, 0 type, 0 order, 0 truncation)"
)
"""The whole of what a run prints last, stated here so that a change to the fixture, the
questions or a probe is a change to this file too. None of the three disagreements is one
BIRD's own check would have scored 1."""

DATA_AS_OF = datetime(2026, 9, 5, tzinfo=UTC)
"""The fixture is built from one file and never changes under a run, so one instant describes
the data every record here is about."""


class Lines:
    """A writer that keeps what was written instead of printing it."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def line(self, text: str) -> None:
        self.written.append(text)


def _options(tmp_path: Path, *, predictions: bool, out: Path | None = None) -> AuditOptions:
    """The command as the gate runs it: this engine, the built file, the shipped questions."""
    return AuditOptions(
        dsn=str(build_fixture(tmp_path / "sandbox")),
        questions=QUESTIONS_FILE,
        predictions=PREDICTIONS_FILE if predictions else None,
        out=out or (tmp_path / "audit"),
        engine=SQLITE,
        data_as_of=DATA_AS_OF,
    )


def _run(tmp_path: Path, *, predictions: bool = False) -> tuple[Summary, Lines, Path]:
    options = _options(tmp_path, predictions=predictions)
    writer = Lines()
    return (
        run_audit(options, SQLITE.connect(options.dsn, scratch="temp"), writer),
        writer,
        (options.out),
    )


def _document(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def _rows(out: Path, question: str, side: str) -> list[list[object]]:
    """The rows one side of a comparison returned, as the counterexample states them."""
    document = _document(out / f"q{question}" / COUNTEREXAMPLE_FILE)
    result = cast("dict[str, Any]", cast("dict[str, Any]", document[side])["result"])
    return [
        [cell["value"] for cell in cast("list[dict[str, Any]]", row)]
        for row in cast("list[Any]", result["rows"])
    ]


def _fired(out: Path, question: str) -> set[str]:
    smells = cast("list[dict[str, Any]]", _document(out / f"q{question}" / SMELLS_FILE)["smells"])
    return {str(smell["name"]) for smell in smells if smell["fired"]}


@pytest.fixture(scope="module")
def gold_only(tmp_path_factory: pytest.TempPathFactory) -> tuple[Summary, Lines, Path]:
    """One gold-only run over the fixture, shared by the readings that only look at it."""
    return _run(tmp_path_factory.mktemp("gold-only"))


@pytest.fixture(scope="module")
def with_predictions(tmp_path_factory: pytest.TempPathFactory) -> tuple[Summary, Lines, Path]:
    """One run with the corrections beside the golds, shared the same way."""
    return _run(tmp_path_factory.mktemp("predictions"), predictions=True)


def test_the_gold_only_run_fires_the_probes_the_fixture_was_written_for(
    gold_only: tuple[Summary, Lines, Path],
) -> None:
    """The three gold-only probes, on the shapes each was written for: an ordering over text
    that holds numbers, a bound whose cut falls inside a tie, and a result that is a function
    of the order the rows are stored in rather than of the rows.

    The third is where the two sandboxes differ and the engine is why. On PostgreSQL it is a
    single-precision sum that adds up differently; SQLite has one floating type and adds it
    with a compensation, so what is asked here is ``group_concat``, which writes its parts in
    the order it read them.
    """
    summary, writer, out = gold_only

    assert writer.written[-1] == GOLD_ONLY_LINE
    assert summary.exit_status == 0, "a gold-only run exits zero until a probe is asked to block"
    assert _fired(out, "879") == {ORDERING_OVER_NUMERIC_TEXT}
    assert _fired(out, "900005") == {ORDERING_OVER_NUMERIC_TEXT}
    assert _fired(out, "900001") == {NOT_A_FUNCTION_OF_THE_DATA}
    assert _fired(out, "900002") == {ARBITRARY_CUT, NOT_A_FUNCTION_OF_THE_DATA}


def test_the_summary_names_the_engine_the_file_and_the_grammar_that_judged_this_run(
    gold_only: tuple[Summary, Lines, Path],
) -> None:
    """A reader of a SQLite run is told what produced it: which engine, which file, which
    parser and which dialect. The planner statistics are empty and that is the answer, not a
    gap: SQLite keeps none until somebody runs ANALYZE, and an audit reads."""
    _, _, out = gold_only
    document = _document(out / SUMMARY_FILE)
    settings = cast("dict[str, Any]", document["session_settings"])

    assert settings["engine"] == ENGINE_SQLITE
    assert document["parser"] == PARSER.json()
    assert document["parser"]["validator"] == VALIDATOR_VERSION
    assert document["parser"]["dialect"] == "sqlite"
    assert document["planner_statistics"] == {}
    assert str(document["backend_identity"]).startswith("SQLite ")
    assert document["effective_database_role"] == "file"
    assert set(cast("dict[str, Any]", settings["recorded"])) == {
        "sqlite_version",
        "encoding",
        "compile_options",
        "collation_list",
        "case_sensitive_like",
        "reverse_unordered_selects",
        "query_only",
        "journal_mode",
        "data_version",
    }


def test_the_fixture_is_measured_under_the_names_the_file_holds(
    gold_only: tuple[Summary, Lines, Path],
) -> None:
    """The golds name ``Team_Attributes`` and the file created ``team_attributes``. SQLite
    matches a relation name without regard to case, so those are one table, measured once and
    under the file's own spelling; a lookup that compared the bytes of the name would report a
    table that is right there as one nobody loaded.

    ``unreadable_tables`` is empty and always will be: a file has no grants."""
    _, _, out = gold_only
    fixture = cast("dict[str, Any]", _document(out / SUMMARY_FILE)["fixture"])

    assert fixture["row_counts"] == {
        "main.atom": 5,
        "main.bond": 3,
        "main.connected": 6,
        "main.drivers": 4,
        "main.results": 7,
        "main.scores": 6,
        "main.spend": 15,
        "main.team": 10,
        "main.team_attributes": 10,
        "main.y": 3,
    }
    assert fixture["missing_tables"] == []
    assert fixture["unreadable_tables"] == []
    assert str(fixture["schema_digest"]).startswith("sha256:")


def test_a_gold_that_names_its_schema_is_told_the_shuffle_did_not_cover_it(
    gold_only: tuple[Summary, Lines, Path],
) -> None:
    """A copy is reached because SQLite resolves an unqualified name in TEMP before ``main``,
    and for no other name. q900005 writes ``main.y``, so its rerun reads the table itself and
    the run says so rather than reporting a shuffle it did not get."""
    _, _, out = gold_only
    shuffle = cast("dict[str, Any]", _document(out / SUMMARY_FILE)["shuffle"])

    assert shuffle["prepared"] is True
    assert shuffle["not_reached_by_a_copy"] == {"main.y": QUALIFIED_NAME_IS_NOT_REACHED}
    assert "y" not in cast("list[str]", shuffle["copied"])


def test_each_shipped_defect_disagrees_with_its_correction_on_this_data(
    with_predictions: tuple[Summary, Lines, Path],
) -> None:
    """The three, end to end. Nothing here says which statement of a pair is wrong: NOT_EQUAL
    says the two disagree on this data under this rule, and the fixture is built so that a
    reader can see which answer the question asked for."""
    summary, writer, out = with_predictions

    assert writer.written[-1] == PREDICTION_LINE
    assert summary.exit_status == 1, "a disagreement is exit status one"
    assert summary.verdicts[ComparabilityResult.NOT_EQUAL.name] == 3
    for question in DEFECTS:
        directory = out / f"q{question}"
        assert (directory / COUNTEREXAMPLE_FILE).is_file()
        assert (directory / GOLD_RECORD_FILE).is_file()
        assert (directory / SECOND_RECORD_FILE).is_file()


def test_1029_takes_the_four_slowest_where_the_question_asked_for_the_fastest(
    with_predictions: tuple[Summary, Lines, Path],
) -> None:
    """The shipped SQLite gold orders ASC and the question asks for the highest four, so the
    two answers share no row at all."""
    _, _, out = with_predictions

    assert _rows(out, "1029", "gold") == [[20], [23], [31], [44]]
    assert _rows(out, "1029", "second") == [[80], [77], [70], [62]]


def test_879_orders_the_speeds_as_text_and_lands_on_another_driver(
    with_predictions: tuple[Summary, Lines, Path],
) -> None:
    """'93.175' is the largest string and 259.870 the largest number, so the nationalities
    differ. The zip's SQLite gold carries this defect; the Hugging Face copy of the same file
    corrects it with the CAST the correction here uses."""
    _, _, out = with_predictions

    assert _rows(out, "879", "gold") == [["Norwegian"]]
    assert _rows(out, "879", "second") == [["Peruvian"]]
    assert _fired(out, "879") == {ORDERING_OVER_NUMERIC_TEXT}


def test_207_reaches_every_atom_of_a_molecule_that_holds_a_double_bond(
    with_predictions: tuple[Summary, Lines, Path],
) -> None:
    """The gold joins through the molecule, so it returns an element that is in no double
    bond; the correction walks atom to connected to bond."""
    _, _, out = with_predictions
    gold = {cell for row in _rows(out, "207", "gold") for cell in row}
    second = {cell for row in _rows(out, "207", "second") for cell in row}

    assert gold == {"c", "o", "n"}
    assert second == {"c", "o"}


def test_a_prediction_that_answers_the_same_question_another_way_is_equal(
    with_predictions: tuple[Summary, Lines, Path],
) -> None:
    """The other verdict, so that the run states both. q900005's correction is the gold with an
    alias and a qualified key: another text, one answer, and EQUAL is what a comparison of two
    statements that agree looks like."""
    summary, _, out = with_predictions

    assert summary.verdicts[ComparabilityResult.EQUAL.name] == 1
    assert _rows(out, "900005", "gold") == _rows(out, "900005", "second")
    assert _rows(out, "900005", "gold") == [["lead"], ["zinc"], ["iron"]], (
        "'10' sorts below '200.5' and both below '9.5', which is the smell's case and not the "
        "disagreement: both statements order the mass as text and agree"
    )


def test_a_write_in_a_gold_is_that_question_s_error_line_and_not_the_end_of_the_run(
    tmp_path: Path,
) -> None:
    """The file is opened read-only and the envelope is on over it, so a gold that writes is
    refused twice over. What a reader sees is one error line naming the side that failed, and
    every other question of the run still answered."""
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "question_id": 900101,
                        "db_id": "synthetic",
                        "question": "Who holds the highest score?",
                        "evidence": "",
                        "SQL": "SELECT name FROM scores ORDER BY score DESC LIMIT 1",
                        "difficulty": "simple",
                    },
                    {
                        "question_id": 900102,
                        "db_id": "synthetic",
                        "question": "Give everyone a point.",
                        "evidence": "",
                        "SQL": "UPDATE scores SET score = score + 1",
                        "difficulty": "simple",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    options = AuditOptions(
        dsn=str(build_fixture(tmp_path / "sandbox")),
        questions=questions,
        out=tmp_path / "audit",
        engine=SQLITE,
        data_as_of=DATA_AS_OF,
    )
    writer = Lines()

    summary = run_audit(options, SQLITE.connect(options.dsn, scratch="temp"), writer)

    assert summary.questions == 2
    assert [error.question_id for error in summary.errors] == [900102]
    assert "not a SELECT" in summary.errors[0].message
    assert any("q900101" in line and "GOLD-ONLY" in line for line in writer.written)


def test_a_rerun_clears_the_run_before_it_and_a_directory_nobody_audited_is_refused(
    tmp_path: Path,
) -> None:
    """The marker is what makes a directory this tool's to clear. A rerun into one leaves one
    run's evidence and not two; a non-empty directory without it is refused with nothing in it
    touched, whichever engine wrote it."""
    out = tmp_path / "audit"
    first, _, _ = _run(tmp_path / "first", predictions=False)
    options = _options(tmp_path / "second", predictions=False, out=out)
    run_audit(options, SQLITE.connect(options.dsn, scratch="temp"), Lines())
    stale = out / "q999999"
    stale.mkdir()
    (stale / "left-behind.json").write_text("{}", encoding="utf-8")

    assert first.questions == 6
    assert (out / MARKER_FILE).is_file()

    run_audit(options, SQLITE.connect(options.dsn, scratch="temp"), Lines())
    assert not stale.exists(), "the run before this one was cleared"
    assert (out / MARKER_FILE).is_file()

    unaudited = tmp_path / "somebody-elses"
    unaudited.mkdir()
    (unaudited / "notes.txt").write_text("mine\n", encoding="utf-8")
    theirs = _options(tmp_path / "third", predictions=False, out=unaudited)
    with pytest.raises(ToolError, match=MARKER_FILE):
        run_audit(theirs, SQLITE.connect(theirs.dsn, scratch="temp"), Lines())
    assert (unaudited / "notes.txt").is_file()
