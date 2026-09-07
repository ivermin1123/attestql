"""Verify the Spider inputs and build the three gold-only question files.

usage: MEASURE_WORK=<work-directory> ATTESTQL_INPUTS=<read-only-inputs> python3 prepare.py

The question files stay under the work directory and are never committed. ``current`` is
Spider's 2024 zip verbatim in BIRD's question-file shape. ``before`` is the same file with only
the 28 SQL lines Spider changed on 2020-06-07 substituted back. ``transformed`` holds only the
213 golds that carry a double-quoted token resolving to neither a table nor a column of their
database; each such token is changed to a single-quoted literal.
"""

import hashlib
import json
import os
import platform
import re
import sqlite3
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import sqlglot

WORK = Path(os.environ["MEASURE_WORK"]).resolve()
INPUTS = Path(os.environ["ATTESTQL_INPUTS"]).resolve()
SPIDER = WORK / "data" / "spider" / "spider_data"
OUT = WORK / "out"
ZIP_SHA = "00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b"
BEFORE_SHA = "6d3ac4f5e2657e30ff9418353be9f1360fe6517075809b8c13bc7a9c3f82a02a"
AFTER_SHA = "36e8c72ec576cc78a225b1f039d5269239d9c80ded027b748fe28aba6797cccf"
BLOCK = re.compile(r"^Question (\d+):\s*(.*?)\s*\|\|\|\s*(\S+)\s*$\nSQL:\s*(.*)$", re.MULTILINE)
DOUBLE_QUOTED = re.compile(r'"([^"]*)"')
NORMALISE = re.compile(r"\s+")
EXPECTED_DOUBLE_QUOTED = {
    "world_1": 86,
    "flight_2": 56,
    "tvshow": 26,
    "cre_Doc_Template_Mgt": 20,
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalise(text: str) -> str:
    """Case, whitespace, punctuation-spacing and quote insensitive.

    ``dev.sql`` is tokenised with spaces around punctuation and inside quotes, while ``dev.json``
    is prose; both quote characters mean a string here, so ``'' and a double quote are read
    alike only for alignment. Correction membership is decided on the raw stripped line, so a
    whitespace-only SQL correction still counts.
    """
    text = text.replace("``", '"').replace("''", '"')
    text = re.sub(r'\s*["\']\s*', r'"', text)
    text = re.sub(r"\s*([,.?!;:()])\s*", r"\1", text)
    return NORMALISE.sub(" ", text.strip().rstrip(";")).casefold()


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_dev_sql(path: Path) -> dict[int, tuple[str, str, str]]:
    blocks = {
        int(found.group(1)): found.groups()
        for found in BLOCK.finditer(path.read_text(encoding="utf-8"))
    }
    if sorted(blocks) != list(range(1, 1035)):
        raise SystemExit(f"{path.name}: expected Question 1..1034 in order, got {len(blocks)}")
    return blocks


def schema_names(schemas: list[dict]) -> dict[str, set[str]]:
    by_db: dict[str, set[str]] = {}
    for schema in schemas:
        names = {*schema["table_names"], *schema["table_names_original"]}
        for key in ("column_names", "column_names_original"):
            names.update(pair[1] for pair in schema[key] if pair[1] != "*")
        by_db[schema["db_id"]] = {name.casefold() for name in names}
    return by_db


def transform(sql: str, names: set[str]) -> tuple[str, list[str]]:
    changed: list[str] = []

    def one(found: re.Match[str]) -> str:
        token = found.group(1)
        if token.casefold() in names:
            return found.group(0)
        changed.append(token)
        return "'" + token.replace("'", "''") + "'"

    return DOUBLE_QUOTED.sub(one, sql), changed


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if digest(WORK / "data" / "spider_data.zip") != ZIP_SHA:
        raise SystemExit("spider_data.zip digest mismatch")

    entries = load_json(SPIDER / "dev.json")
    schemas = load_json(SPIDER / "tables.json")
    gold_lines = (SPIDER / "dev_gold.sql").read_text(encoding="utf-8").splitlines()
    before_path = WORK / "data" / "spider-2020" / "dev.sql.before"
    after_path = WORK / "data" / "spider-2020" / "dev.sql.after"
    for path, expected in ((before_path, BEFORE_SHA), (after_path, AFTER_SHA)):
        if digest(path) != expected:
            raise SystemExit(f"{path.name} digest mismatch")
    if len(entries) != 1034 or len(gold_lines) != 1034:
        raise SystemExit("expected 1,034 dev entries and gold lines")

    dev_ids: dict[str, list[int]] = {}
    for index, entry in enumerate(entries):
        gold_sql, gold_db = gold_lines[index].split("\t", 1)
        if entry["db_id"] != gold_db or normalise(entry["query"]) != normalise(gold_sql):
            raise SystemExit(f"dev.json and dev_gold.sql disagree at index {index}")
        dev_ids.setdefault(entry["db_id"], []).append(index)
    if len(dev_ids) != 20:
        raise SystemExit(f"expected 20 dev databases, got {len(dev_ids)}")
    missing = [db for db in dev_ids if not (SPIDER / "database" / db / f"{db}.sqlite").is_file()]
    if missing:
        raise SystemExit(f"missing databases: {missing}")

    before = parse_dev_sql(before_path)
    after = parse_dev_sql(after_path)
    alignment = {"before": {}, "after": {}, "current_against_after": {}}
    alignment["current_against_after"] = {
        "sql": sum(
            normalise(entries[index]["query"]) == normalise(after[index + 1][3])
            for index in range(1034)
        ),
        "question": sum(
            normalise(entries[index]["question"]) == normalise(after[index + 1][1])
            for index in range(1034)
        ),
    }
    for side, blocks in (("before", before), ("after", after)):
        for field, position in (("sql", 3), ("question", 1)):
            matches = sum(
                normalise(entries[index][field if field != "sql" else "query"])
                == normalise(blocks[index + 1][position])
                for index in range(1034)
            )
            alignment[side][field] = matches

    current = [
        {
            "question_id": index,
            "db_id": entry["db_id"],
            "question": entry["question"],
            "evidence": "",
            "SQL": entry["query"],
        }
        for index, entry in enumerate(entries)
    ]
    names = schema_names(schemas)
    ambiguous: dict[int, dict] = {}
    for row in current:
        tokens = [
            token
            for token in DOUBLE_QUOTED.findall(row["SQL"])
            if token.casefold() not in names[row["db_id"]]
        ]
        if tokens:
            ambiguous[row["question_id"]] = {
                "db_id": row["db_id"],
                "tokens": tokens,
                "sql": transform(row["SQL"], names[row["db_id"]])[0],
            }
    by_db = Counter(row["db_id"] for row in ambiguous.values())
    if (
        len(ambiguous) != 213
        or {db: by_db[db] for db in EXPECTED_DOUBLE_QUOTED} != EXPECTED_DOUBLE_QUOTED
    ):
        raise SystemExit(f"the double-quoted count moved: {len(ambiguous)} {dict(by_db)}")

    transformed = [
        dict(row, SQL=ambiguous[row["question_id"]]["sql"])
        for row in current
        if row["question_id"] in ambiguous
    ]
    sql_changed = [
        index
        for index in range(1034)
        if before[index + 1][3].strip() != after[index + 1][3].strip()
    ]
    question_changed = [
        index
        for index in range(1034)
        if before[index + 1][1].strip() != after[index + 1][1].strip()
    ]
    both = sorted(set(sql_changed) & set(question_changed))
    text_only = sorted(set(question_changed) - set(sql_changed))
    if (
        len(sql_changed) != 28
        or len(question_changed) != 21
        or len(both) != 5
        or len(text_only) != 16
    ):
        raise SystemExit(
            f"the 2020 correction split moved: {len(sql_changed)} SQL, "
            f"{len(question_changed)} question, {len(both)} both"
        )

    before_rows = [
        dict(
            row,
            SQL=before[row["question_id"] + 1][3]
            if row["question_id"] in sql_changed
            else row["SQL"],
        )
        for row in current
    ]
    for name, rows in (
        ("questions-current.json", current),
        ("questions-before.json", before_rows),
        ("questions-transformed.json", transformed),
    ):
        write_json(WORK / "data" / name, rows)

    database_rows = {}
    for db, ids in sorted(dev_ids.items()):
        path = SPIDER / "database" / db / f"{db}.sqlite"
        database_rows[db] = {
            "questions": len(ids),
            "ids": ids,
            "sha256": digest(path),
        }
    inputs = {
        "reading": "Every input this measurement reads, with the digest the run asserts.",
        "environment": {
            "attestql": version("attestql"),
            "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version,
            "sqlglot": sqlglot.__version__,
        },
        "spider_data": {
            "url": "https://drive.google.com/file/d/1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J/view",
            "page": "https://yale-lily.github.io/spider",
            "licence": "CC BY-SA 4.0",
            "file_date": "2024-09-12",
            "sha256": ZIP_SHA,
            "members": {
                name: digest(SPIDER / name) for name in ("dev.json", "dev_gold.sql", "tables.json")
            },
        },
        "spider_2020": {
            "repository": "https://github.com/taoyds/spider",
            "path": "evaluation_examples/dev.sql",
            "before": {
                "ref": "e0b7bc91",
                "url": "https://github.com/taoyds/spider/blob/e0b7bc91/evaluation_examples/dev.sql",
                "sha256": BEFORE_SHA,
            },
            "after": {
                "ref": "25fcd85d",
                "url": "https://github.com/taoyds/spider/blob/25fcd85d/evaluation_examples/dev.sql",
                "sha256": AFTER_SHA,
            },
            "commit_message_date": "2020-06-08",
            "commit_message": "corrected annotated errors/mismatches",
            "site_news_date": "2020-06-07",
            "site_news": "corrected some annotation errors and label mismatches, ~4% of dev examples",
        },
        "dev_databases": database_rows,
        "dev_gold_alignment": {
            "rule": "db_id exactly; SQL after whitespace, punctuation spacing, quote characters, trailing semicolon and case are normalised",
            "matched": 1034,
            "of": 1034,
        },
        "alignment_by_index": alignment,
        "later_question_edits_current_against_after": {
            "count": 1034 - alignment["after"]["question"],
            "ids": [
                index
                for index in range(1034)
                if normalise(entries[index]["question"]) != normalise(after[index + 1][1])
            ],
        },
        "double_quoted_literals": {
            "rule": "a gold carrying at least one double-quoted token that is neither a table nor a column name of its database under tables.json, ignoring case",
            "golds": len(ambiguous),
            "by_database": dict(sorted(by_db.items())),
            "ids": sorted(ambiguous),
            "transformation": "each such token becomes a single-quoted SQLite literal, with any internal quote doubled; every other double-quoted token stays unchanged",
        },
        "passes": {
            "current": "all 1,034 2024-06-08 dev.json golds",
            "before": "all 1,034 golds, with only the 28 corrected ids carrying their parent-commit SQL",
            "transformed": "the 213 ambiguous-literal golds, current SQL with those tokens single-quoted",
        },
    }
    write_json(OUT / "inputs.json", inputs)
    corrections = {
        "reading": "Spider's own 2020-06-07 correction, measured by normalised SQL and question text.",
        "normalisation": "SQL membership is the raw stripped line; question membership is raw stripped text",
        "counts": {
            "sql_changed": len(sql_changed),
            "question_changed": len(question_changed),
            "both_changed": len(both),
            "question_only_changed": len(text_only),
            "untouched": 1034 - len(set(sql_changed) | set(question_changed)),
        },
        "correction_set": [
            {
                "question_id": index,
                "question_number": index + 1,
                "db_id": entries[index]["db_id"],
                "before_sql": before[index + 1][3],
                "after_sql": after[index + 1][3],
            }
            for index in sql_changed
        ],
        "text_only_ids": text_only,
        "both_ids": both,
    }
    write_json(OUT / "corrections.json", corrections)
    print(
        f"prepared 1,034 golds, {len(sql_changed)} SQL corrections, "
        f"{len(ambiguous)} ambiguous-literal golds"
    )


if __name__ == "__main__":
    main()
