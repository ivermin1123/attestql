#!/usr/bin/env python3
"""The acceptance check of ADR-0013 point 8's parser swap, as a script anyone can rerun.

``dump`` parses every distinct gold of a BIRD Mini-Dev question file with whichever
``statements`` module is importable and writes, per question, what the audit reads off a
statement: the replay rule, the tables, the ordering keys (expression, direction, null
placement), the bound, and the DISTINCT flag. Run once against the current parser::

    uv run python compare_parsers.py dump mini_dev_postgresql.json new-parser.json

and once against the previous parser, taken from the history before publication and run in
an environment holding it (``pglast==6.16``), with ``--module-file`` naming that file::

    uv run --isolated --no-project --with pglast==6.16 python compare_parsers.py dump \\
        mini_dev_postgresql.json old-parser.json --module-file old_statements.py

``diff`` compares two dumps field by field and, when given the sweep's ``rows.json``, checks
the replay rule of every question against what the sweep recorded; it prints a Markdown
table of the disagreements.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def _module(module_file: str | None) -> Any:
    if module_file is None:
        return importlib.import_module("attestql.audit.statements")
    spec = importlib.util.spec_from_file_location("previous_statements", module_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{module_file} is not importable as a module")
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs: its dataclasses resolve their annotations through the
    # module they were defined in, which they look up by name.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(question_id: int, parsed: Any) -> dict[str, Any]:
    return {
        "question_id": question_id,
        "rule": parsed.replay_rule.value,
        "tables": list(parsed.tables),
        "ordering": [
            {"expression": key.expression, "descending": key.descending, "nulls": key.nulls}
            for key in parsed.ordering
        ],
        "limit_count": parsed.limit_count,
        "limit_stated": parsed.limit_stated,
        "offset_count": parsed.offset_count,
        "distinct": parsed.distinct,
    }


def dump(questions: Path, out: Path, module_file: str | None) -> None:
    statements = _module(module_file)
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for entry in json.loads(questions.read_text(encoding="utf-8")):
        question_id = int(entry["question_id"])
        if question_id in seen:
            continue
        seen.add(question_id)
        rows.append(_row(question_id, statements.parse_statement(entry["SQL"])))
    out.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(rows)} distinct golds parsed into {out}")


def diff(before: Path, after: Path, sweep: Path | None) -> int:
    old = {row["question_id"]: row for row in json.loads(before.read_text(encoding="utf-8"))}
    new = {row["question_id"]: row for row in json.loads(after.read_text(encoding="utf-8"))}
    fields = (
        "rule",
        "tables",
        "ordering",
        "limit_count",
        "limit_stated",
        "offset_count",
        "distinct",
    )
    disagreements: list[tuple[int, str, Any, Any]] = []
    for question_id in sorted(old):
        for field in fields:
            if old[question_id][field] != new[question_id][field]:
                disagreements.append(
                    (question_id, field, old[question_id][field], new[question_id][field])
                )
    agreeing = len(old) - len({q for q, *_ in disagreements})
    print(
        f"{len(old)} golds; {agreeing} agree on every field; {len(disagreements)} field disagreements"
    )
    print()
    print("| id | field | previous parser | current parser |")
    print("|---|---|---|---|")
    for question_id, field, was, now in disagreements:
        print(f"| q{question_id} | {field} | `{json.dumps(was)}` | `{json.dumps(now)}` |")
    if sweep is not None:
        recorded = {
            int(row["question_id"]): row["rule"]
            for row in json.loads(sweep.read_text(encoding="utf-8"))
        }
        matching = sum(1 for q, row in new.items() if recorded.get(q) == row["rule"])
        print()
        print(f"replay rule against the sweep's rows.json: {matching} of {len(new)} match")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    dumping = commands.add_parser("dump")
    dumping.add_argument("questions", type=Path)
    dumping.add_argument("out", type=Path)
    dumping.add_argument("--module-file", default=None)
    diffing = commands.add_parser("diff")
    diffing.add_argument("before", type=Path)
    diffing.add_argument("after", type=Path)
    diffing.add_argument("--sweep", type=Path, default=None)
    arguments = parser.parse_args(argv)
    if arguments.command == "dump":
        dump(arguments.questions, arguments.out, arguments.module_file)
        return 0
    return diff(arguments.before, arguments.after, arguments.sweep)


if __name__ == "__main__":
    sys.exit(main())
