#!/usr/bin/env python3
"""Reject the em dash, the en dash and the numero sign in Markdown and Python files.

Two exemptions, both for text this project did not write:

* lines inside a Markdown blockquote, because a verbatim quotation keeps its author's
  characters. Blockquote context is tracked across lines (marker lines, lazy continuation
  lines, and the blank line or new block that ends the quote) rather than by matching a
  leading ``>`` on the same line;
* the files named in ``VERBATIM_FILES``, third-party documents kept exactly as received.

Exit status 1 when any finding exists. Each finding names file, line and column.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

FORBIDDEN: dict[str, str] = {
    "\u2014": "U+2014 em dash",
    "\u2013": "U+2013 en dash",
    "\u2116": "U+2116 numero sign",
}
CHECKED_SUFFIXES = frozenset({".md", ".py"})
SKIPPED_DIRS = frozenset({"node_modules", "build", "dist", "__pycache__"})

VERBATIM_FILES: frozenset[str] = frozenset()
"""Documents kept exactly as received and therefore exempt, by exact path, never by pattern.

Empty: the one third-party review that held this exemption left the public tree with the
history it belonged to, and no document written here is exempt from its own rule."""

_BLOCKQUOTE_MARKER = re.compile(r"^ {0,3}>")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
# Constructs that start a new block and therefore end a paragraph (and its lazy continuation):
# ATX headings, list items, thematic breaks, HTML blocks and code fences.
_BLOCK_START = re.compile(
    r"^ {0,3}(?:#{1,6}(?:\s|$)|[-*+]\s|\d{1,9}[.)]\s|(?:-\s*){3,}$|(?:\*\s*){3,}$|(?:_\s*){3,}$"
    r"|<|`{3,}|~{3,})"
)


def repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def iter_checked_files(root: Path) -> Iterator[Path]:
    """Every .md and .py file under root, skipping hidden, cache, build and egg-info directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if not name.startswith(".")
            and name not in SKIPPED_DIRS
            and not name.endswith(".egg-info")
        )
        for name in sorted(filenames):
            if Path(name).suffix in CHECKED_SUFFIXES:
                yield Path(dirpath) / name


def _closes_fence(line: str, fence: str) -> bool:
    match = _FENCE.match(line)
    if match is None:
        return False
    marker = match.group(1)
    return marker[0] == fence[0] and len(marker) >= len(fence) and line.strip() == marker


class _BlockquoteScanner:
    """Line-by-line Markdown block context, enough to know which lines a blockquote owns."""

    def __init__(self) -> None:
        self.in_quote = False
        self.fence = ""  # the open code fence at the current level, or "" when none is open
        self.paragraph_open = False  # the last quoted line was paragraph text

    def consume(self, line: str) -> bool:
        """Return True when ``line`` belongs to a blockquote."""
        if self.in_quote:
            marker = _BLOCKQUOTE_MARKER.match(line)
            if marker is not None:
                self._quoted_content(line[marker.end() :].removeprefix(" "))
                return True
            if (
                self.fence == ""
                and self.paragraph_open
                and line.strip()
                and not _BLOCK_START.match(line)
            ):
                return True  # lazy continuation of the quoted paragraph
            # A blank line or a new block ends the quote; this line belongs to the top level.
            self.in_quote = False
            self.fence = ""
            self.paragraph_open = False
        if self.fence:
            if _closes_fence(line, self.fence):
                self.fence = ""
            return False
        opener = _FENCE.match(line)
        if opener is not None:
            self.fence = opener.group(1)
            return False
        marker = _BLOCKQUOTE_MARKER.match(line)
        if marker is None:
            return False
        self.in_quote = True
        self._quoted_content(line[marker.end() :].removeprefix(" "))
        return True

    def _quoted_content(self, content: str) -> None:
        if self.fence:
            if _closes_fence(content, self.fence):
                self.fence = ""
            self.paragraph_open = False
            return
        opener = _FENCE.match(content)
        if opener is not None:
            self.fence = opener.group(1)
            self.paragraph_open = False
            return
        self.paragraph_open = bool(content.strip()) and not _BLOCK_START.match(content)


def blockquote_line_numbers(lines: Sequence[str]) -> set[int]:
    """The 1-based numbers of every line that belongs to a Markdown blockquote."""
    scanner = _BlockquoteScanner()
    return {number for number, line in enumerate(lines, start=1) if scanner.consume(line)}


def check_file(path: Path, root: Path) -> list[str]:
    relative = path.relative_to(root).as_posix()
    if relative in VERBATIM_FILES:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        return [f"{relative}: not valid UTF-8 ({error})"]
    lines = text.splitlines()
    exempt = blockquote_line_numbers(lines) if path.suffix == ".md" else set[int]()
    findings: list[str] = []
    for number, line in enumerate(lines, start=1):
        if number in exempt:
            continue
        for column, char in enumerate(line, start=1):
            if char in FORBIDDEN:
                findings.append(f"{relative}:{number}:{column}: {FORBIDDEN[char]}")
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--root", type=Path, default=repository_root(), help="repository root")
    root = Path(parser.parse_args(argv).root).resolve()
    findings = [finding for path in iter_checked_files(root) for finding in check_file(path, root)]
    for finding in findings:
        print(finding)
    if findings:
        print(f"check_typography: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("check_typography: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
