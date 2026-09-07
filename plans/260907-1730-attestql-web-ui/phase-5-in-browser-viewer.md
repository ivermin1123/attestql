# Phase 5: the drop zone in the browser

Accepted by the owner 2026-09-07 18:40. Runs after phase 4.

## Context

A person with a private audit should be able to open it on attestql.com without the data
leaving their machine. That needs the Python renderer to run in the browser, so that there is one
implementation and not two. Pyodide runs CPython in WebAssembly and can install a pure-Python
wheel from a URL. Hash verification is not a reason for this phase any more: phase 1's loader
recomputes every hash at render time and the CLI's pages carry the result.

Measured 2026-09-07 on the jsdelivr CDN, Pyodide 314.0.6 (CPython 3.14.2), brotli-compressed
transfer sizes: `pyodide.asm.wasm` 3.44 MB, the standard-library archive 2.51 MB, the loader under
10 KB. Jinja2 3.1.6 and MarkupSafe 3.0.3 are in Pyodide's own package lock. The attestql wheel is
155 KB. Total to first render of a dropped audit: about 6.3 MB, paid once per browser and cached
after, on the page that offers the drop zone only; no other page loads any of it.

Import audit (OBSERVED): `attestql.evidence`, `attestql.kernel` and `attestql.contract` import
only the standard library. The engine bindings (`psycopg`, `postgast`, `sqlglot`) are imported
only under `attestql.audit`. The phase 1 renderer therefore imports only the standard library,
Jinja2 and `attestql.evidence`, and phase 1 gains a test that keeps it so.

## Requirements

- A page `/viewer/` with one drop zone accepting a whole `audit/` directory (directory drop or a
  zip) or any single one of the four files, recognised by its `format` string. Nothing is
  uploaded; the page states so beside the drop zone.
- The page loads Pyodide only after the first drop, with a progress state that names the size
  being fetched and the step (runtime, packages, rendering). Pyodide files are served from the
  site itself (each under Cloudflare Pages' 25 MiB per-file limit) so the page has no
  third-party dependency at run time; the CDN is the fallback if the size budget of phase 3
  cannot hold them.
- Rendering calls the same `attestql.report` entry point the CLI calls, on an in-memory
  filesystem, and shows the result inside the page (a sandboxed `iframe` whose document is set
  from the rendered string).
- The wheel is installed with Pyodide's package installer with dependency resolution off: its
  `Requires-Dist` names `psycopg`, `postgast` (C, no wasm wheel) and `sqlglot` (not in Pyodide's
  lock), none of which the renderer imports, and a plain install would reach PyPI, which the
  acceptance forbids.
- The `tzdata` wheel is bundled with the runtime and installed before the package: Pyodide ships
  no time zone database and `attestql.evidence.serialize` calls `ZoneInfo` for timestamp cells.
- The dropped audit's hashes are recomputed by the same loader the CLI uses (phase 1), so the
  rendered pages carry the same "recomputed from this JSON" line.
- `prefers-reduced-motion` and keyboard operation as in the design spec; the drop zone is also a
  file input.

## Files

- `tools/site/templates/viewer.html`, `tools/site/static/viewer.js` (the shim: read files, boot
  Pyodide, install the wheel from `build/site/wheel/`, call the renderer, place the HTML).
- `tools/site/build.py`: copy the Pyodide runtime files and the built wheel into `build/site/`,
  and raise the size budget accordingly (about 14 MB uncompressed for the runtime).
- `tests/test_report_imports_no_engine.py` (lands in phase 1).
- A Playwright test under `tools/site/tests/` that drops the demo audit and the stress
  directory and asserts the rendered verdict strip and the recomputed-hash line.

## Steps

1. Build the wheel in `tools/site/build.py`; serve it beside the site with the `tzdata` wheel.
2. Write the shim against the CDN first; measure boot time on a laptop and on a throttled
   connection; record both.
3. Move the runtime files into the site; confirm the Pages deploy accepts them.
4. Playwright test; the reduced-motion and keyboard walk; the size and time numbers into the
   verification report.

## Validation

- The drop zone renders the demo audit, the PostgreSQL sandbox audit and the stress directory
  with no network request other than the site's own files, and every record's recomputed-hash
  line reads "match".

## Risk and rollback

- Pyodide tracks CPython closely (314.x is Python 3.14); the package must stay importable on
  the Python that Pyodide ships, which the Playwright test checks.
- The Playwright test drops the stress directory of phase 2, which has a timestamp column,
  so a missing `tzdata` fails the test rather than a visitor's page.
- Rollback: remove `/viewer/` and the runtime files; published pages keep their static hash
  display.
