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

Requires Python 3.12 or newer.

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

CSV/TSV serialization preserves representable lexical values, including delimiters,
quotes, and embedded line breaks. Unrepresentable values raise `WriteError` before
the destination is written. Set `null_sequence` to represent nulls explicitly;
non-null values (including column names) equal to that marker are rejected.
Without a null marker, nulls retain the empty-field representation. Parsing keeps
ordinary type inference, so lexical preservation does not promise Arrow type
round-tripping. TSV uses tabs by default and does not support append.

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

## Write modes

```python
import pyarrow as pa
from mountainash_files import FileSinkSpec, write

write(FileSinkSpec(path="rows.parquet", write_disposition="replace"),
      pa.table({"x": [1]}))
write(FileSinkSpec(path="rows.parquet", write_disposition="append"),
      pa.table({"x": [2]}))  # stores rows 1, then 2
```

`replace` is the default. Tabular `append` reads the complete existing table,
combines it with the incoming rows, and rewrites the destination. A missing
destination is created. Supply an Arrow table, a record dictionary, or a list
of record dictionaries. Raw bytes (including bytearray and memoryview) are
rejected for append. Formats must declare both `APPENDABLE` and `TABULAR`;
plugins must parse their complete table as an Arrow table. Parquet read-column
projection is ignored when loading the append target.

Ordered column names and Arrow types must match exactly: no implicit casts,
column reordering, or schema evolution. `AppendSchemaMismatchError`, a public
`WriteError` subclass, exposes `path`, `expected_schema`, and `actual_schema`.
Existing schema and field metadata are retained; each field is nullable if
either input allows nulls. Typed empty tables obey the same rules; an untyped
empty list has a zero-column schema and does not infer the target's schema.

Append requires full read/write access and single-writer use. Configure a
symmetric transport `Pipeline` explicitly through the sink's `transforms`
for compression/encryption; append uses it for both reading and writing.
Without one, suffixes such as `.gz` do not enable transforms during append.
Permission and parse errors propagate. Format, input, schema, and serialization
validation finish before the first destination write.

The entire read-modify-write is in memory and rewrites even compatible empty
appends. It offers no atomicity or crash recovery beyond the current transport
guarantees; an interrupted write can damage the destination and concurrent
writers can lose updates. `copy` remains byte replacement, not table append.

## Settings 0.1 candidate migration

Files uses transport's storage and authentication profiles; secret resolution
remains owned by settings and transport. Named profiles without custom secret
references continue to use `MOUNTAINASH_PROFILES_CONFIG` as above.

For a profile containing `secret:record.field`, explicitly select a store and
resolve the pair before constructing the file spec:

```python
from mountainash_files import FileSourceSpec, parse
from mountainash_settings import FilesystemBackend, SettingsParameters
from mountainash_transport import resolve_storage

# The application securely creates and owns this existing private directory.
with FilesystemBackend(private_store_directory) as store:
    parameters = SettingsParameters.create(
        config_files=["profiles.yaml"], secret_store=store,
    )
    storage, auth = resolve_storage("source", settings_parameters=parameters)

# The resolved profiles can be used after the application closes the store.
results = parse(FileSourceSpec(
    path="https://example.com/data.csv", storage_profile=storage, auth_profile=auth,
))
```

There is no global provider-name secret selection. Passing only a profile name
whose configuration contains custom secret references fails without a selected
reader; local files need no store. Files does not acquire store ownership.

The coordinated development baseline is **0.1.0**, with transport and its
forwarded extras bounded to `>=0.1.0,<0.2`. Hatch selects sibling source checkouts;
verification records the exact commits and artifact hashes. Publication remains
a separate gate from develop integration.

## Tests

`python -m pytest` runs the core suite with core dependencies and pytest,
pytest-mock, and packaging installed. Optional dependencies are path-selected:

```sh
# In a separate environment with mountainash-files[xlsx] installed:
python -m pytest tests_optional/xlsx
# In a separate environment with mountainash-files[xml] installed:
python -m pytest tests/test_xml.py tests_optional/xml
```

The XLSX fixture is tracked under `tests/fixtures`; core tests never generate it
or require an XLSX engine. Optional cohorts fail if their declared dependency is
missing rather than skipping unrelated tests. The
`tests_optional/mountainash/test_relation.py` cohort additionally needs a
compatible mountainash installation and belongs to the subsequent consumer
qualification; it is excluded from the default suite. Existing Hatch/uv sibling
source configuration is development convenience, not installed-artifact proof.

## License

MIT
