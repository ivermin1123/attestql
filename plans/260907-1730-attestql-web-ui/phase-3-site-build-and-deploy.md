# Phase 3: the site build, landing and method pages, a preview deployment

Status: DONE 2026-09-08. Seven commits on `ivermin1123/web-ui` (`e8632c7` to `b26854e`), with
`just check` green at each. The build makes 56 files and 525,006 bytes in a tenth of a second, the
preview serves it at <https://attestql-ui.pages.dev>, and attestql.com is byte identical to
`site/index.html`. An in-worker review found fifteen things, the first a path traversal the filter
pages introduced, reproduced and repaired in `b26854e`; the coordinator's review on Fable found six
more, the first being that every published page carried the builder's home directory, repaired in
`1e1780d`. Report, with the browser measurements and
the screenshots: `plans/reports/cook-260908-0932-web-ui-phase-3-site.md`. What is left is phase 4's
data, the keyboard stop on a wide table, and the owner's switch; steps 3 and 4 below are done from
one network, which the report states.

## Context

attestql.com is live (main session, 2026-09-07 18:05): Cloudflare Pages project `attestql` under
the owner's personal account, custom domain attached, one CNAME `attestql.com` to
`attestql.pages.dev`, proxied. It serves `site/index.html` from `main` (commit `768fe4f`),
deployed by hand from a directory outside the repository with
`npx wrangler@4.129.0 pages deploy <repo>/site --project-name attestql --branch main`
(wrangler leaves a `.wrangler/` cache in its working directory). The main session owns
`site/index.html` and `README.md` and is changing both for an `attestql demo` opening; neither
is edited by this plan. Experiments go to a separate Pages project on a `pages.dev` address; the
domain moves only on the owner's word.

The renderer from phase 1 produces run and question pages. This phase builds the whole site,
with its own landing and method pages, into a directory outside `site/`, and deploys it to a
preview project. Replacing what attestql.com serves is the owner's step at the end.

## Requirements

- `tools/site/build.py` renders every run under `tools/site/data/<benchmark>/<run>/` with the
  phase 1 renderer into `build/site/runs/<benchmark>/<run>/`, one benchmark index per benchmark,
  then `build/site/index.html` (landing) and `build/site/method/index.html` from templates under
  `tools/site/templates/`, reusing the package's base template, stylesheet and fonts. `build/` is
  already ignored by git.
- Landing content, in this order: one sentence, the package description from `pyproject.toml`
  read at build time; the demo run and its unedited output, produced at build time by
  `attestql demo --out` (its `run_id` and time are the build's own and the page says so); the
  trimmed `counterexample.json` of q879 from that run; the sentence "NOT_EQUAL never means the
  gold is wrong"; three numbers rendered from the aggregate the selection script of phase 4
  writes, each with its source file named in a title attribute (the wrong-but-credited count
  from the PostgreSQL prediction classification, the credited-but-not-equal total over the nine
  PostgreSQL runs against the gold copy the aggregate names, the BIRD dev gold count from the
  BIRD dev classification); the install line; the benchmark index with each run's date, engine,
  question set origin and digest; the three links the current page has. Nothing on it is typed
  by hand that an artifact states.
- Method page: R-ORD and R-SET, the serializer descriptor, the seven preconditions, the probes
  with their `reading` strings, the two benchmark readings computed beside every verdict, and the
  principle sentence. Generated from the strings the package holds where they exist, so the page
  cannot drift from the code; links to `docs/audit-command.md` for the flags.
- Budgets: the account is on the Free plan (owner, 2026-09-07): 20,000 files per site, 25 MiB
  per file. The build fails over 8,000 files, over 40 MB in total, or with any single page over
  2 MB, and prints the offenders. Phase 4's dry run of the selection script confirms the
  selection fits these numbers before any run is published; if it does not, the selection
  narrows, never the budget.
- Preview deployment: from a directory outside the repository,
  `npx wrangler@4.129.0 pages deploy <repo>/build/site --project-name attestql-ui --branch web-ui`.
  The `attestql-ui` project is created once by the owner (or by the first deploy with the
  owner's token); its `pages.dev` address is the review URL. Nothing in this phase touches the
  `attestql` project, the domain or the DNS record.
- Owner step, recorded and not performed by a session: when the built site should replace
  `site/index.html` on attestql.com, deploy `build/site` to project `attestql` with the same
  command, and retire `site/index.html` in a commit on `main`. Until then both exist.
- A GitHub Actions deployment (the owner's preference stated 2026-09-07) is added only at that
  switch, targeting whichever project the owner names, with a Pages-scoped token and the account
  id as repository secrets.

## Files

- `tools/site/build.py`, `tools/site/templates/landing.html`, `tools/site/templates/method.html`,
  `tools/site/README.md` (what the directory is, how to build, how to deploy the preview).
- `tools/site/data/<benchmark>/<run>/` (phase 4 fills it; this phase builds with the sandbox
  output as a stand-in and says so in a banner that phase 4 removes).
- `docs/developer-environment.md`: one paragraph on building the site locally.

## Steps

1. Write the build script and the two templates; run it on the sandbox output; open
   `build/site/index.html` locally.
2. Add the size check and the stand-in banner.
3. Owner creates `attestql-ui` (or authorises the first deploy); deploy the preview from outside
   the repository with the command above; record the `pages.dev` URL in `tools/site/README.md`.
4. Verify from a second network that the preview serves the landing page, a question URL and its
   JSON link.

## Validation

- `uv run python tools/site/build.py` on the sandbox data completes under budget.
- The preview URL serves the built site; attestql.com still serves `site/index.html` unchanged.

## Risk and rollback

- The landing's opening command follows the tool by construction; if `attestql demo` lands with a
  different output shape, the build script's one line changes, not the page.
- Rollback: delete `tools/site/` and the preview project; nothing served on attestql.com changes.
