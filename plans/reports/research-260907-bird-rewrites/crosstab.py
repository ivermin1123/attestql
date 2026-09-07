"""Cross-tabulate replay result classes against primary SQL classes and count candidates.

    python3 crosstab.py

The sample rule is fixed here so the hand readings are auditable: ids sorted numerically, then
every ceil(class size / 8)-th id from the first, at most eight per class.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sample(ids: list[int], size: int = 8) -> list[int]:
    stride = max(1, -(-len(ids) // size))
    return ids[::stride][:size]


def result_class(row: dict) -> str:
    if row["verdict"] == "ERROR":
        return "error"
    if row["verdict"] == "EQUAL":
        return "equal"
    if row["multiset_equal"]:
        return "same_multiset_other_order"
    return row["mechanism"]


def main() -> None:
    verdicts = load(HERE / "verdicts.json")["groups"]["rewrite-399"]["questions"]
    ast = load(HERE / "ast-diff.json")["questions"]
    rows: dict[int, tuple[str, str, dict, dict]] = {}
    for key, replay in verdicts.items():
        question_id = int(key)
        rows[question_id] = (result_class(replay), ast[key]["primary_class"], replay, ast[key])

    table: dict[str, dict[str, dict]] = defaultdict(dict)
    for question_id, (result, sql_class, replay, _) in rows.items():
        cell = table[result].setdefault(sql_class, {"count": 0, "probe_fired": 0, "ids": []})
        cell["count"] += 1
        cell["probe_fired"] += bool(replay["smells"])
        cell["ids"].append(question_id)

    classes = sorted({sql_class for _, sql_class, _, _ in rows.values()})
    sample_ids = {
        sql_class: sample(
            sorted(question_id for question_id, value in rows.items() if value[1] == sql_class)
        )
        for sql_class in classes
    }
    changed = [
        question_id
        for question_id, (_, _, replay, _) in rows.items()
        if replay["verdict"] == "NOT_EQUAL" and replay["multiset_equal"] is False
    ]
    duplicate_ids = [
        question_id
        for question_id, value in sorted(rows.items())
        if question_id in changed
        and value[3]["distinct"]["old"] is False
        and value[3]["distinct"]["new"] is True
        and value[2]["gold_duplicate_rows"]
    ]
    bare_aggregate_ids = [
        question_id
        for question_id, value in sorted(rows.items())
        if question_id in changed
        and value[3]["old_bare_aggregate_projection"]
        and not value[3]["new_bare_aggregate_projection"]
    ]
    direction_ids = [
        question_id
        for question_id, value in sorted(rows.items())
        if question_id in changed and value[1] == "order_by_direction_only"
    ]
    candidates = {
        "current_gold_only_probes": {
            "count": sum(bool(value[2]["smells"]) for value in rows.values()),
            "needs_question": False,
        },
        "duplicate_rows_fixed_by_distinct": {
            "count": len(duplicate_ids),
            "needs_question": False,
            "ids": duplicate_ids,
        },
        "bare_aggregate_mixed_projection": {
            "count": len(bare_aggregate_ids),
            "needs_question": False,
            "ids": bare_aggregate_ids,
        },
        "direction_against_question": {
            "count": len(direction_ids),
            "needs_question": True,
            "ids": direction_ids,
        },
        "projection_contract": {
            "count": sum(
                value[1] == "projection" and question_id in changed
                for question_id, value in rows.items()
            ),
            "needs_question": True,
        },
    }
    current_ids = {question_id for question_id, value in rows.items() if value[2]["smells"]}
    duplicate_ids_set, bare_ids_set = set(duplicate_ids), set(bare_aggregate_ids)
    candidates["gold_only_candidates_combined"] = {
        "count": len(current_ids | duplicate_ids_set | bare_ids_set),
        "current_count": len(current_ids),
        "distinct_increment": len(duplicate_ids_set - current_ids),
        "bare_aggregate_increment": len(bare_ids_set - current_ids - duplicate_ids_set),
        "overlaps": {
            "current_and_distinct": sorted(current_ids & duplicate_ids_set),
            "current_and_bare_aggregate": sorted(current_ids & bare_ids_set),
            "distinct_and_bare_aggregate": sorted(duplicate_ids_set & bare_ids_set),
        },
        "needs_question": False,
    }
    document = {
        "reading": (
            "Rewrite-399 only. Result equal includes EQUAL and NOT_EQUAL rows whose multiset is "
            "equal; error is q1131. Each cell also counts the ids whose old gold fired a probe."
        ),
        "sample_rule": "sorted ids, every ceil(size/8)-th from the first, at most 8 per class",
        "result_totals": dict(sorted(Counter(value[0] for value in rows.values()).items())),
        "sql_class_totals": dict(sorted(Counter(value[1] for value in rows.values()).items())),
        "sql_class_probe_fires": dict(
            sorted(Counter(value[1] for value in rows.values() if value[2]["smells"]).items())
        ),
        "crosstab": dict(sorted(table.items())),
        "sample_ids": sample_ids,
        "candidate_checks": candidates,
    }
    (HERE / "crosstab.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"result_totals": document["result_totals"], "classes": document["sql_class_totals"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
