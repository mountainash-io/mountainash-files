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

Publishing is off until it is activated:

1. Merge the textbook into `develop` and then, through a release, into `main`.
   The production build needs `docs-site/site/` on `main`.
2. Enable GitHub Pages for the repository with GitHub Actions as the source,
   with its `github-pages` environment and the shared custom domain used by the
   other mountainash textbooks.
3. Set the repository Actions variable `TEXTBOOK_PUBLISHING_ENABLED` to `true`.
4. Manually dispatch `deploy-textbook.yml`.

Until then, publishing runs are skipped, so a one-sided bootstrap cannot deploy
an incomplete site.

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
