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

Every probe is then asked twice over the same file, on a statement that fires it and one that
keeps it quiet, because a probe that has never been seen quiet is a probe nobody has shown to
be answering the question rather than always saying yes. Three of the five fire on the golds
above and the quiet halves are beside them; the two the golds do not reach, a cut over the
nulls this engine puts first and the experimental one, fire on statements written here. The
fifth is the one this engine does not have: SQLite adds a REAL aggregate with a compensation,
so a float total does not move with the order its rows were read in, the sums below are quiet
and a REAL that does move is reported as the storage-order finding it is.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.backend import Backend, ShuffledCopies, TableName
from attestql.audit.cli import (
    MARKER_FILE,
    SERIALIZATION,
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
    DEFAULT_SHUFFLE_ROW_LIMIT,
    DIRECTION_AGAINST_QUESTION,
    FLOAT_AGGREGATE_ORDER,
    NOT_A_FUNCTION_OF_THE_DATA,
    ORDERING_OVER_NUMERIC_TEXT,
    QuestionText,
    Smell,
    SmellSettings,
    all_smells,
)
from attestql.audit.sqlite import QUALIFIED_NAME_IS_NOT_REACHED
from attestql.audit.sqlite_statements import PARSER, VALIDATOR_VERSION
from attestql.demo import PREDICTIONS_FILE, QUESTIONS_FILE, build_fixture
from attestql.evidence.replay import ComparabilityResult
from attestql.evidence.types import ENGINE_SQLITE

pytestmark = pytest.mark.sandbox_sqlite

DEFECTS = ("1029", "879", "207")
"""The three questions whose shipped gold and correction disagree on this data."""

NOTHING_TIMED_OUT = ", 0 timed out (0 gold, 0 prediction)"
"""The bound is the default 30 seconds over a file of a few rows a table, so nothing
here reaches it and both lines end with the zero that says the run counted."""

GOLD_ONLY_LINE = f"6 questions: 0 NOT_EQUAL, 5 smells fired{NOTHING_TIMED_OUT}"
PREDICTION_LINE = (
    "6 questions: 3 NOT_EQUAL, 5 smells fired, "
    "0 credited by BIRD but NOT_EQUAL (0 multiplicity, 0 type, 0 order, 0 truncation)"
    f"{NOTHING_TIMED_OUT}"
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


PROBE_TABLES: tuple[TableName, ...] = tuple(
    TableName("", name) for name in ("drivers", "results", "scores", "spend", "team_attributes")
)
"""The tables the statements below read, copied once so that every rerun reads a copy."""

PROBE_SETTINGS = SmellSettings(
    serialization=SERIALIZATION,
    statement_timeout_seconds=30,
    experimental_s2=True,
)
"""The command's own settings with the experimental probe asked for, so all five run."""


@pytest.fixture(scope="module")
def sandbox(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Backend]:
    """The built file, open read-only, with one shuffled copy of each table the probes read.

    The probes are asked here rather than through the command because a probe that stays
    quiet writes no directory: the command records the questions that fired something, and
    both halves of each pair have to be readable for a pair to say anything.
    """
    tmp_path = tmp_path_factory.mktemp("probes")
    backend = SQLITE.connect(str(build_fixture(tmp_path / "sandbox")), scratch="temp")
    try:
        backend.prepare_shuffled_copies(PROBE_TABLES, seed="1", row_limit=DEFAULT_SHUFFLE_ROW_LIMIT)
        yield backend
    finally:
        backend.drop_shuffled_copies()


def _probes(backend: Backend, sql: str, *, question: str = "") -> dict[str, Smell]:
    """Every probe on one statement over the file, by the name each answered under."""
    parsed = SQLITE.parse(sql)
    baseline = backend.execute(sql, statement_timeout_seconds=30)
    found = all_smells(
        parsed,
        backend,
        baseline,
        settings=PROBE_SETTINGS,
        question=QuestionText(question),
        shuffled=ShuffledCopies(
            copied=PROBE_TABLES,
            skipped={},
            unreachable={},
            seed="1",
            row_limit=DEFAULT_SHUFFLE_ROW_LIMIT,
        ),
    )
    return {smell.name: smell for smell in found}


def test_an_ordering_over_numeric_text_fires_over_numbers_and_is_quiet_over_words(
    sandbox: Backend,
) -> None:
    """The two halves of the probe q879 fires. The key is a text column in both, and the
    census is what separates them: three masses that are all numbers reorder under the cast
    and the probe fires; nationalities are not numbers, so the cast is never run and the
    probe answers no rather than never having asked."""
    fires = _probes(sandbox, "SELECT tag FROM y ORDER BY mass ASC")[ORDERING_OVER_NUMERIC_TEXT]
    quiet = _probes(sandbox, "SELECT nationality FROM drivers ORDER BY nationality ASC")[
        ORDERING_OVER_NUMERIC_TEXT
    ]

    assert (fires.fired, fires.applicable) == (True, True)
    assert cast("list[dict[str, Any]]", fires.evidence["keys"])[0]["cast_sql"] == (
        "SELECT tag FROM y ORDER BY CAST(mass AS REAL) ASC"
    )
    assert (quiet.fired, quiet.applicable) == (False, True)
    key = cast("list[dict[str, Any]]", quiet.evidence["keys"])[0]
    assert key["column"] == "drivers.nationality"
    assert key["every_value_is_numeric"] is False


def test_an_ordered_cut_fires_inside_a_tie_and_is_quiet_where_the_ordering_decided_it(
    sandbox: Backend,
) -> None:
    """Three names tied at 99 bounded to one is a cut this statement did not make; one lowest
    score bounded to one is a cut the ordering made, and the probe says which it read."""
    fires = _probes(sandbox, "SELECT name FROM scores ORDER BY score DESC LIMIT 1")[ARBITRARY_CUT]
    quiet = _probes(sandbox, "SELECT name FROM scores ORDER BY score ASC LIMIT 1")[ARBITRARY_CUT]

    assert (fires.fired, fires.evidence["case"]) == (True, "tie-at-the-cut")
    assert cast("dict[str, Any]", fires.evidence["tied_at_the_cut"])["tied_rows"] == 3
    assert (quiet.fired, quiet.applicable, quiet.evidence["case"]) == (False, True, None)


def test_a_cut_fires_on_the_nulls_this_engine_puts_first_and_is_quiet_where_it_puts_them_last(
    sandbox: Backend,
) -> None:
    """The engine's own rule, and the place a probe written for PostgreSQL reads it backwards.
    SQLite sorts a null below every value, so an ascending key puts its nulls first and the two
    rows this bound returns are the two that hold no speed at all; the same key descending puts
    them last and the bound returns two speeds. On PostgreSQL the two statements swap places,
    and neither the probe nor the parse asks which engine it is on: the parse fills the
    placement in per key under its own grammar's rule and the probe reads what it filled in."""
    fires = _probes(
        sandbox, "SELECT fastestLapSpeed FROM results ORDER BY fastestLapSpeed ASC LIMIT 2"
    )[ARBITRARY_CUT]
    quiet = _probes(
        sandbox, "SELECT fastestLapSpeed FROM results ORDER BY fastestLapSpeed DESC LIMIT 2"
    )[ARBITRARY_CUT]

    assert (fires.fired, fires.evidence["case"]) == (True, "null-first")
    assert cast("list[dict[str, Any]]", fires.evidence["ordering_keys"])[0]["nulls"] == "first"
    assert fires.evidence["returned_rows_with_a_null_key"] == [
        [{"type": "null", "value": None}],
        [{"type": "null", "value": None}],
    ]
    assert (quiet.fired, quiet.applicable, quiet.evidence["case"]) == (False, True, None)
    assert cast("list[dict[str, Any]]", quiet.evidence["ordering_keys"])[0]["nulls"] == "last"


def test_a_result_that_moves_with_the_storage_order_fires_and_a_count_does_not(
    sandbox: Backend,
) -> None:
    """``group_concat`` writes its parts in the order it read them, so the same rows in another
    physical order give another answer. A count of the same table is a function of the rows and
    of nothing else, and the probe is quiet having asked rather than quiet for want of asking."""
    fires = _probes(
        sandbox,
        "SELECT category, group_concat(spent) FROM spend GROUP BY category ORDER BY category ASC",
    )[NOT_A_FUNCTION_OF_THE_DATA]
    quiet = _probes(sandbox, "SELECT count(*) FROM spend")[NOT_A_FUNCTION_OF_THE_DATA]

    assert (fires.fired, fires.applicable) == (True, True)
    assert cast("dict[str, Any]", fires.evidence["shuffled_copies"])["differs"] is True
    assert (quiet.fired, quiet.applicable) == (False, True)
    assert cast("dict[str, Any]", quiet.evidence["shuffled_copies"])["verdict"] == "equal"


def test_a_real_total_does_not_move_with_the_order_its_rows_were_read_in(
    sandbox: Backend,
) -> None:
    """The fifth probe, and the one this engine does not reach. SQLite adds a REAL aggregate
    with a Kahan-Babuska-Neumaier compensation, so the same fifteen amounts summed in another
    physical order give the same total to the last digit, whole and per category, and no
    ``float-aggregate-order`` arises from a sum here.

    The backend therefore names no type whose aggregate is order-sensitive, which is what makes
    a REAL cell that does move under a shuffle the storage-order finding rather than arithmetic
    the probe forgives; that rule is asked of the smell itself in
    ``tests/test_audit_smells_read_the_gold_and_the_data.py``."""
    assert sandbox.order_sensitive_aggregate_types() == frozenset()
    for sql in (
        "SELECT sum(spent) FROM spend",
        "SELECT category, sum(spent) FROM spend GROUP BY category ORDER BY category ASC",
    ):
        found = _probes(sandbox, sql)
        assert FLOAT_AGGREGATE_ORDER not in found
        quiet = found[NOT_A_FUNCTION_OF_THE_DATA]
        assert (quiet.fired, quiet.applicable) == (False, True)
        assert cast("dict[str, Any]", quiet.evidence["shuffled_copies"])["verdict"] == "equal"


def test_the_experimental_probe_fires_against_the_question_and_runs_only_when_asked_for(
    sandbox: Backend, gold_only: tuple[Summary, Lines, Path]
) -> None:
    """A question asking for the highest four against a statement that orders ascending fires
    it; the same question against a descending key does not. It is absent from a run that did
    not ask for it, which is what keeps an experiment at 17 % precision out of a summary."""
    _, _, out = gold_only
    highest = "What are the speeds of the four teams with the highest build up play speed?"
    fires = _probes(
        sandbox,
        "SELECT buildUpPlaySpeed FROM team_attributes ORDER BY buildUpPlaySpeed ASC LIMIT 4",
        question=highest,
    )[DIRECTION_AGAINST_QUESTION]
    quiet = _probes(
        sandbox,
        "SELECT buildUpPlaySpeed FROM team_attributes ORDER BY buildUpPlaySpeed DESC LIMIT 4",
        question=highest,
    )[DIRECTION_AGAINST_QUESTION]

    assert (fires.fired, fires.evidence["contradiction"]) == (
        True,
        "maximum intent with an ascending first key",
    )
    assert (quiet.fired, quiet.applicable, quiet.evidence["contradiction"]) == (False, True, None)
    ran = cast("list[dict[str, Any]]", _document(out / "q900002" / SMELLS_FILE)["smells"])
    assert DIRECTION_AGAINST_QUESTION not in {str(smell["name"]) for smell in ran}


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


PAST_THE_BOUND = (
    "WITH RECURSIVE forever(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM forever) "
    "SELECT count(*) FROM forever, scores"
)
"""A gold that cannot finish: the recursion has no base case to stop at, so the statement
runs until this process interrupts it. It reads a table of the fixture so that the run
measures the data for it the way it does for every other question."""


def test_a_gold_the_bound_stops_is_that_question_s_error_line_and_is_counted_as_one(
    tmp_path: Path,
) -> None:
    """SQLite has no statement timeout of its own, so the bound is this process's progress
    handler, and what it stops is reported apart from what the file refuses: a longer bound
    would have recorded this statement, where one naming a table the file does not hold
    would have failed at any bound. The message stays the engine's own; the count is new."""
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "question_id": 900201,
                        "db_id": "synthetic",
                        "question": "How long is forever?",
                        "evidence": "",
                        "SQL": PAST_THE_BOUND,
                        "difficulty": "simple",
                    },
                    {
                        "question_id": 900202,
                        "db_id": "synthetic",
                        "question": "Who holds the highest score?",
                        "evidence": "",
                        "SQL": "SELECT name FROM scores ORDER BY score DESC LIMIT 1",
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
        statement_timeout_seconds=1,
    )
    writer = Lines()

    summary = run_audit(options, SQLITE.connect(options.dsn, scratch="temp"), writer)
    document = _document(options.out / SUMMARY_FILE)

    assert summary.timed_out == {"gold": (900201,), "prediction": ()}
    assert document["timed_out"] == {"gold": [900201], "prediction": []}
    assert writer.written[-1].endswith(", 1 timed out (1 gold, 0 prediction)")
    line = next(found for found in writer.written if found.startswith("q900201 "))
    assert "ERROR" in line
    assert "gold: execute: the statement ran past its 1s timeout" in line
    assert [error.question_id for error in summary.errors] == [900201]
    assert summary.exit_status == 0, "the question that was audited decided it alone"


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
