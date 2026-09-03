#!/usr/bin/env python3
"""The ADR files in docs/adr/ must be exactly the files docs/adr/0000-index.md links to.

Both directions are reported: an ADR the index does not link is invisible, and an index entry
whose file does not exist is a broken promise. Exit status 1 on any mismatch.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from check_doc_links import iter_links, relative_target, resolve

ADR_DIR = Path("docs") / "adr"
INDEX_NAME = "0000-index.md"


def repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def adr_files(adr_dir: Path) -> set[str]:
    return {path.name for path in adr_dir.glob("*.md") if path.name != INDEX_NAME}


def indexed_adrs(index: Path, root: Path) -> dict[str, int]:
    """ADR file names the index links to, each with the first line that links it.

    Targets resolve exactly as ``check_doc_links`` resolves them, so a root-relative link
    (``/docs/adr/...``) counts the same as a sibling-relative one."""
    linked: dict[str, int] = {}
    adr_dir = index.parent.resolve()
    for link in iter_links(index):
        file_part = relative_target(link.target)
        if file_part is None:
            continue
        resolved = resolve(index, root, file_part).resolve()
        is_adr = (
            resolved.parent == adr_dir and resolved.suffix == ".md" and resolved.name != INDEX_NAME
        )
        if is_adr:
            linked.setdefault(resolved.name, link.line)
    return linked


def mismatches(root: Path) -> list[str]:
    adr_dir = root / ADR_DIR
    index = adr_dir / INDEX_NAME
    index_display = (ADR_DIR / INDEX_NAME).as_posix()
    if not index.is_file():
        return [f"{index_display}: missing"]
    files = adr_files(adr_dir)
    linked = indexed_adrs(index, root)
    findings = [
        f"{(ADR_DIR / name).as_posix()} is not linked from {index_display}"
        for name in sorted(files - linked.keys())
    ]
    findings.extend(
        f"{index_display}:{linked[name]}: links {name}, which does not exist in {ADR_DIR.as_posix()}/"
        for name in sorted(linked.keys() - files)
    )
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--root", type=Path, default=repository_root(), help="repository root")
    root = Path(parser.parse_args(argv).root).resolve()
    findings = mismatches(root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"check_adr_index: {len(findings)} mismatch(es)", file=sys.stderr)
        return 1
    print("check_adr_index: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
