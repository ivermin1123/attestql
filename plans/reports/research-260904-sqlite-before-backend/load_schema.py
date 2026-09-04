"""Schema census over the 11 Mini-Dev SQLite databases, read-only.

Writes $W/schema.json: {db_id: {"tables": [...], "columns": {table: [(name, decltype), ...]}}}
"""

import json
import sqlite3

D = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data/zip/minidev/MINIDEV/dev_databases"
W = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rd"

DBS = [
    "california_schools",
    "card_games",
    "codebase_community",
    "debit_card_specializing",
    "european_football_2",
    "financial",
    "formula_1",
    "student_club",
    "superhero",
    "thrombosis_prediction",
    "toxicology",
]


def connect_ro(db_id):
    path = f"{D}/{db_id}/{db_id}.sqlite"
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def main():
    out = {}
    for db_id in DBS:
        con = connect_ro(db_id)
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        columns = {}
        for t in tables:
            cur.execute(f'PRAGMA table_info("{t}")')
            columns[t] = [(r[1], r[2]) for r in cur.fetchall()]  # (name, decltype)
        out[db_id] = {"tables": tables, "columns": columns}
        con.close()
    with open(f"{W}/schema.json", "w") as f:
        json.dump(out, f, indent=1)
    for db_id, info in out.items():
        print(db_id, len(info["tables"]), "tables")


if __name__ == "__main__":
    main()
