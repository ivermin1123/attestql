"""The server goes away under a run, on the sandbox, between two real questions.

``tests/test_audit_command_runs_over_a_question_file.py`` states this against a backend
that was told to refuse. This file is the same claim against a server that really closed
the socket: the audit opens its own connection, the test learns which backend that is,
and after the first question's line is printed the connection is terminated from the
sandbox's own read-only login, which may signal it because both are the same role.

What has to hold afterwards is what a maintainer would look for. The questions after the
kill are error lines carrying the server's message, ``summary.json`` is on disk with them
in ``errors``, and the exit status is the one the questions that were answered earned,
because a question the run could not answer is neither a disagreement nor this tool
failing. The scratch schema holds nothing: this run copies no table into it, and a run
whose connection died cannot drop what it never made.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.cli import SUMMARY_FILE, AuditOptions, run_audit
from attestql.audit.postgres import DEFAULT_SCRATCH_SCHEMA, PostgresBackend

pytestmark = pytest.mark.sandbox

REPOSITORY = Path(__file__).resolve().parent.parent
QUESTIONS_FILE = REPOSITORY / "tools" / "audit-sandbox" / "questions.json"

SANDBOX_DSN = "ATTESTQL_AUDIT_DSN"
"""The connection string the sandbox runner exported, which carries no password."""

TIMEOUT_SECONDS = 30
DATA_AS_OF = datetime(2026, 9, 2, tzinfo=UTC)

QUESTION_IDS = (1029, 879, 207)
"""Three questions, audited in this order, so that one is answered before the kill and
two after it."""

APPLICATION = "attestql-lost-connection"
"""What the audit's own connection calls itself, so that the statement which terminates it
is a constant naming a session rather than a number built into SQL."""

BACKEND_PID_SQL = "SELECT pg_backend_pid()"

TERMINATE_SQL = (
    "SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity "
    "WHERE application_name = 'attestql-lost-connection'"
)
"""The kill. ``WHERE`` is applied before the projection, so nothing but the audit's own
session is signalled, and the role doing the signalling is the role that owns it."""

SCRATCH_TABLES_SQL = (
    "SELECT tablename FROM pg_tables WHERE schemaname = 'attestql_scratch' ORDER BY tablename"
)


class KillsTheAuditsConnection:
    """A writer that takes the server away once the first question has been answered.

    The audit prints a question's line when it is done with it, so a writer runs exactly
    between two questions, which is where a connection is lost in the failure this file is
    about.
    """

    def __init__(self, killer: PostgresBackend) -> None:
        self.written: list[str] = []
        self.terminated: tuple[int, ...] = ()
        self._killer = killer

    def line(self, text: str) -> None:
        self.written.append(text)
        if len(self.written) == 1:
            result = self._killer.execute(TERMINATE_SQL, statement_timeout_seconds=TIMEOUT_SECONDS)
            self.terminated = tuple(int(str(row[0])) for row in result.rows)


def backend_pid(backend: PostgresBackend) -> int:
    result = backend.execute(BACKEND_PID_SQL, statement_timeout_seconds=TIMEOUT_SECONDS)
    return int(str(result.rows[0][0]))


def scratch_tables(backend: PostgresBackend) -> list[str]:
    result = backend.execute(SCRATCH_TABLES_SQL, statement_timeout_seconds=TIMEOUT_SECONDS)
    return [str(row[0]) for row in result.rows]


def options(out: Path) -> AuditOptions:
    """The run, with the shuffle limited to tables of one row so that it copies nothing.

    Every table in the sandbox fixture holds more than one, which the assertion on the
    summary below states: a run whose connection dies cannot drop a copy it committed, so
    this one commits none and the scratch schema is untouched either way.
    """
    return AuditOptions(
        dsn=os.environ[SANDBOX_DSN],
        questions=QUESTIONS_FILE,
        out=out,
        ids=QUESTION_IDS,
        shuffle_row_limit=1,
        statement_timeout_seconds=TIMEOUT_SECONDS,
        data_as_of=DATA_AS_OF,
    )


def test_a_connection_that_dies_between_two_questions_errors_the_rest_and_writes_the_summary(
    sandbox_backend: PostgresBackend, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One question answered, the server gone, two error lines, and a summary on disk."""
    assert f"'{APPLICATION}'" in TERMINATE_SQL
    audited = PostgresBackend.connect(f"{os.environ[SANDBOX_DSN]} application_name={APPLICATION}")
    pid = backend_pid(audited)
    assert pid != backend_pid(sandbox_backend), "the audit and this test share one connection"
    writer = KillsTheAuditsConnection(sandbox_backend)
    out = tmp_path / "audit"

    summary = run_audit(options(out), audited, writer)

    assert writer.terminated == (pid,), "the wrong backend was terminated"
    assert writer.written[0].startswith("q1029 ")
    assert "GOLD-ONLY" in writer.written[0]
    errored = writer.written[1:3]
    assert [line.startswith(("q879 ", "q207 ")) for line in errored] == [True, True]
    assert all("ERROR" in line for line in errored)
    assert all(line.rsplit("smells=none", 1)[1].strip() for line in errored), "no message"
    assert [error.question_id for error in summary.errors] == [879, 207]
    assert {error.step for error in summary.errors} == {"schema_digest"}
    # One question was audited and it agreed with nothing and disagreed with nothing, so
    # the two the run could not answer leave the status where the verdicts put it.
    assert summary.exit_status == 0

    document = cast("dict[str, Any]", json.loads((out / SUMMARY_FILE).read_text(encoding="utf-8")))
    assert [entry["question_id"] for entry in document["errors"]] == [879, 207]
    assert document["verdicts"] == {"GOLD-ONLY": 1, "ERROR": 2}
    assert document["exit_status"] == 0
    assert document["fixture"]["missing_tables"] == []
    assert document["fixture"]["unreadable_tables"] == []
    assert document["shuffle"]["copied"] == [], "a copy this run cannot drop was committed"
    assert "the scratch copies were left behind" in capsys.readouterr().err
    assert f"'{DEFAULT_SCRATCH_SCHEMA}'" in SCRATCH_TABLES_SQL
    assert scratch_tables(sandbox_backend) == []
