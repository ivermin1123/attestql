"""The notes a release carries, which until 2026-09-11 were read from a file nothing wrote.

`release.sh upload` passed `gh release create --notes-file "$ASSETS/notes.md"`, and no code in
the repository created that file. It had not fired yet only because the release it would have
created already existed; the next new tag would have failed there. The notes are made from the
manifest now, because the manifest is the only thing that knows what was built.

The count is the part worth asserting. `manifest.py` writes it under `directories`, and a
generator that defaulted a missing count to zero would publish a number nobody measured under
the tag, so every refusal below is a refusal to guess.
"""

from __future__ import annotations

import json
from pathlib import Path

import notes
import pytest


def manifest(tmp_path: Path, document: object) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_the_notes_name_every_archive_and_sum_what_they_hold() -> None:
    """The summed count is the sentence a reader uses, so it is what is asserted."""
    written = notes.render(
        {
            "tag": "v0.3.1",
            "assets": [
                {"name": "second.tar.gz", "bytes": 2, "directories": 120},
                {"name": "first.tar.gz", "bytes": 1, "directories": 61},
            ],
        },
        "v0.3.1",
    )

    assert "attestql 0.3.1" in written
    assert "2 archives holding 181 question directories in all" in written
    assert written.index("first.tar.gz") < written.index("second.tar.gz"), "sorted by name"
    assert written.endswith("\n")


def test_the_notes_refuse_a_manifest_that_does_not_say_what_an_archive_holds(
    tmp_path: Path,
) -> None:
    """A missing count stops the notes rather than being read as zero."""
    path = manifest(tmp_path, {"tag": "v0.0.0", "assets": [{"name": "a.tar.gz", "bytes": 1}]})

    assert notes.main([str(path), "v0.0.0"]) == 2


def test_the_notes_refuse_a_manifest_naming_no_archive(tmp_path: Path) -> None:
    """An empty asset list is a release with nothing in it, not one with empty notes."""
    path = manifest(tmp_path, {"tag": "v0.0.0", "assets": []})

    assert notes.main([str(path), "v0.0.0"]) == 2


def test_the_notes_refuse_a_manifest_that_is_not_there(tmp_path: Path) -> None:
    assert notes.main([str(tmp_path / "absent.json"), "v0.0.0"]) == 2


def test_the_notes_refuse_a_manifest_that_is_not_json(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("not json", encoding="utf-8")

    assert notes.main([str(path), "v0.0.0"]) == 2


def test_the_notes_state_what_moved_in_the_bytes_of_a_record() -> None:
    """A reader comparing two records of one question has to be able to explain the diff.

    The tool changes that move those bytes are named in the notes published with the
    archives, because the archives are where the records are.
    """
    written = notes.render(
        {"tag": "v0.3.2", "assets": [{"name": "a.tar.gz", "bytes": 1, "directories": 1}]},
        "v0.3.2",
    )

    assert notes.RECORD_BYTES_MOVED, "this release moves them"
    assert notes.RECORD_BYTES_HEADING in written
    for moved in notes.RECORD_BYTES_MOVED:
        assert moved in written


def test_a_release_that_moved_no_record_byte_renders_no_such_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty is the ordinary state, and an empty heading would be a question with no answer."""
    monkeypatch.setattr(notes, "RECORD_BYTES_MOVED", ())

    written = notes.render(
        {"tag": "v0.3.2", "assets": [{"name": "a.tar.gz", "bytes": 1, "directories": 1}]},
        "v0.3.2",
    )

    assert notes.RECORD_BYTES_HEADING not in written
    assert written.endswith("question directories\n")
