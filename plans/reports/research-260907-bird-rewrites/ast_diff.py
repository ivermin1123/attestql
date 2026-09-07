"""Classify, at clause level, what changed between the two SQL statements of each rewrite.

    MEASURE_WORK=<work-directory> <venv>/bin/python ast_diff.py

The comparison is per clause over sqlglot's canonical SQLite rendering, with identifiers
normalised and comments removed. Every touched clause is kept; the primary class is the first
match in PRECEDENCE. A table change or more than three touched clauses is a whole rewrite.
"""

import json
import os
from collections import Counter
from pathlib import Path

import sqlglot
from sqlglot import exp

WORK = Path(os.environ["MEASURE_WORK"])
HERE = Path(__file__).resolve().parent
OLD = WORK / "data/dev/dev_20240627/dev.json"
NEW = WORK / "data/hf/dev_20251106-00000-of-00001.json"
PRECEDENCE = (
    "whole_rewrite",
    "projection",
    "distinct",
    "from_tables",
    "join_condition",
    "where",
    "group_by",
    "having",
    "order_by_key",
    "order_by_direction_only",
    "limit_or_offset",
    "aggregate_function",
    "cast_or_type",
    "subquery_or_cte_shape",
)


def canonical(node: exp.Expression | None) -> str | None:
    if node is None:
        return None
    return node.sql(dialect="sqlite", normalize=True, comments=False, pad=0)


def values(nodes: list[exp.Expression]) -> list[str]:
    return sorted(canonical(node) or "" for node in nodes)


def table_names(expression: exp.Expression) -> list[str]:
    return sorted(
        ".".join(part for part in (table.catalog, table.db, table.name) if part)
        for table in expression.find_all(exp.Table)
    )


def joins(expression: exp.Expression) -> list[str]:
    rendered = []
    for join in expression.find_all(exp.Join):
        rendered.append(
            json.dumps(
                {
                    "kind": join.kind,
                    "side": join.side,
                    "on": canonical(join.args.get("on")),
                    "using": canonical(join.args.get("using")),
                },
                sort_keys=True,
            )
        )
    return sorted(rendered)


def order(expression: exp.Expression) -> tuple[list[str], list[bool]]:
    keys, directions = [], []
    for ordered in expression.find_all(exp.Ordered):
        keys.append(canonical(ordered.this) or "")
        directions.append(bool(ordered.args.get("desc")))
    return keys, directions


def feature(expression: exp.Expression, kind: type[exp.Expression]) -> list[str]:
    return values([node for node in expression.find_all(kind)])


def ctes(expression: exp.Expression) -> list[str]:
    return values([node for node in expression.find_all(exp.CTE)])


def bare_aggregate_projection(expression: exp.Expression) -> bool:
    projections = list(expression.expressions)
    if not projections or expression.args.get("group") is not None:
        return False

    def aggregate(node: exp.Expression) -> bool:
        return isinstance(node, exp.AggFunc) or node.find(exp.AggFunc) is not None

    return any(aggregate(node) for node in projections) and any(
        not aggregate(node) for node in projections
    )


def facts(expression: exp.Expression) -> dict:
    order_keys, directions = order(expression)
    limit = expression.args.get("limit")
    offset = expression.args.get("offset")
    return {
        "projection": values(list(expression.expressions)),
        "distinct": expression.args.get("distinct") is not None,
        "from_tables": table_names(expression),
        "join_condition": joins(expression),
        "where": [canonical(expression.args.get("where"))],
        "group_by": feature(expression, exp.Group),
        "having": [canonical(expression.args.get("having"))],
        "order_by_key": order_keys,
        "order_by_direction": directions,
        "limit_or_offset": [
            canonical(limit) or "",
            canonical(offset) or "",
        ],
        "aggregate_function": feature(expression, exp.AggFunc),
        "cast_or_type": feature(expression, exp.Cast),
        "subquery_or_cte": ctes(expression)
        + values([node for node in expression.find_all(exp.Subquery)]),
        "bare_aggregate_projection": bare_aggregate_projection(expression),
    }


def classify(first: exp.Expression, second: exp.Expression) -> dict:
    old, new = facts(first), facts(second)
    touched = [name for name in old if old[name] != new[name]]
    if "order_by_key" not in touched and "order_by_direction" in touched:
        touched.remove("order_by_direction")
        touched.append("order_by_direction_only")
    if old["from_tables"] != new["from_tables"] or len(touched) > 3:
        touched.append("whole_rewrite")
    primary = next((name for name in PRECEDENCE if name in touched), "whole_rewrite")
    return {
        "touched_clauses": touched,
        "primary_class": primary,
        "distinct": {"old": old["distinct"], "new": new["distinct"]},
        "old_bare_aggregate_projection": old["bare_aggregate_projection"],
        "new_bare_aggregate_projection": new["bare_aggregate_projection"],
    }


def main() -> None:
    old_entries, new_entries = json.loads(OLD.read_text()), json.loads(NEW.read_text())
    rewritten = set(json.loads((HERE / "split.json").read_text())["ids"]["sql_rewritten"])
    new_by_id = {entry["question_id"]: entry for entry in new_entries}
    questions, failures = {}, []
    for entry in old_entries:
        question_id = entry["question_id"]
        if question_id not in rewritten:
            continue
        try:
            first = sqlglot.parse_one(entry["SQL"], read="sqlite")
            second = sqlglot.parse_one(new_by_id[question_id]["SQL"], read="sqlite")
            questions[str(question_id)] = classify(first, second)
        except sqlglot.errors.ParseError as error:
            failures.append({"question_id": question_id, "error": str(error)})
    classes = Counter(row["primary_class"] for row in questions.values())
    document = {
        "reading": (
            "Clause-level sqlglot comparison. Touched clauses are all retained; primary is the "
            "first match in precedence. Whole rewrite means different tables or more than three "
            "touched clauses."
        ),
        "sqlglot_version": sqlglot.__version__,
        "dialect": "sqlite",
        "comparison": "canonical rendering, identifiers normalised, comments removed",
        "precedence": list(PRECEDENCE),
        "parse_failures": failures,
        "class_counts": dict(sorted(classes.items())),
        "questions": dict(sorted(questions.items(), key=lambda item: int(item[0]))),
    }
    (HERE / "ast-diff.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    print(f"parsed {len(questions)} of 399; classes {dict(sorted(classes.items()))}")


if __name__ == "__main__":
    main()
