"""Compare two gold-only audit runs of the same questions on the same server.

Two runs made from two checkouts, one before the protocols were introduced and one after,
over the Hugging Face Mini-Dev question file. What is compared: the console output line for
line, ``summary.json`` key by key, and every question directory both runs wrote, which in
a gold-only run is the gold's evidence record and its smells.

What is expected to differ is stated rather than skipped quietly: the run's own identity
(its id, the directory it wrote into, the instant it started and how long it took) and the
timestamps inside a record. Everything else is compared as it stands, and a difference in
any of it is printed with the path that holds it.

Nothing of BIRD's question or gold text is printed. A value that differs is reported by its
path and, where the value is short and not SQL, by the two values; a server message has the
statement fragment after ``LINE `` cut off, as ``build_artifact.py`` does.

usage: python3 compare_gold_only.py <before-run> <after-run> [--control <a> <b>]
       [--released <stdout.txt>]
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

RUN_OWNED: frozenset[str] = frozenset(
    {
        "run_id",
        "data_as_of",
        "elapsed_seconds",
        "fixture.cache",
        "settings.out",
    }
)
"""Summary keys that name this run rather than what it found, and so are expected to differ.

``run_id`` is a fresh uuid per run; ``data_as_of`` is the instant the run started;
``elapsed_seconds`` is how long each phase took; ``fixture.cache`` and ``settings.out``
name the directory the run was told to write into, which is a different one per run."""

RECORD_OWNED: frozenset[str] = frozenset({"run_id", "executed_at", "data_as_of", "record_hash"})
"""The same, inside an evidence record: its run, the two instants it states, and the hash
over the whole document, which covers those three and therefore moves with them.

``result_hash`` is deliberately not here. It is the sha256 of the result alone under the
canonical serialization, so it is what says the two runs rendered the same answer to the
same bytes, and it is counted below rather than excused."""

LINE_FRAGMENT = re.compile(r"\s+LINE \d+:")
"""What a server error message puts the rejected statement's own text after."""


def cut(text: str) -> str:
    """A server message without the statement fragment it quotes back."""
    return LINE_FRAGMENT.split(text, maxsplit=1)[0].strip()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def flatten(document: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every leaf of a JSON document, by the dotted path that reaches it.

    A list is a leaf: what these documents hold in one is a whole answer, a whole ordering
    or a whole set of smells, and reporting the third element of one differing would say
    less than reporting that the answer differs.
    """
    if isinstance(document, dict):
        keyed = cast("dict[str, Any]", document)
        for key, value in keyed.items():
            path = f"{prefix}.{key}" if prefix else key
            yield from flatten(value, path)
    else:
        yield prefix, document


def owned(path: str, owners: frozenset[str]) -> bool:
    """Whether this leaf is under one of the paths a run owns."""
    return any(path == owner or path.startswith(f"{owner}.") for owner in owners)


def short(value: Any) -> str:
    """One value as a line of a report: cut where a server quoted a statement back.

    A list of named findings is summarised by the ones that fired rather than printed:
    a smell carries the rows it fired on as its evidence, and this file reproduces no
    row of BIRD's data.
    """
    if isinstance(value, list):
        entries = cast("list[Any]", value)
        named: list[dict[str, Any]] = [
            cast("dict[str, Any]", item)
            for item in entries
            if isinstance(item, dict) and "name" in cast("dict[str, Any]", item)
        ]
        if entries and len(named) == len(entries):
            fired = [str(item["name"]) for item in named if item.get("fired")]
            return f"{len(entries)} entries, fired: {', '.join(fired) or 'none'}"
        return f"{len(entries)} entries"
    text = cut(str(value))
    return text if len(text) <= 120 else f"{text[:117]}..."


def compare_json(
    before: Path, after: Path, owners: frozenset[str], out: list[str], label: str
) -> int:
    """Report every leaf the two documents disagree on, excluding the run's own. Count them."""
    left = dict(flatten(load(before)))
    right = dict(flatten(load(after)))
    differing = 0
    for path in sorted(set(left) | set(right)):
        if owned(path, owners) or left.get(path) == right.get(path):
            continue
        differing += 1
        out.append(f"  {label}: {path}")
        out.append(f"    before: {short(left.get(path))}")
        out.append(f"    after:  {short(right.get(path))}")
    expected = sorted(path for path in set(left) | set(right) if owned(path, owners))
    out.append(f"  {label}: {len(left)} leaves, {differing} differ, {len(expected)} run-owned")
    return differing


def compare_stdout(before: Path, after: Path, out: list[str], label: str) -> int:
    """Report every console line the two runs disagree on, with each run's directory masked."""
    left = before.read_text(encoding="utf-8").replace(str(before.parent), "OUT").splitlines()
    right = after.read_text(encoding="utf-8").replace(str(after.parent), "OUT").splitlines()
    differing = 0
    for number, (one, other) in enumerate(zip(left, right, strict=len(left) == len(right)), 1):
        if one == other:
            continue
        differing += 1
        out.append(f"  {label}: line {number}")
        out.append(f"    before: {one}")
        out.append(f"    after:  {other}")
    out.append(f"  {label}: {len(left)} lines against {len(right)}, {differing} differ")
    return differing


def compare_questions(before: Path, after: Path, out: list[str]) -> int:
    """Every question directory both runs wrote, file by file. Count the leaves that differ."""
    left = {path.name for path in before.glob("q*") if path.is_dir()}
    right = {path.name for path in after.glob("q*") if path.is_dir()}
    differing = 0
    for only, side in ((left - right, "before"), (right - left, "after")):
        for name in sorted(only):
            differing += 1
            out.append(f"  questions: {name} written by {side} only")
    matched_result_hashes = 0
    for name in sorted(left & right):
        files = {path.name for path in (before / name).iterdir()}
        files |= {path.name for path in (after / name).iterdir()}
        for file in sorted(files):
            one, other = before / name / file, after / name / file
            if not one.exists() or not other.exists():
                differing += 1
                out.append(f"  questions: {name}/{file} written by one run only")
                continue
            differing += compare_json(one, other, RECORD_OWNED, out, f"{name}/{file}")
            hashes = {dict(flatten(load(side))).get("result_hash") for side in (one, other)}
            if len(hashes) == 1 and None not in hashes:
                matched_result_hashes += 1
    out.append(f"  questions: {len(left & right)} directories in both, {differing} differ")
    out.append(f"  questions: {matched_result_hashes} documents state one result_hash for both")
    return differing


def released_lines(path: Path) -> dict[str, str]:
    """The released run's console lines by question id, the directory column dropped."""
    lines: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if parts and parts[0].startswith("q") and parts[0][1:].isdigit():
            lines[parts[0]] = " ".join(part for part in parts if not part.endswith("/"))
    return lines


def compare_with_released(run: Path, released: Path, out: list[str], label: str) -> int:
    """One run's question lines against the released ones, the summary line left out."""
    mine = released_lines(run / "stdout.txt")
    theirs = released_lines(released)
    differing = 0
    for question in sorted(set(mine) | set(theirs)):
        if mine.get(question) == theirs.get(question):
            continue
        differing += 1
        out.append(f"  released against {label}: {question}")
        out.append(f"    released: {theirs.get(question)}")
        out.append(f"    {label}: {mine.get(question)}")
    out.append(f"  released against {label}: {len(theirs)} question lines, {differing} differ")
    return differing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--control", type=Path, nargs=2, metavar=("A", "B"))
    parser.add_argument("--released", type=Path)
    parsed = parser.parse_args()
    before: Path = parsed.before
    after: Path = parsed.after

    out: list[str] = [f"before: {before}", f"after:  {after}", "", "the two runs:"]
    differing = compare_stdout(before / "stdout.txt", after / "stdout.txt", out, "stdout")
    differing += compare_json(
        before / "summary.json", after / "summary.json", RUN_OWNED, out, "summary"
    )
    differing += compare_questions(before, after, out)

    if parsed.control is not None:
        control_a: Path = parsed.control[0]
        control_b: Path = parsed.control[1]
        out += ["", f"the control, two runs of {control_a.name} and {control_b.name}:"]
        compare_stdout(control_a / "stdout.txt", control_b / "stdout.txt", out, "stdout")

    if parsed.released is not None:
        out += ["", f"against the released run at {parsed.released}:"]
        compare_with_released(before, parsed.released, out, "before")
        compare_with_released(after, parsed.released, out, "after")

    out += ["", f"total differences between the two runs, run identity excluded: {differing}"]
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
