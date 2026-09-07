"""Merge the per-database Spider runs and count gold-only fires and correction recall.

usage: MEASURE_WORK=<work-directory> python3 measure.py

One Spider pass is one run per database. The merge rule sums each summary's counts, keeps every
per-question line, and lists every run id; no question id occurs in two databases. A question
whose statement errored is selected but not audited, and stays in ``errors`` with its reason.
"""

import json
import os
import re
from collections import Counter
from pathlib import Path

import sqlglot
from sqlglot import exp

WORK = Path(os.environ["MEASURE_WORK"]).resolve()
OUT = WORK / "out"
PASSES = ("current", "before", "transformed")
LINE = re.compile(r"^q(\d+)\s+(\S+)\s+(\S*)\s+GOLD-ONLY\s+smells=(\S+)")
ERROR_LINE = re.compile(r"^q(\d+)\s+(\S+)\s+ERROR\s+smells=(\S+)")
PROBES = (
    "ordering-over-numeric-text",
    "arbitrary-cut",
    "not-a-function-of-the-data",
    "float-aggregate-order",
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def statement_tables(sql: str) -> set[str]:
    """The table names sqlglot reads, casefolded; a CTE alias is a table node to it too."""
    tree = sqlglot.parse_one(sql, read="sqlite")
    return {table.name.casefold() for table in tree.find_all(exp.Table)}


def covered_tables(sql: str, copied: list[str]) -> list[str]:
    copied_by_lower = {name.casefold() for name in copied}
    return sorted(statement_tables(sql) & copied_by_lower)


def error_reason(message: str) -> str:
    if message.startswith("execute: Could not decode to UTF-8"):
        return "sqlite-text-is-not-utf-8"
    return "other"


def read_pass(name: str, databases: list[str]) -> dict:
    questions: dict[int, dict] = {}
    errors: list[dict] = []
    smells: Counter = Counter()
    rules: Counter = Counter()
    audited = 0
    selected = 0
    run_ids: list[str] = []
    fixture_refused = 0
    shuffle_not_prepared = 0
    timeout_lines: list[dict] = []
    table_sets: dict[str, list[str]] = {}
    for db in databases:
        directory = OUT / "tool" / name / db
        if not directory.joinpath("summary.json").is_file():
            continue
        summary = load(directory / "summary.json")
        audited += summary["verdicts"].get("GOLD-ONLY", 0)
        selected += len(summary["question_set"]["ids"])
        smells.update(summary["smells"])
        run_ids.append(summary["run_id"])
        fixture_refused += bool(summary["fixture"]["refused"])
        shuffle_not_prepared += not summary["shuffle"]["prepared"]
        table_sets[db] = summary["shuffle"]["copied"]
        errors.extend(
            {
                "question_id": row["question_id"],
                "db": db,
                "side": row["side"],
                "step": row["step"],
                "reason": error_reason(row["message"]),
            }
            for row in summary["errors"]
        )
        for number, text in enumerate(
            directory.joinpath("stdout.txt").read_text(encoding="utf-8").splitlines(), 1
        ):
            if re.search(r"timeout|timed out", text, re.IGNORECASE):
                timeout_lines.append({"db": db, "line": number, "text": text})
            found = ERROR_LINE.match(text)
            if found is not None:
                questions[int(found.group(1))] = {
                    "db": found.group(2),
                    "verdict": "ERROR",
                    "rule": None,
                    "smells": [],
                    "shuffle_tables": table_sets[db],
                }
                continue
            found = LINE.match(text)
            if found is None:
                continue
            fired = [] if found.group(4) == "none" else found.group(4).split(",")
            questions[int(found.group(1))] = {
                "db": found.group(2),
                "verdict": "GOLD-ONLY",
                "rule": found.group(3),
                "smells": fired,
                "shuffle_tables": table_sets[db],
            }
            rules[found.group(3)] += 1
    by_probe = {
        probe: sorted(qid for qid, row in questions.items() if probe in row["smells"])
        for probe in PROBES
    }
    fired_ids = sorted(qid for qid, row in questions.items() if row["smells"])
    return {
        "selected": selected,
        "audited": audited,
        "errored": len(errors),
        "smells": {probe: smells[probe] for probe in PROBES},
        "questions_with_a_smell": len(fired_ids),
        "ids_with_a_smell": fired_ids,
        "by_probe": by_probe,
        "replay_rules": dict(sorted(rules.items())),
        "questions": questions,
        "errors": errors,
        "errors_by_reason": dict(sorted(Counter(row["reason"] for row in errors).items())),
        "errors_by_side": dict(sorted(Counter(row["side"] for row in errors).items())),
        "refusals": {
            "fixture_refused_runs": fixture_refused,
            "shuffle_not_prepared_runs": shuffle_not_prepared,
            "total": fixture_refused + shuffle_not_prepared,
        },
        "timeout_lines": timeout_lines,
        "run_ids": run_ids,
        "shuffle_table_sets": table_sets,
    }


def recall(groups: dict[str, list[int]], passes: dict[str, dict]) -> dict:
    correction = set(groups["correction_set"])
    before_fired = set(passes["before"]["ids_with_a_smell"])
    after_fired = set(passes["current"]["ids_with_a_smell"])
    rows = {}
    for group, ids in groups.items():
        member = set(ids)
        fired = sorted(member & before_fired)
        rows[group] = {
            "size": len(member),
            "fired": len(fired),
            "share": round(len(fired) / len(member), 4) if member else 0.0,
            "ids": fired,
            "by_probe": {
                probe: sorted(member.intersection(passes["before"]["by_probe"][probe]))
                for probe in PROBES
            },
        }
    return {
        "measured_on": "the before pass; the current pass is Spider's after SQL",
        "groups": rows,
        "correction_delta_before_to_after": {
            "stop_firing": sorted((member & before_fired) - after_fired),
            "still_firing": sorted((correction & before_fired) & after_fired),
            "start_firing": sorted((correction & after_fired) - before_fired),
        },
    }


def main() -> None:
    inputs = load(OUT / "inputs.json")
    corrections = load(OUT / "corrections.json")
    databases = sorted(inputs["dev_databases"])
    passes = {name: read_pass(name, databases) for name in PASSES}
    ambiguous = inputs["double_quoted_literals"]["ids"]
    current_sql = {
        row["question_id"]: row["SQL"] for row in load(WORK / "data" / "questions-current.json")
    }
    transformed_sql = {
        row["question_id"]: row["SQL"] for row in load(WORK / "data" / "questions-transformed.json")
    }
    delta_rows = []
    for question_id in ambiguous:
        current = passes["current"]["questions"][question_id]
        transformed = passes["transformed"]["questions"][question_id]
        delta_rows.append(
            {
                "question_id": question_id,
                "db": current["db"],
                "current": {
                    "verdict": current["verdict"],
                    "rule": current["rule"],
                    "probes": current["smells"],
                    "shuffle_covered_tables": covered_tables(
                        current_sql[question_id], current["shuffle_tables"]
                    ),
                    "shuffle_run_tables": current["shuffle_tables"],
                },
                "transformed": {
                    "verdict": transformed["verdict"],
                    "rule": transformed["rule"],
                    "probes": transformed["smells"],
                    "shuffle_covered_tables": covered_tables(
                        transformed_sql[question_id], transformed["shuffle_tables"]
                    ),
                    "shuffle_run_tables": transformed["shuffle_tables"],
                },
            }
        )
    gold_only = {
        "reading": (
            "Gold-only SQLite probes over Spider 1.0 dev. The direction probe was off. A pass "
            "is the merge of one run per database; audited excludes statements that errored."
        ),
        "passes": passes,
        "current_to_transformed_on_the_213_ambiguous_literals": {
            "golds": len(delta_rows),
            "probes_changed": sum(
                row["current"]["probes"] != row["transformed"]["probes"] for row in delta_rows
            ),
            "verdicts_changed": sum(
                row["current"]["verdict"] != row["transformed"]["verdict"] for row in delta_rows
            ),
            "replay_rules_changed": sum(
                row["current"]["rule"] != row["transformed"]["rule"] for row in delta_rows
            ),
            "shuffle_covered_table_sets_changed": sum(
                row["current"]["shuffle_covered_tables"]
                != row["transformed"]["shuffle_covered_tables"]
                for row in delta_rows
            ),
            "shuffle_run_table_sets_changed": sum(
                row["current"]["shuffle_run_tables"] != row["transformed"]["shuffle_run_tables"]
                for row in delta_rows
            ),
            "current_fires": sum(bool(row["current"]["probes"]) for row in delta_rows),
            "transformed_fires": sum(bool(row["transformed"]["probes"]) for row in delta_rows),
            "rows": delta_rows,
        },
    }
    write(OUT / "gold-only.json", gold_only)
    changed_ids = {row["question_id"] for row in corrections["correction_set"]}
    groups = {
        "correction_set": sorted(changed_ids),
        "text_only": corrections["text_only_ids"],
        "untouched": [
            index
            for index in range(1034)
            if index not in changed_ids and index not in set(corrections["text_only_ids"])
        ],
    }
    write(OUT / "recall.json", recall(groups, passes))
    for name in PASSES:
        row = passes[name]
        print(
            f"{name}: selected {row['selected']}, audited {row['audited']}, "
            f"fires {row['questions_with_a_smell']}, errors {row['errored']}, "
            f"refusals {row['refusals']['total']}"
        )


if __name__ == "__main__":
    main()
