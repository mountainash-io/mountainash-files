# Documentation sources

`site/` holds the mountainash-files textbook: MkDocs configuration and the
published Markdown. Everything else here is an internal planning or refresh
artifact. None of it is published.

## Publishing

The [production textbook](https://docs.mountainash.io/mountainash-files/) is
built from `main`; the
[development textbook](https://docs.mountainash.io/mountainash-files/dev/) is
built from `develop`. `.github/workflows/deploy-textbook.yml` builds both branch
snapshots strictly on each push to either branch that touches `docs-site/`, and
publishes them together as one Pages artifact. A failed build leaves the
previous paired site live.

Until a release brings `docs-site/` to `main`, the workflow publishes the
`develop` snapshot alone at `/mountainash-files/dev/`, and the root redirects there.
The first push to `main` that includes the textbook switches to the paired site.

Publishing is off until it is activated:

1. Enable GitHub Pages for the repository with GitHub Actions as the source.
   Leave the custom domain blank: the organisation site `mountainash-io.github.io`
   owns `docs.mountainash.io`, and every repository's Pages site is served under it
   at `/<repository>/`.
2. Set the repository Actions variable `TEXTBOOK_PUBLISHING_ENABLED` to `true`.
3. Push a `docs-site/` change to `develop`, or, once the workflow is on `main`,
   dispatch `deploy-textbook.yml` manually. GitHub offers manual dispatch only for
   workflows on the default branch.

Until the variable is set, publishing runs are skipped.

## Source artifacts

- `profile/`: package documentation profile, with source provenance in `manifest.json`.
- `editorial-brief.md`: confirmed audience, scope and editorial decisions.
- `learning-graph/`: concept graph with module and chapter mappings, plus quality reports.
- `chapter-plan.md`: approved chapter and section structure.
- `site/`: MkDocs configuration and textbook Markdown.

## Local preview

From the repository root, without installing the package or sibling checkouts:

```bash
uv run --no-project --with-requirements docs-site/requirements.txt \
  python -m mkdocs serve --config-file docs-site/site/mkdocs.yml
```

## Refreshing content

Refreshes are manual and use the `textbook-refresh` and
`package-documentation-profile` skills from mountainash-ibook-skills, with this
repository's root as the source. Do not regenerate content merely to publish
it. Code examples in the chapters were run against source revision
`0ee86bc` with the sibling packages at their `origin/develop` heads on
2026-10-29. A later package change can invalidate them, so re-run them during a
refresh.
