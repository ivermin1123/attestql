#!/usr/bin/env python3
"""The notes a release created by `release.sh` carries, from the manifest.

    notes.py <manifest> <tag>

`release.sh` passed `gh release create` a `--notes-file` no code wrote, so the first tag that
needed a release created would have failed there. The manifest is the only thing that knows what
was built, so the notes are made from it.

The count is read as `directories`, the name `manifest.py` writes it under, and a manifest
without it stops this rather than defaulting: notes stating zero question directories per archive
would be a number nobody measured, published under the tag.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

RECORD_BYTES_HEADING = "What moved in the bytes of a record since the last release"

RECORD_BYTES_MOVED: tuple[str, ...] = (
    "A PostgreSQL record's session settings block states the `search_path` its own statement "
    "ran under rather than the one the session was started with, because the envelope pins "
    "it now: every execution resolves an unqualified name against `public`, which is the "
    "schema the fixture digest and the row counts beside it were always about. A run made "
    'from a session holding the usual `"$user", public` therefore records `public` where '
    "it used to record that. The key moves as well as the value: `search_path` is written "
    "where the envelope sets it rather than where the session reported it, so a reader "
    "diffing two records of one question sees a line in a new position and not only a "
    "changed one.",
    "A SQLite record's session settings block holds a tenth setting, `automatic_index`. The "
    "shuffle probe's plan variant turns that pragma off and gives it back, so the value in "
    "force over a statement is now stated rather than assumed to be the build's default. A "
    "SQLite record of the same question made before and after this release differs by those "
    "bytes and by nothing else.",
)
"""Every change in this release that moves the bytes of a record of the same question.

A record is what a replay is checked against, so two records of one question that differ
byte for byte are the first thing a reader has to be able to explain. These sentences are
that explanation, published with the archives the release carries.

An entry is added by the change that moves the bytes and stays until the release that
carries it has shipped, which is when this tuple is emptied again. Empty is the ordinary
state and renders no section at all."""


def render(manifest: dict[str, Any], tag: str) -> str:
    """The notes for one tag: what the archives are, how much of a run each holds, and what
    moved in the bytes of a record since the release before."""
    assets = cast("list[dict[str, Any]]", manifest["assets"])
    if not assets:
        raise ValueError("the manifest names no archive")
    directories = sum(int(one["directories"]) for one in assets)
    lines = [
        f"The audit archives made with attestql {tag.lstrip('v')}. {len(assets)} archives "
        f"holding {directories} question directories in all; SHA256SUMS lists each archive and "
        "its digest. Each archive holds every question directory of one run or group of runs, "
        "with that run's own console output beside it.",
        "",
    ]
    lines.extend(
        f"- `{one['name']}`, {one['bytes']} bytes, {one['directories']} question directories"
        for one in sorted(assets, key=lambda one: str(one["name"]))
    )
    if RECORD_BYTES_MOVED:
        lines.extend(("", f"## {RECORD_BYTES_HEADING}", ""))
        lines.extend(f"- {moved}" for moved in RECORD_BYTES_MOVED)
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="the manifest.py output to describe")
    parser.add_argument("tag", help="the tag the audits were made with")
    arguments = parser.parse_args(argv)

    try:
        manifest = cast("dict[str, Any]", json.loads(arguments.manifest.read_text("utf-8")))
    except (OSError, json.JSONDecodeError) as unreadable:
        print(f"notes: {arguments.manifest} could not be read: {unreadable}", file=sys.stderr)
        return 2
    try:
        sys.stdout.write(render(manifest, arguments.tag))
    except (KeyError, TypeError, ValueError) as incomplete:
        print(
            f"notes: the manifest does not say what every archive holds: {incomplete}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
