# The site

What is served at a URL: the runs rendered by `attestql report`, plus a landing page and a page
about the method that this directory owns. The renderer lives in the package
(`src/attestql/report/`); this directory is the site built out of it, and the two templates here
extend the package's base page and take its stylesheet, its script and its fonts, so there is one
design and not two.

```text
tools/site/build.py            the build
tools/site/templates/          landing.html, method.html, runs.html, benchmark.html
tools/site/data/               the published runs (phase 4 fills it; see its README)
build/site/                    where a build goes; git ignores build/
```

## Build

```sh
uv run python tools/site/build.py
```

It writes `build/site/` and prints the file count, the total bytes and the wall time. `--out`
moves the output; an `--out` inside `site/` is refused, because that directory holds the page
attestql.com serves today and belongs to another session, and an `--out` that is not empty and
holds no `.attestql-site` marker is refused untouched, because a build empties only a directory
of its own.

The build fails, naming what pushed it over, at more than 8,000 files, more than 40 MB in total,
or any single page over 2 MB. Those are under the Cloudflare Pages Free plan's own limits (20,000
files a site, 25 MiB a file), so a run can be added to a passing build without a re-plan. The
answer to a build over budget is a narrower selection of questions and never a larger budget.

While `tools/site/data/` holds no benchmark, the build audits the sandbox the package carries
and renders that, under the benchmark `sandbox` and the run `demo`, with a banner on every page
saying the published runs arrive with the next phase. The banner is removed by a benchmark
directory appearing under `data/` and not by an edit to a template.

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
address of its own for that one deployment; the first was
<https://843f9699.attestql-ui.pages.dev>.

## What this does not touch

The `attestql` project, the domain and the DNS record. attestql.com serves `site/index.html` from
`main` and keeps serving it until the owner decides otherwise; deploying this site there, and
retiring `site/index.html`, is an owner step and not a session's. A GitHub Actions deployment is
added at that switch and not before.
