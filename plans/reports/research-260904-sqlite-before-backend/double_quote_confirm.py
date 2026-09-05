"""Task 1: confirm ADR-0014's claim that libpg_query reads a double-quoted
token as an identifier, silently, with three synthetic statements carrying a
double-quoted token that names no column or table (the SQLite rule that makes
such a token a string literal: https://sqlite.org/lang_keywords.html). Run
under the worktree's uv env (imports attestql).
"""

from attestql.audit.statements import parse_statement

TESTS = [
    'SELECT "hello world" FROM t',
    'SELECT a FROM t WHERE b = "not a real column"',
    'SELECT "2024-01-01" AS d FROM t',
]

for sql in TESTS:
    parsed = parse_statement(sql)
    print(f"{sql!r} -> parsed without error, tables={parsed.tables}")
