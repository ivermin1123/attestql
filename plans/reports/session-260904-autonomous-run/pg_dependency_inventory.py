"""Count the lines under src/ that depend on PostgreSQL, by kind, for ADR-0014.

A line is counted once per kind it matches; the kinds are regular expressions over the
source text and nothing more, so the counts are an inventory to read beside the files, not a
measure of effort. Run from the repository root: ``uv run python <this file>``.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "src" / "attestql"
KINDS = {
    "driver": r"\bpsycopg\b|\bpq\.|\bLoader\b",
    "parser": r"\bpostgast\b|\bnodes\.|libpg_query|pg_query",
    "catalogue": (
        r"pg_catalog|pg_class|pg_namespace|pg_settings|pg_type\b|pg_database|pg_stat"
        r"|has_table_privilege|information_schema|inet_server|current_database|version\(\)"
    ),
    "envelope": (
        r"SET LOCAL|set_config|pg_advisory|search_path|READ ONLY|READ WRITE"
        r"|lock_timeout|statement_timeout"
    ),
    "idiom": r"::text|md5\(|string_agg|FILTER \(WHERE|!~|CREATE TABLE .* AS|coalesce\(",
    "types": r"float4|float8|\binterval\b|\bnumeric\b|\boid\b|type_code",
}


def main() -> None:
    files = sorted(ROOT.rglob("*.py"))
    totals = dict.fromkeys(KINDS, 0)
    print("file | lines | hits by kind")
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        hits = {
            kind: sum(1 for line in lines if re.search(pattern, line))
            for kind, pattern in KINDS.items()
        }
        for kind, count in hits.items():
            totals[kind] += count
        found = {kind: count for kind, count in hits.items() if count}
        print(f"{path.relative_to(ROOT)} | {len(lines)} | {found or 'none'}")
    all_lines = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in files)
    print(f"total | {all_lines} lines in {len(files)} files | {totals}")


if __name__ == "__main__":
    main()
