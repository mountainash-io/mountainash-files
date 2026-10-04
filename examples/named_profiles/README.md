# Named profiles

How do I select storage from configuration?

[example.py](example.py) — run from the repository root after the [shared setup](../README.md#setup):

```bash
python examples/named_profiles/example.py
```

Expected output:

```text
reports: local storage with NoAuthProfile
named and resolved profiles: 2 matching rows
```

[profiles.yaml](profiles.yaml) declares a local store with no credentials.
The recipe temporarily points `MOUNTAINASH_PROFILES_CONFIG` at it, then writes
and parses using `storage_profile="reports"`. It also resolves the pair using
explicit `SettingsParameters` and passes the objects directly to a source spec.

The application owns configuration selection. Custom `secret:record.field`
references need an explicitly selected secret reader before constructing the
file spec; see [profiles and migration](../../docs/profiles.md). Remote storage
uses the same spec fields but needs a supported backend and appropriate auth.

Return to the [recipe index](../README.md).
