"""Re-statements of five public evaluators' result-comparators, as faithful re-implementations
of the functions cited in sources.json, applied here to two already-fetched row sets.

Every function takes:
  gold_cols, gold_rows: cursor.description-derived column names/types, and rows as returned by
                         psycopg2 (float for float8, Decimal for numeric, date/datetime as-is)
  pred_cols, pred_rows: the same for the second statement
  gold_sql: the gold's SQL text (for order-by / DISTINCT detection some evaluators do textually)
  question: the question text (for defog's order/sort/arrange keyword heuristic)
Returns True (the evaluator calls this row EQUAL / scores it 1) or False.
"""

from __future__ import annotations

import contextlib
import re
from collections import Counter
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from itertools import product


def _has_top_order_by(sql: str) -> bool:
    return "order by" in sql.lower()


# ---------------------------------------------------------------------------
# (a) BIRD Mini-Dev / original BIRD: evaluation_ex.py:calculate_ex,
# bird-bench/mini_dev b3d4bcbb; AlibabaResearch/DAMO-ConvAI evaluation.py:execute_sql,
# commit 483554ea. Both are set(predicted_res) == set(ground_truth_res) over
# cursor.fetchall() tuples, no DISTINCT handling, no type coercion beyond Python's own
# int/float/Decimal/bool equality and hashing, order and multiplicity dropped by set().
def bird_ex(gold_cols, gold_rows, pred_cols, pred_rows, gold_sql, question) -> bool:
    return set(gold_rows) == set(pred_rows)


# ---------------------------------------------------------------------------
# (c) test-suite-sql-eval: exec_eval.py:eval_exec_match/result_eq,
# ruiqi-zhong/test-suite-sql-eval 48cb78ec. keep_distinct defaults to False on the CLI
# (evaluation.py:924-926), so DISTINCT is stripped from both statements' text before they
# run; order_matters iff 'order by' appears in the (already-stripped) gold text; multiset
# equality searched over every column permutation (get_constraint_permutation), so a
# renamed or reordered projection with the same declared row count still matches. No
# multi-database distillation here: this replay tool has one database, so the "same
# denotation on every distilled copy" property this evaluator relies on for false-positive
# reduction does not transfer. DISTINCT-stripping is done properly, by the caller
# (execute_pairs.py), which re-executes the DISTINCT-stripped SQL text and passes the rows
# that produces, since the whole point of stripping DISTINCT before running is to expose
# the query's raw join fanout, which a result already fetched with DISTINCT applied cannot
# recover.
_DISTINCT_RE = re.compile(r"\bdistinct\b", re.IGNORECASE)


def _strip_distinct(sql: str) -> str:
    return _DISTINCT_RE.sub("", sql)


def test_suite_result_eq(gold_cols, gold_rows, pred_cols, pred_rows, gold_sql, question) -> bool:
    order_matters = _has_top_order_by(_strip_distinct(gold_sql))
    r1, r2 = list(gold_rows), list(pred_rows)
    if len(r1) != len(r2):
        return False
    if not r1:
        return True
    num_cols = len(r1[0])
    if len(r2[0]) != num_cols:
        return False
    for perm in product(*[range(num_cols) for _ in range(num_cols)]):
        if len(set(perm)) != len(perm):
            continue
        r2p = [tuple(row[i] for i in perm) for row in r2] if num_cols > 1 else r2
        if order_matters:
            if r1 == r2p:
                return True
        else:
            if Counter(r1) == Counter(r2p):
                return True
    return False


# ---------------------------------------------------------------------------
# (e) BIRD-CRITIC-1: evaluation/src/postgresql_test_utils.py:ex_base/preprocess_results,
# bird-bench/BIRD-CRITIC-1 f408d6c9. date/datetime cells become "YYYY-MM-DD" strings on
# both sides, then set(pred) == set(gold); no DISTINCT stripping inside ex_base itself
# (remove_distinct exists but is only invoked by a test_case that calls it explicitly).
def _preprocess_dates(rows):
    out = []
    for row in rows:
        out.append(
            tuple(v.strftime("%Y-%m-%d") if isinstance(v, (date, datetime)) else v for v in row)
        )
    return out


def bird_critic_ex_base(gold_cols, gold_rows, pred_cols, pred_rows, gold_sql, question) -> bool:
    g = _preprocess_dates(gold_rows)
    p = _preprocess_dates(pred_rows)
    if not g or not p:
        return False
    return set(g) == set(p)


# ---------------------------------------------------------------------------
# (f) LiveSQLBench: evaluation/src/test_utils.py:ex_base (its own, distinct from
# BIRD-CRITIC's), bird-bench/livesqlbench e15cd221. Dates to "YYYY-MM-DD"; Decimal and
# float cells rounded to 2 dp with ROUND_HALF_UP; order-sensitive only when the caller
# passes conditions={"order": True} -- here read off the gold SQL's own top-level ORDER BY,
# the same signal AttestQL and test-suite-sql-eval use, since LiveSQLBench's harness has
# no such signal itself (its conditions come from the benchmark's per-instance metadata).
def _round_2dp(value):
    if isinstance(value, Decimal):
        return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if isinstance(value, float):
        return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return value


def _preprocess_live(rows):
    out = []
    for row in rows:
        cells = []
        for v in row:
            if isinstance(v, (date, datetime)):
                cells.append(v.strftime("%Y-%m-%d"))
            else:
                cells.append(_round_2dp(v))
        out.append(tuple(cells))
    return out


def livesqlbench_ex_base(gold_cols, gold_rows, pred_cols, pred_rows, gold_sql, question) -> bool:
    g = _preprocess_live(gold_rows)
    p = _preprocess_live(pred_rows)
    if not g or not p:
        return False
    if _has_top_order_by(gold_sql):
        return g == p
    return set(g) == set(p)


# ---------------------------------------------------------------------------
# (g) defog-ai/sql-eval: eval/eval.py:compare_df/normalize_table, defog-ai/sql-eval
# b8333241. Operates on pandas DataFrames built from the fetched rows and the declared
# column names. Always drops duplicate rows on both sides (an unconditional DISTINCT);
# sorts columns by column name (so a differently-ordered or renamed projection is only
# forgiven if the name set matches); sorts rows on every column left to right unless the
# gold SQL's own text carries an ORDER BY or the question text contains "order", "sort" or
# "arrange"; NaN-fills with a -99999 sentinel before an elementwise "==" (a bug this reading
# preserves rather than fixes: a real -99999 in the data would collide with a NULL).
def defog_compare_df(gold_cols, gold_rows, pred_cols, pred_rows, gold_sql, question) -> bool:
    import pandas as pd

    df_gold = pd.DataFrame(gold_rows, columns=list(gold_cols))
    df_pred = pd.DataFrame(pred_rows, columns=list(pred_cols))

    def normalize(df):
        df = df.drop_duplicates()
        df = df.reindex(sorted(df.columns), axis=1)
        pattern = re.compile(r"\b(order|sort|arrange)\b", re.IGNORECASE)
        has_order = bool(pattern.search(question)) or _has_top_order_by(gold_sql)
        if not has_order:
            df = df.sort_values(by=list(df.columns)).reset_index(drop=True)
        else:
            df = df.reset_index(drop=True)
        return df

    # A raw positional comparison can raise (e.g. an elementwise-comparison error on mixed
    # types); when it does, fall through to the normalized/sorted comparison below, exactly
    # as defog's own compare_df does with its bare except-pass around the same fast path.
    with contextlib.suppress(Exception):
        if (
            df_gold.values.shape == df_pred.values.shape
            and (df_gold.values == df_pred.values).all()
        ):
            return True

    df_gold = normalize(df_gold)
    df_pred = normalize(df_pred)
    if df_gold.shape != df_pred.shape:
        return False
    df_gold = df_gold.fillna(-99999)
    df_pred = df_pred.fillna(-99999)
    try:
        return bool((df_gold.values == df_pred.values).all())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# (d) Spider 2.0: spider2-lite/evaluation_suite/evaluate.py:compare_pandas_table,
# xlang-ai/Spider2 cafb8673. Per-gold-column existence check: every gold column (here,
# since no per-instance condition_cols exists for Mini-Dev, every column) must find at
# least one predicted column (any position) whose value vector matches under 1e-2 absolute
# tolerance for numeric pairs and exact equality otherwise; ignore_order defaults False per
# the caller's standard.get("ignore_order", False), so rows are compared positionally
# unless the gold's own ORDER BY says otherwise (mapped here the same way as the other
# readings, since Mini-Dev carries no per-instance ignore_order flag); NaN is normalized
# to 0 before comparing, so a NULL and a real zero are indistinguishable to this reading.
def spider2_compare_pandas_table(
    gold_cols, gold_rows, pred_cols, pred_rows, gold_sql, question
) -> bool:
    import math

    ignore_order = not _has_top_order_by(gold_sql)

    def normalize(v):
        if v is None:
            return 0
        if isinstance(v, Decimal):
            return float(v)
        return v

    def vectors_match(v1, v2):
        v1 = [normalize(x) for x in v1]
        v2 = [normalize(x) for x in v2]
        if ignore_order:
            v1 = sorted(v1, key=lambda x: (x is None, str(x), isinstance(x, (int, float))))
            v2 = sorted(v2, key=lambda x: (x is None, str(x), isinstance(x, (int, float))))
        if len(v1) != len(v2):
            return False
        for a, b in zip(v1, v2, strict=True):  # length equality just checked above
            if a is None and b is None:
                continue
            if (
                isinstance(a, (int, float))
                and isinstance(b, (int, float))
                and not isinstance(a, bool)
                and not isinstance(b, bool)
            ):
                if not math.isclose(float(a), float(b), abs_tol=1e-2):
                    return False
            elif a != b:
                return False
        return True

    # Every row of one SQL result has the same column count, so each zip(*rows) transpose is
    # over same-length tuples; strict=True asserts that guarantee instead of silently
    # truncating if a malformed row set ever violated it.
    t_gold = list(zip(*gold_rows, strict=True)) if gold_rows else [() for _ in gold_cols]
    t_pred = list(zip(*pred_rows, strict=True)) if pred_rows else []
    if not t_pred:
        return False
    for gold_vector in t_gold:
        if not any(vectors_match(gold_vector, pred_vector) for pred_vector in t_pred):
            return False
    return True


READINGS = {
    "bird_ex": bird_ex,
    "test_suite": test_suite_result_eq,
    "bird_critic": bird_critic_ex_base,
    "livesqlbench": livesqlbench_ex_base,
    "defog": defog_compare_df,
    "spider2": spider2_compare_pandas_table,
}
