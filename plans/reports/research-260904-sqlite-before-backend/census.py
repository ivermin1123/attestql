"""Feature census over the three gold sets using sqlglot's sqlite-dialect AST,
with a stated regex fallback for double-quoted literals and backtick identifiers
(sqlglot does not distinguish a double-quoted identifier from a double-quoted
string literal; that needs the db schema, read separately).

Run with the sqlglot venv: $W/env/bin/python scripts/census.py
"""

import json
import re
import sys

sys.path.insert(
    0,
    "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rd/scripts",
)
import sqlglot
from load_golds import SETS, load
from sqlglot import exp

W = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rd"

with open(f"{W}/schema.json") as f:
    SCHEMA = json.load(f)

_DQ_TOKEN = re.compile(r'"((?:[^"]|"")*)"')
_BT_TOKEN = re.compile(r"`[^`]+`")
_INT_LITERAL = re.compile(r"^-?\d+$")

DATE_FUNC_NAMES = {"JULIANDAY", "TIME", "DATETIME"}


def schema_names(db_id):
    """Lowercased set of every table name and every column name in this db."""
    info = SCHEMA[db_id]
    names = set(t.lower() for t in info["tables"])
    for cols in info["columns"].values():
        for name, _ in cols:
            names.add(name.lower())
    return names


def column_affinity(db_id, table_hint, col_name):
    """SQLite type affinity of a column, by name, using the declared type text
    (approximation via the rules of https://sqlite.org/datatype3.html #3.1):
    contains INT -> INTEGER; contains CHAR/CLOB/TEXT -> TEXT; contains REAL/FLOA/DOUB
    -> REAL; contains BLOB or empty -> BLOB; else NUMERIC. table_hint narrows the
    search when given; otherwise every table of the db is checked and the affinity
    is returned only if every match agrees (else None: ambiguous)."""
    info = SCHEMA[db_id]
    candidates = []
    tables = (
        [table_hint] if table_hint and table_hint in info["columns"] else info["columns"].keys()
    )
    for t in tables:
        for name, decltype in info["columns"].get(t, []):
            if name.lower() == col_name.lower():
                candidates.append((decltype or "").upper())
    if not candidates:
        return None
    affinities = {_affinity_of(d) for d in candidates}
    if len(affinities) != 1:
        return None
    return affinities.pop()


def _affinity_of(decltype):
    d = decltype.upper()
    if "INT" in d:
        return "INTEGER"
    if "CHAR" in d or "CLOB" in d or "TEXT" in d:
        return "TEXT"
    if "REAL" in d or "FLOA" in d or "DOUB" in d:
        return "REAL"
    if "BLOB" in d or d == "":
        return "BLOB"
    return "NUMERIC"


def table_aliases(select):
    """alias (or bare table name) -> table name, for the FROM/JOIN sources of one
    SELECT that are plain tables (not a subquery)."""
    aliases = {}
    for t in select.find_all(exp.Table):
        name = t.name
        alias = t.alias or name
        aliases[alias] = name
    return aliases


def resolve_column(select, aliases, db_id, node):
    """(table_or_None, column_name) for a Column node, best-effort."""
    if not isinstance(node, exp.Column):
        return None
    col = node.name
    tbl = node.table
    if tbl and tbl in aliases:
        return aliases[tbl], col
    if not tbl and len(aliases) == 1:
        return next(iter(aliases.values())), col
    return None, col


def literal_kind(node):
    """'int', 'real', 'text' or None for a Literal node."""
    if not isinstance(node, exp.Literal):
        return None
    if node.is_string:
        return "text"
    return "int" if _INT_LITERAL.match(node.this) else "real"


def census_one(sql, db_id):
    """Return a dict of booleans/counts for one gold, or {'_parse_error': True}."""
    c = {}
    try:
        tree = sqlglot.parse_one(sql, read="sqlite", error_level=sqlglot.ErrorLevel.RAISE)
    except Exception:
        return {"_parse_error": True}

    # double-quoted tokens that name no column/table of this db: a real string literal.
    names = schema_names(db_id)
    dq_tokens = _DQ_TOKEN.findall(sql)
    dq_literals = [tok for tok in dq_tokens if tok.replace('""', '"').lower() not in names]
    c["double_quoted_any"] = len(dq_tokens) > 0
    c["double_quoted_literal"] = len(dq_literals) > 0
    c["double_quoted_literal_tokens"] = dq_literals[:3]

    c["backtick"] = bool(_BT_TOKEN.search(sql))

    selects = list(tree.find_all(exp.Select))

    def nodes():
        for n in tree.walk():
            yield n[0] if isinstance(n, tuple) else n

    all_nodes = list(nodes())
    c["iif"] = any(isinstance(n, exp.If) for n in all_nodes)
    c["strftime"] = any(isinstance(n, exp.TimeToStr) for n in all_nodes)
    c["date_func"] = any(isinstance(n, exp.Date) for n in all_nodes)
    c["julianday_time_datetime"] = any(
        isinstance(n, exp.Anonymous) and n.this.upper() in DATE_FUNC_NAMES for n in all_nodes
    )
    c["any_date_func"] = c["strftime"] or c["date_func"] or c["julianday_time_datetime"]

    casts = [n for n in all_nodes if isinstance(n, exp.Cast)]
    cast_targets = [str(n.to) for n in casts]
    c["cast_any"] = len(casts) > 0
    c["cast_real"] = any(
        "REAL" in t.upper() or "FLOAT" in t.upper() or "DOUBLE" in t.upper() for t in cast_targets
    )
    c["cast_integer"] = any("INT" in t.upper() for t in cast_targets)
    c["cast_other"] = any(
        not (
            "REAL" in t.upper()
            or "FLOAT" in t.upper()
            or "DOUBLE" in t.upper()
            or "INT" in t.upper()
        )
        for t in cast_targets
    )

    c["window"] = any(isinstance(n, exp.Window) for n in all_nodes)
    c["like"] = any(isinstance(n, (exp.Like, exp.ILike)) for n in all_nodes)
    c["concat_pipe"] = any(isinstance(n, exp.DPipe) for n in all_nodes)
    c["exists"] = any(isinstance(n, exp.Exists) for n in all_nodes)
    c["cte"] = any(isinstance(n, (exp.With, exp.CTE)) for n in all_nodes)
    c["union"] = any(isinstance(n, exp.Union) for n in all_nodes)
    c["intersect_except"] = any(isinstance(n, (exp.Intersect, exp.Except)) for n in all_nodes)
    c["substr"] = any(isinstance(n, exp.Substring) for n in all_nodes)
    c["instr"] = any(isinstance(n, exp.StrPosition) for n in all_nodes)
    c["round"] = any(isinstance(n, exp.Round) for n in all_nodes)
    c["glob"] = any(isinstance(n, exp.Glob) for n in all_nodes)

    counts = [n for n in all_nodes if isinstance(n, exp.Count)]
    c["count_star"] = any(isinstance(n.this, exp.Star) for n in counts)
    c["count_col"] = any(not isinstance(n.this, exp.Star) for n in counts)

    # subquery in FROM: a Subquery whose parent is a From or a Join.
    subq_in_from = False
    for n in all_nodes:
        if isinstance(n, exp.Subquery):
            parent = n.parent
            if isinstance(parent, (exp.From, exp.Join)):
                subq_in_from = True
    c["subquery_in_from"] = subq_in_from

    # DISTINCT and LIMIT/ORDER BY at the outermost select-like node.
    outer = tree
    while isinstance(outer, exp.Subquery):
        outer = outer.this
    c["distinct"] = bool(outer.args.get("distinct")) if hasattr(outer, "args") else False
    has_limit = bool(getattr(outer, "args", {}).get("limit"))
    has_order = bool(getattr(outer, "args", {}).get("order"))
    c["limit_no_order"] = has_limit and not has_order

    # GROUP BY with a bare, non-aggregated projected column not among the group keys.
    group_bare_nonagg = False
    for sel in selects:
        group = sel.args.get("group")
        if not group:
            continue
        group_texts = {g.sql(dialect="sqlite") for g in group.expressions}
        for proj in sel.expressions:
            target = proj.this if isinstance(proj, exp.Alias) else proj
            group_tails = {g.split(".")[-1] for g in group_texts}
            if (
                isinstance(target, exp.Column)
                and target.sql(dialect="sqlite") not in group_texts
                and target.name not in group_tails
            ):
                group_bare_nonagg = True
    c["group_bare_nonagg"] = group_bare_nonagg

    # integer division and text-vs-numeric comparison, per SELECT, approximated
    # from declared-type affinity (see column_affinity above); ambiguous columns
    # (name not found, or found with disagreeing affinity across tables) are
    # skipped rather than guessed.
    int_div = False
    text_numeric_cmp = False
    for sel in selects:
        aliases = table_aliases(sel)

        def affinity_of_expr(node, sel=sel, aliases=aliases):
            if isinstance(node, exp.Column):
                tbl, col = resolve_column(sel, aliases, db_id, node)
                return column_affinity(db_id, tbl, col)
            if isinstance(node, exp.Count):
                # COUNT(...) is always an integer, in SQLite and in PostgreSQL.
                return "INTEGER"
            kind = literal_kind(node)
            if kind == "int":
                return "INTEGER"
            if kind == "real":
                return "REAL"
            return None

        for n in sel.walk():
            node = n[0] if isinstance(n, tuple) else n
            if isinstance(node, exp.Div):
                left_aff = affinity_of_expr(node.this)
                right_aff = affinity_of_expr(node.expression)
                if left_aff == "INTEGER" and right_aff == "INTEGER":
                    int_div = True
            if isinstance(node, (exp.EQ, exp.NEQ, exp.GT, exp.LT, exp.GTE, exp.LTE)):
                left_aff = affinity_of_expr(node.this)
                right_aff = affinity_of_expr(node.expression)
                if {left_aff, right_aff} & {"TEXT"} and (
                    {left_aff, right_aff} & {"INTEGER", "REAL"}
                ):
                    text_numeric_cmp = True
    c["int_div_approx"] = int_div
    c["text_numeric_cmp_approx"] = text_numeric_cmp

    return c


FEATURE_KEYS = [
    "double_quoted_any",
    "double_quoted_literal",
    "backtick",
    "iif",
    "strftime",
    "date_func",
    "julianday_time_datetime",
    "any_date_func",
    "cast_any",
    "cast_real",
    "cast_integer",
    "cast_other",
    "int_div_approx",
    "limit_no_order",
    "text_numeric_cmp_approx",
    "window",
    "group_bare_nonagg",
    "like",
    "concat_pipe",
    "subquery_in_from",
    "cte",
    "exists",
    "union",
    "intersect_except",
    "substr",
    "instr",
    "round",
    "distinct",
    "count_star",
    "count_col",
    "glob",
]


def main():
    summary = {}
    for set_name in SETS:
        rows = load(set_name)
        counts = {k: 0 for k in FEATURE_KEYS}
        parse_errors = 0
        dq_examples = []
        for r in rows:
            c = census_one(r["SQL"], r["db_id"])
            if c.get("_parse_error"):
                parse_errors += 1
                continue
            for k in FEATURE_KEYS:
                if c.get(k):
                    counts[k] += 1
            if c.get("double_quoted_literal") and len(dq_examples) < 10:
                dq_examples.append(
                    {
                        "question_id": r["question_id"],
                        "db_id": r["db_id"],
                        "tokens": c["double_quoted_literal_tokens"],
                    }
                )
        summary[set_name] = {"total": len(rows), "parse_errors": parse_errors, "counts": counts}
        with open(f"{W}/census_dq_examples_{set_name}.json", "w") as f:
            json.dump(dq_examples, f, indent=1)
        print(set_name, "done")

    with open(f"{W}/census_summary.json", "w") as f:
        json.dump(summary, f, indent=1)


if __name__ == "__main__":
    main()
