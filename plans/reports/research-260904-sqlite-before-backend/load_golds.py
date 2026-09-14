"""Shared loader for the three gold sets. No third-party import here."""

import json
import os

SCRATCH = os.environ.get("MEASURE_WORK", ".")
"""The directory this run worked in, which held `data/` and `work-r*/`.

Read from the environment and not written here: the run of 2026-09-04 used a scratch
directory belonging to the session that made it, and one machine's layout is not something
this repository publishes. The default is what a rerun from that directory reads."""

D = f"{SCRATCH}/data"

SETS = {
    "bird_dev": f"{D}/dev/dev_20240627/dev.json",
    "minidev_hf": f"{D}/mini_dev_sqlite.json",
    "minidev_zip": f"{D}/zip/minidev/MINIDEV/mini_dev_sqlite.json",
}


def load(set_name):
    with open(SETS[set_name]) as f:
        rows = json.load(f)
    out = []
    for r in rows:
        out.append(
            {
                "question_id": r["question_id"],
                "db_id": r["db_id"],
                "SQL": r["SQL"],
            }
        )
    return out


if __name__ == "__main__":
    for name in SETS:
        rows = load(name)
        print(name, len(rows))
