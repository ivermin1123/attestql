#!/usr/bin/env python3
"""Every relative Markdown link in README.md and under docs/ must resolve to an existing file.

Absolute URLs (any target with a scheme) and in-page anchors are ignored. Text inside fenced
code blocks and inline code spans is not a link. Exit status 1 when any link is broken; each
finding names the source file and line.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

# [text](target), [text](target "title"), ![alt](target); one level of nested brackets in text.
_INLINE_LINK = re.compile(
    r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*(<[^>]*>|[^\s)]+)(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
_REFERENCE_DEFINITION = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
_CODE_SPAN = re.compile(r"(`+).+?\1")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


@dataclass(frozen=True)
class Link:
    source: Path
    line: int
    target: str


def repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _closes_fence(line: str, fence: str) -> bool:
    match = _FENCE.match(line)
    if match is None:
        return False
    marker = match.group(1)
    return marker[0] == fence[0] and len(marker) >= len(fence) and line.strip() == marker


def iter_links(path: Path) -> Iterator[Link]:
    """Every inline link, image and reference definition in ``path``, outside code."""
    fence = ""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if fence:
            if _closes_fence(line, fence):
                fence = ""
            continue
        opener = _FENCE.match(line)
        if opener is not None:
            fence = opener.group(1)
            continue
        prose = _CODE_SPAN.sub("", line)
        definition = _REFERENCE_DEFINITION.match(prose)
        if definition is not None:
            yield Link(path, number, definition.group(1))
            continue
        for match in _INLINE_LINK.finditer(prose):
            yield Link(path, number, match.group(1))


def relative_target(target: str) -> str | None:
    """The file part of a link target, or None when the link is absolute or an in-page anchor."""
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if not target or target.startswith("#") or target.startswith("//") or _SCHEME.match(target):
        return None
    return unquote(target.split("#", 1)[0])


def resolve(source: Path, root: Path, file_part: str) -> Path:
    """A root-relative target (leading slash) resolves from the repository root, as on GitHub."""
    if file_part.startswith("/"):
        return root / file_part.lstrip("/")
    return source.parent / file_part


def documentation_files(root: Path) -> list[Path]:
    files = [root / "README.md"] if (root / "README.md").is_file() else []
    files.extend(sorted((root / "docs").rglob("*.md")))
    return files


def broken_links(root: Path) -> list[str]:
    findings: list[str] = []
    for source in documentation_files(root):
        for link in iter_links(source):
            file_part = relative_target(link.target)
            if file_part is None:
                continue
            resolved = resolve(source, root, file_part)
            if not resolved.is_file():
                where = f"{source.relative_to(root).as_posix()}:{link.line}"
                findings.append(f"{where}: broken link '{link.target}' (no file at {resolved})")
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--root", type=Path, default=repository_root(), help="repository root")
    root = Path(parser.parse_args(argv).root).resolve()
    findings = broken_links(root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"check_doc_links: {len(findings)} broken link(s)", file=sys.stderr)
        return 1
    print("check_doc_links: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
