"""Import boundaries, enforced by walking the AST of every source file (not by grep)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "attestql"
TESTS = Path(__file__).resolve().parent

AUDIT_PARSER = SRC / "audit" / "statements.py"
"""The one module permitted to import a SQL parser.

ADR-0013 point 2 makes a parse part of the audit itself: the replay rule is read off the
gold's ORDER BY and the smells are read off its AST, so the tool cannot run without one.
Point 8 is where the parser's licence is declared, and the licence is why the parser this
allowlist names is a BSD binding to libpg_query and no longer a GPL one. The permission is
an exact path and not a directory, so a second module that started parsing would be a diff
in this file."""

DRIVER_MODULE = SRC / "audit" / "postgres.py"
"""The one module permitted to import the database driver.

ADR-0013 point 4 makes the executor interface engine-neutral from the first commit, and
this is what that means in the source: everything above it speaks to
``audit.backend.Backend``, and the driver is reachable from one file. An exact path again,
for the same reason the allowlist above is one."""

PARSER_TOP_LEVEL = frozenset({"postgast"})
"""The binding to libpg_query, and the whole of what ``statements.py`` may parse with.

A second parser anywhere would be a second opinion about the same statement, and the two
would disagree on the day it mattered."""

# Anything that looks like the V2.9 harness: its package names (lib/, sql/) and its
# bundle root (eda-v29). ADR-0006 confined these to kernel/adapters/; ADR-0013 deleted
# that package with the vendored validator, so the confinement is now the whole tree.
V29_TOP_LEVEL = frozenset({"lib", "sql", "eda_v29"})
V29_MARKERS = ("v29", "eda_v29", "eda-v29")

DRIVER_TOP_LEVEL = frozenset({"psycopg", "psycopg_pool"})
"""The database driver and its pool. Forbidden in ``src/`` and ``tests/`` outside one path.

``psycopg`` left ``V29_TOP_LEVEL`` in the same change that created this set. Dropping
it from there on its own would have permitted it repo-wide for the length of a commit,
so the removal and the exact-path rule that then held were one change or neither.

The allowlisted path was ``security/adapters/postgres.py`` until ADR-0013 deleted it with
the product path it served, and is ``audit/postgres.py`` now. It is one path and it is
exercised: a permission nobody uses is a permission whose widening nobody notices, so the
test below asserts that the one allowed module really does import the driver."""

DRIVER_FORBIDDEN_EVERYWHERE = frozenset({"psycopg2"})
"""Superseded, and allowlisted nowhere at all. It has no path, not even the backend's."""

DYNAMIC_CODE_CALLS = frozenset({"exec", "eval", "compile", "__import__"})
FORBIDDEN_ATTRIBUTE_CALLS = frozenset({("os", "system"), ("os", "popen")})
FORBIDDEN_IMPORTS = frozenset(
    {
        "subprocess",
        "importlib",
        "socket",
        "ssl",
        "http",
        "urllib",
        "ftplib",
        "smtplib",
        "requests",
        "httpx",
        "aiohttp",
    }
)

PACKAGE_METADATA = "importlib.metadata"
"""Where an installed distribution states its own release number, and the whole of the
exemption below. It reads what a package manager wrote and imports no code, which is the
reason ``importlib`` is in the set above."""

METADATA_READER = SRC / "audit" / "statements.py"
"""The one file permitted to read installed package metadata, and permitted
``importlib.metadata`` alone.

A summary states which parser judged its statements, and half of that is the binding's own
release, which the binding does not carry as an attribute. An exact path, as the driver's
and the parser's are, and exercised by the test below, so the day it stops being used is
the day it stops being granted. Every other primitive in the set is forbidden there too,
including the rest of ``importlib``."""

CONSOLE_SCRIPT_TEST = TESTS / "test_audit_end_to_end.py"
"""The one file permitted to start a process, and permitted ``subprocess`` alone.

ADR-0013 point 2 ships a console script, and the only observation that proves the
``[project.scripts]`` entry resolves to the command a stranger is told to run is running it:
calling ``main`` in process proves the function and says nothing about the wiring. The
permission is an exact path, as the driver's and the parser's are, it is exercised (the test
below asserts that this file really does import it), and every other primitive in the set is
forbidden there too.

The cross-process fixture determinism test held the previous ``subprocess`` exemption, also
by exact path, and ADR-0013 deleted it with the fixture it generated."""


def python_files(root: Path) -> list[Path]:
    files = sorted(root.rglob("*.py"))
    assert files, f"no python files under {root}"
    return files


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def imported_modules(path: Path) -> list[str]:
    """Every module name an Import or ImportFrom node in ``path`` refers to."""
    names: list[str] = []
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.append("." * node.level + module)
    return names


def is_external(module: str) -> bool:
    """False for the product's own modules and for relative imports."""
    return not (module.startswith(".") or module == "attestql" or module.startswith("attestql."))


def looks_like_v29(module: str) -> bool:
    """True for an external module that looks like the V2.9 harness or its dependencies."""
    if not is_external(module):
        return False
    top = module.split(".")[0]
    lowered = module.lower()
    return top in V29_TOP_LEVEL or any(marker in lowered for marker in V29_MARKERS)


def looks_like_a_parser(module: str) -> bool:
    """True for the SQL parser, whoever imports it."""
    return is_external(module) and module.split(".")[0] in PARSER_TOP_LEVEL


def looks_like_a_superseded_driver(module: str) -> bool:
    return is_external(module) and module.split(".")[0] in DRIVER_FORBIDDEN_EVERYWHERE


def scanned_files() -> list[Path]:
    """Both scan roots. Product tests reach the server through the backend's own API,
    so a driver import cannot spread through the suite either."""
    return python_files(SRC) + python_files(TESTS)


@pytest.mark.parametrize(
    "path",
    [path for path in scanned_files() if path != DRIVER_MODULE],
    ids=lambda p: str(p.relative_to(SRC.parent.parent)),
)
def test_no_file_but_the_postgres_backend_imports_psycopg(path: Path) -> None:
    offenders = [name for name in imported_modules(path) if name.split(".")[0] == "psycopg"]
    assert not offenders, f"{path} imports the driver: {offenders}"


def test_the_postgres_backend_really_imports_the_driver() -> None:
    """The positive case of the allowlist above, on the same ground as the parser's."""
    imported = imported_modules(DRIVER_MODULE)
    assert any(name.split(".")[0] == "psycopg" for name in imported), (
        f"{DRIVER_MODULE.name} is the allowed driver importer but imports no driver"
    )


def test_the_driver_is_reachable_from_exactly_one_module_under_src() -> None:
    """Stated as a count as well as a rule: two allowed importers would be an interface
    that had stopped being the way to a database."""
    importers = [
        path
        for path in python_files(SRC)
        if any(name.split(".")[0] == "psycopg" for name in imported_modules(path))
    ]
    assert importers == [DRIVER_MODULE]


@pytest.mark.parametrize(
    "path", scanned_files(), ids=lambda p: str(p.relative_to(SRC.parent.parent))
)
def test_no_file_imports_psycopg_pool(path: Path) -> None:
    """Asserted separately from the driver above: the pool has its own top-level name,
    and a rule that only matched the driver would let the pool through unremarked."""
    offenders = [name for name in imported_modules(path) if name.split(".")[0] == "psycopg_pool"]
    assert not offenders, f"{path} imports the pool: {offenders}"


@pytest.mark.parametrize(
    "path", scanned_files(), ids=lambda p: str(p.relative_to(SRC.parent.parent))
)
def test_the_superseded_driver_is_imported_nowhere_at_all(path: Path) -> None:
    offenders = [name for name in imported_modules(path) if looks_like_a_superseded_driver(name)]
    assert not offenders, f"{path} imports a superseded driver: {offenders}"


def test_the_marker_sets_name_the_harness_a_driver_and_a_parser_separately() -> None:
    """Each set moved out on its own, and the sets are asserted so a merge cannot blur them.

    ``psycopg`` left the harness set for an exact-path rule of its own; the parser left it
    when the GPL parser it named was replaced, because what may parse is now an allowlist
    rather than a prohibition."""
    assert {"lib", "sql", "eda_v29"} == V29_TOP_LEVEL
    assert not V29_TOP_LEVEL & (DRIVER_TOP_LEVEL | DRIVER_FORBIDDEN_EVERYWHERE | PARSER_TOP_LEVEL)


@pytest.mark.parametrize(
    "path", scanned_files(), ids=lambda p: str(p.relative_to(SRC.parent.parent))
)
def test_nothing_imports_the_v29_harness(path: Path) -> None:
    """ADR-0006 confined V2.9 to ``kernel/adapters/``. ADR-0013 deleted that package with
    the vendored validator, so the confinement has no room left in it and the rule reaches
    every file in both roots."""
    offenders = [name for name in imported_modules(path) if looks_like_v29(name)]
    assert not offenders, f"{path} imports V2.9-like modules: {offenders}"


@pytest.mark.parametrize(
    "path",
    [path for path in scanned_files() if path != AUDIT_PARSER],
    ids=lambda p: str(p.relative_to(SRC.parent.parent)),
)
def test_no_file_but_the_audit_parser_imports_a_parser(path: Path) -> None:
    offenders = [name for name in imported_modules(path) if looks_like_a_parser(name)]
    assert not offenders, f"{path} imports the parser: {offenders}"


def test_the_audit_parser_really_imports_the_parser() -> None:
    """The positive case of the allowlist, on the same ground as the driver's: a permission
    nobody uses is a permission whose widening nobody notices."""
    reached = [name for name in imported_modules(AUDIT_PARSER) if looks_like_a_parser(name)]
    assert reached, "the audit parser is the allowed parser importer but imports no parser"


def test_the_parser_is_reachable_from_exactly_one_module_under_src() -> None:
    """One parse per statement, and one module that can make one."""
    importers = [
        path
        for path in python_files(SRC)
        if any(looks_like_a_parser(name) for name in imported_modules(path))
    ]
    assert importers == [AUDIT_PARSER]


def forbidden_primitives(path: Path) -> list[str]:
    forbidden_imports = FORBIDDEN_IMPORTS
    if path == CONSOLE_SCRIPT_TEST:
        forbidden_imports = FORBIDDEN_IMPORTS - {"subprocess"}
    found: list[str] = []
    for node in ast.walk(parse(path)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for name in imported_modules_of(node):
                if path == METADATA_READER and name == PACKAGE_METADATA:
                    continue
                if name.split(".")[0] in forbidden_imports:
                    found.append(f"line {node.lineno}: import {name}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in DYNAMIC_CODE_CALLS:
                found.append(f"line {node.lineno}: {func.id}()")
            elif (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and (func.value.id, func.attr) in FORBIDDEN_ATTRIBUTE_CALLS
            ):
                found.append(f"line {node.lineno}: {func.value.id}.{func.attr}()")
    return found


def imported_modules_of(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    return [node.module or ""]


@pytest.mark.parametrize(
    "path",
    python_files(SRC) + python_files(TESTS),
    ids=lambda p: str(p.relative_to(SRC.parent.parent)),
)
def test_no_dynamic_code_execution_or_network_primitives(path: Path) -> None:
    found = forbidden_primitives(path)
    assert not found, f"{path}: {found}"


def test_the_metadata_reader_really_reads_the_metadata_it_is_allowed_to() -> None:
    """The positive case of the one metadata permission, on the same ground as the rest."""
    assert PACKAGE_METADATA in imported_modules(METADATA_READER), (
        f"{METADATA_READER.name} is the allowed metadata reader and reads none"
    )


def test_the_console_script_test_really_starts_the_process_it_is_allowed_to() -> None:
    """The positive case of the one process permission, on the same ground as the driver's."""
    assert "subprocess" in imported_modules(CONSOLE_SCRIPT_TEST), (
        f"{CONSOLE_SCRIPT_TEST.name} is the allowed process starter and starts none"
    )


def test_subprocess_is_reachable_from_exactly_one_file() -> None:
    starters = [
        path
        for path in python_files(SRC) + python_files(TESTS)
        if "subprocess" in imported_modules(path)
    ]
    assert starters == [CONSOLE_SCRIPT_TEST]
