"""The renderer's import graph: no driver, no parser, nowhere in it.

``attestql report`` reads an audit directory and writes pages, and the whole reason it can be
handed a directory another machine produced is that it needs neither engine to do it: no
connection, no grammar, nothing compiled against a server. That is a property of what it
imports, so it is asserted on the import graph and not on a run -- a module that reached a
driver would still render this repository's own directories and would fail on a machine
where the driver is not installable, which is where the pages of phase 5 have to run.

The walk follows the product's own modules through ``attestql.*`` imports, so the boundary
covers what the renderer reaches and not only what it names: ``attestql.evidence`` is
permitted, and it is permitted because it imports nothing but the standard library either.
``tests/test_boundary.py`` states the repository-wide rules this one narrows.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
PACKAGE = "attestql"
REPORT = SRC / PACKAGE / "report"

FORBIDDEN = frozenset({"psycopg", "psycopg_pool", "psycopg2", "postgast", "sqlglot", "sqlite3"})
"""Both drivers and both parsers. A renderer that reached any of them would be a renderer
whose pages could only be made where an engine is."""

PERMITTED = frozenset({"jinja2", "markupsafe"})
"""The one dependency outside the standard library, and the escaping library it brings. The
set is stated so that a second one is a diff in this file rather than a quiet addition."""


def imported(path: Path) -> list[str]:
    """Every module name an import in ``path`` refers to, relative imports resolved."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = path.parent.relative_to(SRC).as_posix().replace("/", ".")
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.append(f"{package}.{module}" if node.level else module)
    return names


def module_file(name: str) -> Path | None:
    """Where one of the product's own modules is, as a file or as a package's ``__init__``."""
    stem = SRC.joinpath(*name.split("."))
    if stem.is_dir():
        return stem / "__init__.py"
    module = stem.with_suffix(".py")
    return module if module.is_file() else None


def reachable() -> dict[str, list[str]]:
    """Every module the renderer reaches, with what each one imports.

    Breadth first from the renderer's own files, following ``attestql`` imports only: the
    graph is what this package can pull in, and a module outside the package is a leaf whose
    name is the thing being asserted about.
    """
    seen: dict[str, list[str]] = {}
    queue = sorted(REPORT.rglob("*.py"))
    assert queue, f"no python files under {REPORT}"
    while queue:
        path = queue.pop()
        name = path.relative_to(SRC).with_suffix("").as_posix().replace("/", ".")
        if name in seen:
            continue
        seen[name] = imported(path)
        for reached in seen[name]:
            if not reached.startswith(f"{PACKAGE}."):
                continue
            found = module_file(reached)
            # An import of a name out of a module reaches the module that holds it.
            if found is None:
                found = module_file(reached.rsplit(".", 1)[0])
            assert found is not None, f"{name} imports {reached}, which is nowhere under {SRC}"
            queue.append(found)
    return seen


REACHED = reachable()


@pytest.mark.parametrize("module", sorted(REACHED), ids=lambda name: name)
def test_nothing_the_renderer_reaches_imports_a_driver_or_a_parser(module: str) -> None:
    offenders = [name for name in REACHED[module] if name.split(".")[0] in FORBIDDEN]

    assert not offenders, f"{module} reaches an engine: {offenders}"


def test_the_renderer_reaches_the_evidence_package_and_not_the_audit() -> None:
    """What it may import, stated as a set: the evidence record's own package and no other.

    The audit holds the writers of these files and their constants, and importing them would
    put both drivers and both parsers behind a page: the file names the renderer reads are
    stated in ``attestql.report.render`` for exactly this reason.
    """
    packages = {name.split(".")[1] for name in REACHED if name.startswith(f"{PACKAGE}.")}

    assert packages == {"report", "evidence", "kernel", "contract"}


def test_the_one_dependency_outside_the_standard_library_is_the_template_engine() -> None:
    """Every third-party import the renderer reaches, against the permitted set."""
    outside = {
        name.split(".")[0]
        for imports in REACHED.values()
        for name in imports
        if not name.startswith(PACKAGE)
    }

    assert outside & PERMITTED == outside & {"jinja2", "markupsafe"}
    assert "jinja2" in outside, "the renderer renders with the template engine"
    assert not outside & FORBIDDEN
