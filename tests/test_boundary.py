"""Import boundaries, enforced by walking the AST of every source file (not by grep)."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "attestql"
TESTS = Path(__file__).resolve().parent

AUDIT_PARSERS: tuple[Path, ...] = (
    SRC / "audit" / "statements.py",
    SRC / "audit" / "sqlite_statements.py",
)
"""The modules permitted to import a SQL parser: one per engine and no more.

ADR-0013 point 2 makes a parse part of the audit itself: the replay rule is read off the
gold's ORDER BY and the smells are read off its AST, so the tool cannot run without one.
Point 8 is where the parser's licence is declared, and the licence is why the parsers this
allowlist names are a BSD binding to libpg_query and an MIT one, and no longer a GPL one.
ADR-0014 point 3 is why there are two: a second engine reads another grammar, and two
parsers over one engine would be a second opinion about the same statement. The permissions
are exact paths and not a directory, so a third module that started parsing would be a diff
in this file."""

DRIVER_MODULES: Mapping[str, Path] = {
    "psycopg": SRC / "audit" / "postgres.py",
    "sqlite3": SRC / "audit" / "sqlite.py",
}
"""Each database driver, and the one module under ``src`` permitted to import it.

ADR-0013 point 4 makes the executor interface engine-neutral from the first commit, and
this is what that means in the source: everything above a backend speaks to
``audit.backend.Backend``, and each driver is reachable from one file. Exact paths again,
for the same reason the allowlist above is one.

``sqlite3`` is in the standard library and is therefore confined under ``src`` rather than
everywhere: a test builds the file it then audits, and building one is what the read-only
backend cannot do."""

DRIVER_MODULE = DRIVER_MODULES["psycopg"]
"""The one module permitted to import the database driver anywhere, tests included. The
prohibition is repository-wide because product tests reach the server through the backend's
own API, so a driver import cannot spread through the suite either."""

PARSER_TOP_LEVEL = frozenset({"postgast", "sqlglot"})
"""The binding to libpg_query and sqlglot: the whole of what the two parser modules may
parse with.

A second parser over one engine would be a second opinion about the same statement, and the
two would disagree on the day it mattered; a parser per engine is one opinion each."""

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

COMMAND_MODULE = SRC / "audit" / "cli.py"
"""The command, which states the installed release when it is asked for ``--version``."""

VERSION_TEST = TESTS / "test_audit_command_runs_over_a_question_file.py"
"""The file that observes what that release reads as, which is the only way to observe it."""

METADATA_READERS: tuple[Path, ...] = (*AUDIT_PARSERS, COMMAND_MODULE, VERSION_TEST)
"""The files permitted to read installed package metadata, permitted ``importlib.metadata``
alone.

A summary states which parser judged its statements, and half of that is the parser's own
release, which the distribution states and the package does not carry as a public attribute.
``--version`` is that same question asked about this project: what a reader is told has to be
the release the code in front of them came from, and only the installed distribution knows
that, where a number this repository stated about itself would be one more place to forget to
move. The test is granted it for the observation it makes, as the console script's test is
granted a process: the only way to show the command and the distribution agree is to read both.

Exact paths, as the drivers' and the parsers' are, and exercised by the test below, so the day
one stops being used is the day it stops being granted. Every other primitive in the set is
forbidden there too, including the rest of ``importlib``."""

URI_ESCAPE = "urllib.parse"
"""Where a percent escape is written, and the whole of the exemption below. It builds URI
text and takes it apart again; what puts ``urllib`` in the set above is ``urllib.request``,
which opens a connection, and that half stays forbidden here as everywhere else."""

URI_ESCAPERS: tuple[Path, ...] = (DRIVER_MODULES["sqlite3"],)
"""The files permitted ``urllib.parse``, permitted that module alone, and the backend that
opens a file through a URI for the same reason it is the file's own driver's importer.

``mode=ro`` is what read-only means for a SQLite file and it is stated in the URI the
connection is opened with, so a path holding a ``?``, a ``#`` or a ``%`` has to be escaped
before it goes into one: unescaped, the filename ends where the path does not. Exact path,
as the driver's and the parser's are, and exercised by the test below, so the day it stops
being used is the day it stops being granted."""

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
    [path for path in scanned_files() if path not in AUDIT_PARSERS],
    ids=lambda p: str(p.relative_to(SRC.parent.parent)),
)
def test_no_file_but_an_audit_parser_imports_a_parser(path: Path) -> None:
    offenders = [name for name in imported_modules(path) if looks_like_a_parser(name)]
    assert not offenders, f"{path} imports the parser: {offenders}"


@pytest.mark.parametrize("path", AUDIT_PARSERS, ids=lambda p: p.name)
def test_each_audit_parser_really_imports_a_parser(path: Path) -> None:
    """The positive case of the allowlist, on the same ground as the driver's: a permission
    nobody uses is a permission whose widening nobody notices."""
    reached = [name for name in imported_modules(path) if looks_like_a_parser(name)]
    assert reached, f"{path.name} is an allowed parser importer but imports no parser"


def test_a_parser_is_reachable_from_exactly_the_parser_modules_under_src() -> None:
    """One parse per statement, and one module per engine that can make one."""
    importers = [
        path
        for path in python_files(SRC)
        if any(looks_like_a_parser(name) for name in imported_modules(path))
    ]
    assert sorted(importers) == sorted(AUDIT_PARSERS)


@pytest.mark.parametrize("driver", sorted(DRIVER_MODULES), ids=lambda name: name)
def test_each_driver_is_reachable_from_exactly_one_module_under_src(driver: str) -> None:
    """Stated per driver as well as per file: everything above a backend speaks to the
    interface, so a second importer of either driver would be an interface that had stopped
    being the way to a database."""
    importers = [
        path
        for path in python_files(SRC)
        if any(name.split(".")[0] == driver for name in imported_modules(path))
    ]
    assert importers == [DRIVER_MODULES[driver]]


def forbidden_primitives(path: Path) -> list[str]:
    forbidden_imports = FORBIDDEN_IMPORTS
    if path == CONSOLE_SCRIPT_TEST:
        forbidden_imports = FORBIDDEN_IMPORTS - {"subprocess"}
    found: list[str] = []
    for node in ast.walk(parse(path)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for name in imported_modules_of(node):
                if path in METADATA_READERS and name == PACKAGE_METADATA:
                    continue
                if path in URI_ESCAPERS and name == URI_ESCAPE:
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


@pytest.mark.parametrize("path", METADATA_READERS, ids=lambda p: p.name)
def test_each_metadata_reader_really_reads_the_metadata_it_is_allowed_to(path: Path) -> None:
    """The positive case of the metadata permissions, on the same ground as the rest."""
    assert PACKAGE_METADATA in imported_modules(path), (
        f"{path.name} is an allowed metadata reader and reads none"
    )


@pytest.mark.parametrize("path", URI_ESCAPERS, ids=lambda p: p.name)
def test_each_uri_escaper_really_escapes_the_path_it_is_allowed_to(path: Path) -> None:
    """The positive case of the URI permission, on the same ground as the metadata one."""
    assert URI_ESCAPE in imported_modules(path), (
        f"{path.name} is an allowed URI escaper and escapes nothing"
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
