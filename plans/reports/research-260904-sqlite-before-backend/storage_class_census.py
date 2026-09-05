"""Task 4a: per-column storage class census, one table scan per table via
conditional aggregation (avoids one scan per column). Read-only URI connections.
"""

import json
import sqlite3
import time

D = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data/zip/minidev/MINIDEV/dev_databases"
W = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/work-rd"

with open(f"{W}/schema.json") as f:
    SCHEMA = json.load(f)

CLASSES = ["null", "integer", "real", "text", "blob"]


def main():
    results = []  # list of dict per column
    t0 = time.time()
    for db_id, info in SCHEMA.items():
        con = sqlite3.connect(f"file:{D}/{db_id}/{db_id}.sqlite?mode=ro", uri=True)
        cur = con.cursor()
        for table, cols in info["columns"].items():
            col_names = [c[0] for c in cols]
            if not col_names:
                continue
            parts = []
            for c in col_names:
                for cls in CLASSES:
                    parts.append(f"SUM(CASE WHEN typeof(\"{c}\")='{cls}' THEN 1 ELSE 0 END)")
            # table/column names come from this db's own schema.json, not from
            # untrusted input; this script only ever runs SELECT.
            sql = f'SELECT COUNT(*), {", ".join(parts)} FROM "{table}"'  # noqa: S608
            cur.execute(sql)
            row = cur.fetchone()
            total = row[0]
            idx = 1
            for c, decltype in cols:
                counts = dict(zip(CLASSES, row[idx : idx + 5], strict=True))
                idx += 5
                non_null_classes = [k for k in CLASSES if k != "null" and counts[k] > 0]
                results.append(
                    {
                        "db_id": db_id,
                        "table": table,
                        "column": c,
                        "decltype": decltype,
                        "total": total,
                        "counts": counts,
                        "distinct_nonnull_classes": len(non_null_classes),
                    }
                )
        con.close()
        print(db_id, "done", f"{time.time() - t0:.1f}s")

    with open(f"{W}/storage_class_census.json", "w") as f:
        json.dump(results, f, indent=1)

    mixed = [r for r in results if r["distinct_nonnull_classes"] > 1]
    print(f"total columns: {len(results)}  mixed (>1 non-null storage class): {len(mixed)}")
    mixed_sorted = sorted(mixed, key=lambda r: -r["total"])
    with open(f"{W}/storage_class_mixed.json", "w") as f:
        json.dump(mixed_sorted, f, indent=1)
    for r in mixed_sorted[:10]:
        print(r["db_id"], r["table"], r["column"], r["decltype"], r["counts"])


if __name__ == "__main__":
    main()
