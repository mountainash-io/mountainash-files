# mountainash-files

Composable file operations with format detection and parsing.
Requires Python 3.12 or later.

## Candidate verification and publishing

Public PyPI publication remains unconfirmed. `mountainash-transport>=26.7.0` and its settings/auth-client/secrets closure must be public before candidate verification can pass; local sibling wheels are diagnostic inputs only.

`build-and-release-package.yml` builds and verifies PR/manual candidates using Python 3.12, fresh external wheel/sdist installations, public PyPI dependencies, `pip check` and module-origin evidence.

Prepare the final version through the normal reviewed release PR. Separately configure the `pypi` GitHub environment with human reviewers and a custom deployment policy allowing only the `main` branch, plus a PyPI Trusted Publisher for this repository, workflow filename `build-and-release-package.yml`, and environment `pypi`. A pending publisher does not reserve the name.

Publication requires an authorized manual `main` run with `publish=true` and environment approval. It uploads the exact verified artifact IDs/hashes, never rebuilds or uses `skip-existing`, and confirms public hashes and installation afterward. `publish=false` and PR runs remain candidate-only.

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
