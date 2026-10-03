# mountainash-files

Composable file operations with format detection and parsing.

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

## License

MIT
