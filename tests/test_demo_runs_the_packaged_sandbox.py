"""``attestql demo``: the sandbox the package carries, written out and audited in one command.

Why the command exists at all. The audit is given a database, a question file and a prediction
file, and a person who has just installed the wheel holds none of the three, so the first
command they were told to run had nothing to run over. ``demo`` writes all three where it is
told and audits them, and the three files come out of the package itself, which is why this
test also asserts that they are there to come out of: a wheel built without them would fail
here rather than on the machine of whoever installed it.

What is observed is that the command writes what it audits, that the lines are the audit's own
and not a second rendering of them, and that the ``rerun:`` line printed last is the run it
just made: the arguments are taken off that line and fed back to the command, and the same
verdicts come out. The whole sandbox is a file, so this needs no container, no port and no
credential and is never skipped, like ``tests/test_audit_sandbox_sqlite.py``, which audits the
same six questions through ``run_audit`` and reads the evidence they leave.
"""

from __future__ import annotations

import io
import json
from collections.abc import Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from attestql.audit.cli import MARKER_FILE, SUMMARY_FILE, main
from attestql.demo import FIXTURE_FILE, FIXTURE_SQL, PREDICTIONS_FILE, QUESTIONS_FILE

pytestmark = pytest.mark.sandbox_sqlite

AUDITED = (
    ("q1029", "NOT_EQUAL"),
    ("q879", "NOT_EQUAL"),
    ("q207", "NOT_EQUAL"),
    ("q900001", "GOLD-ONLY"),
    ("q900002", "GOLD-ONLY"),
    ("q900005", "EQUAL"),
)
"""Every question of the packaged sandbox and the verdict it produces, in the order asked.

Three shipped Mini-Dev golds against their corrections, two synthetic questions with no
prediction to compare, and one whose prediction answers it another way and agrees."""

SUMMARY_LINE = (
    "6 questions: 3 NOT_EQUAL, 5 smells fired, "
    "0 credited by BIRD but NOT_EQUAL (0 multiplicity, 0 type, 0 order, 0 truncation), "
    "0 timed out (0 gold, 0 prediction)"
)
"""The whole of the demo's second-to-last line, which is the audit's own summary line and is
stated here as it is in the sandbox tests, so that a change to the fixture, the questions or a
probe is a change to this file too."""

RERUN_LINE = (
    "rerun: attestql audit --engine sqlite --dsn demo/fixture.sqlite "
    "--questions demo/questions.json --predictions demo/predictions.json --out demo/audit"
)
"""The last line of a demo run with ``--out demo`` from the directory below it: the audit that
was just run, over the paths as the command line gave them, so that a reader can type it where
they are standing."""


@dataclass(frozen=True)
class Demonstration:
    """One run of the command: what it answered, what it printed and where it wrote."""

    status: int
    lines: list[str]
    out: Path


def run(argv: Sequence[str]) -> tuple[int, list[str]]:
    """The command, with the lines kept instead of printed.

    Through ``main`` and not through ``run_demo``, because what is being observed includes the
    subcommand reaching the audit: a test that called the runner directly would say nothing
    about the command line a reader types.
    """
    printed = io.StringIO()
    with redirect_stdout(printed):
        status = main(argv)
    return status, printed.getvalue().splitlines()


def demonstrate(out: Path) -> Demonstration:
    """One ``attestql demo`` into that directory."""
    status, lines = run(["demo", "--out", str(out)])
    return Demonstration(status, lines, out)


def verdicts(lines: Sequence[str]) -> list[tuple[str, str]]:
    """Each question line of a run as the question it answered and the verdict it states."""
    columns = [line.split() for line in lines]
    return [(found[0], found[3]) for found in columns if found and found[0].startswith("q")]


def document(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def demonstrated(tmp_path_factory: pytest.TempPathFactory) -> Demonstration:
    """One demo into a fresh directory, shared by the readings that only look at it."""
    return demonstrate(tmp_path_factory.mktemp("demo") / "sandbox")


def test_the_demo_writes_the_sandbox_it_audits_into_the_directory_it_was_given(
    demonstrated: Demonstration,
) -> None:
    """The three files a run needs, and the audit's own directory beside them. The status is
    one because three of the golds disagree with their corrections on this data, which is the
    finding this sandbox exists to show and not the command failing."""
    out = demonstrated.out
    audit = out / "audit"

    assert demonstrated.status == 1
    assert (out / FIXTURE_FILE).is_file()
    assert (out / QUESTIONS_FILE.name).is_file()
    assert (out / PREDICTIONS_FILE.name).is_file()
    assert (audit / SUMMARY_FILE).is_file()
    assert (audit / MARKER_FILE).is_file(), "the audit's own directory, marked as every run's is"
    assert document(audit / SUMMARY_FILE)["verdicts"] == {
        "NOT_EQUAL": 3,
        "GOLD-ONLY": 2,
        "EQUAL": 1,
    }


def test_the_demo_prints_the_audit_s_own_lines_and_then_the_command_that_made_them(
    demonstrated: Demonstration,
) -> None:
    """One line per question, the summary line, and the rerun line after it. Nothing is
    rendered twice: the lines are the ones the audit wrote to the same writer."""
    lines = demonstrated.lines
    audit = str(demonstrated.out / "audit")

    assert verdicts(lines) == list(AUDITED)
    assert lines[-2] == SUMMARY_LINE
    assert lines[-1] == (
        f"rerun: attestql audit --engine sqlite --dsn {demonstrated.out / FIXTURE_FILE} "
        f"--questions {demonstrated.out / QUESTIONS_FILE.name} "
        f"--predictions {demonstrated.out / PREDICTIONS_FILE.name} --out {audit}"
    )


def test_the_command_the_demo_prints_is_the_run_it_just_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The line is taken at its word: its arguments are handed straight back to the command,
    and the same six verdicts come out over the files the demo wrote.

    Run from inside a directory of its own with a relative ``--out``, which is how a reader
    runs it and the case a printed absolute path would get wrong: what the line states is what
    the command line was given, so it stays typeable where the reader is standing.
    """
    monkeypatch.chdir(tmp_path)
    demonstrated = demonstrate(Path("demo"))

    assert demonstrated.lines[-1] == RERUN_LINE

    arguments = demonstrated.lines[-1].removeprefix("rerun: ").split()
    assert arguments[0] == "attestql", "the line names the command a reader types"

    status, lines = run(arguments[1:])

    assert status == demonstrated.status == 1
    assert verdicts(lines) == verdicts(demonstrated.lines) == list(AUDITED)


def test_a_second_demo_into_the_same_directory_is_a_clean_rerun(tmp_path: Path) -> None:
    """The sandbox is the demo's own, so it is written every time: a fixture deleted and a
    question file emptied between the two runs are both back, and the audit's directory is
    cleared by the marker rule rather than refused for holding the run before it."""
    out = tmp_path / "sandbox"
    first = demonstrate(out)
    (out / FIXTURE_FILE).unlink()
    (out / QUESTIONS_FILE.name).write_text("[]", encoding="utf-8")

    second = demonstrate(out)

    assert first.status == second.status == 1
    assert verdicts(second.lines) == verdicts(first.lines) == list(AUDITED)
    assert second.lines[-2] == SUMMARY_LINE
    assert document(out / "audit" / SUMMARY_FILE)["question_set"]["entries"] == 6


def test_the_package_carries_the_three_files_the_demo_writes_out() -> None:
    """The wheel ships them beside the module that names them, which is what makes the command
    above run at all on a machine that holds nothing but the installed package."""
    beside = Path(__file__).resolve().parents[1] / "src" / "attestql" / "demo"

    for packaged in (FIXTURE_SQL, QUESTIONS_FILE, PREDICTIONS_FILE):
        assert packaged.is_file(), packaged
        assert packaged.parent == beside


def test_a_directory_the_demo_cannot_be_written_into_is_the_tool_failing_to_start(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--out`` naming a file is exit status 2 with the reason on stderr, as every other way
    this tool cannot run at all is: nothing was audited, so nothing is being reported."""
    taken = tmp_path / "sandbox"
    taken.write_text("mine\n", encoding="utf-8")

    status, lines = run(["demo", "--out", str(taken)])

    assert status == 2
    assert lines == []
    assert f"attestql: the demo cannot be written into {taken}" in capsys.readouterr().err
