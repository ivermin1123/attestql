"""Tasks 4c (REGEXP), 4d (read-only/WAL), 4e (query_only), 4f (per-connection
state and float rendering). Self-contained, prints everything; also writes a
JSON of the results for the report to quote numbers from.
"""

import json
import os
import re as _re
import shutil
import sqlite3
import sys

D = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data/zip/minidev/MINIDEV/dev_databases"
W = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rd"

sys.path.insert(0, f"{W}/scripts")
from load_golds import SETS, load  # noqa: E402

out = {}


def section(name):
    print(f"\n=== {name} ===")


# --- 4c: REGEXP ---
section("4c REGEXP")
con = sqlite3.connect(":memory:")
con.execute("CREATE TABLE t(a)")
con.execute("INSERT INTO t VALUES ('abc')")
try:
    con.execute("SELECT * FROM t WHERE a REGEXP 'a'").fetchall()
    out["regexp_no_func_error"] = None
except sqlite3.OperationalError as e:
    out["regexp_no_func_error"] = str(e)
print("no REGEXP registered:", out["regexp_no_func_error"])

con.create_function(
    "REGEXP", 2, lambda pattern, value: _re.search(pattern, value or "") is not None
)
rows = con.execute("SELECT * FROM t WHERE a REGEXP 'a'").fetchall()
out["regexp_after_register"] = rows
print("after create_function:", rows)
con.close()

# grep gold texts for REGEXP usage
regexp_golds = {}
for set_name in SETS:
    hits = [r["question_id"] for r in load(set_name) if "REGEXP" in r["SQL"].upper()]
    regexp_golds[set_name] = hits
out["regexp_golds"] = regexp_golds
print("golds using REGEXP:", regexp_golds)

# --- 4d: read-only opening, WAL ---
section("4d read-only / WAL")
copy_dir = f"{W}/wal_copy"
os.makedirs(copy_dir, exist_ok=True)
src = f"{D}/student_club/student_club.sqlite"
dst = f"{copy_dir}/student_club.sqlite"
shutil.copyfile(src, dst)

# switch the copy to WAL (writable connection, our own copy only)
con = sqlite3.connect(dst)
con.execute("PRAGMA journal_mode=WAL")
con.execute("CREATE TABLE IF NOT EXISTS _touch(x)")
con.execute("INSERT INTO _touch VALUES (1)")
con.commit()
con.close()
out["wal_files_present"] = sorted(os.listdir(copy_dir))
print("files after WAL switch + write:", out["wal_files_present"])

# open read-only while -wal/-shm exist
try:
    ro = sqlite3.connect(f"file:{dst}?mode=ro", uri=True)
    row = ro.execute("SELECT COUNT(*) FROM _touch").fetchone()
    out["ro_open_with_wal_present"] = {"ok": True, "row": row}
    ro.close()
except Exception as e:
    out["ro_open_with_wal_present"] = {"ok": False, "error": str(e)}
print("mode=ro with -wal/-shm present:", out["ro_open_with_wal_present"])

# remove -wal/-shm, try again (absent case)
for suffix in ("-wal", "-shm"):
    p = dst + suffix
    if os.path.exists(p):
        os.remove(p)
try:
    ro2 = sqlite3.connect(f"file:{dst}?mode=ro", uri=True)
    row2 = ro2.execute("SELECT COUNT(*) FROM _touch").fetchone()
    jm = ro2.execute("PRAGMA journal_mode").fetchone()
    out["ro_open_with_wal_absent"] = {"ok": True, "row": row2, "journal_mode_reported": jm}
    ro2.close()
except Exception as e:
    out["ro_open_with_wal_absent"] = {"ok": False, "error": str(e)}
print("mode=ro with -wal/-shm removed:", out["ro_open_with_wal_absent"])

# immutable=1 case (re-copy fresh WAL state first)
shutil.copyfile(src, dst)
con = sqlite3.connect(dst)
con.execute("PRAGMA journal_mode=WAL")
con.execute("CREATE TABLE IF NOT EXISTS _touch(x)")
con.execute("INSERT INTO _touch VALUES (1)")
con.commit()
con.close()
try:
    imm = sqlite3.connect(f"file:{dst}?mode=ro&immutable=1", uri=True)
    row3 = imm.execute("SELECT COUNT(*) FROM _touch").fetchone()
    out["ro_immutable_with_wal_present"] = {"ok": True, "row": row3}
    imm.close()
except Exception as e:
    out["ro_immutable_with_wal_present"] = {"ok": False, "error": str(e)}
print("mode=ro&immutable=1 with -wal/-shm present:", out["ro_immutable_with_wal_present"])

# are any of the 11 shipped databases in WAL mode?
wal_modes = {}
for db_id in os.listdir(D):
    path = f"{D}/{db_id}/{db_id}.sqlite"
    if not os.path.isfile(path):
        continue
    ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    jm = ro.execute("PRAGMA journal_mode").fetchone()[0]
    wal_modes[db_id] = jm
    ro.close()
out["shipped_db_journal_modes"] = wal_modes
print("journal_mode of the 11 shipped databases:", wal_modes)

# --- 4e: query_only ---
section("4e PRAGMA query_only")
con = sqlite3.connect(dst)  # our own WAL copy, writable connection
con.execute("PRAGMA query_only=1")
try:
    con.execute("INSERT INTO _touch VALUES (2)")
    out["query_only_insert_error"] = None
except sqlite3.OperationalError as e:
    out["query_only_insert_error"] = str(e)
print("INSERT under query_only=1:", out["query_only_insert_error"])
con.close()

try:
    ro3 = sqlite3.connect(f"file:{dst}?mode=ro", uri=True)
    ro3.execute("INSERT INTO _touch VALUES (3)")
    out["mode_ro_insert_error"] = None
except sqlite3.OperationalError as e:
    out["mode_ro_insert_error"] = str(e)
print("INSERT over mode=ro:", out["mode_ro_insert_error"])
ro3.close()

# --- 4f: per-connection state ---
section("4f per-connection state")
con = sqlite3.connect(":memory:")
out["sqlite_version"] = con.execute("SELECT sqlite_version()").fetchone()[0]
out["compile_options"] = [r[0] for r in con.execute("PRAGMA compile_options").fetchall()]
out["collation_list"] = [r[1] for r in con.execute("PRAGMA collation_list").fetchall()]
out["encoding"] = con.execute("PRAGMA encoding").fetchone()[0]
out["case_sensitive_like_default"] = None  # no pragma readback; demonstrated below
print("sqlite_version():", out["sqlite_version"])
print("compile_options:", out["compile_options"])
print("collation_list:", out["collation_list"])
print("encoding:", out["encoding"])

# case_sensitive_like demonstration
con.execute("CREATE TABLE t(a)")
con.execute("INSERT INTO t VALUES ('ABC')")
default_like = con.execute("SELECT * FROM t WHERE a LIKE 'abc'").fetchall()
con.execute("PRAGMA case_sensitive_like=1")
cs_like = con.execute("SELECT * FROM t WHERE a LIKE 'abc'").fetchall()
out["like_default_matches_case"] = default_like
out["like_case_sensitive_matches_case"] = cs_like
print("LIKE 'abc' vs 'ABC', default:", default_like, "case_sensitive_like=1:", cs_like)
con.close()

# reverse_unordered_selects demonstration on a real unordered gold
mdv = load("minidev_hf")
unordered = [
    r for r in mdv if "ORDER BY" not in r["SQL"].upper() and "LIMIT" not in r["SQL"].upper()
]
demo = None
for r in unordered:
    path = f"{D}/{r['db_id']}/{r['db_id']}.sqlite"
    try:
        c1 = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows_off = c1.execute(r["SQL"]).fetchall()
        c1.close()
        c2 = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        c2.execute("PRAGMA reverse_unordered_selects=1")
        rows_on = c2.execute(r["SQL"]).fetchall()
        c2.close()
        if len(rows_off) > 1 and rows_off != rows_on and sorted(rows_off) == sorted(rows_on):
            demo = {
                "question_id": r["question_id"],
                "db_id": r["db_id"],
                "first_row_off": rows_off[0],
                "first_row_on": rows_on[0],
                "n_rows": len(rows_off),
            }
            break
    except Exception as e:
        print(f"skipping q{r['question_id']} ({r['db_id']}): {e}")
out["reverse_unordered_selects_demo"] = demo
print("reverse_unordered_selects order-change demo:", demo)

# float rendering: CAST(x AS TEXT)/printf 15 sig digits vs Python shortest repr
con = sqlite3.connect(":memory:")
value = 1.0 / 3.0
row = con.execute("SELECT CAST(? AS TEXT), printf('%!.20g', ?)", (value, value)).fetchone()
out["float_repr_demo"] = {"python_repr": repr(value), "sqlite_cast_text": row[0]}
print("Python repr:", repr(value), " SQLite CAST(x AS TEXT):", row[0])
con.close()

with open(f"{W}/measurements_c_to_f.json", "w") as f:
    json.dump(out, f, indent=1, default=str)
