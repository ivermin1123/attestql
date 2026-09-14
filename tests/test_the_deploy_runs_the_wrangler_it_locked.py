"""The one Node tool that holds a credential runs from a resolved tree, and the others do not.

`site.yml` hands wrangler a Cloudflare API token with Pages edit on the account. `npx --yes
wrangler@<version>` resolved that version's dependency tree at deploy time, so what ran with the
token was whatever the registry served that minute below the pinned top level. The manifest and
the lockfile beside it fix the whole tree, `npm ci` installs exactly that, and the deploy runs
the binary that install produced.

markdownlint and cspell stay on `npx` at the versions the justfile pins. They read files, hold no
credential, and run inside a gate a maintainer is already watching; locking them would buy a tree
nothing trusts with anything. This file is what keeps that split, and the pins under it, from
drifting: a bump to one file alone fails here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

REPOSITORY = Path(__file__).resolve().parent.parent
WORKFLOW = REPOSITORY / ".github" / "workflows" / "site.yml"
EXACT = re.compile(r"\d+\.\d+\.\d+")


def manifest() -> dict[str, object]:
    return cast("dict[str, object]", json.loads((REPOSITORY / "package.json").read_text("utf-8")))


def manifest_pin() -> str:
    """The wrangler version `package.json` states, which must be an exact one."""
    stated = cast("dict[str, str]", manifest()["devDependencies"])
    pinned = stated["wrangler"]
    assert EXACT.fullmatch(pinned), (
        f"package.json asks for wrangler {pinned}; a range resolves to a different tool on "
        "the day of the deploy, which is the thing the lockfile is here to stop"
    )
    return pinned


def lock_pin() -> str:
    """The wrangler version `package-lock.json` resolves, which is what `npm ci` installs."""
    locked = json.loads((REPOSITORY / "package-lock.json").read_text("utf-8"))
    packages = cast("dict[str, dict[str, str]]", locked["packages"])
    assert "node_modules/wrangler" in packages, "the lockfile resolves no wrangler"
    return packages["node_modules/wrangler"]["version"]


def test_the_lockfile_resolves_the_wrangler_the_manifest_pins() -> None:
    """One version, stated twice. `npm ci` refuses the pair when they part, and so does this."""
    assert manifest_pin() == lock_pin(), (
        f"package.json pins wrangler {manifest_pin()} and package-lock.json resolves "
        f"{lock_pin()}; `npm ci` installs the lockfile, so the pin would be decoration"
    )


def test_the_deploy_installs_the_locked_tree_and_runs_the_binary_it_made() -> None:
    """`npx --yes wrangler@...` is what this replaces, so its absence is asserted too."""
    workflow = WORKFLOW.read_text("utf-8")

    assert "npm ci" in workflow, "the deploy installs nothing from the lockfile"
    assert "node_modules/.bin/wrangler" in workflow, (
        "the deploy does not run the binary `npm ci` produced, so the locked tree is unused"
    )
    assert "npx" not in workflow, (
        "the deploy still reaches npx, which resolves a tree at deploy time rather than "
        "installing the one this repository locked"
    )


def test_the_deploy_still_pins_every_action_it_uses_by_commit() -> None:
    """A tag moves and a commit does not, and this workflow reads two repository secrets."""
    used = re.findall(r"uses:\s*(\S+)", WORKFLOW.read_text("utf-8"))

    assert used, "the workflow uses no action, which means this file is reading the wrong one"
    for action in used:
        _, _, pinned = action.partition("@")
        assert re.fullmatch(r"[0-9a-f]{40}", pinned), (
            f"{action} is pinned by a movable reference; the deploy holds a Cloudflare token"
        )


def test_the_gate_s_node_tools_stay_on_npx_and_are_not_in_the_manifest() -> None:
    """Locking a tool that holds no credential would state a trust the gate does not need."""
    recipes = (REPOSITORY / "justfile").read_text("utf-8")
    for tool in ("markdownlint-cli2", "cspell"):
        assert f"npx --yes {tool}@" in recipes, f"{tool} no longer runs through npx in the gate"

    stated = cast("dict[str, str]", manifest()["devDependencies"])
    assert set(stated) == {"wrangler"}, (
        f"package.json holds {sorted(stated)}; the deploy's tool is the one locked here"
    )
    assert "dependencies" not in manifest(), "nothing here is a runtime dependency of anything"
