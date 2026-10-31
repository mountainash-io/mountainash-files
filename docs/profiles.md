# Storage profiles and the 0.1 baseline

[README](../README.md) · [Named-profile recipe](../examples/named_profiles/)

Files uses transport's storage and authentication profiles; secret resolution
remains owned by settings and transport. A file spec accepts a materialised
storage profile or a name. An explicit `auth_profile` object overrides the
authentication paired with a named profile.

## Named profiles

Set `MOUNTAINASH_PROFILES_CONFIG` to a YAML file with a `storage_profiles:` section
and pass `storage_profile="<name>"` on `FileSourceSpec` or `FileSinkSpec`:

```yaml
storage_profiles:
  reports:
    provider: local
    auth:
      mode: none
```

Alternatively, use `resolve_storage()` with explicit `SettingsParameters` and
pass the returned pair to the spec. The [offline recipe](../examples/named_profiles/)
demonstrates both routes with a local profile. A remote profile requires the
appropriate transport backend, optional dependencies and credentials.

## Optional location confinement

Confinement is off by default. `ROOT_PATH` resolves relative paths, but does not
reject an absolute outside path or `..`. Enable confinement in an existing
profile, for example:

```yaml
storage_profiles:
  reports:
    provider: local
    parameters:
      ROOT_PATH: /srv/reports
      LOCATION_POLICY: {}
```

An omitted `FileSourceSpec.policy` or `FileSinkSpec.policy` inherits the resolved
profile policy. Explicit `policy=None` disables it; a `LocationPolicy` replaces
it without merging remote allow-lists. This applies to parsing, streaming,
schema inspection, glob/archive children, writing and each copy endpoint
independently. Disabling source confinement never disables the sink's policy.

For trusted access outside the configured root:

```python
source = FileSourceSpec(
    path="../archive.csv", storage_profile="reports", policy=None,
)
```

This does not disable authentication, TLS verification, SSH target validation or
OS permissions. Migration: profiles that previously relied on `ROOT_PATH`
implicitly confining access must now set `LOCATION_POLICY={}`. Profile settings
require the existing `[http]` extra; unprofiled local access remains base-safe.


## Secret references

For a profile containing `secret:record.field`, explicitly select a store and
resolve the pair before constructing the file spec. This application fragment
requires an existing private store directory and a `profiles.yaml` containing
the `source` profile and its secret references:

```python
from pathlib import Path

from mountainash_files import FileSourceSpec, parse
from mountainash_settings import FilesystemBackend, SettingsParameters
from mountainash_transport import resolve_storage

# The application securely creates and owns this existing private directory.
private_store_directory = Path("/private/config-records")
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

## Migration and publication

Named profiles without custom secret references continue to use
`MOUNTAINASH_PROFILES_CONFIG`. Applications using custom secret references must
select a reader at their boundary as shown above.

The coordinated development baseline is **0.1.0**, with transport and its
forwarded extras bounded to `>=0.1.0,<0.2`. Hatch selects sibling source checkouts;
verification records the exact commits and artifact hashes. Publication remains
a separate gate from develop integration. See [release procedures](../RELEASE.md).
