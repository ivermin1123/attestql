"""Comparing a gold statement with a second statement on one database.

The rule is read off the gold, not chosen: R-ORD when the gold carries a top-level ORDER
BY, R-SET when it does not. The ordering both records are recorded under is the gold's,
so the comparison is between two answers and not between two ORDER BY clauses; each
statement's own ordering is kept beside the verdict as data, because a disagreement about
ordering is half of what a reader is being shown.

The second statement is supplied and never generated: a model's prediction, an upstream
correction, a human's fix. What comes back is a verdict, the records both executions
produced, and the rows each result holds that the other does not.

NOT_EQUAL says that these two statements disagree on this data under this rule. It does
not say which of them is wrong, and nothing in this module decides that. NOT_COMPARABLE
says a precondition differed and names it, which is not a disagreement at all.

The two projections are compared by position and declared type, so a prediction that names
its columns differently is not a disagreement either. The names both results carry are
written into the counterexample when they differ, beside the verdict rather than under it,
because a reader who sees two column lists side by side should be told they were not what
was compared instead of working it out.

``bird_ex`` is computed beside the verdict because a counterexample has to state what the
benchmark's own evaluator would say about the same two results. It answers for the
benchmark, so it reads the cells the way the benchmark's driver hands them over: psycopg2
builds a Python float for a float column, this tool loads the exact decimal the server
printed for one, and the reading undoes that before its two sets are built. Where the two
answers disagree, that difference is the point, and ``mechanism`` names what makes it: the
same distinct rows at different counts, the same values at different declared types, the
same multiset in another order, or one result a cut of the other. A NOT_EQUAL that is none
of those is ``other`` and is never guessed at.

``test_suite_ex`` is the second public reading of the same two results, recorded beside
``bird_ex`` for the reason ``bird_ex`` is recorded beside the verdict: a reader comparing
readings should not have to run one. It keeps row multiplicity, keeps row order when the
gold orders, and still admits a projection whose columns are in another order, so it
refuses rows the benchmark credits without refusing every one of them.

Which side failed is carried out of here rather than reconstructed. A question that ends in
an error ended in the gold, in the prediction, or in the run around both, and a reader told
only the server's message cannot tell those apart; ``sided`` names the side of every refusal
raised under it, and the innermost name wins, so a fixture measured while a statement is
being recorded stays the run's.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from attestql.audit.backend import Backend, BackendRefused
from attestql.audit.fixture import fixture_digest
from attestql.audit.statements import (
    CHECKS_PASSED,
    VALIDATOR_VERSION,
    OrderingKey,
    ParsedStatement,
    StatementRefused,
)
from attestql.evidence.build import ExecutionIdentity, build_evidence_record
from attestql.evidence.record import EvidenceRecord
from attestql.evidence.render import (
    Json,
    RowDifference,
    record_json,
    result_digest,
    result_json,
    row_difference,
    row_difference_json,
    statement_source_json,
    write_json,
)
from attestql.evidence.replay import (
    ComparabilityResult,
    ComparabilityVerdict,
    compare_r_ord,
    compare_r_set,
)
from attestql.evidence.serialize import SerializationDescriptor, UnsupportedValue, typed_row
from attestql.evidence.types import (
    FixtureDigest,
    QuestionMetadata,
    ReplayRule,
    SessionSettings,
    SortKey,
    StatementSource,
)
from attestql.kernel.types import (
    ExecutionResult,
    ProjectedColumnWidth,
    ResultWidthProof,
    ValidatedStatement,
    admit,
)

DEFAULT_STATEMENT_TIMEOUT_SECONDS = 30
"""How long one statement of an audit may run. Set on the session and read back."""

WIDTH_POLICY_VERSION = "audit:observed-widths"
"""What the width proof on an audited statement is, named for what it is.

A real proof bounds a projection before the statement is sent, from a policy over a known
schema. An audit runs arbitrary benchmark SQL against a database it did not design and has
no such policy, so the widths are measured from the rendering of what came back. The
record does not carry this: ADR-0013 dropped ``policy_version`` because a version naming a
measurement taken after the fact states nothing a reader can rely on. It exists because
``admit`` requires a proof, and it is named so that nothing here reads as one."""

COUNTEREXAMPLE_FORMAT = "attestql/audit/counterexample/1"
"""What the layout below is, for a reader who opens one of these files.

It moves when a key a reader was reading changes meaning or leaves, and not when one is
added: everything written under this version so far is still there and still means what it
meant, and a document that gained a field is not one an existing reader has to be told
about. That is what was done when ``mechanism`` was added beside ``bird_ex`` and it is what
is done here for ``test_suite_ex``."""

COUNTEREXAMPLE_FILE = "counterexample.json"
GOLD_RECORD_FILE = "evidence-gold.json"
SECOND_RECORD_FILE = "evidence-second.json"

BIRD_EX_METHOD = (
    "set(second_rows) == set(gold_rows), float4/float8 cells as Python float as psycopg2 "
    "returns them, numeric as Decimal"
)
BIRD_EX_SOURCE = "https://github.com/bird-bench/mini_dev/blob/main/evaluation/evaluation_ex.py"

TEST_SUITE_EX_METHOD = (
    "result_eq: equal row counts and equal column counts, each row unordered as a quick "
    "rejection, then the two equal as a list when the gold text holds ORDER BY and as a "
    "multiset otherwise, under some permutation of the columns; DISTINCT is not stripped "
    "and re-executed, and the cells are PostgreSQL's as psycopg2 returns them"
)
TEST_SUITE_EX_SOURCE = (
    "ruiqi-zhong/test-suite-sql-eval, exec_eval.py, result_eq, at commit 48cb78ec: "
    "https://github.com/ruiqi-zhong/test-suite-sql-eval/blob/"
    "48cb78ecf7f610620206283846c76751b18a1326/exec_eval.py"
)

PSYCOPG2_FLOAT_TYPES = ("float4", "float8")
"""The declared types psycopg2 hands BIRD as a Python float rather than as a Decimal."""

VERDICT_READING = (
    "NOT_EQUAL states that these two statements disagree on this data under this rule. It "
    "does not state which of them is wrong."
)

SIDE_GOLD = "gold"
SIDE_PREDICTION = "prediction"
SIDE_RUN = "run"
"""Which side of a question a refusal came from. The second statement of an audit is a
prediction, which is the word an error line uses; ``run`` is everything around the two,
the fixture measurement above all, and is what a refusal nothing narrower named is."""

MECHANISM_MULTIPLICITY = "multiplicity"
MECHANISM_TYPE = "type"
MECHANISM_ORDER = "order"
MECHANISM_TRUNCATION = "truncation"
MECHANISM_OTHER = "other"

MECHANISM_CLASSES: tuple[str, ...] = (
    MECHANISM_MULTIPLICITY,
    MECHANISM_TYPE,
    MECHANISM_ORDER,
    MECHANISM_TRUNCATION,
    MECHANISM_OTHER,
)
"""Every class a NOT_EQUAL is put in, in the order a summary counts them."""

MECHANISM_READING = (
    "The class states what makes these two results unequal under this rule, read off the "
    "two results and nothing else. It does not state which of the two statements is wrong."
)

PROJECTION_NAMES_READING = (
    "The two statements name their result columns differently. A projection is compared by "
    "position and declared type, so these names did not decide the verdict. They are part of "
    "the canonical rendering each result is hashed under, so the two result hashes differ "
    "with them."
)
"""What a reader is told when a counterexample carries two projections named differently:
what those names are, and what they are not."""


@dataclass(frozen=True)
class BirdEx:
    """What BIRD's own evaluator would say about the same two results.

    ``calculate_ex`` is ``1`` when ``set(predicted) == set(gold)`` over the row tuples and
    ``0`` otherwise. It is computed here rather than imported so that what this tool claims
    the benchmark says is visible in one expression, and it is recorded beside the verdict
    so a reader can see the two answers side by side.

    The row tuples are the ones psycopg2 would have built, which is why the cells are read
    off the results and not off the rows alone: a float column reaches BIRD as a Python
    float and a numeric one as a Decimal, and Python holds those two unequal on every value
    a double does not hold exactly. Nothing else about the reading is this tool's, a NaN
    included: two of them are unequal here because they are unequal in the set the benchmark
    builds.
    """

    value: int
    equal: bool
    gold_rows: int
    second_rows: int
    gold_distinct_rows: int
    second_distinct_rows: int


@dataclass(frozen=True)
class TestSuiteEx:
    """What the test-suite evaluator would say about the same two results.

    ``result_eq`` of Zhong, Yu and Klein 2020 is the other reading a benchmark reader is
    likely to hold against a verdict, and the one that refuses part of what BIRD credits
    rather than all of it or none: it keeps row multiplicity, it keeps row order when the
    gold orders, and it still admits a projection whose columns came back in another order.
    It is computed here rather than imported for the reason ``bird_ex`` is, and recorded
    beside it so that a reader sees the three answers at once.

    Two things the evaluator does are not mirrored, and they are why this is a reading of
    that rule and not that rule. It strips DISTINCT from both statements' texts and
    re-executes them, which is what exposes a join's raw fanout; these rows are already
    fetched and no fetched result recovers what DISTINCT removed, so DISTINCT stays applied
    here and this answers for the evaluator only where neither statement holds one. And it
    runs on SQLite, while these rows come from PostgreSQL through this tool's loader, so
    the cells are the ones ``bird_ex`` reads: what psycopg2 would have handed the benchmark
    over. The two readings recorded here differ in their rule and never in their cells.

    ``order_matters`` is the evaluator's own test for an ordered gold, ``order by`` anywhere
    in the lowercased gold text, which is not this tool's R-ORD: a gold that orders inside a
    subquery is ordered there and R-SET here, and the field is recorded because that is a
    difference a reader of two disagreeing readings will want to see.
    """

    value: int
    equal: bool
    order_matters: bool
    gold_rows: int
    second_rows: int
    gold_columns: int
    second_columns: int


@dataclass(frozen=True)
class Mechanism:
    """What makes a NOT_EQUAL a NOT_EQUAL, in one class and the observations behind it.

    The rows are keyed the way the comparison keys them, so what is counted here is what
    the verdict was decided on and not a second reading of the same results. The classes
    are tried in the order the fields below are read, because more than one can hold at
    once and the first is the one that would still hold if the others were repaired: two
    results at different declared types are unequal at every count and every order, so
    that is what they are, and only results whose types agree are asked about counts.

    ``multiplicity`` is the same distinct rows at different counts, ``type`` the same
    positions at different declared types, ``order`` one multiset in two orders under
    R-ORD, and ``truncation`` one result that is the first rows of the other. Anything
    else is ``other``: the two results hold different values, and this says so rather
    than naming a mechanism nothing here observed.
    """

    classification: str
    gold_types: tuple[str, ...]
    second_types: tuple[str, ...]
    multiset_equal: bool
    set_equal: bool
    order_equal: bool
    shorter_result_is_a_prefix: bool


@dataclass(frozen=True)
class RecordedStatement:
    """One statement, executed once, with what was read off it and what it produced.

    The gold-only mode of ADR-0013 point 2 has no second statement to compare with and
    still has to hold both: the smells read the parse, and the directory a fired smell
    writes holds the record. The parse is the one the caller handed in, returned beside
    the record so that what ran and what came of it are one object.
    """

    parsed: ParsedStatement
    record: EvidenceRecord


@dataclass(frozen=True)
class Comparison:
    """One gold and one second statement, executed and compared, with the evidence."""

    question: QuestionMetadata
    replay_rule: ReplayRule
    verdict: ComparabilityVerdict
    gold: EvidenceRecord
    second: EvidenceRecord
    gold_result_hash: str
    second_result_hash: str
    differing_rows: RowDifference
    gold_ordering: tuple[OrderingKey, ...]
    second_ordering: tuple[OrderingKey, ...]
    bird_ex: BirdEx
    test_suite_ex: TestSuiteEx
    mechanism: Mechanism | None
    """Why the two disagree, on a NOT_EQUAL and on nothing else: an EQUAL has no
    disagreement to explain and a NOT_COMPARABLE names its own preconditions."""


class SideFailed(Exception):
    """A question that could not be answered, and the side of it that could not.

    "The gold does not run on this database" and "the prediction does not run on this
    database" are two findings about a benchmark and not one, and an error line carrying
    only the server's message left a reader to open the record to tell them apart. The
    refusal itself is kept unchanged in ``failed``: what stopped the question is still the
    parser's or the server's own words, and ``side`` is what is added in front of them.
    """

    def __init__(self, side: str, failed: Exception) -> None:
        super().__init__(str(failed))
        self.side = side
        self.failed = failed


@contextmanager
def sided(side: str) -> Generator[None]:
    """Name the side of every refusal raised inside, unless one inside already named its own.

    The inner name wins because it is the narrower observation: a fixture measured while a
    statement is being recorded is the run's measurement and not that statement's, and a
    caller that wraps the whole recording in ``gold`` is saying which statement it handed
    over, not that everything underneath belongs to it.
    """
    try:
        yield
    except SideFailed:
        raise
    except (StatementRefused, BackendRefused, UnsupportedValue) as failed:
        raise SideFailed(side, failed) from failed


def _as_a_driver_float(value: object) -> object:
    """One cell of a float column as psycopg2 would have built it.

    This tool loads such a cell as the exact decimal the server printed, so that is what is
    converted; the decimal was built from that rendering, so ``float`` of it is the double
    ``float`` of the text gives. A NULL is None on both sides of the conversion, and a
    backend that already returned a Python float returned what the driver would have.
    """
    return float(value) if isinstance(value, Decimal) else value


def _as_psycopg2_returns_them(result: ExecutionResult) -> list[tuple[object, ...]]:
    """One result's rows as the driver BIRD runs would have handed them over.

    psycopg2 builds a Python float for a ``float4`` or a ``float8`` and a Decimal for a
    ``numeric``, and Python compares the two exactly, so 0.1 the double is not 0.1 the
    decimal. This tool loads a float column as the decimal the server printed instead,
    which is what typed replay needs and what a reading of the benchmark has to undo before
    it answers for the benchmark. Every other declared type is left as it came back.
    """
    floats = tuple(column.pg_type in PSYCOPG2_FLOAT_TYPES for column in result.columns)
    if not any(floats):
        return list(result.rows)
    return [
        tuple(
            _as_a_driver_float(value) if is_float else value
            for value, is_float in zip(row, floats, strict=True)
        )
        for row in result.rows
    ]


def bird_ex(gold: ExecutionResult, second: ExecutionResult) -> BirdEx:
    """BIRD's execution-accuracy check over the two results, read as its own driver reads them."""
    gold_rows = _as_psycopg2_returns_them(gold)
    second_rows = _as_psycopg2_returns_them(second)
    equal = set(second_rows) == set(gold_rows)
    return BirdEx(
        value=1 if equal else 0,
        equal=equal,
        gold_rows=len(gold_rows),
        second_rows=len(second_rows),
        gold_distinct_rows=len(set(gold_rows)),
        second_distinct_rows=len(set(second_rows)),
    )


def bird_ex_json(measured: BirdEx) -> Json:
    return {
        "value": measured.value,
        "equal": measured.equal,
        "method": BIRD_EX_METHOD,
        "source": BIRD_EX_SOURCE,
        "gold_rows": measured.gold_rows,
        "second_rows": measured.second_rows,
        "gold_distinct_rows": measured.gold_distinct_rows,
        "second_distinct_rows": measured.second_distinct_rows,
    }


def _unordered_row(row: tuple[object, ...]) -> tuple[object, ...]:
    """One row with its cells sorted, under the evaluator's own key and its own ties.

    ``str(x) + str(type(x))`` sorts cells of any two types against each other and keeps a
    string apart from the number that prints the same way. It is the evaluator's key and
    it is reproduced rather than improved: what is being answered is what that rule says.
    """
    return tuple(sorted(row, key=lambda cell: str(cell) + str(type(cell))))


def _quick_rejection(
    gold: list[tuple[object, ...]], second: list[tuple[object, ...]], *, order_matters: bool
) -> bool:
    """Whether the two results still might be equal once every row is unordered.

    Two results equal under some permutation of the columns hold the same bag of unordered
    rows, so a pair that fails this cannot be saved by any permutation and is rejected
    before one is built. Under an ordering gold the two lists have to agree row by row;
    otherwise the evaluator compares them as sets here, having already counted the rows,
    and leaves the multiplicities to the multiset comparison under a permutation.
    """
    left = [_unordered_row(row) for row in gold]
    right = [_unordered_row(row) for row in second]
    return left == right if order_matters else set(left) == set(right)


def _admitted_column_permutations(
    gold: list[tuple[object, ...]], second: list[tuple[object, ...]], columns: int
) -> Iterator[tuple[int, ...]]:
    """Every column order of the second result the evaluator's constraint lets it try.

    A column of the second result can stand where a column of the gold stands only if every
    value it holds is a value that gold column holds: under a permutation that makes the two
    results equal, every permuted row is a gold row, so every cell of it is. A permutation
    the constraint drops could not have made them equal, which is why dropping it costs
    nothing and is what keeps a wide result from being a search over every column order.

    The evaluator builds the same constraint from twenty rows drawn at random, and skips it
    entirely at three columns or fewer. Every row is read here instead: it is deterministic,
    where a random draw is not, and it can only remove permutations that could not have made
    the two results equal, so what the search answers is still the evaluator's answer.

    An order that takes one column twice is not built at all, where the evaluator builds it
    and drops it on the next line. That is its own rule applied one column earlier, and it
    is what keeps a wide result from being a walk over every column raised to itself: eight
    columns are forty thousand orders here and sixteen million there.
    """
    gold_holds = [{row[column] for row in gold} for column in range(columns)]
    second_holds = [{row[column] for row in second} for column in range(columns)]
    admitted = [
        tuple(
            candidate
            for candidate in range(columns)
            if second_holds[candidate] <= gold_holds[column]
        )
        for column in range(columns)
    ]

    def extend(taken: tuple[int, ...]) -> Iterator[tuple[int, ...]]:
        if len(taken) == columns:
            yield taken
            return
        for candidate in admitted[len(taken)]:
            if candidate not in taken:
                yield from extend((*taken, candidate))

    return extend(())


def _result_eq(
    gold: list[tuple[object, ...]], second: list[tuple[object, ...]], *, order_matters: bool
) -> bool:
    """``result_eq`` over two results already fetched, its early exits and its search kept.

    Both empty is equal. Then the row counts have to agree, which is where multiplicity is
    kept and where a prediction that dropped a duplicate row is refused, and the column
    counts have to agree. The unordered rows are the quick rejection, and what survives it
    goes to the search: the two are equal if under some admitted column order they are the
    same list, when the gold orders, or the same multiset otherwise.
    """
    if not gold and not second:
        return True
    if len(gold) != len(second):
        return False
    columns = len(gold[0])
    if len(second[0]) != columns:
        return False
    if not _quick_rejection(gold, second, order_matters=order_matters):
        return False
    counted = Counter(gold)

    def agrees(permutation: tuple[int, ...]) -> bool:
        permuted = [tuple(row[at] for at in permutation) for row in second]
        return permuted == gold if order_matters else Counter(permuted) == counted

    return any(
        agrees(permutation) for permutation in _admitted_column_permutations(gold, second, columns)
    )


def test_suite_ex(gold: ExecutionResult, second: ExecutionResult, gold_sql: str) -> TestSuiteEx:
    """The test-suite evaluator's check over the two results, on the cells BIRD's driver builds.

    The gold's text is read for one thing and by the evaluator's own test for it: ``order
    by`` anywhere in it, lowercased, is what makes the two results compared in order. The
    cells are ``bird_ex``'s, so the two readings recorded beside a verdict differ in their
    rule alone.
    """
    gold_rows = _as_psycopg2_returns_them(gold)
    second_rows = _as_psycopg2_returns_them(second)
    order_matters = "order by" in gold_sql.lower()
    equal = _result_eq(gold_rows, second_rows, order_matters=order_matters)
    return TestSuiteEx(
        value=1 if equal else 0,
        equal=equal,
        order_matters=order_matters,
        gold_rows=len(gold_rows),
        second_rows=len(second_rows),
        gold_columns=len(gold.columns),
        second_columns=len(second.columns),
    )


def test_suite_ex_json(measured: TestSuiteEx) -> Json:
    return {
        "value": measured.value,
        "equal": measured.equal,
        "method": TEST_SUITE_EX_METHOD,
        "source": TEST_SUITE_EX_SOURCE,
        "order_matters": measured.order_matters,
        "gold_rows": measured.gold_rows,
        "second_rows": measured.second_rows,
        "gold_columns": measured.gold_columns,
        "second_columns": measured.second_columns,
    }


def _is_a_prefix(gold: Sequence[object], second: Sequence[object]) -> bool:
    """Whether the shorter of two row sequences is the first rows of the longer one.

    What a LIMIT over the same rows in the same order produces, and the one shape of
    disagreement a reader repairs by looking at a bound rather than at the answer. The
    shorter side has to hold a row: a result that came back empty is not a cut of the
    other one, it is a different answer, and calling it a truncation would name a
    mechanism where there is only an absence.
    """
    if len(gold) == len(second):
        return False
    shorter, longer = (gold, second) if len(gold) < len(second) else (second, gold)
    return bool(shorter) and list(shorter) == list(longer[: len(shorter)])


def mechanism(gold: ExecutionResult, second: ExecutionResult, rule: ReplayRule) -> Mechanism:
    """Why these two results are not equal under this rule, read off the two of them."""
    gold_types = tuple(column.pg_type for column in gold.columns)
    second_types = tuple(column.pg_type for column in second.columns)
    gold_rows = [typed_row(row) for row in gold.rows]
    second_rows = [typed_row(row) for row in second.rows]
    multiset_equal = Counter(gold_rows) == Counter(second_rows)
    set_equal = set(gold_rows) == set(second_rows)
    order_equal = gold_rows == second_rows
    prefix = _is_a_prefix(gold_rows, second_rows)
    if gold_types != second_types:
        classification = MECHANISM_TYPE
    elif multiset_equal:
        classification = (
            MECHANISM_ORDER if rule is ReplayRule.R_ORD and not order_equal else MECHANISM_OTHER
        )
    elif set_equal:
        classification = MECHANISM_MULTIPLICITY
    elif prefix:
        classification = MECHANISM_TRUNCATION
    else:
        classification = MECHANISM_OTHER
    return Mechanism(
        classification=classification,
        gold_types=gold_types,
        second_types=second_types,
        multiset_equal=multiset_equal,
        set_equal=set_equal,
        order_equal=order_equal,
        shorter_result_is_a_prefix=prefix,
    )


def mechanism_json(found: Mechanism) -> Json:
    return {
        "class": found.classification,
        "gold_types": list(found.gold_types),
        "second_types": list(found.second_types),
        "multiset_equal": found.multiset_equal,
        "set_equal": found.set_equal,
        "order_equal": found.order_equal,
        "shorter_result_is_a_prefix": found.shorter_result_is_a_prefix,
        "reading": MECHANISM_READING,
    }


def width_proof(
    result: ExecutionResult, serialization: SerializationDescriptor
) -> ResultWidthProof:
    """The widths this execution measured, which is not the same thing as a width proof."""
    widths: list[ProjectedColumnWidth] = []
    for index, column in enumerate(result.columns):
        widest = _widest(result, index, serialization)
        widths.append(
            ProjectedColumnWidth(
                name=column.name,
                pg_type=column.pg_type,
                max_encoded_bytes=widest,
                max_decoded_bytes=widest,
            )
        )
    return ResultWidthProof(columns=tuple(widths), policy_version=WIDTH_POLICY_VERSION)


def _widest(result: ExecutionResult, index: int, serialization: SerializationDescriptor) -> int:
    cells = (
        len(serialization.render_value(row[index]).encode(serialization.encoding))
        for row in result.rows
    )
    return max((*cells, 1))


def _admitted(
    parsed: ParsedStatement, result: ExecutionResult, serialization: SerializationDescriptor
) -> ValidatedStatement:
    return admit(
        parsed.sql, (), VALIDATOR_VERSION, CHECKS_PASSED, width_proof(result, serialization)
    )


def _execute_and_record(
    parsed: ParsedStatement,
    *,
    question: QuestionMetadata,
    question_set_version: str,
    statement_source: StatementSource,
    backend: Backend,
    serialization: SerializationDescriptor,
    identity: ExecutionIdentity,
    settings: SessionSettings,
    fixture: FixtureDigest,
    rule: ReplayRule,
    ordering: tuple[SortKey, ...],
    rerun_instruction: str,
    data_as_of: datetime,
    statement_timeout_seconds: int,
) -> EvidenceRecord:
    """Run one statement and state, in one record, everything that produced its rows.

    The rule and the ordering are arguments and not read off ``parsed``, because the two
    sides of a comparison are recorded under the gold's rule and the gold's ordering; a
    record that stated its own would make the comparison a comparison of rules.
    """
    result = backend.execute(parsed.sql, statement_timeout_seconds=statement_timeout_seconds)
    if not result.columns:
        # PostgreSQL accepts a bare SELECT and answers it with one row of no columns, which
        # is what a model that predicted nothing at all reaches this with. There is no
        # projection to compare, to record or to hash, so it is refused the way a statement
        # that did not parse is.
        raise StatementRefused(
            "the statement projects no column, so there is no answer to record or compare"
        )
    # The clock is this process's, taken the moment the rows came back: the interface a
    # second engine implements does not promise a server clock, and a record says when the
    # audit ran the statement rather than what the server thought the time was.
    executed_at = datetime.now(UTC)
    return build_evidence_record(
        question_as_asked=question.question_text,
        question=question,
        question_set_version=question_set_version,
        statement_source=statement_source,
        statement=_admitted(parsed, result, serialization),
        bound_parameters=(),
        result=result,
        identity=identity,
        session_settings_in_force=settings,
        canonical_ordering=ordering,
        serialization=serialization,
        replay_rule=rule,
        fixture=fixture,
        data_as_of=data_as_of,
        executed_at=executed_at,
        rerun_instruction=rerun_instruction,
    )


def record_statement(
    *,
    question: QuestionMetadata,
    question_set_version: str,
    statement_source: StatementSource,
    parsed: ParsedStatement,
    backend: Backend,
    serialization: SerializationDescriptor,
    session_settings: SessionSettings,
    run_id: str,
    directory: Path,
    data_as_of: datetime,
    statement_timeout_seconds: int = DEFAULT_STATEMENT_TIMEOUT_SECONDS,
    with_content_digests: bool = False,
    source_digest: str = "",
) -> RecordedStatement:
    """Execute one statement under its own rule and record it, with nothing to compare.

    The statement arrives parsed and the session arrives read, because a caller that
    audits a whole question file holds both before the first statement runs: the tables to
    measure are read off the parses, and one read of the session is what every record of
    that run states.

    Raises ``SideFailed`` naming ``run`` when what the measurement around the statement
    needs is refused, and otherwise raises the statement's own refusal for the caller to
    name the side of: this records one statement and does not know whose it is.
    """
    rule = parsed.replay_rule
    with sided(SIDE_RUN):
        fixture = fixture_digest(
            backend,
            parsed.tables,
            directory=directory,
            with_content_digests=with_content_digests,
            source_digest=source_digest,
        )
        identity = ExecutionIdentity(
            effective_database_role=backend.effective_database_role(), run_id=run_id
        )
        rerun_instruction = _rerun_instruction(backend.identity(), rule)
    record = _execute_and_record(
        parsed,
        question=question,
        question_set_version=question_set_version,
        statement_source=statement_source,
        backend=backend,
        serialization=serialization,
        identity=identity,
        settings=session_settings,
        fixture=fixture,
        rule=rule,
        ordering=parsed.sort_keys if rule is ReplayRule.R_ORD else (),
        rerun_instruction=rerun_instruction,
        data_as_of=data_as_of,
        statement_timeout_seconds=statement_timeout_seconds,
    )
    return RecordedStatement(parsed=parsed, record=record)


def _rerun_instruction(backend_identity: str, rule: ReplayRule) -> str:
    return (
        f"re-run this statement read-only against {backend_identity} under the session "
        "settings and over the data this record's fixture digest names, and compare the "
        f"two results under {rule.value}"
    )


def compare_statements(
    *,
    question: QuestionMetadata,
    question_set_version: str,
    gold_parsed: ParsedStatement,
    gold_source: StatementSource,
    second_parsed: ParsedStatement,
    second_source: StatementSource,
    backend: Backend,
    serialization: SerializationDescriptor,
    session_settings: SessionSettings,
    run_id: str,
    directory: Path,
    data_as_of: datetime,
    statement_timeout_seconds: int = DEFAULT_STATEMENT_TIMEOUT_SECONDS,
    with_content_digests: bool = False,
    source_digest: str = "",
) -> Comparison:
    """Execute both statements on one backend and compare them under the gold's rule.

    Both statements arrive parsed and the session arrives read, for the reason
    ``record_statement`` states.

    Raises ``SideFailed`` naming the side that stopped the comparison: the gold, the
    prediction, or the run around them when it is the measurement both are recorded under.
    """
    rule = gold_parsed.replay_rule
    ordering = gold_parsed.sort_keys if rule is ReplayRule.R_ORD else ()
    tables = (*gold_parsed.tables, *second_parsed.tables)
    with sided(SIDE_RUN):
        fixture = fixture_digest(
            backend,
            tables,
            directory=directory,
            with_content_digests=with_content_digests,
            source_digest=source_digest,
        )
        identity = ExecutionIdentity(
            effective_database_role=backend.effective_database_role(), run_id=run_id
        )
        rerun = _rerun_instruction(backend.identity(), rule)

    def record_of(parsed: ParsedStatement, source: StatementSource) -> EvidenceRecord:
        return _execute_and_record(
            parsed,
            question=question,
            question_set_version=question_set_version,
            statement_source=source,
            backend=backend,
            serialization=serialization,
            identity=identity,
            settings=session_settings,
            fixture=fixture,
            rule=rule,
            ordering=ordering,
            rerun_instruction=rerun,
            data_as_of=data_as_of,
            statement_timeout_seconds=statement_timeout_seconds,
        )

    with sided(SIDE_GOLD):
        gold_record = record_of(gold_parsed, gold_source)
    with sided(SIDE_PREDICTION):
        second_record = record_of(second_parsed, second_source)
    verdict = (
        compare_r_ord(gold_record, second_record)
        if rule is ReplayRule.R_ORD
        else compare_r_set(gold_record, second_record)
    )
    return Comparison(
        question=question,
        replay_rule=rule,
        verdict=verdict,
        gold=gold_record,
        second=second_record,
        gold_result_hash=result_digest(gold_record.result, serialization),
        second_result_hash=result_digest(second_record.result, serialization),
        differing_rows=row_difference(gold_record.result.rows, second_record.result.rows),
        gold_ordering=gold_parsed.ordering,
        second_ordering=second_parsed.ordering,
        bird_ex=bird_ex(gold_record.result, second_record.result),
        test_suite_ex=test_suite_ex(gold_record.result, second_record.result, gold_parsed.sql),
        mechanism=(
            mechanism(gold_record.result, second_record.result, rule)
            if verdict.result is ComparabilityResult.NOT_EQUAL
            else None
        ),
    )


def _ordering_json(ordering: Sequence[OrderingKey]) -> list[Json]:
    return [
        {"expression": key.expression, "descending": key.descending, "nulls": key.nulls}
        for key in ordering
    ]


def _fixture_json(fixture: FixtureDigest) -> Json:
    return {
        "schema_digest": fixture.schema_digest,
        "row_counts": dict(fixture.row_counts),
        "content_digests": dict(fixture.content_digests),
        "source_file_sha256": fixture.source_file_sha256,
    }


def _projection_names(result: ExecutionResult) -> tuple[str, ...]:
    """The column names in order, as the execution reported them: evidence, never a verdict.

    Read here and nowhere in the comparison. ``replay`` matches a projection by position and
    declared type, so this is the one place a name is looked at at all.
    """
    return tuple(column.name for column in result.columns)


def _projection_names_note(comparison: Comparison) -> Json:
    """The column names of both results, when the two projections disagree on them.

    Empty when they agree, which is what keeps the note worth reading: a field present on
    every counterexample is one a reader stops seeing, and there is nothing to say when
    both statements named the same columns.
    """
    gold = _projection_names(comparison.gold.result)
    second = _projection_names(comparison.second.result)
    if gold == second:
        return {}
    return {
        "projection_names_differ": {
            "gold": list(gold),
            "second": list(second),
            "reading": PROJECTION_NAMES_READING,
        }
    }


def counterexample_json(comparison: Comparison) -> Json:
    """The comparison as one document: the verdict, both sides, and what differs."""
    serialization = comparison.gold.serialization
    return {
        "format": COUNTEREXAMPLE_FORMAT,
        "question": {
            "question_id": comparison.question.question_id,
            "question_set": comparison.question.question_set,
            "question_text": comparison.question.question_text,
            "evidence_text": comparison.question.evidence_text,
        },
        "question_set_version": comparison.gold.question_set_version,
        "sources": {
            "gold": statement_source_json(comparison.gold.statement_source),
            "second": statement_source_json(comparison.second.statement_source),
        },
        "replay_rule": comparison.replay_rule.value,
        "verdict": {
            "result": comparison.verdict.result.value,
            "mismatched": list(comparison.verdict.mismatched),
            "reading": VERDICT_READING,
        },
        **_projection_names_note(comparison),
        "bird_ex": bird_ex_json(comparison.bird_ex),
        "test_suite_ex": test_suite_ex_json(comparison.test_suite_ex),
        "mechanism": (
            None if comparison.mechanism is None else mechanism_json(comparison.mechanism)
        ),
        "gold": {
            "executed_sql": comparison.gold.executed_sql,
            "own_ordering": _ordering_json(comparison.gold_ordering),
            "result": result_json(comparison.gold.result, serialization),
            "record": GOLD_RECORD_FILE,
        },
        "second": {
            "executed_sql": comparison.second.executed_sql,
            "own_ordering": _ordering_json(comparison.second_ordering),
            "result": result_json(comparison.second.result, comparison.second.serialization),
            "record": SECOND_RECORD_FILE,
        },
        "canonical_ordering": [
            {"column": key.column, "descending": key.descending}
            for key in comparison.gold.canonical_ordering
        ],
        "differing_rows": row_difference_json(
            comparison.differing_rows,
            left_key="in_gold_not_in_second",
            right_key="in_second_not_in_gold",
        ),
        "result_hashes": {
            "gold": comparison.gold_result_hash,
            "second": comparison.second_result_hash,
        },
        "backend_identity": comparison.gold.backend_identity_at_checkout,
        "fixture": _fixture_json(comparison.gold.fixture),
        "run_id": comparison.gold.run_id,
    }


def write_comparison(comparison: Comparison, directory: Path) -> None:
    """The counterexample and both evidence records, as three files in one directory."""
    write_json(directory / COUNTEREXAMPLE_FILE, counterexample_json(comparison))
    write_json(directory / GOLD_RECORD_FILE, record_json(comparison.gold))
    write_json(directory / SECOND_RECORD_FILE, record_json(comparison.second))


__all__ = [
    "BIRD_EX_METHOD",
    "COUNTEREXAMPLE_FILE",
    "COUNTEREXAMPLE_FORMAT",
    "DEFAULT_STATEMENT_TIMEOUT_SECONDS",
    "GOLD_RECORD_FILE",
    "MECHANISM_CLASSES",
    "MECHANISM_MULTIPLICITY",
    "MECHANISM_ORDER",
    "MECHANISM_OTHER",
    "MECHANISM_READING",
    "MECHANISM_TRUNCATION",
    "MECHANISM_TYPE",
    "PROJECTION_NAMES_READING",
    "SECOND_RECORD_FILE",
    "SIDE_GOLD",
    "SIDE_PREDICTION",
    "SIDE_RUN",
    "TEST_SUITE_EX_METHOD",
    "TEST_SUITE_EX_SOURCE",
    "VERDICT_READING",
    "WIDTH_POLICY_VERSION",
    "BirdEx",
    "Comparison",
    "Mechanism",
    "RecordedStatement",
    "SideFailed",
    "TestSuiteEx",
    "bird_ex",
    "bird_ex_json",
    "compare_statements",
    "counterexample_json",
    "mechanism",
    "mechanism_json",
    "record_statement",
    "sided",
    "test_suite_ex",
    "test_suite_ex_json",
    "width_proof",
    "write_comparison",
]
