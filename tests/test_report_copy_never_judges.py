"""The copy rule: a page states what the files state, and never says who was right.

The design spec forbids a short list of phrases in the templates' own literals. The subject
is the literals and not the page, because the tool's own strings say the thing the rule is
about: ``compare.py`` writes "It does not state which of them is wrong" into every
counterexample and ``smells.py`` writes "it does not state that the statement is wrong" into
every probe document, and both are rendered verbatim. A test over the rendered page would
have to forbid the product's own sentences to pass, which is the opposite of what the rule is
for; a test over the literals forbids the page from adding a judgement of its own.

So this reads the template files, takes the Jinja expressions and statements out -- what is
left is exactly the text a template author typed -- and searches that. The second half is the
positive control: the JSON's ``reading`` strings, holding the very words the list forbids, are
on the rendered page, whole.
"""

from __future__ import annotations

import io
import re
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from attestql.audit.cli import main
from attestql.report.render import TEMPLATES

pytestmark = pytest.mark.sandbox_sqlite

FORBIDDEN: tuple[str, ...] = (
    "is correct",
    "is wrong",
    "incorrect",
    "accuracy",
    "passes",
    "fails",
    "score:",
)
"""What a template may not say, from the design spec's copy rules.

The affirmative forms, and ``score:`` rather than ``score``, because the forbidden thing is a
page labelling a number as a score of its own: a benchmark's ``score`` inside a quoted method
string is that evaluator's word for what it computes and is not this page's claim. Every
entry is searched case insensitively."""

JINJA = re.compile(r"\{#.*?#\}|\{%.*?%\}|\{\{.*?\}\}", re.DOTALL)
"""An expression, a statement or a comment. What is left when these are gone is the literal
text a template author typed, which is the subject of the rule."""

VERBATIM: tuple[str, ...] = (
    "It does not state which of them is wrong.",
    "it does not state that the statement is wrong, and a maintainer decides.",
)
"""Two of the tool's own ``reading`` strings, allowed by name in the design spec and asserted
on the page below: they hold the words the list forbids, and they are what the rule protects
rather than what it is aimed at."""


def literals(path: Path) -> str:
    """One template with its Jinja gone: the text it states whatever the model holds."""
    return JINJA.sub(" ", path.read_text(encoding="utf-8"))


def templates() -> list[Path]:
    found = sorted(TEMPLATES.glob("*.html"))
    assert found, f"no templates under {TEMPLATES}"
    return found


@pytest.mark.parametrize("path", templates(), ids=lambda path: path.name)
def test_no_template_literal_judges_a_statement(path: Path) -> None:
    """The rule itself, one template at a time, so a failure names the file it is in."""
    text = literals(path).lower()

    found = [phrase for phrase in FORBIDDEN if phrase in text]

    assert not found, f"{path.name} states {found}"


def test_the_rule_is_about_the_literals_and_not_about_the_json_s_own_readings(
    tmp_path: Path,
) -> None:
    """The positive control. The two sentences hold the forbidden words and are on the page.

    Without this, the rule above could be satisfied by a renderer that dropped the readings,
    which is the one thing a page of this tool may not do: the reading is what keeps a
    NOT_EQUAL from being read as a verdict about the gold.
    """
    sandbox = tmp_path / "sandbox"
    printed = io.StringIO()
    with redirect_stdout(printed):
        assert main(["demo", "--out", str(sandbox)]) == 1
        assert main(["report", str(sandbox / "audit"), "--out", str(tmp_path / "report")]) == 0
    page = (tmp_path / "report" / "q879" / "index.html").read_text(encoding="utf-8")

    for sentence in VERBATIM:
        assert sentence in page, sentence
    assert any(phrase in page.lower() for phrase in FORBIDDEN), (
        "the readings hold the words the templates may not state, which is the point"
    )
