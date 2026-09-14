#!/usr/bin/env python3
"""Every published run against the run that replaced it, and what moved.

    reconcile.py [--work /tmp/attestql-runs] [--published tools/site/data]

The site's 121 runs were made with 0.3.1 and are replaced here by runs made with the tree that
becomes 0.4.0. Between those two, the review-findings plan (phases 4 to 6) changed the bytes of a
record in two stated ways and the shape of a summary in one, and nothing else should have moved:
a PostgreSQL record's session settings state the `search_path` the envelope pinned, in the
envelope's position; a SQLite record's session settings hold a tenth pragma, `automatic_index`;
and `summary.json` names the question directories the run wrote under `question_directories`.
The two budgets that refuse (rows fetched, rows compared) were measured to sit above every
published record, so no ERROR should appear where none was.

This states what actually moved, so that anything else is seen. A verdict that moved because a
statement crossed or stopped crossing its wall-clock bound is timing and not behaviour; those are
listed apart, with whether the run kept a crowded copy, which is what says the rerun happened.
The order-dependent gold probes on PostgreSQL move with the planner's statistics, which the
refresh of 0.3.1 measured; their deltas are reported by name and read against that.
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
DIRECTORIES_KEY = "question_directories"


def document(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def timeouts(summary: dict[str, Any]) -> set[tuple[int, str]]:
    """Every question the bound stopped, as (question id, side)."""
    stated = cast("dict[str, list[int]]", summary["timed_out"])
    return {(question, side) for side, found in stated.items() for question in found}


def directories_on_disk(run: Path) -> set[str]:
    """The question directories a run wrote, read from the file system and not the summary."""
    return {one.name for one in run.iterdir() if one.is_dir() and one.name.startswith("q")}


def record_layouts(run: Path) -> Counter[str]:
    """How many gold records under a run state each layout version, read where a record
    states it, under ``serialization``."""
    found: Counter[str] = Counter()
    for record in run.glob("q*/evidence-gold.json"):
        found[str(document(record).get("serialization", {}).get("version"))] += 1
    return found


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=Path("/tmp/attestql-runs"))  # noqa: S108
    parser.add_argument("--published", type=Path, default=REPOSITORY / "tools" / "site" / "data")
    arguments = parser.parse_args(argv)

    fresh_root = arguments.work / "runs"
    moved: Counter[str] = Counter()
    verdicts_moved: list[dict[str, Any]] = []
    absent: list[str] = []
    summaries_without_the_key: list[str] = []
    summaries_disagreeing_with_disk: list[dict[str, Any]] = []
    layouts: Counter[str] = Counter()
    compared = 0

    for old_path in sorted(arguments.published.rglob("summary.json")):
        run = old_path.parent.relative_to(arguments.published)
        new_path = fresh_root / run / "summary.json"
        if not new_path.is_file():
            absent.append(str(run))
            continue
        compared += 1
        old, new = document(old_path), document(new_path)
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
        if DIRECTORIES_KEY not in new:
            summaries_without_the_key.append(str(run))
        else:
            stated = {f"q{one}" for one in cast("list[int]", new[DIRECTORIES_KEY])}
            on_disk = directories_on_disk(new_path.parent)
            if stated != on_disk:
                summaries_disagreeing_with_disk.append(
                    {
                        "run": str(run),
                        "stated_not_on_disk": sorted(stated - on_disk),
                        "on_disk_not_stated": sorted(on_disk - stated),
                    }
                )
        layouts.update(record_layouts(new_path.parent))

    report = {
        "compared": compared,
        "published_with_no_fresh_run": absent,
        "smells_moved": dict(sorted(moved.items())),
        "verdicts_moved": verdicts_moved,
        "fresh_summaries_without_question_directories": summaries_without_the_key,
        "fresh_summaries_disagreeing_with_disk": summaries_disagreeing_with_disk,
        "fresh_record_layouts": dict(sorted(layouts.items())),
    }
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
