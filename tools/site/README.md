# The site

What is served at a URL: the runs rendered by `attestql report`, plus a landing page and a page
about the method that this directory owns. The renderer lives in the package
(`src/attestql/report/`); this directory is the site built out of it, and the two templates here
extend the package's base page and take its stylesheet, its script and its fonts, so there is one
design and not two.

```text
tools/site/build.py            the build
tools/site/templates/          landing.html, method.html, runs.html, benchmark.html, group.html
tools/site/data/               the published runs; see its README
build/site/                    where a build goes; git ignores build/
```

A benchmark holds runs, and on an engine where one connection is one database file it holds
groups of them: a question set naming eleven databases is eleven invocations of the audit, so a
prediction file is a group and the address of a run is one segment deeper
(`runs/minidev-sqlite/gpt-4/formula_1/`). A group has a page of its own and a line on its
benchmark's index stating the sums of its runs' counts, which they can be because no question is
in two of them; it is never a merged `summary.json`. `build.py` reads both shapes and needs to
be told nothing.

Every page takes the stylesheet, the script and the three font files from the one `static/` at
the site's root rather than carrying a copy of them: at 121 runs a copy per run would be a tenth
of everything the site is allowed to weigh. A report `attestql report` writes still carries its
own, so a directory it wrote opens on its own.

## Build

```sh
uv run python tools/site/build.py
```

It writes `build/site/` and prints the file count, the total bytes and the wall time. `--out`
moves the output; an `--out` inside `site/` is refused, because that directory holds the page
attestql.com serves today and belongs to another session, and an `--out` that is not empty and
holds no `.attestql-site` marker is refused untouched, because a build empties only a directory
of its own.

The build is refused, with what pushed it over named, at more than 8,000 files, more than 40 MB
in total, or any single page over 2 MB. Those are under the Cloudflare Pages Free plan's own limits (20,000
files a site, 25 MiB a file), so a run can be added to a passing build without a re-plan. The
answer to a build over budget is a narrower selection of questions and never a larger budget.

While `tools/site/data/` holds no benchmark, the build audits the sandbox the package carries
and renders that, under the benchmark `sandbox` and the run `demo`, with a banner on every page
saying the published runs arrive with the next phase. The banner is removed by a benchmark
directory appearing under `data/` and not by an edit to a template. Since 2026-09-08 that
directory holds the five published audits, so the banner is on no page of a build; the tests
that are about that state point `data/` at a directory that is not there.

## Deploy the preview

Cloudflare Pages project `attestql-ui`, a preview of its own with nothing attached to it. Run
this from a directory outside the repository: wrangler leaves a `.wrangler/` cache where it runs,
and that cache is not repository content.

```sh
cd "$TMPDIR"
npx --yes wrangler@4.129.0 pages deploy <repo>/build/site \
    --project-name attestql-ui --branch web-ui
```

Preview URL, deployed 2026-09-08: <https://attestql-ui.pages.dev>. Each deploy also prints an
address of its own for that one deployment; the current one, the first to serve the published
runs, is <https://b5a78fd6.attestql-ui.pages.dev>.

The demo the build audits runs at a fixed `/tmp/attestql-site-sandbox`, not under `build/`. The
SQLite backend records the absolute path of the file it opened and every question page states it,
so where the demo runs is published: the path is chosen to name no user, no repository and no
build location.

## attestql.com

attestql.com serves this build since 2026-09-08, on the owner's word. `.github/workflows/site.yml`
builds the site with the command above on every push to `main` and publishes it to the Cloudflare
Pages project `attestql`, whose production branch is `main` and which holds the domain; a manual
run of the same workflow publishes whichever ref it was started on to the preview project
`attestql-ui` instead, so a branch can be looked at before it is merged. The workflow reads two
repository secrets, `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`, the token holding
"Cloudflare Pages: Edit" on that account and nothing else; wrangler takes both from the
environment and neither reaches a log. The first deployment was made by hand from outside the
repository with the command of the previous section and `--project-name attestql --branch main`.
The domain and the DNS record were not touched: the project already held them. `site/index.html`
is no longer what the domain serves; it stays in the repository as the source of the three links
the landing carries until the session that owns it retires it.
