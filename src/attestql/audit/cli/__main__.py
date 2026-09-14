"""``python -m attestql.audit.cli``, which runs the same ``main`` the console script runs.

This form is new with the package. The command was one module until the split of 2026-09-14
and that module carried no ``__main__`` guard, so ``python -m attestql.audit.cli`` imported
it, defined everything in it and ran no command at all. A package cannot be run that way
without a ``__main__`` module, so here is one.

The entry point is still ``pyproject.toml``'s ``attestql.audit.cli:main``. This calls that
same function and decides nothing of its own.
"""

from __future__ import annotations

from attestql.audit.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
