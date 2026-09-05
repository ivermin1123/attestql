"""DateStyle: ISO timestamptz loads fine; a non-ISO DateStyle crashes psycopg's loader."""

import json
from pathlib import Path

import psycopg

W = Path(__file__).resolve().parent
DSN = "host=127.0.0.1 port=5499 dbname=bird user=auditor"
SQL = "SELECT '2012-08-30 12:00:00+00'::timestamptz"

out = {}
with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
    cur.execute("BEGIN READ ONLY")
    cur.execute(SQL)
    row = cur.fetchone()
    out["DateStyle=ISO, MDY (default)"] = {
        "wire_format": cur.pgresult.fformat(0),
        "value": str(row[0]),
    }
    cur.execute("ROLLBACK")

with psycopg.connect(DSN, autocommit=True) as conn, conn.cursor() as cur:
    cur.execute("BEGIN READ ONLY")
    cur.execute("SET LOCAL DateStyle = 'German, DMY'")
    try:
        cur.execute(SQL)
        row = cur.fetchone()
        out["DateStyle=German, DMY"] = {
            "wire_format": cur.pgresult.fformat(0),
            "value": str(row[0]),
        }
    except NotImplementedError as exc:
        out["DateStyle=German, DMY"] = {"error": f"{type(exc).__name__}: {exc}"}
    cur.execute("ROLLBACK")

(W / "datestyle_timestamptz_demo.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
