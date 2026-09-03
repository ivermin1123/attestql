"""The audit core against the sandbox fixture: the three defects, reproduced end to end.

Every other audit test scripts its backend. This one runs the real one, on the server
``tools/audit-sandbox/run.sh`` starts, over the synthetic fixture that reproduces the shape of
the three shipped-gold defects the spike found on Mini-Dev. What it observes is that the three
disagreements survive the whole path (parse, execute read-only, measure the data, compare under
the rule the gold's own ORDER BY chooses) and that the benchmark's own evaluator scores all three
at zero, which is the honest half of the spike's finding.

The gold and the corrections are read from the two files beside the fixture rather than written
here, so this test and the audit command being built next consume the same inputs and a change to
either file is a change to both.

Nothing here says which statement of a pair is wrong. NOT_EQUAL says the two disagree on this
data under this rule, and the fixture is built so that a reader can see which one the question
asked for.

The last two tests are here for the same reason: where PostgreSQL puts the nulls of an ordering
key is the server's answer and not a rule this repository can state on its own, so the two
statements that differ only in a written NULLS FIRST are run against it and the smell is read off
what came back.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.backend import BackendRefused
from attestql.audit.compare import Comparison, compare_statements
from attestql.audit.fixture import file_digest, fixture_digest
from attestql.audit.postgres import PostgresBackend
from attestql.audit.smells import ARBITRARY_CUT, Smell, SmellSettings, arbitrary_cut
from attestql.audit.statements import parse_statement
from attestql.evidence.replay import ComparabilityResult
from attestql.evidence.serialize import SerializationDescriptor
from attestql.evidence.types import QuestionMetadata, ReplayRule, StatementSource

pytestmark = pytest.mark.sandbox

SANDBOX = Path(__file__).resolve().parent.parent / "tools" / "audit-sandbox"
QUESTIONS_FILE = SANDBOX / "questions.json"
PREDICTIONS_FILE = SANDBOX / "predictions.json"

QUESTION_SET = "attestql_audit_sandbox"
QUESTION_SET_VERSION = file_digest(QUESTIONS_FILE)
"""The digest of the file the gold statements were read from, as a record states it."""

QUESTIONS_SOURCE = StatementSource(
    path=str(QUESTIONS_FILE), digest=QUESTION_SET_VERSION, origin=None, date=None
)
PREDICTIONS_SOURCE = StatementSource(
    path=str(PREDICTIONS_FILE), digest=file_digest(PREDICTIONS_FILE), origin=None, date=None
)
"""The two files beside the fixture, as the records of this run name them. Nothing states
where they came from, because they are this repository's own."""

DATA_AS_OF = datetime(2026, 9, 2, tzinfo=UTC)
"""The fixture is loaded from one file and never changes under a run, so one instant
describes the data every record here is about."""

DESCRIPTOR = SerializationDescriptor(
    version="audit-sandbox-smoke/1",
    numeric_scale=6,
    timestamp_format="%Y-%m-%dT%H:%M:%S.%fZ",
    timezone="UTC",
    null_rendering="NULL",
    encoding="utf-8",
)

FIXTURE_ROWS = {
    "public.team": 10,
    "public.team_attributes": 10,
    "public.drivers": 4,
    "public.results": 7,
    "public.molecule": 2,
    "public.atom": 5,
    "public.bond": 3,
    "public.connected": 6,
    "public.spend": 15,
    "public.scores": 6,
}
"""What fixture.sql inserts, table by table. A record's fixture digest states these counts, so
stating them again here is how a fixture edited without this test being read is caught."""

TIMEOUT_SECONDS = 30

SMELL_SETTINGS = SmellSettings(serialization=DESCRIPTOR, statement_timeout_seconds=TIMEOUT_SECONDS)

SLOWEST_LAP = "SELECT fastestlapspeed FROM results ORDER BY fastestlapspeed ASC LIMIT 1"
SLOWEST_LAP_NULLS_FIRST = (
    "SELECT fastestlapspeed FROM results ORDER BY fastestlapspeed ASC NULLS FIRST LIMIT 1"
)
"""The same bounded question twice over the two nulls in results.fastestlapspeed: once with
the placement left to the server, once with the placement written into the statement."""


def _document(path: Path) -> dict[str, Any]:
    """One JSON file as it was written. The values are the file's, converted where used."""
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def _questions() -> dict[str, dict[str, Any]]:
    rows = cast("list[dict[str, Any]]", _document(QUESTIONS_FILE)["questions"])
    return {str(row["question_id"]): row for row in rows}


QUESTIONS = _questions()
PREDICTIONS = {key: str(value) for key, value in _document(PREDICTIONS_FILE).items()}


def _compare(backend: PostgresBackend, directory: Path, question_id: str) -> Comparison:
    """One gold and its correction, executed on the sandbox and compared."""
    entry = QUESTIONS[question_id]
    return compare_statements(
        question=QuestionMetadata(
            question_id=question_id,
            question_set=QUESTION_SET,
            question_text=str(entry["question"]),
            evidence_text=str(entry["evidence"]),
        ),
        question_set_version=QUESTION_SET_VERSION,
        gold_sql=str(entry["SQL"]),
        gold_source=QUESTIONS_SOURCE,
        second_sql=PREDICTIONS[question_id],
        second_source=PREDICTIONS_SOURCE,
        backend=backend,
        serialization=DESCRIPTOR,
        run_id="audit-sandbox-smoke",
        directory=directory,
        data_as_of=DATA_AS_OF,
        statement_timeout_seconds=TIMEOUT_SECONDS,
    )


def _column(comparison: Comparison, side: str) -> list[object]:
    record = comparison.gold if side == "gold" else comparison.second
    return [row[0] for row in record.result.rows]


def test_1029_takes_the_four_slowest_where_the_question_asked_for_the_fastest(
    sandbox_backend: PostgresBackend, tmp_path: Path
) -> None:
    """The gold's ASC NULLS FIRST against the correction's DESC NULLS LAST, under R-ORD."""
    comparison = _compare(sandbox_backend, tmp_path, "1029")
    # buildupplayspeed is bigint and both statements project it alone, so the column is whole
    # numbers; the equality below is what proves it, and the cast is what lets max and min read it.
    gold = cast("list[int]", _column(comparison, "gold"))
    second = cast("list[int]", _column(comparison, "second"))

    assert comparison.replay_rule is ReplayRule.R_ORD
    assert comparison.verdict.result is ComparabilityResult.NOT_EQUAL
    assert gold == [20, 23, 31, 44]
    assert second == [80, 77, 70, 62]
    # The whole of the disagreement: every speed the gold returned is below every speed the
    # correction returned, so the two answers share no row at all.
    assert max(gold) < min(second)
    assert comparison.bird_ex.value == 0


def test_879_orders_the_speeds_as_text_and_lands_on_another_driver(
    sandbox_backend: PostgresBackend, tmp_path: Path
) -> None:
    """'93.175' is the largest string and 259.870 the largest number; the nationalities differ."""
    comparison = _compare(sandbox_backend, tmp_path, "879")

    assert comparison.replay_rule is ReplayRule.R_ORD
    assert comparison.verdict.result is ComparabilityResult.NOT_EQUAL
    assert _column(comparison, "gold") == ["Norwegian"]
    assert _column(comparison, "second") == ["Peruvian"]
    assert comparison.bird_ex.value == 0


def test_207_reaches_every_atom_of_a_molecule_that_holds_a_double_bond(
    sandbox_backend: PostgresBackend, tmp_path: Path
) -> None:
    """The gold joins through the molecule, so it returns an element that is in no double bond."""
    comparison = _compare(sandbox_backend, tmp_path, "207")
    gold = set(_column(comparison, "gold"))
    second = set(_column(comparison, "second"))

    assert comparison.replay_rule is ReplayRule.R_SET
    assert comparison.verdict.result is ComparabilityResult.NOT_EQUAL
    assert gold == {"c", "o", "n"}
    assert second == {"c", "o"}
    assert gold > second
    assert comparison.bird_ex.value == 0


def _cut(backend: PostgresBackend, sql: str) -> tuple[tuple[tuple[object, ...], ...], Smell]:
    """The rows the bound returned, and what the arbitrary-cut smell made of the statement."""
    baseline = backend.execute(sql, statement_timeout_seconds=TIMEOUT_SECONDS)
    found = arbitrary_cut(parse_statement(sql), backend, baseline, settings=SMELL_SETTINGS)
    return baseline.rows, found


def test_an_ascending_bound_over_a_column_holding_nulls_returns_a_speed(
    sandbox_backend: PostgresBackend,
) -> None:
    """PostgreSQL sorts a null above every value, so an ascending key puts its nulls last:
    the one row this bound returns is a speed, and there is no null-first cut to report."""
    rows, found = _cut(sandbox_backend, SLOWEST_LAP)
    key = cast("dict[str, Any]", found.evidence["ordering_keys"][0])

    assert rows == (("218.300",),)
    assert found.name == ARBITRARY_CUT
    assert (found.fired, found.applicable) == (False, True)
    assert found.evidence["case"] is None
    assert key["nulls"] == "default"
    assert key["nulls_first_in_effect"] is False
    assert key["returned_rows_null_in_this_key"] == 0


def test_the_same_bound_written_nulls_first_returns_a_null_and_fires(
    sandbox_backend: PostgresBackend,
) -> None:
    """What the statement writes wins over the server's own placement, and the evidence says
    which of the two returned the null the reader is being shown."""
    rows, found = _cut(sandbox_backend, SLOWEST_LAP_NULLS_FIRST)
    key = cast("dict[str, Any]", found.evidence["ordering_keys"][0])

    assert rows == ((None,),)
    assert (found.fired, found.applicable) == (True, True)
    assert found.evidence["case"] == "null-first"
    assert key["nulls"] == "first"
    assert key["nulls_first_in_effect"] is True
    assert key["fires"] is True
    assert found.evidence["returned_rows_with_a_null_key"] == [[{"type": "null", "value": None}]]
    # The row carries the projected speed and the key the variant statement projected beside
    # it, both null: that is the whole of why this row was the one the bound returned.
    assert found.counterexample_rows == ((None, None),)


def test_the_fixture_holds_the_rows_the_three_defects_need(
    sandbox_backend: PostgresBackend, tmp_path: Path
) -> None:
    """The digest is measured on the server, and what it counted is what fixture.sql wrote."""
    digest = fixture_digest(sandbox_backend, tuple(FIXTURE_ROWS), directory=tmp_path)

    assert dict(digest.row_counts) == FIXTURE_ROWS
    assert digest.schema_digest.startswith("sha256:")
    assert digest.content_digests == {}


def test_the_auditor_reads_the_fixture_and_writes_only_the_scratch_schema(
    sandbox_backend: PostgresBackend,
) -> None:
    """Read-only three times over, and the one place a smell may copy rows to."""
    with pytest.raises(BackendRefused):
        sandbox_backend.execute(
            "CREATE TABLE public.smoke_probe (x integer)", statement_timeout_seconds=TIMEOUT_SECONDS
        )
    with pytest.raises(BackendRefused):
        sandbox_backend.execute(
            "INSERT INTO scores (name, score) VALUES ('probe', 1)",
            statement_timeout_seconds=TIMEOUT_SECONDS,
        )

    # What the role itself holds, read from the server rather than inferred from the refusals
    # above: those two are the read-only transaction speaking, and this is the login.
    granted = sandbox_backend.execute(
        "SELECT current_user, "
        "has_table_privilege('public.scores', 'INSERT'), "
        "has_schema_privilege('public', 'CREATE'), "
        "has_schema_privilege('attestql_scratch', 'CREATE'), "
        "current_setting('default_transaction_read_only')",
        statement_timeout_seconds=TIMEOUT_SECONDS,
    )
    assert granted.rows == (("auditor", False, False, True, "on"),)
