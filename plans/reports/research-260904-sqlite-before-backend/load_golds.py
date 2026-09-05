"""Shared loader for the three gold sets. No third-party import here."""

import json

D = "/private/tmp/claude-501/-Users-hoangle-Desktop-code-attestql/51c539ba-76fd-46dc-8441-ddbacaec3449/scratchpad/data"

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
