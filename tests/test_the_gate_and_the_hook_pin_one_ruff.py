"""`just lint` and the pre-commit hook run ruff over the same files, and two ruff versions
disagree about them: a rule added between releases makes the hook pass a commit the gate then
refuses, or the reverse. The dev group therefore pins ruff exactly and
`.pre-commit-config.yaml` pins the same value, and this test is what keeps the two from
drifting. A dependency bot updates one file at a time, so without an assertion the split is
silent until a contributor hits it.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import cast

REPOSITORY = Path(__file__).resolve().parent.parent
HOOK_REPOSITORY = "https://github.com/astral-sh/ruff-pre-commit"


def gate_pin() -> str:
    """The dev group's ruff requirement, which must be an exact pin."""
    stated = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
    groups = cast("dict[str, list[str]]", stated["dependency-groups"])
    pins = [entry for entry in groups["dev"] if entry.replace(" ", "").startswith("ruff==")]
    assert pins, "the dev group names no exact ruff pin; a floor lets the hook and the gate part"
    assert len(pins) == 1, f"more than one ruff entry in the dev group: {pins}"
    return pins[0].replace(" ", "").removeprefix("ruff==")


def hook_pin() -> str:
    """The `rev` of the ruff hook repository, with the `v` its tags carry removed."""
    config = (REPOSITORY / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    found = re.search(
        rf"- repo: {re.escape(HOOK_REPOSITORY)}\s*\n\s*rev: v?(?P<version>\S+)", config
    )
    assert found is not None, f"no {HOOK_REPOSITORY} block with a rev in .pre-commit-config.yaml"
    return found.group("version")


def test_the_dev_group_and_the_hook_name_the_same_ruff() -> None:
    """One version, stated twice. Bumping either file alone fails here."""
    assert gate_pin() == hook_pin(), (
        f"pyproject.toml pins ruff {gate_pin()} and .pre-commit-config.yaml pins {hook_pin()}; "
        "the hook and `just lint` would then read the same files under two rule sets"
    )
