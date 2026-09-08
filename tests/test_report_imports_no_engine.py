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
Every ancestor package's ``__init__`` is walked with the module under it, because Python
executes those to import it: a forbidden import added to ``attestql/evidence/__init__.py``
would be a driver loaded by a page, and a walk that stopped at ``evidence/load.py`` would
not see it. The last test builds a tree where the forbidden import is only in an ancestor
and shows the walk reaching it. ``tests/test_boundary.py`` states the repository-wide rules
this one narrows.
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


def imported(path: Path, src: Path) -> list[str]:
    """Every module name an import in ``path`` refers to, relative imports resolved."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = path.parent.relative_to(src).as_posix().replace("/", ".")
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names.append(f"{package}.{module}" if node.level else module)
    return names


def module_file(name: str, src: Path) -> Path | None:
    """Where one of the product's own modules is, as a file or as a package's ``__init__``."""
    stem = src.joinpath(*name.split("."))
    if stem.is_dir():
        return stem / "__init__.py"
    module = stem.with_suffix(".py")
    return module if module.is_file() else None


def module_name(path: Path, src: Path) -> str:
    """The dotted name of a file, a package's ``__init__`` under the package's own name."""
    name = path.relative_to(src).with_suffix("").as_posix().replace("/", ".")
    return name.removesuffix(".__init__")


def package_ancestors(name: str, src: Path) -> list[Path]:
    """Every ancestor package's ``__init__``, which Python runs before the module itself.

    ``import attestql.evidence.load`` executes ``attestql/__init__.py`` and
    ``attestql/evidence/__init__.py`` first, so what those two import is imported by anything
    that imports the module under them. A walk that visited only the leaf would report a
    boundary the runtime does not hold.
    """
    parts = name.split(".")
    inits = [src.joinpath(*parts[:depth], "__init__.py") for depth in range(1, len(parts))]
    return [init for init in inits if init.is_file()]


def reachable(root: Path, src: Path, package: str) -> dict[str, list[str]]:
    """Every module reached from the files under ``root``, with what each one imports.

    Breadth first, following the product's own imports only: a module outside the package is
    a leaf whose name is the thing being asserted about. Parameterised over the tree so the
    positive control below can walk one where the forbidden import is planted.
    """
    seen: dict[str, list[str]] = {}
    queue = sorted(root.rglob("*.py"))
    assert queue, f"no python files under {root}"
    while queue:
        path = queue.pop()
        name = module_name(path, src)
        if name in seen:
            continue
        seen[name] = imported(path, src)
        queue.extend(package_ancestors(name, src))
        for reached in seen[name]:
            if not reached.startswith(f"{package}."):
                continue
            found = module_file(reached, src)
            # An import of a name out of a module reaches the module that holds it.
            if found is None:
                found = module_file(reached.rsplit(".", 1)[0], src)
            assert found is not None, f"{name} imports {reached}, which is nowhere under {src}"
            queue.append(found)
    return seen


REACHED = reachable(REPORT, SRC, PACKAGE)


@pytest.mark.parametrize("module", sorted(REACHED), ids=lambda name: name)
def test_nothing_the_renderer_reaches_imports_a_driver_or_a_parser(module: str) -> None:
    offenders = [name for name in REACHED[module] if name.split(".")[0] in FORBIDDEN]

    assert not offenders, f"{module} reaches an engine: {offenders}"


def test_the_walk_visits_every_ancestor_package_of_a_module_it_reaches() -> None:
    """The packages themselves, not only the modules under them.

    ``attestql.report.render`` imports ``attestql.evidence.load``; Python runs
    ``attestql/__init__.py`` and ``attestql/evidence/__init__.py`` to do it, so both are in
    the set the test above is parametrised over. They import nothing forbidden today, which
    is why this is asserted rather than observed.
    """
    assert {"attestql", "attestql.evidence", "attestql.kernel", "attestql.contract"} <= set(REACHED)


def test_a_forbidden_import_in_an_ancestor_package_is_reached(tmp_path: Path) -> None:
    """The positive control, on a tree built for it: the driver is imported nowhere but in a
    package two levels above the module that reaches it, and the walk finds it there.

    Without the ancestors, this walk would return the leaf and its own imports and the
    parametrised test above would pass over a page that loads a driver at import time.
    """
    src = tmp_path
    (src / "product" / "pages").mkdir(parents=True)
    (src / "product" / "evidence").mkdir()
    (src / "product" / "__init__.py").write_text("import psycopg\n", encoding="utf-8")
    (src / "product" / "evidence" / "__init__.py").write_text("", encoding="utf-8")
    (src / "product" / "evidence" / "load.py").write_text("", encoding="utf-8")
    (src / "product" / "pages" / "__init__.py").write_text("", encoding="utf-8")
    (src / "product" / "pages" / "render.py").write_text(
        "from product.evidence.load import loaded\n", encoding="utf-8"
    )

    reached = reachable(src / "product" / "pages", src, "product")

    assert "product" in reached, "the ancestor package is walked"
    offenders = [
        (module, name)
        for module, imports in reached.items()
        for name in imports
        if name.split(".")[0] in FORBIDDEN
    ]
    assert offenders == [("product", "psycopg")]


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
