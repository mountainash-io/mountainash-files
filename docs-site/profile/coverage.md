# Profile coverage — mountainash-files

Source `0ee86bcc` on `docs/package-profile`. Requested behaviour: full (initial profile; no prior profile existed, so `previous_hash` is null).

Discovered 26 modules: 25 profiled, 1 ignored.

## Missing

None. Every in-scope module has a profile.

## Stale

None. Every record carries the target source hash.

## Orphaned

None. This is the first profile for this package.

## Ignored

- `src/mountainash_files/specs/__init__.py`: Pure re-export aggregator for specs.* with no behaviour; exports are recorded on the defining modules

## Low confidence

None.

## Test coverage gaps

- `mountainash_files.formats._delimited` and `mountainash_files.formats._rows` are tested only through the CSV/TSV parse and serialise paths, with no direct unit tests.
- `mountainash_files.formats._xlsx_calamine` is tested through `tests/test_xlsx_engines.py` and `tests_optional/xlsx/`, which require the `[xlsx]` extra.

## Documentation coverage gaps

- No conceptual architecture document covers the registry, the access-mode routing or the transport boundary. The only docs are `docs/advanced-usage.md` (a reference), `docs/migration-reader-engines.md` and `docs/profiles.md`.
- No format support matrix (parse / write / schema / append / access mode per format) exists. XLSX has no serialiser and only Parquet supports append; these facts are spread across the source.
- No document describes the archive hardening in `_archives.check_zip_container` (directory-ambiguity rejection, bounding of the actual inflated size).
- Examples cover users. No example shows `inspect_schema` or `register_format`.

## Audience coverage

- **users**: 8 concepts, 7 featured modules
- **maintainers**: 7 concepts, 4 featured modules
- **backend-architecture**: 6 concepts, 5 featured modules
- **broader-hype**: 3 concepts, 3 featured modules

## Open questions

- `mountainash_files`: __version__ is not re-exported from the package root, so mountainash_files.__version__ is unavailable. Is that intentional?
- `mountainash_files`: ArchiveExtractionError, ArchiveEmptyMatchError and ArchiveLimitError can reach callers but are not exported from the root. Should they be public?
- `mountainash_files.__version__`: The root package does not import this module. Should the version be exposed at runtime?
- `mountainash_files._archives`: The archive exception classes are not exported from the package root, so callers cannot catch them without a private import.
- `mountainash_files.formats._registry`: Should the internal getters (get_parser, resolve_format) become a public introspection API for extension authors?
- `mountainash_files.formats.csv`: Should an unknown dtype name in CsvSpec.dtypes raise instead of falling back to string?
- `mountainash_files.formats.parquet`: Should ParquetSpec expose writer options such as compression and row-group size?
- `mountainash_files.formats.xlsx`: Is an XLSX writer planned? The pyproject [xlsx] extra already includes openpyxl, which can write workbooks.
- `mountainash_files.specs.archive`: ZipArchive.password is typed str | None but _unpack_zip also accepts secret-like objects (get_secret_value / resolve). Should the type say so?
