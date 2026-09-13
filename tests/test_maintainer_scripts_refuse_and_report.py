"""The maintainer scripts under `tools/`, run.

These are shell, so the only way to observe what they do is to run them, and this file is the
second of the two `tests/test_boundary.py` permits to start a process. Every test here drives a
script with a work directory of its own and stops it before it opens a database, a container or
a port, so the file needs no Docker, no network and no port.

## `audits.sh`: what it says when a rerun of a crowded run fails

The first pass was taught on 2026-09-11 to collect the status of every job it started, and it
reports a failure now instead of printing its DONE marker over one. `rerun_timeouts`, which runs
after that pass, was left out: it moves the crowded answer aside as `<name>.under-load`, makes
the run again alone, and then reads the new summary without ever looking at what the run
returned. A rerun that never happened therefore left the moved directory as the only copy of the
run and the whole stage still exited 0.

The reproduction needs no audit and no server. A work directory holding one summary that names a
question the bound stopped, and a question file naming no database, is enough: `sqlite_one`
refuses before it opens anything, and what is asserted is the exit code the operator sees.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "site-select" / "audits.sh"


def work_directory(root: Path, out: Path) -> Path:
    """A work directory holding one run whose summary says the bound stopped a question."""
    out.mkdir(parents=True)
    (out / "summary.json").write_text(json.dumps({"timed_out": {"gold": [5]}}), encoding="utf-8")
    questions = root / "data" / "questions"
    questions.mkdir(parents=True)
    # No entry names any database, so the rerun refuses before it opens a file.
    (questions / "dev_20251106-00000-of-00001.json").write_text("[]", encoding="utf-8")
    return root


def rerun(root: Path, prefix: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ, RUNS_WORK=str(root), ATTESTQL=str(root / "attestql-absent"))
    return subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT), "rerun", prefix],  # noqa: S607
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


def test_a_rerun_that_failed_is_reported_rather_than_counted_as_done(tmp_path: Path) -> None:
    """The exit code is the whole finding: the operator's only signal that a run is missing."""
    out = tmp_path / "runs" / "bird-dev-sqlite" / "dev-20251106" / "california_schools"
    work_directory(tmp_path, out)

    finished = rerun(tmp_path, "runs/bird-dev-sqlite/")

    assert finished.returncode != 0, finished.stdout
    assert "1 rerun(s) under runs/bird-dev-sqlite/ failed" in finished.stderr


def test_a_failed_rerun_says_where_the_only_copy_of_the_run_is(tmp_path: Path) -> None:
    """The crowded answer is what is left, and the message names it rather than the operator
    finding an empty directory where the run was."""
    out = tmp_path / "runs" / "bird-dev-sqlite" / "dev-20251106" / "california_schools"
    work_directory(tmp_path, out)

    finished = rerun(tmp_path, "runs/bird-dev-sqlite/")

    assert "the only copy of this run" in finished.stderr
    assert (out.parent / "california_schools.under-load" / "summary.json").is_file()


def test_a_run_whose_shape_has_no_rerun_rule_is_a_failure_too(tmp_path: Path) -> None:
    """An unknown benchmark is a run this script cannot make again, so it is not a pass."""
    out = tmp_path / "runs" / "not-a-benchmark" / "some-group" / "california_schools"
    work_directory(tmp_path, out)

    finished = rerun(tmp_path, "runs/not-a-benchmark/")

    assert finished.returncode != 0, finished.stdout
    assert "no rule for" in finished.stderr
    # Nothing could be made again, so the run itself is put back where it was.
    assert (out / "summary.json").is_file()


def test_a_work_directory_with_nothing_to_rerun_passes(tmp_path: Path) -> None:
    """The counter is of failures, not of runs: an untouched pass still exits 0."""
    (tmp_path / "runs").mkdir()

    finished = rerun(tmp_path, "runs/")

    assert finished.returncode == 0, finished.stderr
    assert "runs the bound stopped something in: 0" in finished.stdout
