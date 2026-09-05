"""Does a SQLite aggregate over REALs change when the same rows are read in another order?

The evidence behind the SQLite backend answering ``order_sensitive_aggregate_types`` with
nothing, and behind the probe comparison in the SQLite measurement report. It asks the
question three ways and prints what it found:

1. the sandbox's own fifteen amounts, summed whole and per category, in four read orders;
2. 28,000 random multisets of 4 to 32 doubles spanning twenty orders of magnitude, each
   summed in four to six read orders;
3. the two shapes where SQLite's integer accumulator is involved: a mix of INTEGER and REAL
   values, and integers whose running total overflows a signed 64-bit accumulator.

    python plans/reports/session-260904-autonomous-run/b4-sqlite-float-sums/float_sum_order.py

Every database is in memory, nothing is downloaded, and no benchmark data is read: the values
are generated here from a stated seed, so two runs of this script ask the same question. The
SQLite library version is printed first, because the answer holds from 3.43.0, where the
Kahan-Babuska-Neumaier compensation was added to ``sum``, ``total`` and ``avg``.
"""

from __future__ import annotations

import random
import sqlite3
import sys

SEEDS = (7, 11)
"""The two seeds the random multisets are drawn from, so a run reproduces another."""

TRIALS = (20_000, 8_000)
"""How many multisets each seed draws. 28,000 in total, which is what the report states."""

SIZES = ((4, 5, 6), (8, 16, 32))
"""How many values a multiset holds, per seed: small enough to be summed many ways, and
large enough that a compensation carried across many additions would have to hold."""

EXPONENTS = ((-3, 18), (-20, 20))
"""The decimal exponent range each seed spans. A summation whose order matters shows it
where the magnitudes differ, so the values are spread rather than clustered."""

ORDERS = ("rowid", "rowid DESC", "{value}", "{value} DESC")
"""The read orders every multiset is summed in, with the value column left to be filled in.
A subquery with its own ORDER BY is what hands the aggregate its rows in a stated order,
which is the whole of the question."""

GROUPED_ORDERS = ("g, v", "g DESC, v DESC")
"""Two more orders for the larger multisets, over a column that ties many rows together."""

SANDBOX_AMOUNTS: tuple[tuple[str, float], ...] = (
    ("field", 1000000.0),
    ("field", 0.11),
    ("field", 0.22),
    ("field", 0.33),
    ("field", 0.44),
    ("field", 0.55),
    ("field", 0.66),
    ("field", 0.77),
    ("field", 0.88),
    ("depot", 0.19),
    ("depot", 0.28),
    ("depot", 0.37),
    ("yard", 0.46),
    ("yard", 0.55),
    ("yard", 0.64),
)
"""``spend`` of ``tools/audit-sandbox-sqlite/fixture.sql``: one large amount and fourteen
small ones, which is the shape a naive running double loses digits on."""

MIXED: tuple[tuple[str, tuple[object, ...]], ...] = (
    ("an integer above 2^53 with a fraction after it", (9007199254740993, 1, 0.5)),
    ("two halves of 2^53 and a fraction", (4503599627370497, 4503599627370497, 0.5)),
    ("a fraction between two large integers", (10000000000000001, 3, 0.5)),
    ("integers whose running total overflows int64", (2**62, 2**62, -(2**63 - 1), 3)),
    ("the same overflow with a REAL in the multiset", (2**62, 2**62, -(2**63 - 1), 0.5)),
)
"""The shapes that reach SQLite's integer accumulator, which switches to the float one when
a value is not an integer or when the running total overflows. Where the switch happens is
a property of the order, so these are where an order-dependent total would be if there was
one to find."""


def totals(
    connection: sqlite3.Connection, values: tuple[object, ...], orders: tuple[str, ...]
) -> set[str]:
    """``sum`` over those values in each of those read orders, as the text of each answer.

    An error is one of the answers and is kept as its message: ``sum`` over integers whose
    running total overflows raises rather than returning, and a set holding both an answer
    and an error is an order that mattered, reported as what it was.
    """
    connection.execute("DROP TABLE IF EXISTS t")
    connection.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, g INTEGER, v)")
    connection.executemany(
        "INSERT INTO t VALUES(?, ?, ?)",
        [(index, index % 10, value) for index, value in enumerate(values)],
    )
    answers: set[str] = set()
    for order in orders:
        try:
            row = connection.execute(
                f"SELECT sum(v), typeof(sum(v)) FROM (SELECT v FROM t ORDER BY {order})"  # noqa: S608
            ).fetchone()
        except sqlite3.Error as refused:
            answers.add(f"error: {refused}")
        else:
            answers.add(f"{row[0]!r} {row[1]}")
    return answers


def the_sandbox_amounts(connection: sqlite3.Connection) -> None:
    """The fixture's own fifteen amounts, whole and per category, in the four read orders."""
    connection.execute("DROP TABLE IF EXISTS spend")
    connection.execute("CREATE TABLE spend(id INTEGER PRIMARY KEY, category TEXT, spent REAL)")
    connection.executemany(
        "INSERT INTO spend VALUES(?, ?, ?)",
        [(index, category, spent) for index, (category, spent) in enumerate(SANDBOX_AMOUNTS)],
    )
    orders = tuple(order.format(value="spent") for order in ORDERS)
    for aggregate in ("sum(spent)", "total(spent)", "avg(spent)"):
        whole = {
            repr(
                connection.execute(
                    f"SELECT {aggregate} FROM (SELECT spent FROM spend ORDER BY {order})"  # noqa: S608
                ).fetchone()[0]
            )
            for order in orders
        }
        grouped = {
            repr(
                connection.execute(
                    f"SELECT group_concat(t) FROM (SELECT category, {aggregate} AS t "  # noqa: S608
                    f"FROM (SELECT * FROM spend ORDER BY {order}) "
                    "GROUP BY category ORDER BY category)"
                ).fetchone()[0]
            )
            for order in orders
        }
        print(f"  {aggregate:14} whole {sorted(whole)}")
        print(f"  {aggregate:14} per category {sorted(grouped)}")


def the_random_multisets(connection: sqlite3.Connection) -> int:
    """Every drawn multiset summed in every read order; how many gave more than one answer."""
    differing = 0
    for seed, trials, sizes, exponents in zip(SEEDS, TRIALS, SIZES, EXPONENTS, strict=True):
        draw = random.Random(seed)  # noqa: S311  # a stated seed, so a run reproduces
        orders = tuple(order.format(value="v") for order in ORDERS)
        if sizes != SIZES[0]:
            orders += GROUPED_ORDERS
        found = 0
        for _ in range(trials):
            values = tuple(
                draw.choice((1, -1)) * draw.uniform(1, 10) * 10 ** draw.randint(*exponents)
                for _ in range(draw.choice(sizes))
            )
            answers = totals(connection, values, orders)
            if len(answers) > 1:
                found += 1
                if found <= 3:
                    print(f"  seed {seed}: {sorted(answers)} from {values}")
        print(
            f"  seed {seed}: {trials} multisets of {sizes} over 1e{exponents[0]}..1e{exponents[1]}, "
            f"{len(orders)} read orders each, {found} gave more than one answer"
        )
        differing += found
    return differing


def the_integer_accumulator(connection: sqlite3.Connection) -> None:
    """The five shapes that reach the integer accumulator, and what each order answered."""
    for what, values in MIXED:
        answers = totals(connection, values, tuple(o.format(value="v") for o in ORDERS))
        print(f"  {what}: {sorted(answers)}")


def main() -> int:
    """Ask the three questions and say whether any read order changed a total."""
    print(f"sqlite {sqlite3.sqlite_version}, python {sys.version.split()[0]}")
    print(
        f"compensated summation is SQLite 3.43.0 and later: "
        f"{tuple(int(part) for part in sqlite3.sqlite_version.split('.')) >= (3, 43, 0)}"
    )
    connection = sqlite3.connect(":memory:")
    try:
        print("the sandbox's fifteen amounts, four read orders:")
        the_sandbox_amounts(connection)
        print("random multisets:")
        differing = the_random_multisets(connection)
        print("the integer accumulator:")
        the_integer_accumulator(connection)
    finally:
        connection.close()
    print(f"multisets whose total depended on the read order: {differing} of {sum(TRIALS)}")
    return 0 if differing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
