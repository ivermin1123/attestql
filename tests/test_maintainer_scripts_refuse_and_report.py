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

REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "tools" / "site-select" / "audits.sh"
SANDBOX = REPOSITORY / "tools" / "audit-sandbox" / "run.sh"


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


# `run.sh`: what it accepts as an output directory
#
# The harness writes a server's whole data directory into `--out`, and the guard that it is
# outside the repository read `cd && pwd`, which is a logical path: every symlink is still in
# it. A link under the repository pointing at a directory outside it therefore resolved to a
# path the guard accepted, and the harness then wrote through the link, back into the working
# tree. `render.py` makes the same check on a resolved path, which is what this now is.
#
# Only the guard is driven. `docker` and `lsof` are shims on PATH, so the tests need no
# container, no port and no network: what the shim records is whether the script reached the
# step after the guard.


def guard(tmp_path: Path, out: Path) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the sandbox harness far enough to answer the guard, and no further."""
    shims = tmp_path / "shims"
    shims.mkdir()
    reached = tmp_path / "reached-docker"
    (shims / "docker").write_text(
        f'#!/bin/sh\necho "$@" >> "{reached}"\nexit 1\n', encoding="utf-8"
    )
    # Nothing is listening on the harness's port as far as these tests are concerned: the
    # machine's own ports are not what is under test here.
    (shims / "lsof").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    for shim in shims.iterdir():
        shim.chmod(0o755)
    environment = dict(os.environ, PATH=f"{shims}:{os.environ.get('PATH', '')}")
    finished = subprocess.run(  # noqa: S603
        ["bash", str(SANDBOX), str(out), "--", "true"],  # noqa: S607
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    return finished, reached


def test_an_output_directory_that_is_a_symlink_into_the_repository_is_refused(
    tmp_path: Path,
) -> None:
    """The reproduction the review recorded: a logical path walks straight through the check."""
    link = tmp_path / "somewhere-outside"
    link.symlink_to(REPOSITORY / "build", target_is_directory=True)

    finished, reached = guard(tmp_path, link)

    assert finished.returncode == 2, finished.stdout
    assert "symlink" in finished.stderr
    assert not reached.exists(), "the refusal comes before the container"


def test_an_output_directory_reached_through_a_symlink_is_refused_by_the_resolved_path(
    tmp_path: Path,
) -> None:
    """The link is a directory of the path rather than its last part, so the name check above
    does not see it and the resolved path is what refuses."""
    inside = REPOSITORY / "build" / "attestql-sandbox-symlink-test"
    inside.mkdir(parents=True, exist_ok=True)
    link = tmp_path / "by-way-of"
    link.symlink_to(REPOSITORY / "build", target_is_directory=True)

    try:
        finished, reached = guard(tmp_path, link / "attestql-sandbox-symlink-test")

        assert finished.returncode == 2, finished.stdout
        assert "must be outside the repository" in finished.stderr
        assert not reached.exists()
    finally:
        inside.rmdir()


def test_an_output_directory_outside_the_repository_passes_the_guard(tmp_path: Path) -> None:
    """The other half: a plain directory outside is what the harness is for, and the run gets
    as far as the container step this test then refuses to run."""
    out = tmp_path / "sandbox"

    finished, reached = guard(tmp_path, out)

    assert "must be outside the repository" not in finished.stderr
    assert "symlink" not in finished.stderr
    assert reached.is_file(), "the guard passed and the harness reached docker"
