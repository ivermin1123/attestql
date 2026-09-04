"""One-shot demonstrations for several session-settable GUCs (task R-B item 1).

Each factor: a SELECT run twice under two values of one setting, over the
auditor role's own read-only transaction (or postgres for a DDL-needing demo).
One JSON file is written per factor into this directory.
"""

import json
from pathlib import Path

import psycopg

W = Path(__file__).resolve().parent
AUDITOR = "host=127.0.0.1 port=5499 dbname=bird user=auditor"
SUPERUSER = "host=127.0.0.1 port=5499 dbname=bird user=postgres"


def two_values(dsn, setting, value_a, value_b, sql):
    out = {}
    for _label, value in (("a", value_a), ("b", value_b)):
        with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("BEGIN READ ONLY")
            quoted = value.replace("'", "''")
            cur.execute(f"SET LOCAL {setting} = '{quoted}'")
            try:
                cur.execute(sql)
                row = cur.fetchone()
                out[f"{setting}={value}"] = [str(v) for v in row] if row else []
            except (psycopg.Error, NotImplementedError) as exc:
                out[f"{setting}={value}"] = f"{type(exc).__name__}: {exc}"
            cur.execute("ROLLBACK")
    return out


def write(name, payload):
    (W / f"{name}.json").write_text(json.dumps(payload, indent=1))
    print(name, payload)


write(
    "timezone_demo",
    two_values(
        AUDITOR,
        "TimeZone",
        "UTC",
        "America/New_York",
        "SELECT '2020-06-01 12:00:00+00'::timestamptz",
    ),
)
write(
    "extra_float_digits_demo",
    two_values(AUDITOR, "extra_float_digits", "0", "3", "SELECT 1.0::float8 / 3.0::float8"),
)
write(
    "intervalstyle_demo",
    two_values(
        AUDITOR, "IntervalStyle", "postgres", "iso_8601", "SELECT interval '1 year 2 months 3 days'"
    ),
)
write(
    "bytea_output_demo",
    two_values(AUDITOR, "bytea_output", "hex", "escape", r"SELECT '\xDEADBEEF'::bytea"),
)
write(
    "lc_time_demo",
    two_values(
        AUDITOR, "lc_time", "en_US.utf8", "C", "SELECT to_char('2024-03-04'::date, 'Day, Month')"
    ),
)
write(
    "lc_numeric_demo",
    two_values(
        AUDITOR, "lc_numeric", "en_US.utf8", "C", "SELECT to_char(1234.5::numeric, 'FM999G999D99')"
    ),
)
write(
    "lc_monetary_demo",
    two_values(
        AUDITOR, "lc_monetary", "en_US.utf8", "C", "SELECT to_char(1234.5::numeric, 'L999999.99')"
    ),
)
write(
    "client_encoding_demo",
    two_values(AUDITOR, "client_encoding", "UTF8", "LATIN1", "SELECT 'A' || chr(233)"),
)
write(
    "standard_conforming_strings_demo",
    two_values(AUDITOR, "standard_conforming_strings", "on", "off", r"SELECT 'a\nb'"),
)
write(
    "backslash_quote_demo",
    two_values(AUDITOR, "backslash_quote", "safe_encoding", "on", r"SELECT E'\\'"),
)
write(
    "array_nulls_demo",
    two_values(AUDITOR, "array_nulls", "on", "off", "SELECT '{1,NULL,3}'::int[]"),
)
