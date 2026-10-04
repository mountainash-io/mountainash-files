# API and format reference

[README](../README.md) · [Recipes](../examples/) · [Profiles](profiles.md)

## Operations and results

| Operation | Returns | Purpose |
|---|---|---|
| `parse(source, *, params=None, output="arrow")` | `list[ParseResult]` | Read and parse one file, a glob or archive members |
| `parse_bytes(data, format, *, output="arrow")` | `ParseResult` | Parse bytes or a binary file-like object |
| `write(sink, data, *, params=None)` | `None` | Serialise data and write it; raw `bytes` bypass format handling |
| `serialise_bytes(data, format)` | `bytes` | Serialise without storage access |
| `copy(source, sink, *, params=None)` | `None` | Copy bytes, applying source and sink transforms |
| `stream(source, *, params=None)` | context manager yielding a binary stream | Read transformed bytes without parsing |

`ParseResult` contains `data`, `format_key`, `spec` and `skipped_members`.
Tabular results default to Arrow tables; `output="pydata"` returns Python records.
Non-tabular plugins retain their own payloads. Scalar JSON arrays can be read
with `output="pydata"`; requesting Arrow for non-record scalar arrays raises
`ParseError`. `ParseResult.data` is dynamically typed for plugin compatibility.

`copy()` does not convert formats or append tables. To convert, parse then write
the parsed table ([recipe](../examples/format_conversion/)). `stream()` currently
reads the entire source into memory before yielding a `BytesIO`; it does not
provide bounded-memory streaming.

## File specs and format selection

`FileSourceSpec` and `FileSinkSpec` are immutable dataclasses sharing:

| Field | Meaning |
|---|---|
| `path` | String path or URI; `{name}` placeholders use the operation's `params` |
| `format` | Format key or `FormatSpec` instance; otherwise inferred from suffix |
| `storage_profile`, `auth_profile` | Transport profiles; storage may also be a name |
| `transforms` | Explicit transport `Pipeline` |
| `archive` | Read-side extraction with `ZipArchive` or `GzipCompression` |

Sources additionally accept `glob` and `on_missing="raise"` or `"skip"`.
Sinks accept `write_disposition="replace"` or `"append"` and `create_path=True`
(create local parent directories). The `archive` field does not create an archive
on write; use a transport transform for gzip output.

Explicit format specs take precedence over suffixes. Format keys are `csv`,
`tsv`, `json`, `parquet`, `xlsx` and `xml`. Path inference supplies NDJSON options
for `.ndjson` and `.jsonl`; for in-memory NDJSON use `JsonSpec(ndjson=True)`, not
`format="ndjson"`. Format resolution is suffix-based, not content sniffing.
Recognising a compression suffix during format selection does not itself supply
a decompressor.

## Format options

Import format specs from their corresponding modules:

| Spec | Import module | Selected options |
|---|---|---|
| `CsvSpec` | `mountainash_files.formats.csv` | `delimiter`, `header_rows`, `comment_char`, `null_sequence`, `columns`, `dtypes` |
| `TsvSpec` | `mountainash_files.formats.tsv` | CSV options with a tab delimiter by default |
| `JsonSpec` | `mountainash_files.formats.json` | `property`, `item_type`, `item_keys`, `header`, `ndjson` |
| `ParquetSpec` | `mountainash_files.formats.parquet` | `columns` |
| `XlsxSpec` | `mountainash_files.formats.xlsx` | `sheet_name`, `sheet_number`, `engine`, header and row options |
| `XmlSpec` | `mountainash_files.formats.xml` | `xpath`, `encoding` |

See the [format-options recipe](../examples/format_options/) for explicit CSV
parsing and serialisable `to_options()` / `from_options()` round trips.

CSV/TSV serialisation preserves representable lexical values, including delimiters,
quotes and embedded line breaks. Unrepresentable values raise `WriteError` before
the destination is written. Set `null_sequence` to represent nulls explicitly;
non-null values (including column names) equal to that marker are rejected.
Without a null marker, nulls retain the empty-field representation. Parsing keeps
ordinary type inference, so lexical preservation does not promise Arrow type
round-tripping. TSV uses tabs by default and does not support append.

## Write modes

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
Permission and parse errors propagate. Format, input, schema, and serialisation
validation finish before the first destination write.

The entire read-modify-write is in memory and rewrites even compatible empty
appends. It offers no atomicity or crash recovery beyond the current transport
guarantees; an interrupted write can damage the destination and concurrent
writers can lose updates. `copy` remains byte replacement, not table append.
See the [append recipe](../examples/parquet_append/).

## Globs, archives and missing files

For local files, `glob` selects sorted file paths beneath the source's base
directory. Remote globs require transport's object-listing capability and match
the pattern against object basenames. A glob with no matches returns `[]`.

`ZipArchive(file_pattern="*.csv")` selects members and sorts by name by default.
Each selected member produces a result; its suffix selects the format unless
the source supplies an explicit format. `inner=GzipCompression()` decompresses
gzip members before parsing. Unknown member formats fail by default;
`on_unrecognised="skip"` logs skips and records their names in each result's
`skipped_members`. An archive with no recognised members still raises an error.
No matching members raises an archive extraction error.

For a missing source, `on_missing="skip"` makes `parse()` return `[]`, `copy()`
do nothing and `stream()` yield an empty stream. It does not suppress permission,
format or parse errors. Unknown suffixes are resolved before normal-file reads.

## Compression and storage

Supply `transforms=Pipeline(Gzip())` to compress writes. Normal reads infer gzip
from `.gz` when no explicit pipeline is supplied; an explicit pipeline takes
precedence. Archive reads disable transport suffix inference so archive extraction
can handle decompression. Append requires its explicit symmetric pipeline as
described above. See [compression](../examples/gzip_pipeline/) and
[byte operations](../examples/byte_operations/).

Backend selection, storage/auth pairing and credentials are transport concerns.
See [profiles](profiles.md) for named profiles and selected secret readers.

## Custom formats

Define a frozen dataclass inheriting `FormatSpec` with `FORMAT` and `SUFFIXES`,
then call `register_format(MySpec, parser, serialiser=serialiser)`. A parser
accepts bytes or a binary stream plus the spec; a serialiser accepts data plus
the spec and returns bytes. Serialisers are optional for read-only formats.
Non-tabular formats should set `TABULAR = False` to retain their payload type.

Registrations reject conflicting keys, suffixes and media types unless
`override=True` is explicit. Lazy registrations accept `"package.module:attr"`
references and require an explicit format key and suffixes. Installed plugins
can register through the `mountainash_files.formats` entry-point group.
