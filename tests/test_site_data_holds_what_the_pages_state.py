"""What `tools/site-select/select.py` wrote under `tools/site/data/`, read as a page reads it.

The script is not imported here. Its own name is the standard library's `select`, which
everything that waits on a file descriptor imports, and `tests/test_boundary.py` forbids
`importlib` in every file under `src/` and `tests/` for the reason its one exemption states:
`importlib.metadata` is allowed because it imports no code, and loading a file as a module is
the thing the rule is against. So what is read here is what the script wrote, which is the
ground every page of this site stands on, and the budgets it predicts against, which are read
out of both scripts' source rather than out of a run of either.

The refusals that keep this data as it is -- a release asset's address, a symlink, two hand
readings of one question that differ -- are asserted over the whole of what was published:
121 runs, 131 archives' worth of lines and 22 classifications. The same rules are asserted
behaviourally in `tests/test_report_renders_an_audit_directory.py`, on the renderer's own copy
of them, which is inside the package and can be called.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import build as site
import pytest

REPOSITORY = Path(__file__).resolve().parent.parent
DATA = REPOSITORY / "tools" / "site" / "data"
SELECT = REPOSITORY / "tools" / "site-select" / "select.py"
BUILD = REPOSITORY / "tools" / "site" / "build.py"
BUDGETS = ("MAX_FILES", "MAX_BYTES", "MAX_PAGE_BYTES")

assert Path(site.__file__ or "") == BUILD, (
    "`build` is also the name of the git-ignored output directory, which resolves as a "
    "namespace package when the repository root comes first on the path: this asserts the "
    "module read here is the script and not that directory"
)

pytestmark = pytest.mark.skipif(
    not DATA.is_dir() or not any(DATA.glob("*/")),
    reason="the published runs are not in this checkout; the build renders the stand-in",
)


def document(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _budget_source(path: Path) -> dict[str, str]:
    """The three budgets as the file states them, as expressions rather than as numbers.

    Compared as source, because `40 * 1024 * 1024` is arithmetic and not a literal: what is
    asserted is that the two files say the same thing, which is what a reader comparing them
    would check.
    """
    found: dict[str, str] = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in BUDGETS:
                found[target.id] = ast.dump(node.value)
    return found


def _question_directories(under: Path) -> int:
    """Every `q<id>/` published under a run or a group, which is what its pages are."""
    return len([path for path in under.rglob("q*") if path.is_dir() and path.name[1:].isdigit()])


def _rows(note: Any, classification: Any) -> list[dict[str, Any]]:
    """The rows of one classification, by the join the note beside it states."""
    if note["shape"] == "per_file":
        return [row for stated in classification["per_file"].values() for row in stated["rows"]]
    return list(classification["rows"])


def test_the_selection_predicts_against_the_three_budgets_the_build_refuses_over() -> None:
    """The selection is where a site can still be made smaller; the build is the authority.

    Two copies of three numbers, because the script that chooses what to publish before a
    build and the build that measures after one cannot import each other. A selection made
    against a larger budget than the build allows is a selection that fails at the last step.
    """
    chosen, refused = _budget_source(SELECT), _budget_source(BUILD)

    assert sorted(chosen) == sorted(BUDGETS), f"{SELECT.name} states {sorted(chosen)}"
    assert chosen == refused
    assert min(site.MAX_FILES, site.MAX_BYTES, site.MAX_PAGE_BYTES) > 0


def test_every_published_run_states_an_address_a_reader_can_fetch_and_a_count_it_can_hold() -> None:
    """The address becomes an `href` on the run page and the count becomes a sentence on it.

    A `javascript:` address would run on a reader's click, where autoescaping only puts the
    value safely inside the attribute; a count below what is published here would be a page
    saying it holds more of the run than the run wrote.
    """
    published = sorted(DATA.rglob("published.json"))
    assert len(published) > 100, "one per run, and one more per group"

    for path in published:
        stated = document(path)
        where = path.parent.relative_to(DATA)
        assert stated["url"].startswith("https://"), where
        assert stated["name"].endswith(".tar.gz"), where
        assert len(stated["sha256"]) == 64, where
        assert stated["bytes"] > 0, where
        assert isinstance(stated["directories"], int), where
        assert stated["directories"] >= _question_directories(path.parent), where


def test_no_question_is_named_twice_in_the_file_that_says_which_database_it_is_about() -> None:
    """BIRD's Mini-Dev question file holds 137 and 138 twice, and a page is one question.

    The file is read by question id, so a repeat is one entry silently taking the place of
    another. Identical repeats are one entry here, which is what the file meant by them.
    """
    for path in sorted(DATA.rglob("questions.json")):
        stated = [question["question_id"] for question in document(path)]
        assert len(stated) == len(set(stated)), path.relative_to(DATA)


def test_nothing_published_here_is_a_link_to_somewhere_else() -> None:
    """A link would publish whatever it points at, from wherever that is, under this name."""
    assert [path for path in DATA.rglob("*") if path.is_symlink()] == []


def test_every_class_a_maintainer_recorded_is_a_class_its_own_source_defines() -> None:
    """`A` on its own is a letter, and the page states what the letter means beside it.

    The meanings are cut out of the document that defines them and named in `classes_source`,
    so a class no source defines would be a page showing a letter and nothing else.
    """
    notes = sorted(DATA.rglob("classification-source.json"))
    assert notes, "every run with a hand classification has one"

    for path in notes:
        note = document(path)
        rows = _rows(note, document(path.parent / "classification.json"))
        assert note["classes_source"], path.relative_to(DATA)
        for row in rows:
            assert note["classes"].get(row["class"]), (path.relative_to(DATA), row["class"])


def test_the_aggregate_states_what_was_found_and_how_much_of_it_has_a_page() -> None:
    """Two numbers per key, and the one the landing shows is what was found.

    A site whose own file budget changed the number it reports would be reporting the budget,
    so `published` is never the number and is never above it either.
    """
    stated = document(DATA / "aggregate.json")

    assert sorted(stated) == sorted(key for key, _ in site.HEADLINE)
    for key, number in stated.items():
        assert number["value"] > 0, key
        assert 0 <= number["published"] <= number["value"], key
        assert number["source"], key


def test_no_question_was_read_by_hand_twice_and_read_two_different_ways() -> None:
    """One page shows one reading, so two rows for one question have to say one thing.

    The classifications were written against a question file that repeats 137 and 138, so a
    row per repeat is a shape they can have. Rows that agree are one reading; rows that differ
    are two, and joining them by question id would keep whichever came last and say nothing
    about the other.
    """
    for path in sorted(DATA.rglob("classification.json")):
        note = document(path.parent / "classification-source.json")
        read: dict[str, dict[str, str]] = {}
        for row in _rows(note, document(path)):
            stated = {"class": row["class"], "reason": row[note["reason_field"]]}
            question = str(row["question_id"])
            assert read.get(question, stated) == stated, (path.relative_to(DATA), question)
            read[question] = stated
