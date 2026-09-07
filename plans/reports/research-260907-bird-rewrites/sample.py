"""Write the fixed hand-reading sample to the work directory, outside the repository.

    MEASURE_WORK=<work-directory> python3 sample.py

For a NOT_EQUAL id the two results come from AttestQL's counterexample. For an EQUAL id both
statements are run once here under the same 30 s wall-clock budget; the tool saves no result
for an EQUAL answer. An ERROR states that no result exists.
"""

import json
import os
import sqlite3
import time
from pathlib import Path

WORK = Path(os.environ["MEASURE_WORK"])
HERE = Path(__file__).resolve().parent
OLD = WORK / "data/dev/dev_20240627/dev.json"
NEW = WORK / "data/hf/dev_20251106-00000-of-00001.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def database_path(db: str) -> Path:
    copy = WORK / "data/dev/copies" / db / f"{db}.sqlite"
    return copy if copy.exists() else WORK / "data/dev/dev_databases" / db / f"{db}.sqlite"


def run(sql: str, db: str) -> dict:
    connection = sqlite3.connect(f"file:{database_path(db)}?mode=ro", uri=True)
    deadline = time.monotonic() + 30

    def stop() -> int:
        return 1 if time.monotonic() > deadline else 0

    connection.set_progress_handler(stop, 1000)
    try:
        cursor = connection.execute(sql)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description or ()]
        return {
            "columns": columns,
            "row_count": len(rows),
            "first_rows": rows[:10],
            "duplicate_full_rows": len(rows) - len({repr(row) for row in rows}),
        }
    except Exception as error:  # the worksheet states the engine's refusal
        return {"error": f"{type(error).__name__}: {error}"}
    finally:
        connection.close()


def tool_result(record: dict, side: str) -> dict:
    result = record[side]["result"]
    rows = result["rows"]
    rendered = [json.dumps(row, sort_keys=True) for row in rows]
    return {
        "columns": [column["name"] for column in result["columns"]],
        "declared_types": [column["declared_type"] for column in result["columns"]],
        "row_count": result["row_count"],
        "first_rows": rows[:10],
        "duplicate_full_rows": len(rendered) - len(set(rendered)),
    }


def main() -> None:
    old, new = load(OLD), load(NEW)
    old_by_id = {entry["question_id"]: entry for entry in old}
    new_by_id = {entry["question_id"]: entry for entry in new}
    verdicts = load(HERE / "verdicts.json")["groups"]["rewrite-399"]["questions"]
    ast = load(HERE / "ast-diff.json")["questions"]
    samples = load(HERE / "crosstab.json")["sample_ids"]
    lines = [
        "# Hand-reading sample",
        "",
        "Read the question and evidence from both copies, both statements, and both results.",
        "",
    ]
    for sql_class, ids in samples.items():
        lines.extend([f"## {sql_class}", ""])
        for question_id in ids:
            key = str(question_id)
            replay = verdicts[key]
            entry, changed = old_by_id[question_id], new_by_id[question_id]
            lines.extend(
                [
                    f"### q{question_id} ({replay['db']}; verdict {replay['verdict']})",
                    "",
                    f"- old question: {entry['question']}",
                    f"- new question: {changed['question']}",
                    f"- old evidence: {entry.get('evidence', '')}",
                    f"- new evidence: {changed.get('evidence', '')}",
                    f"- replay rule: {replay['rule']}; mechanism: {replay['mechanism']}; "
                    f"multiset equal: {replay['multiset_equal']}; bird_ex: {replay['bird_ex']}; "
                    f"test_suite_ex: {replay['test_suite_ex']}",
                    f"- touched clauses: {', '.join(ast[key]['touched_clauses'])}",
                    "",
                    "old SQL:",
                    "",
                    "```sql",
                    entry["SQL"],
                    "```",
                    "",
                    "new SQL:",
                    "",
                    "```sql",
                    changed["SQL"],
                    "```",
                    "",
                ]
            )
            if replay["verdict"] == "NOT_EQUAL":
                record = load(
                    WORK
                    / "out/tool/rewrite-399"
                    / replay["db"]
                    / f"q{question_id}"
                    / "counterexample.json"
                )
                lines.extend(
                    [
                        f"- old result: {json.dumps(tool_result(record, 'gold'), ensure_ascii=False)}",
                        f"- new result: {json.dumps(tool_result(record, 'second'), ensure_ascii=False)}",
                        "",
                    ]
                )
            elif replay["verdict"] == "EQUAL":
                lines.extend(
                    [
                        f"- old result: {json.dumps(run(entry['SQL'], replay['db']), ensure_ascii=False)}",
                        f"- new result: {json.dumps(run(changed['SQL'], replay['db']), ensure_ascii=False)}",
                        "",
                    ]
                )
            else:
                lines.append(f"- result unavailable: {json.dumps(replay['error'])}\n")
    output = WORK / "out/manual-readings.md"
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{sum(map(len, samples.values()))} readings: {output}")


if __name__ == "__main__":
    main()
