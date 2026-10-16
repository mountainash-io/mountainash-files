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
| `stream(source, *, params=None, access="sequential", range_policy=None)` | context manager yielding a binary stream | Read transformed bytes without parsing |
| `inspect_schema(source, *, params=None, infer_schema_rows=None)` | `list[SchemaResult]` | Observe each selected input's Arrow schema without returning rows |
| `inspect_schema_bytes(data, format, *, infer_schema_rows=None)` | `SchemaResult` | Observe the schema of bytes or a binary file-like object |

`ParseResult` contains `data`, `format_key`, `spec` and `skipped_members`.
Tabular results default to Arrow tables; `output="pydata"` returns Python records.
Non-tabular plugins retain their own payloads. Scalar JSON arrays can be read
with `output="pydata"`; requesting Arrow for non-record scalar arrays raises
`ParseError`. `ParseResult.data` is dynamically typed for plugin compatibility.

`copy()` does not convert formats or append tables. To convert, parse then write
the parsed table ([recipe](../examples/format_conversion/)). Parsing and copying
materialise bytes through transport's `read()`. `stream()` instead delegates to
transport's `read_stream()` without first consuming the returned stream.

Keep reads inside the context: the stream closes on normal exit or exceptions.
Opening can fail, and decoding or I/O errors can also occur during consumption.
`on_missing="skip"` handles missing sources while opening, not exceptions raised
by your code or subsequent reads. Seekability follows the effective transformed
stream: check `seekable()` before seeking; offsets refer to decoded bytes.
Unlike the previous `BytesIO` implementation, seeking is not guaranteed for all
backends. Transport's GPG transform and some backends still buffer internally,
so this API does not promise bounded memory for every source.

`access` (`"sequential"`, `"random"` or `"buffered"`) and `range_policy` pass to
transport unchanged. `stream()` does not fall back: if transport refuses the
combination (for example `access="random"` with a transform, or a server without
byte ranges), the error propagates. Use `access="random"` for seekable ranged
reads of remote objects. `parse()` chooses the access mode itself, per format.

## Schema discovery

```python
from mountainash_files import FileSourceSpec, inspect_schema

result, = inspect_schema(FileSourceSpec(path="sales.csv"), infer_schema_rows=1000)
result.schema   # pyarrow.Schema
result.basis    # "metadata", "full" or "bounded"
```

`SchemaResult` contains `schema`, `basis`, `format_key`, `spec` and
`skipped_members`. Selection (templates, globs, archives, transforms, profiles,
`on_missing`) works as in `parse()`, with one result per selected input.

Each built-in format runs its own parse engine over the inspected records and
keeps only the schema, so a `full` result has the types `parse()` produces for
the same input and spec. A result is an observation, not a contract: discovery
does not change later parses, and a changed source can parse differently.

| Basis | Meaning |
|---|---|
| `metadata` | Read from format metadata (Parquet footer); no records inspected |
| `full` | Every record was inspected |
| `bounded` | Coverage of every record was not established; later fields or types may be missing |

`infer_schema_rows=None` (the default) inspects every record. A positive integer
bounds the data records inspected per selected input; header and comment records
are not counted. If a CSV header row comes after the Nth data record, the records
before it are read and also contribute. A result is also `bounded` when the spec sets
`infer_sample_rows`. Other budget values raise `ValueError` before any I/O.

A budget is the only cost control. What it saves depends on the format:

| Format | Fetched | Full budget | Finite budget |
|---|---|---|---|
| Parquet | Footer only (ranged reads; whole object with transforms or servers without ranges) | Metadata only | Same |
| CSV / TSV, NDJSON | Whole object for a full budget; a prefix read forward and closed early for a finite one (whole object with transforms or archives) | About one parse | Only the prefix, so cost follows the budget, not the file size (UTF-16/32 NDJSON is read whole) |
| JSON document | Whole object | About one parse | Still decodes the whole document |
| XLSX | Whole workbook | About one parse | Still decodes the whole sheet; little faster than full |

For example, on one million rows a full CSV discovery took about 0.3 s and a
1,000-record discovery about 0.05 s, fetching about 2.6 MB of 32 MB over HTTP.

XML and plugins without an inspector raise `SchemaDiscoveryUnsupportedError`
before reading a single file, even with `on_missing="skip"`; archive members
are checked after the archive is read. Malformed content raises
`ParseError`, including JSON whose selected records are not tabular. A caller's
stream passed to `inspect_schema_bytes()` is read but not closed.

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
Their read options apply consistently to parsing (including glob children),
copying and streaming:

| Source field | Meaning |
|---|---|
| `infer: bool \| None = None` | `None` preserves operation defaults; `True` enables suffix inference; `False` disables inference, not an explicit pipeline |
| `gpg: GPG \| None = None` | Configured transport decoder for inferred `.gpg`, `.pgp` and `.asc` transforms |
| `gzip: Gzip \| None = None` | Configured transport decoder for inferred `.gz` and `.gzip` transforms |

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
| `CsvSpec` | `mountainash_files.formats.csv` | `delimiter`, `header_rows`, `comment_char`, `null_sequence`, `columns`, `dtypes`, `temporal` |
| `TsvSpec` | `mountainash_files.formats.tsv` | CSV options with a tab delimiter by default |
| `JsonSpec` | `mountainash_files.formats.json` | `property`, `item_type`, `item_keys`, `header`, `ndjson`, `temporal`, `infer_sample_rows` |
| `ParquetSpec` | `mountainash_files.formats.parquet` | `columns` |
| `XlsxSpec` | `mountainash_files.formats.xlsx` | `sheet_name`, `sheet_number`, header and row options, `temporal`, `infer_sample_rows` |
| `XmlSpec` | `mountainash_files.formats.xml` | `xpath`, `encoding` |

See the [format-options recipe](../examples/format_options/) for explicit CSV
parsing and serialisable `to_options()` / `from_options()` round trips.

CSV/TSV serialisation preserves representable lexical values, including delimiters,
quotes and embedded line breaks. Unrepresentable values raise `WriteError` before
the destination is written. Set `null_sequence` to represent nulls explicitly;
non-null values (including column names) equal to that marker are rejected.
Without a null marker, nulls retain the empty-field representation. Parsing infers
`int64`, `double`, `bool`, `date32`, `timestamp[s]` and `string` columns, so lexical
preservation does not promise Arrow type round-tripping. See
[reader engines](migration-reader-engines.md) for inference controls. TSV uses tabs by default and does not support append.

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

Supply `transforms=Pipeline(Gzip())` to compress writes. With `infer=None`, normal
reads infer gzip from `.gz`/`.gzip` when no explicit pipeline is supplied; an
explicit pipeline takes precedence. `infer=True` combined with `transforms`
raises transport's `ValueError`. `infer=False` allows copying or streaming encoded
bytes unchanged when no pipeline is supplied. `parse_bytes()` never applies
transport transforms.

Configure inferred decryption on the source, for example:

```python
from mountainash_files import FileSourceSpec, parse
from mountainash_transport import GPG

source = FileSourceSpec(
    path="sales.csv.gz.gpg",
    gpg=GPG(gnupghome="/path/to/keyring"),
)
results = parse(source)  # decrypt, decompress, then parse
```

GPG requires the encryption extra, GnuPG and appropriate keys. Without a configured
GPG instance, inferred encrypted suffixes raise `ValueError`. For explicit pipelines,
include every required transform, e.g. `Pipeline(GPG(...), Gzip())` for `.gz.gpg`;
the `gpg`/`gzip` source options configure inference, not an explicit pipeline.

Archive reads default to disabled inference so archive extraction can handle
decompression. Override this with `infer=True` for an outer transport layer, e.g.
`FileSourceSpec(path="data.zip.gz", archive=ZipArchive(), infer=True)`. An explicit
pipeline also runs before archive extraction. Do not enable gzip inference when
`archive=GzipCompression()` will unwrap that same layer.
Append still requires its explicit symmetric sink pipeline as described above;
source-only read options do not change writes. See [compression](../examples/gzip_pipeline/) and
[byte operations](../examples/byte_operations/).

Backend selection, storage/auth pairing and credentials are transport concerns.
See [profiles](profiles.md) for named profiles and selected secret readers.

## Custom formats

Define a frozen dataclass inheriting `FormatSpec` with `FORMAT` and `SUFFIXES`,
then call `register_format(MySpec, parser, serialiser=serialiser)`. A parser
accepts bytes or a binary stream plus the spec; a serialiser accepts data plus
the spec and returns bytes. Serialisers are optional for read-only formats.
Non-tabular formats should set `TABULAR = False` to retain their payload type.

`register_format(..., access="random")` asks `parse()` for a seekable ranged
handle when no transforms apply; the parser then receives a handle or `bytes`
and must finish reading before it returns. See the
[migration notes](migration-reader-engines.md#plugin-formats).

To support schema discovery, pass `schema_inspector=` (a callable or a
`"package.module:attr"` reference). It receives bytes or a binary stream, the
spec and `infer_schema_rows`, and returns `(pyarrow.Schema, basis)`; it must not
close a borrowed stream. `schema_access=` (`"bytes"`, `"random"`,
`"sequential"`, or a callable of the spec and budget) chooses what
`inspect_schema()` hands it when no transforms apply. Archives, transforms and
refused ranges always supply bytes, so an inspector must handle both. Formats
without an inspector parse normally but raise `SchemaDiscoveryUnsupportedError`
on discovery.

Registrations reject conflicting keys, suffixes and media types unless
`override=True` is explicit. Lazy registrations accept `"package.module:attr"`
references and require an explicit format key and suffixes. Installed plugins
can register through the `mountainash_files.formats` entry-point group.
