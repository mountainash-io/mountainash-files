# FAQ

## Getting started

<!-- faq:what-does-parse-return concepts:22,23 -->
### Why does `parse` return a list when I read one file?

`parse` returns one `ParseResult` per selected input. A glob, or a ZIP archive with several members, selects more than one, so the return type is always a list. For a single file, unpack it with `[result] = parse(spec)`. See [parse](chapters/reading-and-writing/index.md#parse).
<!-- /faq:what-does-parse-return -->

<!-- faq:arrow-or-records concepts:24 -->
### How do I get Python dictionaries instead of an Arrow table?

Pass `output="pydata"` to `parse` or `parse_bytes`. Tabular formats then return a list of records. Non-tabular formats such as XML return their natural Python object whichever output you choose. See [Arrow or Python records](chapters/reading-and-writing/index.md#arrow-or-python-records).
<!-- /faq:arrow-or-records -->

<!-- faq:how-format-chosen concepts:17 -->
### How does mountainash-files decide which format a file is?

An explicit `format` on the spec wins, either a format key such as `"csv"` or a format spec instance. Without one, the last path suffix that names a registered format decides, and compression and encryption suffixes such as `.gz` and `.gpg` are skipped. See [How a format is chosen](chapters/files-specs-and-formats/index.md#how-a-format-is-chosen).
<!-- /faq:how-format-chosen -->

<!-- faq:media-type concepts:16 -->
### Can I select a format by media type, for example from an HTTP `Content-Type`?

Formats declare media types and the format resolver accepts them, but no public operation passes a media type and file specs have no media-type field. Map the media type to a format key yourself and pass it as `format`. See [Media type detection](chapters/files-specs-and-formats/index.md#media-type-detection).
<!-- /faq:media-type -->

<!-- faq:which-extra concepts:6,95 -->
### Which optional extra do I need?

`xlsx` adds Excel reading, `xml` adds lxml, and `http`, `s3`, `sftp`, `gcs` and `azure` add the matching storage backends through mountainash-transport. `encryption` adds GPG support. Reading Excel without the `xlsx` extra raises `MissingDependencyError`, which names the extra. See [Optional extras](chapters/files-specs-and-formats/index.md#optional-extras).
<!-- /faq:which-extra -->

## Reading files

<!-- faq:many-files concepts:30,31 -->
### How do I read every CSV file in a directory?

Set `glob` on the `FileSourceSpec`, for example `glob="*.csv"`, with `path` naming the directory. `*` matches within one path segment and `**` matches any number of segments, on every storage backend. See [Globs](chapters/selecting-files/index.md#globs).
<!-- /faq:many-files -->

<!-- faq:missing-file concepts:33 -->
### Can a missing file return nothing instead of raising?

Yes. Set `on_missing="skip"` on the source spec, and `parse` returns an empty list for a missing file. See [Missing files](chapters/selecting-files/index.md#missing-files).
<!-- /faq:missing-file -->

<!-- faq:zip-members concepts:34,35,36 -->
### How do I read only some files from a ZIP archive?

Give the spec `archive=ZipArchive(file_pattern="*.csv")`. Members that match are parsed in name order. A member whose format cannot be resolved raises, unless you set `on_unrecognised="skip"`. Skipped member names are then reported on each result. See [ZIP archives](chapters/selecting-files/index.md#zip-archives).
<!-- /faq:zip-members -->

<!-- faq:jsonl-explicit-format concepts:19,62 -->
### Why does a `.jsonl` file fail to parse when I pass `format="json"`?

The `.ndjson` and `.jsonl` suffixes switch on `ndjson=True` only when the format is chosen from the suffix. An explicit `format="json"` uses the default `JsonSpec`, which expects one JSON document. Leave `format` unset, or pass `JsonSpec(ndjson=True)`. See [Suffix overrides](chapters/format-options/index.md#suffix-overrides).
<!-- /faq:jsonl-explicit-format -->

<!-- faq:csv-types concepts:57 -->
### How do I force a CSV column's type?

Set `CsvSpec.dtypes` to pairs of column name and type name. It recognises `string`, `int64`, `int32`, `float64`, `float32` and `bool`, and any other type name is read as string. See [Column types](chapters/format-options/index.md#column-types).
<!-- /faq:csv-types -->

<!-- faq:csv-nulls concepts:53 -->
### Why do nulls come back as empty strings after writing and reading a CSV?

By default the CSV writer quotes every field, so a null is written as `""`, and a quoted empty field reads back as an empty string. Set the same `null_sequence` on the spec for both writing and reading, for example `CsvSpec(null_sequence="NULL")`. See [Null sequence](chapters/format-options/index.md#null-sequence).
<!-- /faq:csv-nulls -->

<!-- faq:remote-parquet-columns concepts:67 -->
### Does reading a few Parquet columns from remote storage download the whole file?

No, if you set `ParquetSpec.columns` and no decompression or decryption transform applies. The read then uses a random-access handle, and only the footer and the selected column chunks are fetched. Without a projection the whole object is read. See [Parquet](chapters/format-options/index.md#parquet).
<!-- /faq:remote-parquet-columns -->

<!-- faq:schema-without-rows concepts:76,78 -->
### How do I see a file's columns and types without loading it?

Call `inspect_schema` with the same source spec you would pass to `parse`. Each `SchemaResult` has the Arrow schema and a `basis` of `metadata`, `full` or `bounded`. Parquet reads only its footer. `infer_schema_rows` limits how many records inform the schema, and CSV and NDJSON stop reading once they have that many. See [Schema discovery](chapters/schema-discovery/index.md).
<!-- /faq:schema-without-rows -->

## Writing files

<!-- faq:write-records concepts:26 -->
### Why does writing a list of dictionaries to CSV or Parquet fail?

`write` hands its data to the format's serialiser unchanged. The CSV, TSV and Parquet serialisers need a `pyarrow.Table`, and a list of records raises `AttributeError`. JSON accepts records. Convert first with `pa.Table.from_pylist(records)`. See [write](chapters/reading-and-writing/index.md#write).
<!-- /faq:write-records -->

<!-- faq:excel-write concepts:70 -->
### Can I write Excel files?

No. The Excel format has a reader and a schema inspector but no serialiser, so `write` and `serialise_bytes` with Excel raise `WriteError`. See [Excel is read-only](chapters/format-options/index.md#excel-is-read-only).
<!-- /faq:excel-write -->

<!-- faq:append concepts:83,84,85 -->
### Which formats support append?

Only Parquet. `write_disposition="append"` reads the existing file, requires the incoming data to have the same column names and types in the same order, and rewrites the combined table. A mismatch raises `AppendSchemaMismatchError`. See [Appending to Parquet](chapters/write-modes/index.md#appending-to-parquet).
<!-- /faq:append -->

<!-- faq:gz-write concepts:44,45 -->
### Why is a file I wrote to `data.csv.gz` not compressed?

Writes do not infer transforms from the path suffix. To compress on write, give the sink spec a transform pipeline. See [Compression and encryption transforms](chapters/storage-and-transforms/index.md#compression-and-encryption-transforms).
<!-- /faq:gz-write -->

## Storage and errors

<!-- faq:named-profile concepts:41 -->
### How do I read from S3 or another remote store?

Install the matching extra and either use a URL path with an anonymous profile, or name a storage profile, such as `storage_profile="reports"`, that mountainash-transport resolves from settings. See [Storage and auth profiles](chapters/storage-and-transforms/index.md#storage-and-auth-profiles).
<!-- /faq:named-profile -->

<!-- faq:archive-errors concepts:96 -->
### How do I catch `ArchiveLimitError`?

The archive errors are not exported from the package root, and they do not subclass `FormatError`. Catch `Exception` and check the class name, or let the error propagate. See [Archive errors](chapters/errors/index.md#archive-errors).
<!-- /faq:archive-errors -->

<!-- faq:version concepts:120 -->
### How do I get the installed version?

Use `importlib.metadata.version("mountainash-files")`. The package root does not expose a version string. See [Version source](chapters/architecture/index.md#version-source).
<!-- /faq:version -->

## Extending

<!-- faq:custom-format concepts:97 -->
### How do I add a format that mountainash-files does not support?

Define a frozen dataclass subclass of `FormatSpec`, write a parser (and optionally a serialiser and schema inspector), and call `register_format`. To make it available on install, register it from a module listed in the `mountainash_files.formats` entry-point group. See [Custom formats and plugins](chapters/custom-formats/index.md).
<!-- /faq:custom-format -->

<!-- faq:plugin-import concepts:102,105 -->
### Why does my entry-point plugin fail to import `register_format` from `mountainash_files`?

Plugin discovery runs while the package root is still initialising, so a plugin module cannot import from `mountainash_files` itself. It has to import `register_format` from the registry module. See [Entry-point plugins](chapters/custom-formats/index.md#entry-point-plugins).
<!-- /faq:plugin-import -->
