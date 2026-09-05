"""``attestql audit`` end to end on the sandbox: the command, the evidence, the status.

``tests/test_audit_sandbox_smoke.py`` observes the audit core against the same fixture, one
comparison at a time. This file runs the command itself: one ``run_audit`` over the eight
questions and the three corrections that live beside the fixture, and then reads what a
maintainer would read afterwards -- the lines it printed, the directories it wrote, the
counterexample in each of them, ``summary.json``, and the exit status.

Three of the eight questions reproduce the shape of a shipped-gold defect and are NOT_EQUAL
against their correction; two more are this repository's own and exist so that two of the
gold-only smells have something to fire on. Nothing here says a gold is wrong: the
counterexamples state what differs, and the fixture is built so that a reader can see which
answer the question asked for. The sixth reads the one table the sandbox's auditor is not
granted, and is here because a run has to survive it and the summary has to say which of the
two ways to be unmeasurable it was.

The last two name their table's schema, one of them a schema that is not the default and that
has to be written back exactly as the gold wrote it. They are here because a qualified name is
measured, resolved and rerun differently at every one of those steps, and because the two
tables they name share a relation name and a column name and declare that column differently:
a run that resolved either by the relation alone would answer both questions about one table.

The shuffled copies the fourth smell needs are made in ``attestql_scratch``, the one schema
the sandbox's read-only ``auditor`` owns, and the last test observes that the run left no
table behind in it. The audited tables are never written to.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.backend import TableName
from attestql.audit.cli import SMELLS_FILE, SUMMARY_FILE, AuditOptions, Summary, run_audit
from attestql.audit.compare import COUNTEREXAMPLE_FILE, GOLD_RECORD_FILE, SECOND_RECORD_FILE
from attestql.audit.postgres import (
    DEFAULT_SCRATCH_SCHEMA,
    QUALIFIED_NAME_IS_NOT_REACHED,
    PostgresBackend,
    _lock_key,  # pyright: ignore[reportPrivateUsage]  # the key the backend locks on, so the test cannot name another
)
from attestql.audit.statements import VALIDATOR_VERSION
from attestql.evidence.replay import ComparabilityResult

pytestmark = pytest.mark.sandbox

REPOSITORY = Path(__file__).resolve().parent.parent
SANDBOX = REPOSITORY / "tools" / "audit-sandbox"
QUESTIONS_FILE = SANDBOX / "questions.json"
PREDICTIONS_FILE = SANDBOX / "predictions.json"

SANDBOX_DSN = "ATTESTQL_AUDIT_DSN"
"""The connection string the sandbox runner exported, which carries no password."""

TIMEOUT_SECONDS = 30
COMMAND_TIMEOUT_SECONDS = 600
"""How long the console script gets. It builds the project into its environment first."""

DATA_AS_OF = datetime(2026, 9, 2, tzinfo=UTC)
"""The fixture is loaded from one file and never changes under a run, so one instant
describes the data every record here is about."""

DEFECTS = ("1029", "879", "207")
"""The three questions whose shipped gold and correction disagree on this data."""

NO_CREDIT = " credited by BIRD but NOT_EQUAL (0 multiplicity, 0 type, 0 order, 0 truncation)"
"""What the run given predictions states about the gap between the two readings: none of
the three disagreements here is one BIRD's own check would have scored 1."""

SUMMARY_LINE = f"8 questions: 3 NOT_EQUAL, 6 smells fired, 0{NO_CREDIT}"
EXPERIMENTAL_SUMMARY_LINE = f"8 questions: 3 NOT_EQUAL, 7 smells fired, 0{NO_CREDIT}"
"""The same run with the experimental smell asked for: q1029 fires it and nothing else moves."""

COPIED_TABLES = [
    "atom",
    "bond",
    "connected",
    "drivers",
    "results",
    "scores",
    "spend",
    "team",
    "team_attributes",
]
"""Every table the golds name without a schema and the auditor may read, which is what the
shuffle copies and what the reruns then read instead. ``public.molecule`` is in the fixture and
in no gold, and ``public.sealed`` is in a gold and not readable, so neither is copied and neither
is read. The two the golds name with a schema are below: a copy of one of those is a table no
rerun would reach."""

NOT_COPIED = {"Quoted.y": QUALIFIED_NAME_IS_NOT_REACHED, "public.y": QUALIFIED_NAME_IS_NOT_REACHED}
"""The two tables a gold here names with a schema. A rerun reaches the copies by the search path,
which a qualified name never consults, so no copy of these is made and the summary says why."""


class Lines:
    """A writer that keeps what it was given, which is what a test reads."""

    def __init__(self) -> None:
        self.written: list[str] = []

    def line(self, text: str) -> None:
        self.written.append(text)


@dataclass(frozen=True)
class Run:
    """One whole audit: its summary, the lines it printed and where it wrote them."""

    summary: Summary
    lines: tuple[str, ...]
    out: Path

    def line_of(self, question_id: str) -> str:
        """The one line that question printed, whichever order the questions were answered in."""
        found = [line for line in self.lines if line.startswith(f"q{question_id} ")]
        assert len(found) == 1, f"q{question_id} printed {found}"
        return found[0]

    def directory(self, question_id: str) -> Path:
        return self.out / f"q{question_id}"

    def document(self, question_id: str, name: str) -> dict[str, Any]:
        path = self.directory(question_id) / name
        return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))

    def summary_document(self) -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            json.loads((self.out / SUMMARY_FILE).read_text(encoding="utf-8")),
        )


def options(out: Path, **changed: Any) -> AuditOptions:
    """The command as this file runs it, with the credential deliberately absent."""
    stated: dict[str, Any] = {
        "dsn": os.environ[SANDBOX_DSN],
        "questions": QUESTIONS_FILE,
        "out": out,
        "data_as_of": DATA_AS_OF,
        "statement_timeout_seconds": TIMEOUT_SECONDS,
        **changed,
    }
    return AuditOptions(**stated)


def audit(backend: PostgresBackend, out: Path, **changed: Any) -> Run:
    lines = Lines()
    summary = run_audit(options(out, **changed), backend, lines)
    return Run(summary=summary, lines=tuple(lines.written), out=out)


SCRATCH_TABLES_SQL = (
    "SELECT tablename FROM pg_tables WHERE schemaname = 'attestql_scratch' ORDER BY tablename"
)
"""What the scratch schema holds, as one literal statement rather than a built one: this is
the tool's own default, and the test below asserts that the two say the same name."""


def scratch_tables(backend: PostgresBackend) -> list[str]:
    """What the scratch schema holds, read back over the same read-only login."""
    result = backend.execute(SCRATCH_TABLES_SQL, statement_timeout_seconds=TIMEOUT_SECONDS)
    return [str(row[0]) for row in result.rows]


def values_of(document: dict[str, Any], side: str) -> list[object]:
    """The rows of one side of a counterexample's difference, as the values they hold."""
    groups = cast("list[dict[str, Any]]", document["differing_rows"][side])
    return [cast("dict[str, Any]", group["row"][0])["value"] for group in groups]


def result_values(document: dict[str, Any]) -> list[object]:
    """The first column of a record's result, which is what every gold here projects."""
    rows = cast("list[list[dict[str, Any]]]", document["result"]["rows"])
    return [row[0]["value"] for row in rows]


@pytest.fixture(scope="module")
def audited(sandbox_backend: PostgresBackend, tmp_path_factory: pytest.TempPathFactory) -> Run:
    """One audit of the eight questions with the three corrections, run once for this file."""
    return audit(sandbox_backend, tmp_path_factory.mktemp("audit"), predictions=PREDICTIONS_FILE)


def test_every_question_prints_the_line_adr_0013_writes_down(audited: Run) -> None:
    """The eight lines, whole: the id, the database, the replay rule, the verdict, the smells
    and the directory. A defect that stopped reproducing changes one of these."""
    out = audited.out.as_posix()

    assert audited.line_of("1029") == (
        f"q1029 european_football_2 R-ORD  NOT_EQUAL  smells=none  {out}/q1029/"
    )
    assert audited.line_of("879") == (
        f"q879  formula_1   R-ORD  NOT_EQUAL  smells=ordering-over-numeric-text  {out}/q879/"
    )
    assert audited.line_of("207") == f"q207  toxicology  R-SET  NOT_EQUAL  smells=none  {out}/q207/"
    assert audited.line_of("900001") == (
        f"q900001 synthetic   R-ORD  GOLD-ONLY  smells=float-aggregate-order  {out}/q900001/"
    )
    assert audited.line_of("900002") == (
        "q900002 synthetic   R-ORD  GOLD-ONLY  "
        f"smells=arbitrary-cut,not-a-function-of-the-data  {out}/q900002/"
    )
    assert audited.line_of("900003") == (
        "q900003 synthetic          ERROR      smells=none  "
        "run: row_counts: permission denied for table sealed"
    )
    assert audited.line_of("900004") == (
        f"q900004 synthetic   R-ORD  GOLD-ONLY  smells=ordering-over-numeric-text  {out}/q900004/"
    )
    assert audited.line_of("900005") == (
        f"q900005 synthetic   R-ORD  GOLD-ONLY  smells=ordering-over-numeric-text  {out}/q900005/"
    )
    assert audited.lines[-1] == SUMMARY_LINE


def test_a_table_the_auditor_may_not_read_is_not_a_table_that_is_not_there(audited: Run) -> None:
    """``public.sealed`` is in the fixture and revoked from the auditor, so the summary names
    it as unreadable and not as missing: the first is repaired with a GRANT and the second in
    the question file, and a run that spelled them the same way sent the reader to the wrong
    one. The question that reads it is its own line with the server's own message, and the
    five the auditor may read are audited as they were before it existed."""
    written = audited.summary_document()["fixture"]
    line = audited.line_of("900003")

    assert written["unreadable_tables"] == ["sealed"]
    assert written["missing_tables"] == []
    assert "sealed" not in written["measured_tables"]
    assert "ERROR" in line
    assert "run: row_counts: permission denied for table sealed" in line, (
        "the measurement both records are made under is neither statement's"
    )
    assert audited.summary.verdicts["ERROR"] == 1
    assert not audited.directory("900003").exists(), "a question that errored wrote a directory"


def test_a_disagreement_is_exit_status_one(audited: Run) -> None:
    """ADR-0013 point 2: the counts live in the summary and never in the exit code."""
    assert audited.summary.exit_status == 1
    assert audited.summary.not_equal == 3
    assert ComparabilityResult.NOT_COMPARABLE.name not in audited.summary.verdicts
    assert audited.summary_document()["exit_status"] == 1


def test_the_summary_states_the_shuffled_copies_the_run_made(audited: Run) -> None:
    written = audited.summary_document()["shuffle"]

    assert written["prepared"] is True
    assert written["reason"] == ""
    assert written["scratch_schema"] == DEFAULT_SCRATCH_SCHEMA
    assert written["copied"] == COPIED_TABLES
    assert written["skipped"] == {}
    assert written["not_reached_by_a_copy"] == NOT_COPIED


def test_the_summary_names_the_server_and_the_grammar_that_judged_this_run(
    audited: Run, sandbox_backend: PostgresBackend
) -> None:
    """What a reader needs to compare this summary with another one: the build the rows came
    from, beside the version number it already had, and the parser that decided every
    statement was one SELECT. The gather is read from the server twice, once before the
    questions and once after them, because every execution sets it to 0 on its own
    transaction and a value that survived the run would mean one of those rollbacks did
    not.

    The two memory settings are stated the other way round, beside this run's own choices
    rather than among the session's: they are what every statement was held to, in the
    kilobytes and the bare multiple ``pg_settings`` reports, and a real server answered
    the read-back that produced them.

    The four the recorded block gained are asserted present rather than equal to a value:
    the encoding, the provider, the ICU locale and the collation version are whatever the
    container's own database holds, and what a record has to state is that they were read.
    ``datcollversion`` and ``daticulocale`` are empty on a database that has none, so their
    presence is the assertion and not their content."""
    written = audited.summary_document()
    recorded = written["session_settings_recorded"]
    major = str(int(recorded["server_version_num"]) // 10_000)
    afterwards = sandbox_backend.session_settings().recorded["max_parallel_workers_per_gather"]

    assert recorded["server_version"].startswith(major)
    assert recorded["max_parallel_workers_per_gather"] == afterwards
    assert written["settings"]["work_mem"] == "4096"
    assert written["settings"]["hash_mem_multiplier"] == "2"
    assert recorded["server_encoding"]
    assert recorded["datlocprovider"] in {"c", "i"}
    assert set(recorded) >= {"server_encoding", "datlocprovider", "daticulocale", "datcollversion"}
    assert written["parser"]["validator"] == VALIDATOR_VERSION
    assert written["parser"]["postgast"]
    assert isinstance(written["parser"]["grammar_version"], int)
    assert written["parser"]["grammar_version"] > 0


def test_each_disagreement_is_a_directory_a_reader_can_open(audited: Run) -> None:
    """Three files per defect: what differs, and the record of each side that says so."""
    for question_id in DEFECTS:
        directory = audited.directory(question_id)
        assert sorted(path.name for path in directory.iterdir()) == sorted(
            [COUNTEREXAMPLE_FILE, GOLD_RECORD_FILE, SECOND_RECORD_FILE, SMELLS_FILE]
        )
        counterexample = audited.document(question_id, COUNTEREXAMPLE_FILE)
        assert counterexample["verdict"]["result"] == "not_equal"
        # BIRD scores all three at zero, which is the honest half of the finding: the
        # benchmark's own evaluator marks the correction wrong.
        assert counterexample["bird_ex"]["value"] == 0


def test_1029_returns_the_four_slowest_where_the_question_asked_for_the_fastest(
    audited: Run,
) -> None:
    """The gold's ASC NULLS FIRST against the correction's DESC NULLS LAST, under R-ORD.

    The records hold each side in the order its own statement returned it; the difference
    below is keyed by row and is grouped in its own order, which is why both are read.
    """
    counterexample = audited.document("1029", COUNTEREXAMPLE_FILE)
    gold = result_values(audited.document("1029", GOLD_RECORD_FILE))
    second = result_values(audited.document("1029", SECOND_RECORD_FILE))

    assert counterexample["replay_rule"] == "R-ORD"
    assert gold == [20, 23, 31, 44]
    assert second == [80, 77, 70, 62]
    # Every speed the gold returned is below every speed the correction returned: the two
    # answers share no row at all, which is what the difference states from both sides.
    assert values_of(counterexample, "in_gold_not_in_second") == [20, 23, 31, 44]
    assert sorted(cast("list[int]", values_of(counterexample, "in_second_not_in_gold"))) == [
        62,
        70,
        77,
        80,
    ]


def test_879_orders_the_speeds_as_text_and_lands_on_another_driver(audited: Run) -> None:
    counterexample = audited.document("879", COUNTEREXAMPLE_FILE)

    assert counterexample["replay_rule"] == "R-ORD"
    assert values_of(counterexample, "in_gold_not_in_second") == ["Norwegian"]
    assert values_of(counterexample, "in_second_not_in_gold") == ["Peruvian"]
    smells = audited.document("879", SMELLS_FILE)["smells"]
    assert [entry["name"] for entry in smells if entry["fired"]] == ["ordering-over-numeric-text"]


def test_207_reaches_every_atom_of_a_molecule_that_holds_a_double_bond(audited: Run) -> None:
    """The gold joins through the molecule, so its elements are a strict superset."""
    gold = set(result_values(audited.document("207", GOLD_RECORD_FILE)))
    second = set(result_values(audited.document("207", SECOND_RECORD_FILE)))
    counterexample = audited.document("207", COUNTEREXAMPLE_FILE)

    assert counterexample["replay_rule"] == "R-SET"
    assert gold == {"c", "o", "n"}
    assert second == {"c", "o"}
    assert gold > second
    assert values_of(counterexample, "in_second_not_in_gold") == []


def test_the_two_gold_only_questions_fire_the_smells_the_fixture_was_written_for(
    audited: Run,
) -> None:
    """A sum whose last digit is the read order, and a bound with a three-way tie under it."""
    spend = audited.document("900001", SMELLS_FILE)["smells"]
    fired = next(entry for entry in spend if entry["fired"])
    assert fired["name"] == "float-aggregate-order"
    assert fired["evidence"]["shuffled_copies"]["differs"] is True
    assert [cell["column"] for cell in fired["evidence"]["float_cells"]] == ["sum", "sum", "sum"]

    scores = audited.document("900002", SMELLS_FILE)["smells"]
    assert [entry["name"] for entry in scores if entry["fired"]] == [
        "arbitrary-cut",
        "not-a-function-of-the-data",
    ]
    assert not (audited.out / "q900001" / COUNTEREXAMPLE_FILE).exists(), "there was no prediction"


def test_a_gold_that_names_a_schema_is_measured_and_read_under_that_schema(audited: Run) -> None:
    """Two tables called ``y`` in two schemas, each with a ``weight`` declared differently.

    The summary measures both under the names the golds wrote, and each gold's smells read the
    columns of the table its own statement named: the bigint one has nothing to find, and the
    text one holding numerals is exactly what the first smell is for. Resolving either by the
    relation alone would have answered both questions about one of the two tables.
    """
    measured = audited.summary_document()["fixture"]["measured_tables"]
    quoted = audited.document("900004", SMELLS_FILE)["smells"]
    public = audited.document("900005", SMELLS_FILE)["smells"]
    quoted_key = _ordering_key(quoted)
    public_key = _ordering_key(public)

    assert {"Quoted.y", "public.y"} <= set(measured)
    assert quoted_key["column"] == "Quoted.y.weight"
    assert public_key["column"] == "public.y.mass"
    # The census is the proof that the rows read were the named table's own: four in the one
    # schema and three in the other, and neither table holds the other's column at all.
    assert quoted_key["census"]["rows"] == 4
    assert public_key["census"]["rows"] == 3
    assert (quoted_key["verdict"], public_key["verdict"]) == ("not_equal", "not_equal")
    assert [entry["name"] for entry in quoted if entry["fired"]] == ["ordering-over-numeric-text"]
    assert [entry["name"] for entry in public if entry["fired"]] == ["ordering-over-numeric-text"]


def test_a_gold_that_names_a_schema_is_told_the_shuffle_did_not_cover_it(audited: Run) -> None:
    """The copies are reached by the search path and a qualified name consults none, so the
    rerun read the table itself. The smell says which tables it did not shuffle and why, the
    way it says which were too large, rather than reporting a rerun over data that never moved.
    """
    shuffle = _shuffle_of(audited.document("900004", SMELLS_FILE)["smells"])

    assert shuffle["tables"] == ["Quoted.y"]
    assert shuffle["tables_not_shuffled"] == ["Quoted.y"]
    assert shuffle["tables_not_reached_by_a_copy"] == NOT_COPIED
    assert shuffle["tables_skipped_for_size"] == {}
    # The bare name of the same fixture is copied, so what is not covered here is the spelling
    # and not the table: nothing about q900004 stopped the shuffle from running.
    assert "scores" in audited.summary_document()["shuffle"]["copied"]


def test_a_gold_only_run_exits_zero_until_a_heuristic_is_asked_to_block(
    sandbox_backend: PostgresBackend, tmp_path: Path
) -> None:
    """Smells are heuristics: they report by default and fail a run only when asked to."""
    quiet = audit(sandbox_backend, tmp_path / "quiet")
    blocking = audit(sandbox_backend, tmp_path / "blocking", fail_on_smell=True)

    assert quiet.summary.exit_status == 0
    assert quiet.summary.not_equal == 0
    assert quiet.summary.smells_fired == 6
    assert blocking.summary.exit_status == 1
    assert blocking.summary.smells_fired == 6


def test_the_experimental_smell_reads_the_question_against_the_gold(
    sandbox_backend: PostgresBackend, tmp_path: Path
) -> None:
    """q1029 asks for the highest speeds and its gold orders ascending, which is s2's case."""
    asked = audit(sandbox_backend, tmp_path / "s2", ids=(1029,), experimental_s2=True)

    assert asked.line_of("1029") == (
        "q1029 european_football_2 R-ORD  GOLD-ONLY  smells=direction-against-question  "
        f"{asked.out.as_posix()}/q1029/"
    )


def test_the_console_script_runs_the_same_audit_as_its_own_process(tmp_path: Path) -> None:
    """The ``[project.scripts]`` entry, proven the only way it can be: by running it.

    This is the command ADR-0013 point 2 puts in front of a stranger, run as a stranger
    would run it, with the experimental smell asked for so that its line is exercised too.
    """
    uv = shutil.which("uv")
    assert uv is not None, "uv is how this project is run"
    finished = subprocess.run(  # noqa: S603
        [
            uv,
            "run",
            "attestql",
            "audit",
            "--dsn",
            os.environ[SANDBOX_DSN],
            "--questions",
            str(QUESTIONS_FILE),
            "--predictions",
            str(PREDICTIONS_FILE),
            "--out",
            str(tmp_path / "audit"),
            "--experimental-s2",
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )

    assert finished.returncode == 1, finished.stderr
    assert finished.stdout.splitlines()[-1] == EXPERIMENTAL_SUMMARY_LINE


def test_the_run_leaves_no_table_behind_in_the_scratch_schema(
    audited: Run, sandbox_backend: PostgresBackend
) -> None:
    """The copies are this tool's own and outlive nothing; the schema is not its to remove."""
    assert f"'{DEFAULT_SCRATCH_SCHEMA}'" in SCRATCH_TABLES_SQL
    assert audited.summary_document()["shuffle"]["copied"] == COPIED_TABLES
    assert scratch_tables(sandbox_backend) == []


def _ordering_key(smells: list[dict[str, Any]]) -> dict[str, Any]:
    """The one ordering key the numeric-text smell resolved, out of that question's smells."""
    found = next(entry for entry in smells if entry["name"] == "ordering-over-numeric-text")
    keys = cast("list[dict[str, Any]]", found["evidence"]["keys"])
    assert len(keys) == 1, keys
    return keys[0]


def _shuffle_of(smells: list[dict[str, Any]]) -> dict[str, Any]:
    """What the rerun smell said its shuffle covered of that question's tables."""
    found = next(entry for entry in smells if entry["name"] == "not-a-function-of-the-data")
    return cast("dict[str, Any]", found["evidence"]["shuffle"])


def advisory(backend: PostgresBackend, function: str) -> bool:
    """One advisory lock question over the scratch schema's key, as another run would ask it.

    The key is derived here the way the backend derives it, so the test and the code cannot
    disagree about which lock is being asked for.
    """
    statement = f"SELECT {function}({_lock_key(DEFAULT_SCRATCH_SCHEMA)})"
    result = backend.execute(statement, statement_timeout_seconds=TIMEOUT_SECONDS)
    return bool(result.rows[0][0])


def test_a_second_connection_cannot_take_the_scratch_schema_while_the_copies_are_there(
    sandbox_backend: PostgresBackend,
) -> None:
    """The lock is held for the run, not for the transaction that made the copies.

    A second connection asks for the same key on the same server and is refused for as long
    as the copies are there: this is what keeps two runs told one scratch schema from
    reading and dropping each other's tables. ``pg_try_advisory_lock`` rather than the
    waiting one, so a schema this test cannot have is a false and not a hung suite, and what
    it is granted once the copies are gone it gives back.
    """
    other = PostgresBackend.connect(os.environ[SANDBOX_DSN])
    sandbox_backend.prepare_shuffled_copies(
        (TableName("", "drivers"),), seed="lock", row_limit=1_000
    )
    try:
        assert advisory(other, "pg_try_advisory_lock") is False
    finally:
        sandbox_backend.drop_shuffled_copies()

    assert advisory(other, "pg_try_advisory_lock") is True
    assert advisory(other, "pg_advisory_unlock") is True
