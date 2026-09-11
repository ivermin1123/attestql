#!/usr/bin/env python3
"""Reject a commit message that credits an AI assistant.

This repository's rule is that a commit message names no AI. Three commits of 2026-09-07 reached
`main` carrying a `Co-Authored-By` trailer anyway, and removing them cost a history rewrite and the
repair of 60 evidence references, so the rule is held here rather than by memory.

What is refused is attribution, not subject matter: a trailer crediting an assistant or a vendor's
no-reply address, and the generated-with marker some tools append. A message whose prose discusses
an AI system is a message about a topic and passes, because the rule is about who a commit claims
wrote it.

Takes the path of the message file, which is what git passes a `commit-msg` hook. Exit status 1
when any finding exists, and each finding names the line.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

ASSISTANTS = ("claude", "copilot", "chatgpt", "gpt-4", "gpt-5", "codex", "gemini", "cursor")
VENDOR_ADDRESSES = ("noreply@anthropic.com", "noreply@openai.com", "noreply@github.com")

TRAILER = re.compile(r"^\s*co[-\s]?authored[-\s]?by\s*:\s*(?P<value>.*)$", re.IGNORECASE)
GENERATED = re.compile(
    r"generated\s+with\s+\[?(claude|chatgpt|codex|copilot|cursor|gemini)", re.IGNORECASE
)
ROBOT = "\N{ROBOT FACE}"


def findings(message: str) -> list[tuple[int, str, str]]:
    """Every line that credits an assistant, as (line number, reason, the line)."""
    found: list[tuple[int, str, str]] = []
    for number, line in enumerate(message.splitlines(), start=1):
        trailer = TRAILER.match(line)
        if trailer is not None:
            value = trailer.group("value").lower()
            named = next((name for name in ASSISTANTS if name in value), None)
            address = next((one for one in VENDOR_ADDRESSES if one in value), None)
            if named is not None:
                found.append((number, f"a co-author trailer naming {named}", line.strip()))
            elif address is not None:
                found.append((number, f"a co-author trailer using {address}", line.strip()))
        if GENERATED.search(line):
            found.append((number, "a generated-with marker", line.strip()))
        if ROBOT in line:
            found.append((number, "the robot emoji some tools append", line.strip()))
    return found


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message_file", help="the file git passes a commit-msg hook")
    arguments = parser.parse_args(argv)

    path = Path(arguments.message_file)
    try:
        message = path.read_text(encoding="utf-8")
    except OSError as unreadable:
        print(f"check_commit_message: cannot read {path}: {unreadable}", file=sys.stderr)
        return 1

    found = findings(message)
    if not found:
        print("check_commit_message: ok")
        return 0

    for number, reason, line in found:
        print(f"{path}:{number}: {reason}: {line}", file=sys.stderr)
    print(
        "check_commit_message: a commit message names no AI in this repository. "
        "Remove the line above and commit again.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
