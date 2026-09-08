"""Merge a serial timeout-only rerun into the full loaded summary.

The loaded run stays as ``.under-load`` and the alone subset as ``.timeout-rerun``. The
target keeps one full summary, with only timed-out questions replaced by the serial reading.
"""

import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

LINE = re.compile(
    r"^q(\d+)\s+(\S+)\s+(\S*)\s+(EQUAL|NOT_EQUAL|NOT_COMPARABLE|ERROR)\s+smells=(\S+)"
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(directory: Path) -> dict[int, dict]:
    out = {}
    for line in directory.joinpath("stdout.txt").read_text(encoding="utf-8").splitlines():
        found = LINE.match(line)
        if found is None:
            continue
        question_id, db, _rule, verdict, smells = found.groups()
        row = {
            "line": line,
            "db": db,
            "verdict": verdict,
            "smells": [] if smells == "none" else smells.split(","),
        }
        if verdict == "EQUAL":
            row["bird_ex"] = 1
        elif verdict == "NOT_EQUAL":
            counterexample = directory / f"q{question_id}" / "counterexample.json"
            if counterexample.exists():
                evidence = load(counterexample)
                row["bird_ex"] = evidence["bird_ex"]["value"]
                row["mechanism"] = evidence["mechanism"]["class"]
                row["test_suite_ex"] = str(evidence["test_suite_ex"]["value"])
        out[int(question_id)] = row
    return out


def stats(question_rows: dict[int, dict], errors: list[dict]) -> dict:
    by_mechanism = Counter()
    by_test_suite = Counter()
    for row in question_rows.values():
        if row["verdict"] == "NOT_EQUAL" and row.get("bird_ex") == 1:
            by_mechanism[row["mechanism"]] += 1
            by_test_suite[row["test_suite_ex"]] += 1
    return {
        "verdicts": Counter(row["verdict"] for row in question_rows.values()),
        "smells": Counter(smell for row in question_rows.values() for smell in row["smells"]),
        "smells_fired": sum(len(row["smells"]) for row in question_rows.values()),
        "by_mechanism": by_mechanism,
        "by_test_suite": by_test_suite,
        "errors": errors,
    }


def main() -> None:
    loaded_summary, serial_summary, target = (Path(arg) for arg in sys.argv[1:4])
    loaded, serial = load(loaded_summary), load(serial_summary)
    loaded_dir, serial_dir = loaded_summary.parent, serial_summary.parent
    affected = {
        int(found.group(1))
        for line in serial_dir.joinpath("stdout.txt").read_text().splitlines()
        if (found := LINE.match(line))
    }
    question_rows = {
        question_id: row
        for question_id, row in rows(loaded_dir).items()
        if question_id not in affected
    } | rows(serial_dir)
    errors = [error for error in loaded["errors"] if error["question_id"] not in affected] + serial[
        "errors"
    ]
    measured = stats(question_rows, errors)
    merged = dict(loaded)
    merged.update(
        {
            "verdicts": dict(measured["verdicts"]),
            "smells": dict(measured["smells"]),
            "smells_fired": measured["smells_fired"],
            "credited_but_not_equal": {
                "total": measured["by_mechanism"].total(),
                "by_mechanism": dict(measured["by_mechanism"]),
                "by_test_suite_ex": dict(measured["by_test_suite"]),
            },
            "errors": measured["errors"],
            "timed_out": serial["timed_out"],
            "elapsed_seconds": {
                key: loaded.get("elapsed_seconds", {}).get(key, 0)
                + serial.get("elapsed_seconds", {}).get(key, 0)
                for key in loaded.get("elapsed_seconds", {})
            },
            "run_ids": [*loaded.get("run_ids", []), *serial.get("run_ids", [])],
            "exit_status": serial["exit_status"],
        }
    )
    target.mkdir(parents=True, exist_ok=True)
    for source_dir, replacing in ((loaded_dir, False), (serial_dir, True)):
        for child in source_dir.iterdir():
            if not child.name.startswith("q") or not child.is_dir():
                continue
            question_id = int(child.name[1:])
            if replacing != (question_id in affected):
                continue
            if (target / child.name).exists():
                shutil.rmtree(target / child.name)
            shutil.copytree(child, target / child.name)
    shutil.copyfile(serial_summary, target / "summary.json")
    (target / "summary.json").write_text(json.dumps(merged, indent=1) + "\n", encoding="utf-8")
    base_lines = [
        line
        for line in loaded_dir.joinpath("stdout.txt").read_text().splitlines()
        if not (found := LINE.match(line)) or int(found.group(1)) not in affected
    ]
    serial_lines = serial_dir.joinpath("stdout.txt").read_text().splitlines()
    (target / "stdout.txt").write_text(
        "\n".join(base_lines + serial_lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
