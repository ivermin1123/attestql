"""What `select_questions.py --out` may empty, which until 2026-09-11 was anything.

The selector cleared its output directory by removing everything under it except a README, with
no check that the directory was its own. `--out` is a path a person types, its default is the
published data under `tools/site/data/`, and a mistyped one would have cost somebody the files
the selector did not write. A reproduction removed a file called `keep/irreplaceable.txt`.

`tools/site/build.py` and `attestql report` already had the rule: a directory that is empty or
absent is taken over and marked, one that holds the marker is emptied and marked again, and one
holding anything else is refused untouched. This is the selector following it, with the symlink
and the repository added because a resolved path is the only one whose parents can be checked.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import select_questions as selection


def marked(path: Path) -> Path:
    """A directory that an earlier selection wrote, as its marker says."""
    path.mkdir(parents=True, exist_ok=True)
    (path / selection.SELECTION_MARKER).write_text(
        selection.SELECTION_MARKER_TEXT, encoding="utf-8"
    )
    return path


def test_a_directory_holding_files_and_no_marker_is_refused_untouched(tmp_path: Path) -> None:
    """The reproduction the review recorded: a file nobody could get back."""
    out = tmp_path / "somewhere"
    out.mkdir()
    irreplaceable = out / "irreplaceable.txt"
    irreplaceable.write_text("not the selector's", encoding="utf-8")

    with pytest.raises(selection.SelectionRefused, match=selection.SELECTION_MARKER):
        selection.prepare_output(out)

    assert irreplaceable.read_text(encoding="utf-8") == "not the selector's"


def test_a_directory_an_earlier_selection_wrote_is_emptied_and_marked_again(
    tmp_path: Path,
) -> None:
    out = marked(tmp_path / "mine")
    (out / "old-benchmark").mkdir()
    (out / "old-benchmark" / "summary.json").write_text("{}", encoding="utf-8")
    (out / "README.md").write_text("written by a person", encoding="utf-8")

    selection.prepare_output(out)

    assert not (out / "old-benchmark").exists()
    assert (out / selection.SELECTION_MARKER).is_file()
    assert (out / "README.md").read_text(encoding="utf-8") == "written by a person", (
        "the directory's own README is not the selector's to remove"
    )


def test_a_directory_that_is_not_there_yet_is_made_and_marked(tmp_path: Path) -> None:
    out = tmp_path / "absent" / "deeper"

    selection.prepare_output(out)

    assert (out / selection.SELECTION_MARKER).is_file()


def test_an_empty_directory_is_taken_over(tmp_path: Path) -> None:
    out = tmp_path / "empty"
    out.mkdir()

    selection.prepare_output(out)

    assert (out / selection.SELECTION_MARKER).is_file()


def test_a_symbolic_link_is_refused(tmp_path: Path) -> None:
    """What a link points at is decided somewhere else, so what would be emptied is too."""
    target = marked(tmp_path / "target")
    link = tmp_path / "link"
    link.symlink_to(target)

    with pytest.raises(selection.SelectionRefused, match="symbolic link"):
        selection.prepare_output(link)


@pytest.mark.parametrize("ancestor", [selection.REPOSITORY, selection.REPOSITORY.parent])
def test_the_repository_and_every_directory_above_it_are_refused(ancestor: Path) -> None:
    """Checked on the resolved path, which is the only one whose parents mean anything."""
    with pytest.raises(selection.SelectionRefused, match="repository or a directory above"):
        selection.prepare_output(ancestor)


def test_the_published_data_directory_is_recognised_as_the_selectors_own() -> None:
    """The directory the default `--out` names holds the marker, so a selection into it is not
    refused. Without it the guard would refuse the one directory it exists to write."""
    assert (selection.DATA / selection.SELECTION_MARKER).is_file(), (
        f"{selection.DATA} needs the marker for the default --out to work"
    )
