# Glossary

<!-- glossary:access-mode concepts:48,104 -->
## Access mode

How a format's reader receives a file: as whole-object `bytes`, a `random` (seekable, ranged) handle, or a `sequential` stream. Each format registers its mode, and the read falls back to bytes when transforms apply or the backend refuses. See [Access routing](chapters/architecture/index.md#access-routing).
<!-- /glossary:access-mode -->

<!-- glossary:append-schema-check concepts:85 -->
## Append schema check

The rule that data appended to a Parquet file has the destination's column names and types, in the same order. Nullability may differ. A mismatch raises `AppendSchemaMismatchError`. See [The append schema check](chapters/write-modes/index.md#the-append-schema-check).
<!-- /glossary:append-schema-check -->

<!-- glossary:arrow-table concepts:2 -->
## Arrow table

A `pyarrow.Table`: named, typed columns held in Apache Arrow's columnar memory format. It is the default result of parsing a tabular format and the input that most serialisers expect. See [Arrow tables](chapters/files-specs-and-formats/index.md#arrow-tables).
<!-- /glossary:arrow-table -->

<!-- glossary:auth-profile concepts:42 -->
## Auth profile

A mountainash-auth-client object that carries the credentials a storage backend uses. An explicit `auth_profile` on a spec overrides one resolved from a named storage profile. See [Storage and auth profiles](chapters/storage-and-transforms/index.md#storage-and-auth-profiles).
<!-- /glossary:auth-profile -->

<!-- glossary:capability-flags concepts:21 -->
## Capability flags

Class attributes on a `FormatSpec` that declare what the format supports: `TABULAR` (output is normalised to Arrow or records) and `APPENDABLE` (append is allowed). See [Capability flags](chapters/format-options/index.md#capability-flags).
<!-- /glossary:capability-flags -->

<!-- glossary:decompression-limits concepts:38,71 -->
## Decompression limits

Positive caps on the decompressed bytes and the number of members an archive or Excel workbook may produce. Exceeding one raises `ArchiveLimitError` before the full payload is held in memory. See [Decompression limits](chapters/selecting-files/index.md#decompression-limits).
<!-- /glossary:decompression-limits -->

<!-- glossary:entry-point-plugin concepts:102 -->
## Entry-point plugin

An installed package that registers formats from a module listed in the `mountainash_files.formats` entry-point group. The modules are imported once, when mountainash-files is first imported. See [Entry-point plugins](chapters/custom-formats/index.md#entry-point-plugins).
<!-- /glossary:entry-point-plugin -->

<!-- glossary:file-sink-spec concepts:10 -->
## FileSinkSpec

The write-side file spec. It adds `write_disposition` (`replace` or `append`) and `create_path`, which controls whether missing parent directories are created. See [FileSinkSpec](chapters/files-specs-and-formats/index.md#filesinkspec).
<!-- /glossary:file-sink-spec -->

<!-- glossary:file-source-spec concepts:9 -->
## FileSourceSpec

The read-side file spec. It adds a `glob`, an `on_missing` policy, the transform-inference switch `infer`, and GPG and gzip transform options. See [FileSourceSpec](chapters/files-specs-and-formats/index.md#filesourcespec).
<!-- /glossary:file-source-spec -->

<!-- glossary:file-spec concepts:8 -->
## FileSpec

An immutable description of one file location: its path, an optional format, a storage profile, an auth profile, an archive, transforms and a location policy. Operations take its source or sink subclass. See [File specs](chapters/files-specs-and-formats/index.md#file-specs).
<!-- /glossary:file-spec -->

<!-- glossary:format-key concepts:13 -->
## Format key

The lowercase name a format is registered under, such as `csv`, `json` or `parquet`. It can be passed as a spec's `format`, and it appears as `format_key` on results. See [Formats and format specs](chapters/files-specs-and-formats/index.md#formats-and-format-specs).
<!-- /glossary:format-key -->

<!-- glossary:format-spec concepts:14 -->
## FormatSpec

The base class for a format's options. Each format defines a frozen dataclass subclass, such as `CsvSpec`, that declares its key, suffixes and media types, and holds the options its parser and serialiser read. See [FormatSpec](chapters/files-specs-and-formats/index.md#formatspec).
<!-- /glossary:format-spec -->

<!-- glossary:location-policy concepts:43 -->
## Location policy

A mountainash-transport `LocationPolicy` that limits which local paths and remote hosts a spec may reach. A location outside it raises `LocationNotAllowed`. See [Location policy](chapters/storage-and-transforms/index.md#location-policy).
<!-- /glossary:location-policy -->

<!-- glossary:ndjson concepts:62 -->
## NDJSON

Newline-delimited JSON: one JSON value per line. `JsonSpec(ndjson=True)` reads and writes it, and the `.ndjson` and `.jsonl` suffixes select it automatically. See [NDJSON](chapters/format-options/index.md#ndjson).
<!-- /glossary:ndjson -->

<!-- glossary:output-mode concepts:24 -->
## Output mode

The `output` argument of `parse` and `parse_bytes`: `arrow` (the default) returns tabular data as an Arrow table, and `pydata` returns a list of records. See [Arrow or Python records](chapters/reading-and-writing/index.md#arrow-or-python-records).
<!-- /glossary:output-mode -->

<!-- glossary:parse-result concepts:23 -->
## ParseResult

The value `parse` returns for each selected input. It holds `data`, the `format_key`, the `spec` used and any `skipped_members` from an archive. See [ParseResult](chapters/reading-and-writing/index.md#parseresult).
<!-- /glossary:parse-result -->

<!-- glossary:path-template concepts:30 -->
## Path template

A spec path containing `str.format` placeholders, such as `"sales/{year}.csv"`. The `params` argument of an operation fills them in. See [Path templates](chapters/selecting-files/index.md#path-templates).
<!-- /glossary:path-template -->

<!-- glossary:projection concepts:67 -->
## Projection

Reading only selected columns. `ParquetSpec.columns` projects top-level and dotted nested columns, and allows ranged reads from remote storage. See [Column projection](chapters/format-options/index.md#column-projection).
<!-- /glossary:projection -->

<!-- glossary:schema-basis concepts:78 -->
## Schema basis

How a `SchemaResult` was obtained: `metadata` (read from file metadata, such as a Parquet footer), `full` (inferred from every record) or `bounded` (inferred from a limited number of records). See [How a schema was obtained](chapters/schema-discovery/index.md#how-a-schema-was-obtained).
<!-- /glossary:schema-basis -->

<!-- glossary:schema-result concepts:77 -->
## SchemaResult

The value `inspect_schema` returns for each selected input. It holds the Arrow `schema`, its `basis`, the `format_key` and the `spec` used. See [Inspecting a schema](chapters/schema-discovery/index.md#inspecting-a-schema).
<!-- /glossary:schema-result -->

<!-- glossary:storage-profile concepts:40,41 -->
## Storage profile

A mountainash-transport object that selects a storage backend and its connection settings. A spec accepts the object itself, a profile name resolved from settings, or `None`, in which case the backend is chosen from the path scheme. See [Storage and auth profiles](chapters/storage-and-transforms/index.md#storage-and-auth-profiles).
<!-- /glossary:storage-profile -->

<!-- glossary:suffix-override concepts:19 -->
## Suffix override

Option values that a format applies when it is selected from a particular suffix. For example, `.jsonl` selects JSON with `ndjson=True`. See [Suffix overrides](chapters/format-options/index.md#suffix-overrides).
<!-- /glossary:suffix-override -->

<!-- glossary:tabular-format concepts:4 -->
## Tabular format

A format whose parsed data is a table of rows and columns, and which is normalised to an Arrow table or records. XML is the only built-in non-tabular format. See [Tabular and non-tabular data](chapters/files-specs-and-formats/index.md#tabular-and-non-tabular-data).
<!-- /glossary:tabular-format -->

<!-- glossary:temporal-inference concepts:58 -->
## Temporal inference

Converting text columns whose values are ISO dates or datetimes into Arrow date and timestamp types. Set `temporal="text"` on the CSV, JSON or Excel spec to keep them as strings. See [Dates and times](chapters/format-options/index.md#dates-and-times).
<!-- /glossary:temporal-inference -->

<!-- glossary:transform-pipeline concepts:44 -->
## Transform pipeline

A mountainash-transport `Pipeline` of byte transforms, such as gzip or GPG. A source pipeline unwraps bytes before parsing, and a sink pipeline wraps them before writing. See [Compression and encryption transforms](chapters/storage-and-transforms/index.md#compression-and-encryption-transforms).
<!-- /glossary:transform-pipeline -->

<!-- glossary:transform-suffix concepts:18 -->
## Transform suffix

A compression or encryption suffix, such as `.gz` or `.gpg`, that format resolution skips. As a result, `sales.csv.gz` resolves to CSV. See [Transform suffixes](chapters/files-specs-and-formats/index.md#transform-suffixes).
<!-- /glossary:transform-suffix -->

<!-- glossary:write-disposition concepts:83 -->
## Write disposition

What `write` does with an existing destination: `replace` overwrites it, and `append` adds rows to a Parquet file after the append schema check. See [Replace and append](chapters/write-modes/index.md#replace-and-append).
<!-- /glossary:write-disposition -->
