#!/usr/bin/env python3
"""The manifest `select.py --published` reads, from the archives `release.sh` built.

    manifest.py <assets directory> <tag> <owner/repository>

One entry per archive: what it is called, where the release serves it, how large it is, what it
hashes to, and how many question directories it holds, both in all and per run.

That last number is what a run page needs in order to say how much of the run is on the site.
The site shows a selection of a run's questions, chosen against a file and a byte budget, and a
page stating how many it shows without stating how many there are says nothing a reader can use.
It is counted here rather than in the work directory because the archive is what the sentence is
about: what the page links to is what holds the rest.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tarfile
from collections import Counter
from pathlib import Path

QUESTION = re.compile(r"^(.*)/q\d+/$")
"""One question directory inside an archive: the run it belongs to, and the question it is.

Members are listed with a trailing slash, so this matches the directory itself and never a file
inside it, and the run is everything in front of it, which is the path `select.py` addresses a
run by."""

RUN = re.compile(r"^(.*)/summary\.json$")
"""One run inside an archive, by the file that makes a directory a run.

Every run is counted, so that a run that wrote no question directory states a count of zero
rather than no count at all: the two are not the same thing, and a page that has neither
number says nothing where it could say what the archive holds."""


def main() -> int:
    assets, tag, repository = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    found: list[dict[str, object]] = []
    for archive in sorted(assets.glob("*.tar.gz")):
        per_run = _question_directories(archive)
        found.append(
            {
                "name": archive.name,
                "url": f"https://github.com/{repository}/releases/download/{tag}/{archive.name}",
                "bytes": archive.stat().st_size,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "directories": sum(per_run.values()),
                "per_run": dict(sorted(per_run.items())),
            }
        )
    if not found:
        print(f"{assets} holds no archive to make a manifest of", file=sys.stderr)
        return 2
    json.dump({"tag": tag, "assets": found}, sys.stdout, indent=1)
    print()
    return 0


def _question_directories(archive: Path) -> Counter[str]:
    """How many question directories each run inside one archive wrote.

    Read with `tarfile` rather than by running `tar`, so that this script imports nothing that
    imports the standard library's `select`: `select.py` sits in this same directory, and the
    directory a script is run from comes first on the path.
    """
    with tarfile.open(archive, "r:gz") as opened:
        names = opened.getnames()
    members = [f"{name}/" if not name.endswith("/") else name for name in names]
    found = Counter({run: 0 for name in names if (run := _run_of(name)) is not None})
    found.update(
        match.group(1) for member in members if (match := QUESTION.match(member)) is not None
    )
    return found


def _run_of(name: str) -> str | None:
    match = RUN.match(name)
    return match.group(1) if match is not None else None


if __name__ == "__main__":
    sys.exit(main())
