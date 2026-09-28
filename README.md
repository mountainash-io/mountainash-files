# mountainash-files

Composable file operations with format detection and parsing.

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

### Settings 0.1 candidate migration

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

The transport `>=26.7.0,<27` range is provisional for the migration rehearsal:
the published 26.7.0 wheel is not the migrated candidate. Verification must pin
the exact transport/settings/auth-client artifacts, and the dependency floor
must advance to the migrated transport release before publication. Downstream
merge/publication remains on hold until settings 0.1.0 is published. This work
does not qualify remote services or the separate mountainash consumer release.

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
