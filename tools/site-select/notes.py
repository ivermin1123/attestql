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


def render(manifest: dict[str, Any], tag: str) -> str:
    """The notes for one tag: what the archives are, and how much of a run each holds."""
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
