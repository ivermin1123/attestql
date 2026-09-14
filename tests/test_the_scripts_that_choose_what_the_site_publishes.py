"""The three maintainer scripts that decide what reaches attestql.com and what a release holds.

`select_questions.py` chooses the question directories the site is about, `manifest.py` states
what each release archive holds, and `question_ids.py` is what tells one audit which questions
of a question file belong to the database it was pointed at. Nothing a reader sees is checked
against a server: what these three write is read by the site build and by a run page, and a
number one of them gets wrong is a number a page states.

What is not here is here already, and duplicating it would make two places to change: the budget
cut is `tests/test_the_budget_cut_leaves_every_benchmark_a_share.py`, the output directory's
lifecycle is `tests/test_selection_empties_only_its_own_directory.py`, and the release notes,
`notes.py` whole, are `tests/test_release_notes_describe_what_was_built.py`. This file covers
what those three leave: the run discovery, the release-asset line each run is given, the whole
of `manifest.py`, and `question_ids.py`.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tarfile
from pathlib import Path

import manifest
import pytest
import question_ids
import select_questions as selection


def write(path: Path, document: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def run_directory(root: Path, slug: str, questions: tuple[int, ...] = ()) -> Path:
    """One audit directory: the summary that makes it a run, and its question directories."""
    audit = root / slug
    write(audit / selection.SUMMARY_FILE, {"run_id": f"audit-{slug.replace('/', '-')}"})
    for question_id in questions:
        write(audit / f"q{question_id}" / selection.COUNTEREXAMPLE_FILE, {"verdict": "NOT_EQUAL"})
    return audit


def archive_of(directory: Path, target: Path) -> Path:
    """That directory as `release.sh` builds one: the runs under a `runs/` prefix."""
    with tarfile.open(target, "w:gz") as opened:
        opened.add(directory, arcname="runs")
    return target


def test_a_run_is_a_directory_holding_a_summary_and_a_group_is_the_level_above_one(
    tmp_path: Path,
) -> None:
    """The two shapes the work directory has, told apart by where the summary is.

    A PostgreSQL benchmark audits one database per run, so a run sits directly under its
    benchmark. A SQLite one takes `--dsn` as a file, so a prediction file is eleven runs and
    the level between them is the group; a page of a group is what a reader of the benchmark
    index meets first, so the two levels are not interchangeable.
    """
    work = tmp_path / "work"
    run_directory(work, "minidev-pg/gpt-4-turbo")
    run_directory(work, "bird-dev-sqlite/dev-20251106/formula_1")

    found = selection.discover(work)

    assert [run.slug for run in found] == [
        "bird-dev-sqlite/dev-20251106/formula_1",
        "minidev-pg/gpt-4-turbo",
    ], "sorted, and the group is part of the slug"
    grouped, flat = found
    assert (grouped.benchmark, grouped.group, grouped.name) == (
        "bird-dev-sqlite",
        "dev-20251106",
        "formula_1",
    )
    assert (flat.benchmark, flat.group, flat.name) == ("minidev-pg", "", "gpt-4-turbo")
    assert grouped.archive == "bird-dev-sqlite-dev-20251106.tar.gz", "the group's own archive"
    assert flat.archive == "minidev-pg-gpt-4-turbo.tar.gz"


def test_the_crowded_answer_a_rerun_kept_beside_its_own_is_not_a_run(tmp_path: Path) -> None:
    """`audits.sh` moves a run that timed out under load aside and runs it again alone.

    Both directories stay, because a reader of the reconciliation is owed both, and exactly
    one of them is what the site publishes. A discovery that took both would publish a run
    twice under two names and count its questions twice in the budget.
    """
    work = tmp_path / "work"
    run_directory(work, "minidev-pg/gpt-4-turbo")
    run_directory(work, "minidev-pg/gpt-4-turbo.under-load")
    run_directory(work, "minidev-pg/.hidden")

    assert [run.slug for run in selection.discover(work)] == ["minidev-pg/gpt-4-turbo"]


def test_every_run_is_told_which_archive_holds_it_and_how_many_questions_that_is(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run page says how much of the run the site shows, which needs the archive's count.

    The run's own file states the run's count and the group's file states the group's sum, so
    neither page states the other's number. A run under a group is in its group's archive,
    which is why one asset answers for both files.
    """
    out = tmp_path / "data"
    run_directory(out, "bird-dev-sqlite/dev-20251106/formula_1")
    run_directory(out, "minidev-pg/gpt-4-turbo")
    written = write_manifest(tmp_path)

    assert selection.write_published(out, written) == 0, "an exit status, not a count"
    assert "written for 2 runs" in capsys.readouterr().out

    grouped = json.loads(
        (out / "bird-dev-sqlite/dev-20251106/formula_1" / selection.PUBLISHED_FILE).read_text(
            encoding="utf-8"
        )
    )
    assert grouped["name"] == "bird-dev-sqlite-dev-20251106.tar.gz"
    assert grouped["sha256"] == "a" * 64
    assert grouped["directories"] == 3, "this run's own count, out of the archive's five"
    group_page = json.loads(
        (out / "bird-dev-sqlite/dev-20251106" / selection.PUBLISHED_FILE).read_text(
            encoding="utf-8"
        )
    )
    assert group_page["directories"] == 5, "the archive's sum, which is the group's"
    flat = json.loads(
        (out / "minidev-pg/gpt-4-turbo" / selection.PUBLISHED_FILE).read_text(encoding="utf-8")
    )
    assert flat["directories"] == 7


def write_manifest(root: Path) -> Path:
    """A manifest of two archives, one of a group and one of a single run."""
    return write(
        root / "manifest.json",
        {
            "tag": "v0.3.1",
            "assets": [
                {
                    "name": "bird-dev-sqlite-dev-20251106.tar.gz",
                    "url": "https://github.com/o/r/releases/download/v0.3.1/a.tar.gz",
                    "bytes": 11,
                    "sha256": "a" * 64,
                    "directories": 5,
                    "per_run": {"runs/bird-dev-sqlite/dev-20251106/formula_1": 3},
                },
                {
                    "name": "minidev-pg-gpt-4-turbo.tar.gz",
                    "url": "https://github.com/o/r/releases/download/v0.3.1/b.tar.gz",
                    "bytes": 22,
                    "sha256": "b" * 64,
                    "directories": 7,
                    "per_run": {"runs/minidev-pg/gpt-4-turbo": 7},
                },
            ],
        },
    )


def test_a_run_whose_archive_the_manifest_does_not_name_is_refused(tmp_path: Path) -> None:
    """Silence here would publish a run page with no link to the rest of the run."""
    out = tmp_path / "data"
    run_directory(out, "minidev-sqlite/gpt-4/toxicology")
    written = write_manifest(tmp_path)

    with pytest.raises(selection.SelectionRefused) as refused:
        selection.write_published(out, written)

    assert "names no asset minidev-sqlite-gpt-4.tar.gz" in str(refused.value)


def test_an_asset_address_that_is_not_a_link_is_refused(tmp_path: Path) -> None:
    """Every run page carries this address, so a value that is not one is 121 broken links."""
    out = tmp_path / "data"
    run_directory(out, "minidev-pg/gpt-4-turbo")
    written = write(
        tmp_path / "manifest.json",
        {
            "tag": "v0.3.1",
            "assets": [
                {
                    "name": "minidev-pg-gpt-4-turbo.tar.gz",
                    "url": "gpt-4-turbo.tar.gz",
                    "bytes": 22,
                    "sha256": "b" * 64,
                    "directories": 7,
                    "per_run": {"runs/minidev-pg/gpt-4-turbo": 7},
                }
            ],
        },
    )

    with pytest.raises(selection.SelectionRefused) as refused:
        selection.write_published(out, written)

    assert "has to begin with https://" in str(refused.value)


def test_the_manifest_states_the_size_the_digest_and_what_every_run_in_an_archive_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The manifest is where the counts on a run page come from, so it is read here whole.

    The digest and the size are what a reader checks a downloaded archive against, and the
    per-run counts are what every run and group page states about how much of itself the site
    shows.
    """
    work = tmp_path / "work"
    run_directory(work, "minidev-pg/gpt-4-turbo", questions=(1, 2, 3))
    run_directory(work, "minidev-pg/gpt-4", questions=(7,))
    assets = tmp_path / "assets"
    assets.mkdir()
    built = archive_of(work, assets / "minidev-pg.tar.gz")
    monkeypatch.setattr(sys, "argv", ["manifest.py", str(assets), "v0.3.1", "owner/repository"])

    assert manifest.main() == 0

    stated = json.loads(capsys.readouterr().out)
    assert stated["tag"] == "v0.3.1"
    (asset,) = stated["assets"]
    assert asset["name"] == "minidev-pg.tar.gz"
    assert asset["url"] == (
        "https://github.com/owner/repository/releases/download/v0.3.1/minidev-pg.tar.gz"
    )
    assert asset["bytes"] == built.stat().st_size
    assert asset["sha256"] == hashlib.sha256(built.read_bytes()).hexdigest(), (
        "the digest is what a reader checks a downloaded archive against, so it is taken "
        "again here from the file the manifest describes"
    )
    assert asset["directories"] == 4
    assert asset["per_run"] == {
        "runs/minidev-pg/gpt-4": 1,
        "runs/minidev-pg/gpt-4-turbo": 3,
    }, "one entry per run, sorted, and each holding its own count"


def test_a_run_that_wrote_no_question_directory_is_counted_as_zero_and_not_left_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run with no disagreement and no probe writes no directory, and that is a number.

    Left out of the manifest it would be a run whose page can state neither how many
    questions the site shows of it nor how many there are, which are not the same silence.
    """
    work = tmp_path / "work"
    run_directory(work, "minidev-pg/agreed")
    assets = tmp_path / "assets"
    assets.mkdir()
    archive_of(work, assets / "minidev-pg.tar.gz")
    monkeypatch.setattr(sys, "argv", ["manifest.py", str(assets), "v0.3.1", "owner/repository"])

    assert manifest.main() == 0

    (asset,) = json.loads(capsys.readouterr().out)["assets"]
    assert asset["per_run"] == {"runs/minidev-pg/agreed": 0}
    assert asset["directories"] == 0


def test_an_assets_directory_holding_no_archive_is_a_refusal_and_not_an_empty_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty manifest would be read by the selector as a release that published nothing."""
    monkeypatch.setattr(sys, "argv", ["manifest.py", str(tmp_path), "v0.3.1", "owner/repository"])

    assert manifest.main() == 2

    printed = capsys.readouterr()
    assert "holds no archive to make a manifest of" in printed.err
    assert printed.out == "", "nothing on stdout, which is where the manifest would have gone"


def test_the_ids_of_one_database_are_printed_once_and_in_the_order_the_file_holds_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """What `audits.sh` passes to `--ids`, so a run over one file audits that file's questions.

    The GitHub zip's own Mini-Dev file names two ids twice. The audit deduplicates them before
    it runs anything, so printing one twice would change nothing and state something false
    about the file; the order is the file's, because the predictions of a position-keyed
    prediction file are read against it.
    """
    questions = write(
        tmp_path / "questions.json",
        [
            {"question_id": 7, "db_id": "toxicology"},
            {"question_id": 3, "db_id": "formula_1"},
            {"question_id": 11, "db_id": "toxicology"},
            {"question_id": 7, "db_id": "toxicology"},
        ],
    )
    monkeypatch.setattr(sys, "argv", ["question_ids.py", str(questions), "toxicology"])

    question_ids.main()

    assert capsys.readouterr().out == "7,11\n"
