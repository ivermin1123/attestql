import json
import sys

sys.path.insert(0, "/Users/hoangle/Desktop/code/attestql-research/src")
import postgast
from postgast import pg_query_pb2 as nodes

from attestql.audit.statements import (
    StatementRefused,
    _breadth_first,  # private, read-only research use
    parse_statement,
)

D = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data"
W = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rb"

with open(f"{D}/hf/mini_dev_pg-00000-of-00001.json") as f:
    golds = json.load(f)

# column type map: table -> column -> data_type
coltypes = {}
with open(f"{W}/columns.txt") as f:
    for line in f:
        table, col, dtype = line.rstrip("\n").split("|")
        coltypes.setdefault(table, {})[col] = dtype

TEXTY = {"text", "character varying", "character", "citext"}


def resolve_type(parsed, colref):
    if colref is None:
        return None
    if len(colref) == 1:
        col = colref[0]
        if len(parsed.tables) == 1:
            tbl = parsed.tables[0].name
        else:
            return None
        return coltypes.get(tbl, {}).get(col)
    elif len(colref) >= 2:
        alias = colref[-2]
        col = colref[-1]
        tn = parsed.aliases.get(alias)
        if tn is None:
            return None
        return coltypes.get(tn.name, {}).get(col)
    return None


def funcnames(node):
    return tuple(postgast.unwrap_node(n).sval for n in node.funcname)


results = []
for row in golds:
    qid = row["question_id"]
    dbid = row["db_id"]
    sql = row["SQL"]
    entry = {"question_id": qid, "db_id": dbid}
    try:
        parsed = parse_statement(sql)
    except StatementRefused as e:
        entry["refused"] = str(e)
        results.append(entry)
        continue
    entry["rule"] = parsed.replay_rule.value
    entry["distinct"] = parsed.distinct
    entry["limit_stated"] = parsed.limit_stated
    entry["has_order"] = bool(parsed.ordering)

    order_keys = []
    text_order = False
    for key in parsed.ordering:
        t = resolve_type(parsed, key.column_reference)
        is_text = t in TEXTY
        order_keys.append(
            {
                "expr": key.expression,
                "column_ref": key.column_reference,
                "type": t,
                "is_text": is_text,
            }
        )
        if is_text:
            text_order = True
    entry["order_keys"] = order_keys
    entry["text_order_key"] = text_order

    # raw tree walk for MIN/MAX, GROUP BY, comparisons, LIKE over text columns
    tree = postgast.parse(sql)
    minmax_text = False
    groupby_text = False
    ord_cmp_text = False
    eq_text = False
    like_text = False
    for node in _breadth_first(tree):
        if isinstance(node, nodes.FuncCall):
            fn = funcnames(node)
            if fn and fn[-1] in ("min", "max") and len(node.args) == 1:
                arg = postgast.unwrap_node(node.args[0])
                if isinstance(arg, nodes.ColumnRef):
                    fields = tuple(
                        postgast.unwrap_node(p).sval
                        for p in arg.fields
                        if isinstance(postgast.unwrap_node(p), nodes.String)
                    )
                    t = resolve_type(parsed, fields if fields else None)
                    if t in TEXTY:
                        minmax_text = True
        elif isinstance(node, nodes.A_Expr):
            lexpr = postgast.unwrap_node(node.lexpr) if node.HasField("lexpr") else None
            if isinstance(lexpr, nodes.ColumnRef):
                fields = tuple(
                    postgast.unwrap_node(p).sval
                    for p in lexpr.fields
                    if isinstance(postgast.unwrap_node(p), nodes.String)
                )
                t = resolve_type(parsed, fields if fields else None)
                if t in TEXTY:
                    if node.kind == nodes.AEXPR_LIKE:
                        like_text = True
                    elif node.kind == nodes.AEXPR_OP:
                        opname = tuple(postgast.unwrap_node(n).sval for n in node.name)
                        if opname and opname[-1] in ("<", ">", "<=", ">="):
                            ord_cmp_text = True
                        elif opname and opname[-1] in ("=", "<>"):
                            eq_text = True

    # group_clause / distinct-over-text via top select statement only (breadth_first
    # covers subqueries too, acceptable approximation)
    select_stmt = postgast.unwrap_node(tree.stmts[0].stmt)
    for gnode in select_stmt.group_clause:
        g = postgast.unwrap_node(gnode)
        if isinstance(g, nodes.ColumnRef):
            fields = tuple(
                postgast.unwrap_node(p).sval
                for p in g.fields
                if isinstance(postgast.unwrap_node(p), nodes.String)
            )
            t = resolve_type(parsed, fields if fields else None)
            if t in TEXTY:
                groupby_text = True

    entry["minmax_text"] = minmax_text
    entry["groupby_text"] = groupby_text
    entry["ord_cmp_text"] = ord_cmp_text
    entry["eq_text"] = eq_text
    entry["like_text"] = like_text
    results.append(entry)

with open(f"{W}/parsed_golds.json", "w") as f:
    json.dump(results, f, indent=1)

n = len(results)
refused = sum(1 for r in results if "refused" in r)
text_order = sum(1 for r in results if r.get("text_order_key"))
minmax_text = sum(1 for r in results if r.get("minmax_text"))
groupby_text = sum(1 for r in results if r.get("groupby_text"))
ord_cmp_text = sum(1 for r in results if r.get("ord_cmp_text"))
eq_text = sum(1 for r in results if r.get("eq_text"))
like_text = sum(1 for r in results if r.get("like_text"))
r_ord = sum(1 for r in results if r.get("rule") == "R-ORD")
r_set = sum(1 for r in results if r.get("rule") == "R-SET")
print(f"total={n} refused={refused} r_ord={r_ord} r_set={r_set}")
print(
    f"text_order_key={text_order} minmax_text={minmax_text} groupby_text={groupby_text} ord_cmp_text={ord_cmp_text} eq_text={eq_text} like_text={like_text}"
)
