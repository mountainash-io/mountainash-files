# mountainash-files

Composable file operations with format detection and parsing.
Requires Python 3.12 or later.

## Candidate verification and publishing

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

Public verification requires compatible PyPI wheels for dependencies and build tools. Source-only dependencies cannot pass and are not built implicitly; the candidate's own sdist is still rebuilt through the controlled path.

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

## Development and tests

Keep sibling checkouts next to this repository: `mountainash-settings`,
`mountainash-secrets`, `mountainash-auth-client`, `mountainash-transport`, and
`mountainash`. Hatch bootstraps the runtime siblings before installing files:

```sh
hatch run test:test
hatch run test:cov
```

CI checks out the four runtime siblings into `temp/` from the PR head branch
(or dispatched ref), falling back to the PR base branch (or `fallback_branch`).
The pytest workflow separately checks out test-only `mountainash`, then runs
`hatch run test_github:cov`. All tests under `tests/`, including cross-package
integration tests, run; sibling repositories' own suites are not collected.
Hatch owns local/CI source paths rather than a conflicting local-only uv override.
The `build_github` environment supplies the SBOM commands. Main-targeting PRs also
validate runtime dependencies and require a `release/*` or `hotfix/*` source branch.

## Overview

This package provides a unified interface for file operations across multiple file formats with automatic format detection and parsing capabilities.

## Support matrix

### Formats

| Format | Parse | Serialise | Append | Extra |
|---|---|---|---|---|
| csv / tsv | ✅ | ✅ | — | core (pyarrow) |
| json | ✅ | ✅ | — | core (pyarrow) |
| parquet | ✅ | ✅ | ✅ | core (pyarrow) |
| xlsx | ✅ | — | — | `[xlsx]` (fastexcel or openpyxl) |
| xml | ✅ | ✅ | — | core (stdlib); `[xml]` for lxml |

### Storage (via mountainash-transport)

| Provider | Status | Extra |
|---|---|---|
| local | ✅ implemented | core |
| http/https | ✅ implemented | core |
| s3 (aws/express/r2/minio/b2) | ✅ implemented | `[s3]` |
| sftp | ✅ implemented | `[sftp]` |
| gcs, azure, ftp, smb, github | profile-only (backend pending in transport) | — |

Named profiles: set `MOUNTAINASH_PROFILES_CONFIG` to a YAML config with a
`storage_profiles:` section and pass `storage_profile="<name>"` on any
`FileSourceSpec`/`FileSinkSpec`. Missing extras raise `MissingDependencyError`
naming the exact extra to install.

## License

MIT
