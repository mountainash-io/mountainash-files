# mountainash-files

Composable file operations with format detection and parsing.
Requires Python 3.12 or later.

## Candidate verification and publishing

Public PyPI publication remains unconfirmed. Candidate verification does not require
the MountainAsh dependency chain to be published first: it builds approved sibling
wheels for settings, secrets, auth-client, and transport from branch-aware checkouts.
Other dependencies resolve from public PyPI. Consumers still need compatible
MountainAsh siblings; a standalone public-PyPI-only installation is not yet claimed.

`build-and-release-package.yml` builds a wheel and sdist with Python 3.12 and
verifies both in fresh environments outside the checkout, including dependency
consistency, import origins, and matching sdist-derived metadata. Evidence records
artifact hashes, sibling revisions/hashes, installation reports, and full/direct
SBOMs. Runtime dependency bounds are unchanged.

Open PRs and default manual runs are candidate-only. Merged PRs publish the exact
verified artifacts to a GitHub release and open a `develop` PR in
`mountainash-io/mountainash-wheels` containing the verified wheel. Merges into
`develop` produce `rc` versions; `main` uses the reviewed source version; other
supported targets produce beta versions. Generated suffixes are not committed.

Manual runs expose independent `release` (GitHub/wheels) and `publish` (PyPI) flags,
both false by default, plus `release_type` (`production`, `rc`, or `beta`) and
`fallback_branch` (`develop` or `main`). For example, a candidate-only rehearsal:

```sh
gh workflow run build-and-release-package.yml --repo mountainash-io/mountainash-files \
  --ref develop -f release=false -f publish=false \
  -f release_type=production -f fallback_branch=develop
```

Publication prerequisites:

- Make `CI_APP_ID` and `CI_APP_PRIVATE_KEY` available to this repository. The App
  installation needs read access to the four runtime siblings and test-only
  `mountainash`, plus **Contents: write** and **Pull requests: write** on
  `mountainash-wheels`. Read-only wheels access is insufficient: the transport
  rollout reached the wheels push and failed with HTTP 403. Grant access before
  enabling distribution; workflows do not suppress permission failures.
- Make `CODECOV_TOKEN` available for the pytest report uploads.
- For PyPI, configure a `pypi` GitHub environment requiring human reviewers and
  allowing only the `main` branch through a custom deployment policy. Configure
  a PyPI Trusted Publisher for this repository, workflow
  `build-and-release-package.yml`, and environment `pypi`.

PyPI publication requires an authorized manual `main` run with `publish=true`,
`release_type=production`, and environment approval. It uploads the exact verified
wheel/sdist and checks public hashes and installation with the approved sibling
wheels afterward. No rebuild, asset replacement, or `skip-existing` fallback is
used. Use `release=false` for a PyPI-only run when the GitHub release already exists.

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
