# Developer tasks. `just check` is the single command a milestone verification runs; it stops at
# the first failing recipe. Needs uv, just (brew install just) and Node.js: markdownlint and
# cspell run through npx at the versions pinned below.

markdownlint_version := "0.23.2"
cspell_version := "10.1.1"
markdown_files := '"README.md" "docs/**/*.md" "plans/**/*.md"'

# List the recipes.
default:
    @just --list

# Lint and formatting check. Changes nothing.
lint:
    uv run ruff check .
    uv run ruff format --check .

# Ruff's safe auto-fixes and the formatter, nothing that could alter meaning.
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Pyright strict over src, tests and tools: the engine and config Pylance runs in the editor.
typecheck:
    uv run pyright

# The three repository checks: typography, documentation links, ADR index.
repocheck:
    uv run python tools/check_typography.py
    uv run python tools/check_doc_links.py
    uv run python tools/check_adr_index.py

# markdownlint and cspell over the documentation.
docs:
    npx --yes markdownlint-cli2@{{markdownlint_version}} {{markdown_files}}
    npx --yes cspell@{{cspell_version}} --no-progress {{markdown_files}}

# The test suite. The sandbox-marked tests skip themselves here; `just sandbox` is where they run.
test:
    uv run pytest

# The audit end to end: the pinned PostgreSQL 16 sandbox, the fixture that reproduces the three
# shipped-gold defects, the read-only auditor login, and the sandbox-marked tests against it.
# Needs Docker and port 5497. Neither is a skip: ADR-0013 point 11 puts this run in the merge
# gate, so a missing Docker or a taken port fails the gate rather than passing it quietly.
sandbox:
    tools/audit-sandbox/run.sh "${TMPDIR:-/tmp}/attestql-audit-sandbox" -- uv run pytest -q -m sandbox

# Every gate in order: lint, typecheck, repocheck, docs, test, sandbox. Stops at the first failure.
check: lint typecheck repocheck docs test sandbox
