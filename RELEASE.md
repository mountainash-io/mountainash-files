# Candidate verification and publishing

[README](README.md) · [Contributing](CONTRIBUTING.md)

`build-and-release-package.yml` deliberately separates the branch-aware,
sibling-wheel **development rehearsal** from public-PyPI readiness. The rehearsal
builds approved settings, secrets, auth-client, and transport sibling wheels from
checked-out sources, then verifies files' wheel and an sdist-derived wheel in fresh
external environments. Its evidence records artifact hashes, sibling revisions and
hashes, install reports, module origins, and full/direct SBOMs. Runtime dependency
bounds remain unchanged.

The opt-in `verify-public` job downloads the exact rehearsal wheel/sdist and
evidence artifact IDs, rechecks the `release.json` filenames and hashes, builds a
fresh wheel from the sdist, and verifies both wheels in temporary environments. It
uses public PyPI only for dependencies and build tools, source-checks static and
backend-reported dynamic build requirements, retains their actual install reports,
never consults the sibling wheelhouse, and rejects missing or non-public
install-report sources. The rebuilt wheel is verification evidence only; it is
never published.

Public verification requires compatible PyPI wheels for dependencies and build
tools. Source-only dependencies cannot pass and are not built implicitly; the
candidate's own sdist is still rebuilt through the controlled path.

For a no-publication public-only rehearsal on any allowed branch:

```sh
gh workflow run build-and-release-package.yml --repo mountainash-io/mountainash-files \
  --ref develop -f verify_public=true -f release=false -f publish=false \
  -f release_type=production -f fallback_branch=develop
```

Open PRs and default manual runs are development-rehearsal-only. Merged PRs publish
the exact verified artifacts to a GitHub release and open a `develop` PR in
`mountainash-io/mountainash-wheels`. Merges into `develop` produce `rc` versions;
`main` uses the reviewed source version; other supported targets produce beta
versions. Generated suffixes are not committed.

Manual runs expose independent `release` (GitHub/wheels), `publish` (PyPI), and
`verify_public` flags, all false by default, plus `release_type` (`production`,
`rc`, or `beta`) and `fallback_branch` (`develop` or `main`). Publication requires
an authorized manual `main` run with `publish=true`, `release_type=production`,
both a successful public-only gate and protected-environment approval. It uploads
the exact verified wheel/sdist with unchanged OIDC and hash confirmation; no
rebuild, asset replacement, or `skip-existing` fallback is used. Post-publication
installation accepts only `distribution==version` from public PyPI and rejects
every local/non-public dependency source. Use `release=false` for a PyPI-only run
when the GitHub release already exists.

See the [shared release procedures](https://github.com/mountainash-io/mountainash-central/blob/main/05.devops/releases/shared/README.md)
for the distinction between source/wheelhouse rehearsal, public-only readiness, and
actual publication.

**These packages remain unready and unpublished.** Until the entire runtime
dependency chain is public, a missing dependency is a correct public-only readiness
failure; no successful end-to-end public-PyPI install is claimed.
