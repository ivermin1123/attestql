#!/usr/bin/env python3
"""Every published run against the run that replaced it, and what moved.

    reconcile.py [--work /tmp/attestql-runs] [--published tools/site/data]

The site's 121 runs were made with 0.2.2 and are replaced here by runs made with 0.3.1. Three
things changed between those releases and nothing else should have: `duplicate-full-row` did not
exist in 0.2.2 and fires now, `arbitrary-cut` no longer fires on a DISTINCT statement whose
ordering key its select list does not hold, and a result holding a non-finite number receives a
verdict instead of an error. This states what actually moved, so that anything else is seen.

A verdict that moved because a statement crossed or stopped crossing its wall-clock bound is
timing and not behaviour; those are listed apart, with whether the run kept a crowded copy, which
is what says the rerun happened.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

REPOSITORY = Path(__file__).resolve().parents[3]
UNDER_LOAD = ".under-load"


def summary(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def timeouts(document: dict[str, Any]) -> set[tuple[int, str]]:
    """Every question the bound stopped, as (question id, side)."""
    stated = cast("dict[str, list[int]]", document["timed_out"])
    return {(question, side) for side, found in stated.items() for question in found}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("/tmp/attestql-runs"))  # noqa: S108
    parser.add_argument("--published", type=Path, default=REPOSITORY / "tools" / "site" / "data")
    arguments = parser.parse_args(argv)

    fresh_root = arguments.work / "runs"
    moved: Counter[str] = Counter()
    verdicts_moved: list[dict[str, Any]] = []
    absent: list[str] = []
    compared = 0

    for old_path in sorted(arguments.published.rglob("summary.json")):
        run = old_path.parent.relative_to(arguments.published)
        new_path = fresh_root / run / "summary.json"
        if not new_path.is_file():
            absent.append(str(run))
            continue
        compared += 1
        old, new = summary(old_path), summary(new_path)
        old_smells = cast("dict[str, int]", old["smells"])
        new_smells = cast("dict[str, int]", new["smells"])
        for name in set(old_smells) | set(new_smells):
            delta = new_smells.get(name, 0) - old_smells.get(name, 0)
            if delta:
                moved[name] += delta
        if old["verdicts"] != new["verdicts"]:
            verdicts_moved.append(
                {
                    "run": str(run),
                    "published": old["verdicts"],
                    "fresh": new["verdicts"],
                    "timeouts_only": timeouts(old) != timeouts(new),
                    "published_timeouts": sorted(timeouts(old)),
                    "fresh_timeouts": sorted(timeouts(new)),
                    "kept_a_crowded_copy": (fresh_root / f"{run}{UNDER_LOAD}").is_dir(),
                }
            )

    report = {
        "compared": compared,
        "published_with_no_fresh_run": absent,
        "smells_moved": dict(sorted(moved.items())),
        "verdicts_moved": verdicts_moved,
    }
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
