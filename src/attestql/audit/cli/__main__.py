"""``python -m attestql.audit.cli``, which is the console script by another name.

The command was one module until the split of 2026-09-14, and a module run this way executes
its own body; a package does not, so the entry point is stated here rather than being lost in
the move. ``pyproject.toml`` names ``attestql.audit.cli:main`` and that is what this calls.
"""

from __future__ import annotations

from attestql.audit.cli import main

raise SystemExit(main())
