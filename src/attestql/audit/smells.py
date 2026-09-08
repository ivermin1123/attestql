"""The five gold-only smells: mechanical reasons to read a gold statement again.

ADR-0013 point 2 and the four probes of
``plans/reports/mechanism-260902-2055-gold-audit-detection.md``, measured over all 498
Mini-Dev golds in ``plans/reports/measurement-260902-2226-gold-only-probes-mini-dev.md``
and shipped under the decisions that measurement recorded. Each smell takes the parsed
gold, a backend and the result the gold produced, asks the database one more question,
and answers whether something about the statement makes its answer arbitrary.

**A smell is a heuristic and never a verdict.** Nothing here says a gold is wrong.
Every ``Smell`` carries ``heuristic: true`` and a ``means`` sentence a maintainer can
read, and the fired ones are a reading order, not a defect list. On the measured corpus
two of three valid fires were worth acting on and one in three was not.

**What each one asks.**

``ordering-over-numeric-text`` orders by a text column whose values all look like
numbers, then reruns the gold with that key cast to numeric: when the two answers differ,
the statement sorted 91.610 above 257.320 and the question almost certainly did not mean
that.

``arbitrary-cut`` looks at a LIMIT and asks whether the cut is arbitrary and the answer
depends on it. An unordered bound fires when a rerun over shuffled data changes the
result. An ordered bound fires when the rows at the cut are tied on every ordering key
and those tied rows project different answers; tied rows that project the same answer
are not a hazard, which is what removed every miss on the measured corpus. Its third
case is a key that puts nulls first and a bounded result that then holds one.

``not-a-function-of-the-data`` reruns the gold over a seeded shuffled copy of its tables
and compares the full result under the gold's own rule. When the two differ, the answer
depended on the order rows happened to be stored in. When the only differing cells are of
a type whose aggregates the engine adds up value by value, and they agree to six
significant digits, the smell is reported as ``float-aggregate-order`` instead: that is
summation order, not a defect in the statement, and BIRD compares floats exactly. Which
types those are is the engine's own answer: PostgreSQL names ``float4`` and ``float8``,
and SQLite names none, because it adds a REAL aggregate with a compensation and a changed
REAL there is the statement depending on the storage order after all.

``duplicate-full-row`` reads the result the gold itself returned and counts whole rows that
came back more than once. It asks the database nothing: a statement that returns the same row
twice and never says DISTINCT disagrees on multiplicity alone with an equally correct statement
that returns each row once, and under a multiset comparison that disagreement is the whole
verdict. Of the 399 dev golds BIRD rewrote on 2025-11-06, 23 whose answer changed are of this
shape and 22 of them fire none of the other probes; of the credited predictions a typed
comparison calls unequal, 1,697 of 1,751 differ by multiplicity alone. A repeat is not a defect:
a question can ask for one row per occurrence, which is why this is a reading order like every
other smell here.

``direction-against-question`` is experimental and off unless asked for. It reads the
question text for words meaning a maximum or a minimum and fires on the contradiction
with the first ordering key. Its precision on the measured corpus was 17 %, and it needs
a birthday inversion rule and an "alphabetical" exception before it is a feature.

Nothing here writes to the database. The shuffled copies are made once per run by the
backend and are named in the evidence, including the tables too large to have been
copied, so a quiet smell never reads as a measurement that was taken.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, localcontext

from attestql.audit.backend import (
    Backend,
    BackendRefused,
    ShuffledCopies,
    TableName,
    TextCensus,
    planner_statistics_json,
)
from attestql.audit.parse import ORDERING_KEY_PREFIX, OrderingKey, ParsedStatement
from attestql.evidence.render import Json, json_row, result_digest, result_json
from attestql.evidence.replay import ComparabilityResult, ReplayRule, compare_results
from attestql.evidence.serialize import SerializationDescriptor, typed_row, typed_value
from attestql.kernel.types import ExecutionResult

ORDERING_OVER_NUMERIC_TEXT = "ordering-over-numeric-text"
ARBITRARY_CUT = "arbitrary-cut"
NOT_A_FUNCTION_OF_THE_DATA = "not-a-function-of-the-data"
DUPLICATE_FULL_ROW = "duplicate-full-row"
FLOAT_AGGREGATE_ORDER = "float-aggregate-order"
DIRECTION_AGAINST_QUESTION = "direction-against-question"

SMELL_NAMES: tuple[str, ...] = (
    ORDERING_OVER_NUMERIC_TEXT,
    ARBITRARY_CUT,
    NOT_A_FUNCTION_OF_THE_DATA,
    FLOAT_AGGREGATE_ORDER,
    DUPLICATE_FULL_ROW,
    DIRECTION_AGAINST_QUESTION,
)
"""Every name a smell can be reported under, so a summary can count them all at zero."""

ROWS_IN_EVIDENCE = 10
"""How many rows a fired smell shows. The record beside it holds the whole result."""

NUMERIC_TEXT = r"^-?[0-9]+(\.[0-9]+)?$"
"""What counts as a numeric-looking text value. A form this rejects is counted
non-numeric and the smell stays quiet, which is the conservative direction."""

SIGNIFICANT_DIGITS = 6
"""How far two float values have to agree before their difference is called summation
order rather than a difference in the answer."""

DEFAULT_SHUFFLE_ROW_LIMIT = 300_000
"""A table with more rows than this is not copied for the shuffle; the skip is recorded."""

DEFAULT_SHUFFLE_SEED = 1
"""The seed the shuffled copies are ordered by, so one run reproduces another."""

NO_SHUFFLE = "no shuffled copies were prepared"
"""Why a smell that reruns over shuffled copies did not ask its question at all. A caller
that knows the reason states it instead; this is what is said when it has none."""

MAX_INTENT: tuple[str, ...] = (
    "highest",
    "most",
    "max",
    "maximum",
    "top",
    "largest",
    "greatest",
    "biggest",
    "longest",
    "latest",
    "newest",
    "best",
    "richest",
    "oldest",
)
MIN_INTENT: tuple[str, ...] = (
    "lowest",
    "least",
    "min",
    "minimum",
    "fewest",
    "smallest",
    "shortest",
    "earliest",
    "youngest",
    "worst",
    "cheapest",
    "poorest",
)
"""The two intent lists the experimental smell searches for, whole words and case
insensitive, over the question and its hint together."""

_MEANS: Mapping[str, str] = {
    ORDERING_OVER_NUMERIC_TEXT: (
        "this statement orders by a text column holding only numbers, and ordering it as "
        "a number gives a different answer, so the gold may be sorting 9.5 above 10"
    ),
    ARBITRARY_CUT: (
        "this statement cuts its result at a LIMIT that does not decide which rows come "
        "back, so a different but equally correct statement can return other rows and score zero"
    ),
    NOT_A_FUNCTION_OF_THE_DATA: (
        "rerun over the same rows in another physical order this statement gives another "
        "answer, so its result depends on how the rows are stored and not only on the data"
    ),
    FLOAT_AGGREGATE_ORDER: (
        "this statement aggregates floating point numbers, so its last digits depend on "
        "the order the rows were summed in; the values agree to six significant digits"
    ),
    DUPLICATE_FULL_ROW: (
        "this statement returns the same whole row more than once and never says DISTINCT, "
        "so a statement answering the same question once per row disagrees on multiplicity alone"
    ),
    DIRECTION_AGAINST_QUESTION: (
        "the question asks for a maximum or a minimum and the statement orders the other "
        "way, so the bounded result may be the wrong end of the list; experimental"
    ),
}

_WORD = re.compile(r"[a-z]+")


@dataclass(frozen=True)
class Smell:
    """What one smell found on one gold statement.

    ``applicable`` says the question was asked at all: a statement with no LIMIT is not
    quiet about its cut, it has none. ``fired`` says the answer was yes. ``evidence``
    holds what was measured, always with ``heuristic`` and ``means`` in it, and
    ``counterexample_rows`` holds the rows a reader should look at first, bounded, and is
    empty unless the smell fired.
    """

    name: str
    fired: bool
    applicable: bool
    evidence: Json
    counterexample_rows: tuple[tuple[object, ...], ...] = ()

    def __post_init__(self) -> None:
        if self.fired and not self.applicable:
            raise ValueError(f"{self.name} fired on a statement it does not apply to")
        if self.counterexample_rows and not self.fired:
            raise ValueError(f"{self.name} is quiet and still carries counterexample rows")


@dataclass(frozen=True)
class SmellSettings:
    """What every smell needs beyond the statement, the backend and the result."""

    serialization: SerializationDescriptor
    statement_timeout_seconds: int
    shuffle_seed: int = DEFAULT_SHUFFLE_SEED
    shuffle_row_limit: int = DEFAULT_SHUFFLE_ROW_LIMIT
    plan_variant: bool = False
    experimental_s2: bool = False


@dataclass(frozen=True)
class QuestionText:
    """The question as it was asked and the hint the set supplied beside it."""

    question: str
    evidence: str = field(default="")


def _evidence(name: str, payload: Json) -> Json:
    """One smell's evidence, with what it is and what it would mean stated in it."""
    return {"heuristic": True, "means": _MEANS[name], **payload}


def _quiet(name: str, payload: Json, *, applicable: bool) -> Smell:
    return Smell(name=name, fired=False, applicable=applicable, evidence=_evidence(name, payload))


def _fired(name: str, payload: Json, rows: Sequence[tuple[object, ...]]) -> Smell:
    return Smell(
        name=name,
        fired=True,
        applicable=True,
        evidence=_evidence(name, payload),
        counterexample_rows=tuple(rows[:ROWS_IN_EVIDENCE]),
    )


def _declared_type(columns: Mapping[str, str], column: str) -> str | None:
    """The declared type of a column, matching the case the catalogue reports it in."""
    if column in columns:
        return columns[column]
    lowered = column.lower()
    for name, declared in columns.items():
        if name.lower() == lowered:
            return declared
    return None


def _resolve_key(
    parsed: ParsedStatement, catalogue: Mapping[TableName, Mapping[str, str]], key: OrderingKey
) -> tuple[TableName, str, str] | str:
    """An ordering key as ``(relation, column, declared type)``, or why it is not one.

    The relation is the name the statement wrote, schema and all, and the catalogue was
    asked under those names: two tables called ``y`` in two schemas are two entries, and
    the key resolves against the one its own FROM clause named.
    """
    fields = key.column_reference
    if not fields:
        return "the key is an expression and not a column"
    if len(fields) == 1:
        name = fields[0]
        if name in parsed.output_names:
            return "the key names an output column of the select list"
        holders = [
            relation
            for relation in sorted(set(parsed.aliases.values()))
            if _declared_type(catalogue.get(relation, {}), name) is not None
        ]
        if not holders:
            return "no table in the FROM clause holds a column of that name"
        if len(holders) > 1:
            return f"the name is held by {len(holders)} of the tables in the FROM clause"
        relation = holders[0]
    else:
        found = parsed.aliases.get(fields[-2])
        if found is None:
            return "the qualifier does not name a table of the FROM clause"
        relation = found
    declared = _declared_type(catalogue.get(relation, {}), fields[-1])
    if declared is None:
        return f"{relation.text} has no column named {fields[-1]}"
    return (relation, fields[-1], declared)


def _census_json(census: TextCensus) -> Json:
    return {
        "rows": census.rows,
        "nulls": census.nulls,
        "empty_strings": census.empty_strings,
        "non_numeric": census.non_numeric,
        "pattern": census.pattern,
    }


def ordering_over_numeric_text(
    parsed: ParsedStatement, backend: Backend, baseline: ExecutionResult, *, settings: SmellSettings
) -> Smell:
    """The gold orders by text that holds numbers, and ordering it as numbers differs."""
    name = ORDERING_OVER_NUMERIC_TEXT
    if not parsed.ordering:
        return _quiet(
            name, {"reason": "the statement states no top level ORDER BY"}, applicable=False
        )
    if parsed.set_operation or parsed.from_has_subquery:
        return _quiet(
            name,
            {"reason": "an ordering key of a set operation or a subselect resolves to no column"},
            applicable=False,
        )
    try:
        catalogue = backend.column_types(parsed.tables)
    except BackendRefused as refused:
        return _quiet(name, {"error": refused.detail, "step": refused.step}, applicable=True)
    keys: list[Json] = []
    over_text: list[tuple[int, TableName, str]] = []
    for index, key in enumerate(parsed.ordering):
        resolved = _resolve_key(parsed, catalogue, key)
        if isinstance(resolved, str):
            keys.append({"key": key.expression, "not_applicable": resolved})
            continue
        relation, column, declared = resolved
        # Whether a declaration is text is the engine's reading of it and not a list kept
        # here: one catalogue renders a closed set of names and another keeps the text of
        # the CREATE statement, where VARCHAR(50) is a text column and matches no name.
        textual = backend.declared_type_is_text(declared)
        keys.append(
            {
                "key": key.expression,
                "column": f"{relation.text}.{column}",
                "declared_type": declared,
                "not_applicable": None if textual else "the column is not declared as text",
            }
        )
        if textual:
            over_text.append((index, relation, column))
    if not over_text:
        return _quiet(
            name,
            {"reason": "no ORDER BY key resolves to a text column", "keys": keys},
            applicable=False,
        )
    return _numeric_cast_reruns(parsed, backend, baseline, settings, keys, over_text)


def _numeric_cast_reruns(
    parsed: ParsedStatement,
    backend: Backend,
    baseline: ExecutionResult,
    settings: SmellSettings,
    keys: list[Json],
    over_text: Sequence[tuple[int, TableName, str]],
) -> Smell:
    """Census each text key and, when it holds only numbers, rerun the gold cast."""
    name = ORDERING_OVER_NUMERIC_TEXT
    fired = False
    for index, relation, column in over_text:
        evidence = keys[index]
        try:
            census = backend.numeric_text_census(relation, column, NUMERIC_TEXT)
        except BackendRefused as refused:
            evidence["census_error"] = refused.detail
            continue
        evidence["census"] = _census_json(census)
        readable = census.rows - census.nulls - census.empty_strings
        if census.non_numeric or readable < 1:
            evidence["every_value_is_numeric"] = False
            continue
        evidence["every_value_is_numeric"] = True
        cast_sql = parsed.with_ordering_key_cast_to_numeric(index)
        evidence["cast_sql"] = cast_sql
        try:
            rerun = backend.execute(
                cast_sql, statement_timeout_seconds=settings.statement_timeout_seconds
            )
        except BackendRefused as refused:
            evidence["cast_error"] = refused.detail
            continue
        verdict = compare_results(
            baseline, rerun, rule=ReplayRule.R_ORD, serialization=settings.serialization
        )
        evidence["verdict"] = verdict.result.value
        evidence["gold_result"] = result_json(
            baseline, settings.serialization, bound=ROWS_IN_EVIDENCE
        )
        evidence["cast_result"] = result_json(rerun, settings.serialization, bound=ROWS_IN_EVIDENCE)
        fired = fired or verdict.result is ComparabilityResult.NOT_EQUAL
    payload: Json = {"keys": keys}
    if not fired:
        return _quiet(name, payload, applicable=True)
    return _fired(name, payload, baseline.rows)


def _nulls_first_in_effect(key: OrderingKey) -> bool:
    """Whether this key would put its nulls at the top of the result.

    The parse decides it wherever the engine's default is settled, and ``default`` means
    that parse left it open. On PostgreSQL a null sorts as larger than every value, so an
    ascending key puts its nulls last and a descending key puts them first, which is what
    is read here; SQLite sorts a null below every value and its ordering is the mirror,
    which the SQLite parse fills in per key rather than leaving to be read here.

    Reading PostgreSQL's default the other way round is what made this probe call a plain
    ``ORDER BY x ASC LIMIT 1`` a null-first cut, which on PostgreSQL it is not and on
    SQLite it is.
    """
    if key.nulls != "default":
        return key.nulls == "first"
    return key.descending


def arbitrary_cut(
    parsed: ParsedStatement,
    backend: Backend,
    baseline: ExecutionResult,
    *,
    settings: SmellSettings,
    shuffled: ShuffledCopies | None = None,
    no_shuffle: str = "",
) -> Smell:
    """The gold bounds its result at a cut that does not decide which rows come back.

    ``no_shuffle`` is why there are no copies, when the caller knows: the no-ORDER-BY case
    is answered by rerunning over them, so without them the question was not asked and the
    smell says which reason stopped it rather than reading as a quiet no.
    """
    name = ARBITRARY_CUT
    if not parsed.limit_stated:
        return _quiet(name, {"reason": "the statement states no LIMIT"}, applicable=False)
    if parsed.limit_count is None:
        return _quiet(name, {"reason": "the LIMIT is not an integer constant"}, applicable=False)
    if parsed.offset_stated and parsed.offset_count is None:
        return _quiet(name, {"reason": "the OFFSET is not an integer constant"}, applicable=False)
    offset = parsed.offset_count or 0
    cut = offset + parsed.limit_count
    if cut < 1:
        return _quiet(
            name,
            {"reason": "the bound admits no row, so there is no cut", "cut": cut},
            applicable=False,
        )
    if not parsed.ordering:
        return _unordered_cut(parsed, backend, baseline, settings, shuffled, no_shuffle, cut)
    if parsed.set_operation:
        return _quiet(
            name,
            {"reason": "a set operation has no select list to project its ordering keys through"},
            applicable=False,
        )
    return _ordered_cut(parsed, backend, settings, offset, cut)


def _unordered_cut(
    parsed: ParsedStatement,
    backend: Backend,
    baseline: ExecutionResult,
    settings: SmellSettings,
    shuffled: ShuffledCopies | None,
    no_shuffle: str,
    cut: int,
) -> Smell:
    """A bound with no ordering: fired when the same rows in another order answer otherwise."""
    name = ARBITRARY_CUT
    payload: Json = {
        "case": "no-ordering",
        "cut": cut,
        "why": "the statement bounds its result and states no ORDER BY, so which rows it "
        "returns is whichever ones the plan produced first",
    }
    if shuffled is None:
        # Not applicable rather than quiet: the one measurement that answers this case was
        # not taken, and a reader has to be able to tell that from a bound that was tested.
        payload["reason"] = f"{no_shuffle or NO_SHUFFLE}, so the bound was not tested"
        return _quiet(name, payload, applicable=False)
    payload["shuffle"] = _shuffle_json(parsed, shuffled)
    try:
        rerun = backend.execute_shuffled(
            parsed.sql, statement_timeout_seconds=settings.statement_timeout_seconds
        )
    except BackendRefused as refused:
        payload["error"] = refused.detail
        return _quiet(name, payload, applicable=True)
    verdict = compare_results(
        baseline, rerun, rule=ReplayRule.R_SET, serialization=settings.serialization
    )
    payload["verdict"] = verdict.result.value
    payload["gold_result"] = result_json(baseline, settings.serialization, bound=ROWS_IN_EVIDENCE)
    payload["shuffled_result"] = result_json(rerun, settings.serialization, bound=ROWS_IN_EVIDENCE)
    if verdict.result is not ComparabilityResult.NOT_EQUAL:
        return _quiet(name, payload, applicable=True)
    return _fired(name, payload, rerun.rows)


def _ordered_cut(
    parsed: ParsedStatement,
    backend: Backend,
    settings: SmellSettings,
    offset: int,
    cut: int,
) -> Smell:
    """An ordered bound: the rows at the cut, and where the nulls in the keys went."""
    name = ARBITRARY_CUT
    variant_sql = parsed.without_the_bound_and_projecting_its_keys()
    payload: Json = {
        "cut": cut,
        "offset": offset,
        "distinct_kept": parsed.distinct,
        "unbounded_sql": variant_sql,
    }
    try:
        unbounded = backend.execute(
            variant_sql, statement_timeout_seconds=settings.statement_timeout_seconds
        )
    except BackendRefused as refused:
        payload["error"] = refused.detail
        return _quiet(name, payload, applicable=True)
    keys = len(parsed.ordering)
    projected = len(unbounded.columns) - keys
    rows = unbounded.rows
    payload["unbounded_rows"] = len(rows)
    payload["projected_columns"] = [column.name for column in unbounded.columns[:projected]]
    payload["ordering_key_columns"] = [
        column.name
        for column in unbounded.columns[projected:]
        if column.name.startswith(ORDERING_KEY_PREFIX)
    ]
    tied = _tied_at_the_cut(rows, cut, projected)
    null_rows = _rows_with_a_null_key(parsed, rows[offset:cut], projected, payload)
    cases: list[str] = []
    if tied is not None:
        positions, answers = tied
        payload["tied_at_the_cut"] = {
            "positions": list(positions[:ROWS_IN_EVIDENCE]),
            "tied_rows": len(positions),
            "distinct_projected_answers": answers,
            "rows": [
                json_row(rows[position][:projected]) for position in positions[:ROWS_IN_EVIDENCE]
            ],
        }
        if answers > 1:
            cases.append("tie-at-the-cut")
    if null_rows:
        cases.append("null-first")
    payload["case"] = ", ".join(cases) if cases else None
    if not cases:
        return _quiet(name, payload, applicable=True)
    shown = [rows[position] for position in (tied[0] if tied and tied[1] > 1 else ())]
    return _fired(name, payload, shown or null_rows)


def _tied_at_the_cut(
    rows: Sequence[tuple[object, ...]], cut: int, projected: int
) -> tuple[tuple[int, ...], int] | None:
    """The run of rows tied with the cut on every ordering key, and how many answers it holds.

    ``None`` when there is no row after the cut, or when the rows on either side of it
    differ in a key: then the cut is the ordering's own and not this tool's to question.
    """
    if len(rows) <= cut or cut < 1:
        return None
    at_the_cut = typed_row(rows[cut][projected:])
    if typed_row(rows[cut - 1][projected:]) != at_the_cut:
        return None
    first = cut - 1
    while first > 0 and typed_row(rows[first - 1][projected:]) == at_the_cut:
        first -= 1
    last = cut
    while last + 1 < len(rows) and typed_row(rows[last + 1][projected:]) == at_the_cut:
        last += 1
    positions = tuple(range(first, last + 1))
    answers = {typed_row(rows[position][:projected]) for position in positions}
    return positions, len(answers)


def _rows_with_a_null_key(
    parsed: ParsedStatement,
    returned: Sequence[tuple[object, ...]],
    projected: int,
    payload: Json,
) -> tuple[tuple[object, ...], ...]:
    """The returned rows whose null in a nulls-first key is why they were returned."""
    keys: list[Json] = []
    with_a_null: list[tuple[object, ...]] = []
    for index, key in enumerate(parsed.ordering):
        first = _nulls_first_in_effect(key)
        nulls = [row for row in returned if row[projected + index] is None]
        keys.append(
            {
                "key": key.expression,
                "direction": "desc" if key.descending else "asc",
                "nulls": key.nulls,
                "nulls_first_in_effect": first,
                "returned_rows_null_in_this_key": len(nulls),
                "fires": bool(first and nulls),
            }
        )
        if first and nulls:
            with_a_null.extend(nulls)
    payload["ordering_keys"] = keys
    if with_a_null:
        payload["returned_rows_with_a_null_key"] = [
            json_row(row[:projected]) for row in with_a_null[:ROWS_IN_EVIDENCE]
        ]
    return tuple(with_a_null)


def _shuffle_json(parsed: ParsedStatement, shuffled: ShuffledCopies) -> Json:
    """What the shuffle covered of this statement's tables, and what it did not.

    A table is covered when the rerun reads the copy instead of it, which is a property of
    the name the statement wrote: the copies were made under the caller's own names, so
    this is a membership test and never a match on the tail of one.
    """
    copied = set(shuffled.copied)
    return {
        "seed": shuffled.seed,
        "row_limit": shuffled.row_limit,
        "tables": [table.text for table in parsed.tables],
        "tables_not_shuffled": [table.text for table in parsed.tables if table not in copied],
        "tables_skipped_for_size": {name.text: rows for name, rows in shuffled.skipped.items()},
        "tables_not_reached_by_a_copy": {
            name.text: reason for name, reason in shuffled.unreachable.items()
        },
    }


def _planner_statistics_json(backend: Backend, parsed: ParsedStatement) -> Json:
    """What the plans of this statement's reruns were chosen from, taken at smell time.

    Recorded whether the smell fires or not, because a quiet run and a fired one over the
    same data are only comparable when both say it: the copies are read with the plan the
    planner chose from these, and an autoanalyze between two runs is enough to change it.

    A backend that will not answer leaves the block empty. These are context beside a rerun
    and never the reason a question fails, and the rerun's own refusal is already recorded.
    """
    try:
        return planner_statistics_json(backend.planner_statistics(parsed.tables))
    except BackendRefused:
        return {}


def not_a_function_of_the_data(
    parsed: ParsedStatement,
    backend: Backend,
    baseline: ExecutionResult,
    *,
    settings: SmellSettings,
    shuffled: ShuffledCopies | None = None,
    no_shuffle: str = "",
) -> Smell:
    """The same rows in another order, or read another way, give another answer.

    With neither shuffled copies nor a plan variant nothing was rerun, so the smell is not
    applicable and says why rather than reading as a statement that survived a rerun.
    """
    name = NOT_A_FUNCTION_OF_THE_DATA
    rule = parsed.replay_rule
    payload: Json = {
        "rule": rule.value,
        "baseline_result_hash": result_digest(baseline, settings.serialization),
        "baseline_result": result_json(baseline, settings.serialization, bound=ROWS_IN_EVIDENCE),
        "planner_statistics": _planner_statistics_json(backend, parsed),
    }
    reruns: list[_Rerun] = []
    if shuffled is None:
        payload["shuffled_copies"] = {"run": False, "reason": no_shuffle or NO_SHUFFLE}
    else:
        payload["shuffle"] = _shuffle_json(parsed, shuffled)
        _rerun(
            payload,
            "shuffled_copies",
            reruns,
            lambda: backend.execute_shuffled(
                parsed.sql, statement_timeout_seconds=settings.statement_timeout_seconds
            ),
            settings,
            baseline,
            rule,
        )
    if settings.plan_variant:
        _rerun(
            payload,
            "plan_variant",
            reruns,
            lambda: backend.execute_plan_variant(
                parsed.sql, statement_timeout_seconds=settings.statement_timeout_seconds
            ),
            settings,
            baseline,
            rule,
        )
    else:
        payload["plan_variant"] = {"run": False, "reason": "the plan variant was not asked for"}
    asked = shuffled is not None or settings.plan_variant
    differing = [rerun for rerun in reruns if rerun.differs]
    if not differing:
        return _quiet(name, payload, applicable=asked)
    floats = _float_order_only(
        baseline,
        [rerun.result for rerun in differing],
        backend.order_sensitive_aggregate_types(),
    )
    if floats is not None:
        payload["float_cells"] = floats
        payload["significant_digits"] = SIGNIFICANT_DIGITS
        return _fired(FLOAT_AGGREGATE_ORDER, payload, differing[0].result.rows)
    return _fired(name, payload, differing[0].result.rows)


@dataclass(frozen=True)
class _Rerun:
    """One rerun of a gold, and whether it answered differently."""

    variant: str
    result: ExecutionResult
    differs: bool


def _rerun(
    payload: Json,
    variant: str,
    reruns: list[_Rerun],
    execute: Callable[[], ExecutionResult],
    settings: SmellSettings,
    baseline: ExecutionResult,
    rule: ReplayRule,
) -> None:
    """One rerun of the gold, its verdict against the baseline, and both written down."""
    try:
        result = execute()
    except BackendRefused as refused:
        payload[variant] = {"run": True, "error": refused.detail, "step": refused.step}
        return
    verdict = compare_results(baseline, result, rule=rule, serialization=settings.serialization)
    differs = verdict.result is ComparabilityResult.NOT_EQUAL
    payload[variant] = {
        "run": True,
        "verdict": verdict.result.value,
        "differs": differs,
        "result_hash": result_digest(result, settings.serialization),
        "result": result_json(result, settings.serialization, bound=ROWS_IN_EVIDENCE),
    }
    reruns.append(_Rerun(variant=variant, result=result, differs=differs))


def _significant(value: Decimal, digits: int) -> Decimal:
    """One value at that many significant digits, so two of them can be compared there."""
    with localcontext() as context:
        context.prec = digits
        return +value


def _float_order_only(
    baseline: ExecutionResult,
    reruns: Sequence[ExecutionResult],
    order_sensitive_types: frozenset[str],
) -> list[Json] | None:
    """The differing cells when every one of them is a float agreeing to six digits.

    ``None`` as soon as anything else differs: a row count, a projection, a value of any
    other type, or two floats that disagree in the digits that were compared. The rows
    are paired by position, which is what a difference of summation order leaves intact
    and what a difference in the rows themselves does not.

    ``order_sensitive_types`` is the engine's own answer to which result types an aggregate
    adds up in the order the rows arrive in, and it is the whole of what makes a column
    eligible here. An engine that answers with nothing forgives nothing: every changed cell
    is then a statement that depends on the storage order and is reported as one.
    """
    cells: list[Json] = []
    floats = {
        index
        for index, column in enumerate(baseline.columns)
        if column.declared_type in order_sensitive_types
    }
    if not floats:
        return None
    for rerun in reruns:
        if rerun.columns != baseline.columns or len(rerun.rows) != len(baseline.rows):
            return None
        for position, (left, right) in enumerate(zip(baseline.rows, rerun.rows, strict=True)):
            for index, (one, other) in enumerate(zip(left, right, strict=True)):
                if typed_value(one) == typed_value(other):
                    continue
                if (
                    index not in floats
                    or not isinstance(one, Decimal)
                    or not isinstance(other, Decimal)
                ):
                    return None
                if not one.is_finite() or not other.is_finite():
                    return None
                if _significant(one, SIGNIFICANT_DIGITS) != _significant(other, SIGNIFICANT_DIGITS):
                    return None
                cells.append(
                    {
                        "row": position,
                        "column": baseline.columns[index].name,
                        "declared_type": baseline.columns[index].declared_type,
                        "baseline": format(one, "f"),
                        "rerun": format(other, "f"),
                    }
                )
    return cells if cells else None


def duplicate_full_row(parsed: ParsedStatement, baseline: ExecutionResult) -> Smell:
    """Whether the gold's own result returns the same whole row more than once.

    The one smell that asks the database nothing. Every other probe here runs a second
    statement to find out what the first one depended on; this one reads the result that
    is already in hand, because the hazard is in the answer and not in how it was reached.

    The rows are counted through ``typed_row``, the keys a comparison counts them under, so
    two rows are the same row here exactly when the comparator would hold them equal: a
    TEXT ``1`` and an INTEGER ``1`` stay two rows.

    A fire needs a repeat that was seen, which is why the bound is read afterwards and not
    before: a result cut at a row cap can hold a repeat, and the repeat it holds is real,
    while its silence proves nothing about the rows beyond the cut. A statement that states
    DISTINCT cannot repeat a row at all, and a result of one row has nothing to repeat;
    both are not applicable rather than quiet.
    """
    counted: Counter[tuple[tuple[str, object], ...]] = Counter()
    first_seen: dict[tuple[tuple[str, object], ...], tuple[int, tuple[object, ...]]] = {}
    for index, row in enumerate(baseline.rows):
        key = typed_row(row)
        counted[key] += 1
        first_seen.setdefault(key, (index, row))
    repeated = [(key, count) for key, count in counted.items() if count > 1]
    payload: Json = {
        "rows": len(baseline.rows),
        "distinct_rows": len(counted),
        "repeated_rows": len(repeated),
        "largest_repeat": max((count for _, count in repeated), default=1),
        "result_bounded": baseline.truncated,
        "distinct_stated": parsed.distinct,
    }
    if repeated:
        order = sorted(repeated, key=lambda pair: (-pair[1], first_seen[pair[0]][0]))
        shown = order[:ROWS_IN_EVIDENCE]
        payload["repeats_of_the_rows_shown"] = [count for _, count in shown]
        return _fired(DUPLICATE_FULL_ROW, payload, [first_seen[key][1] for key, _ in shown])
    if parsed.distinct:
        payload["not_applicable"] = "the statement states DISTINCT, so it cannot repeat a row"
        return _quiet(DUPLICATE_FULL_ROW, payload, applicable=False)
    if baseline.truncated:
        payload["not_applicable"] = (
            "the result is bounded, so a repeat beyond the bound would not have been seen"
        )
        return _quiet(DUPLICATE_FULL_ROW, payload, applicable=False)
    if len(baseline.rows) < 2:
        payload["not_applicable"] = "a result of fewer than two rows has nothing to repeat"
        return _quiet(DUPLICATE_FULL_ROW, payload, applicable=False)
    return _quiet(DUPLICATE_FULL_ROW, payload, applicable=True)


def direction_against_question(
    parsed: ParsedStatement,
    backend: Backend,
    baseline: ExecutionResult,
    *,
    settings: SmellSettings,
    question: QuestionText,
) -> Smell:
    """The question asks for one end of the list and the statement orders to the other."""
    del backend  # the question and the parse decide this one; the data is not asked
    name = DIRECTION_AGAINST_QUESTION
    if not parsed.ordering or not parsed.limit_stated:
        return _quiet(
            name,
            {"reason": "the statement states no top level ORDER BY with a LIMIT"},
            applicable=False,
        )
    words = set(_WORD.findall(f"{question.question} {question.evidence}".lower()))
    maxima = [word for word in MAX_INTENT if word in words]
    minima = [word for word in MIN_INTENT if word in words]
    first = parsed.ordering[0]
    against_maximum = bool(maxima) and not minima and not first.descending
    against_minimum = bool(minima) and not maxima and first.descending
    contradiction = (
        "maximum intent with an ascending first key"
        if against_maximum
        else ("minimum intent with a descending first key" if against_minimum else None)
    )
    payload: Json = {
        "maximum_intent_words": maxima,
        "minimum_intent_words": minima,
        "order_by": _order_by_text(parsed.ordering),
        "first_key_direction": "desc" if first.descending else "asc",
        "contradiction": contradiction,
        "gold_result": result_json(baseline, settings.serialization, bound=ROWS_IN_EVIDENCE),
    }
    if contradiction is None:
        return _quiet(name, payload, applicable=True)
    return _fired(name, payload, baseline.rows)


def _order_by_text(ordering: Sequence[OrderingKey]) -> str:
    """The ORDER BY as the statement wrote it, so the evidence can name what it read."""
    return ", ".join(
        f"{key.expression} {'DESC' if key.descending else 'ASC'}"
        + ("" if key.nulls == "default" else f" NULLS {key.nulls.upper()}")
        for key in ordering
    )


def all_smells(
    parsed: ParsedStatement,
    backend: Backend,
    baseline: ExecutionResult,
    *,
    settings: SmellSettings,
    question: QuestionText,
    shuffled: ShuffledCopies | None = None,
    no_shuffle: str = "",
) -> tuple[Smell, ...]:
    """Every smell that release 1 runs on one gold, in the order it runs them.

    The experimental one is absent unless it was asked for, so a summary that counts the
    smells it was given never counts an experiment as a finding. ``no_shuffle`` is the
    run's one reason there are no shuffled copies, repeated into every smell that needed
    them, so each question's evidence says why rather than only that.
    """
    found = [
        ordering_over_numeric_text(parsed, backend, baseline, settings=settings),
        arbitrary_cut(
            parsed, backend, baseline, settings=settings, shuffled=shuffled, no_shuffle=no_shuffle
        ),
        not_a_function_of_the_data(
            parsed, backend, baseline, settings=settings, shuffled=shuffled, no_shuffle=no_shuffle
        ),
        duplicate_full_row(parsed, baseline),
    ]
    if settings.experimental_s2:
        found.append(
            direction_against_question(
                parsed, backend, baseline, settings=settings, question=question
            )
        )
    return tuple(found)


def probe_meanings() -> Mapping[str, str]:
    """What each probe would mean if it fired, by name, as its evidence states it.

    The same strings ``_evidence`` writes into every probe's ``means``. They are read from
    here by a page that lists the probes a run can make before it has made any -- a method
    page has no ``smells.json`` to read them out of -- and the mapping is returned as a copy
    so that what a reader is shown and what a probe writes cannot come apart.
    """
    return dict(_MEANS)


def smells_json(found: Sequence[Smell]) -> Json:
    """Every smell that ran on one gold, as one document a maintainer reads."""
    return {
        "format": SMELLS_FORMAT,
        "reading": SMELLS_READING,
        "smells": [
            {
                "name": smell.name,
                "fired": smell.fired,
                "applicable": smell.applicable,
                "evidence": smell.evidence,
                "counterexample_rows": [json_row(row) for row in smell.counterexample_rows],
            }
            for smell in found
        ],
    }


SMELLS_FORMAT = "attestql/audit/smells/2"
SMELLS_READING = (
    "A smell is a mechanical reason to read this gold statement again. It is a heuristic: "
    "it does not state that the statement is wrong, and a maintainer decides."
)


__all__ = [
    "ARBITRARY_CUT",
    "DEFAULT_SHUFFLE_ROW_LIMIT",
    "DEFAULT_SHUFFLE_SEED",
    "DIRECTION_AGAINST_QUESTION",
    "DUPLICATE_FULL_ROW",
    "FLOAT_AGGREGATE_ORDER",
    "MAX_INTENT",
    "MIN_INTENT",
    "NOT_A_FUNCTION_OF_THE_DATA",
    "NO_SHUFFLE",
    "NUMERIC_TEXT",
    "ORDERING_OVER_NUMERIC_TEXT",
    "ROWS_IN_EVIDENCE",
    "SIGNIFICANT_DIGITS",
    "SMELLS_FORMAT",
    "SMELLS_READING",
    "SMELL_NAMES",
    "QuestionText",
    "Smell",
    "SmellSettings",
    "all_smells",
    "arbitrary_cut",
    "direction_against_question",
    "duplicate_full_row",
    "not_a_function_of_the_data",
    "ordering_over_numeric_text",
    "probe_meanings",
    "smells_json",
]
