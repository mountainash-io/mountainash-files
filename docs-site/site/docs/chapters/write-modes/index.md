---
title: Write modes and Parquet append
---

# Write modes and Parquet append

`write()` either replaces the destination or appends rows to it. The sink spec decides which, through `write_disposition`, and also decides whether missing parent directories are created. Replace works for every format with a serialiser and for raw bytes. Append works for Parquet, the only built-in format that supports it, and it checks the schema before anything is written.

## Replace and append

<!-- concept:83 -->

`FileSinkSpec.write_disposition` takes two values:

| Value | Behaviour |
|---|---|
| `"replace"` (default) | Serialise the data and write it over the destination, creating it if it does not exist. |
| `"append"` | Read the existing table, add the incoming rows, and rewrite the destination. Only formats whose spec declares both `APPENDABLE` and `TABULAR` support it; among the built-in formats that is Parquet. |

Any other value raises `WriteError: Unknown write disposition: 'upsert'` before the format is resolved. Appending to CSV, TSV, JSON, XML or any other format without the flags raises `WriteError: Format 'csv' does not support append of tabular data.` and leaves the destination untouched. The [support matrix](../format-options/index.md#what-each-format-supports) lists the flags for each format.

With `"replace"`, CSV, TSV and Parquet serialisers expect a `pyarrow.Table`. Passing a record dictionary or a list of records to them fails with a plain `AttributeError` from the serialiser, such as `'list' object has no attribute 'columns'`, not a `WriteError`. Convert records first with `pa.Table.from_pylist(records)`. The JSON serialiser accepts records directly, and append accepts records for any appendable format.

```python
import tempfile
from pathlib import Path

import pyarrow as pa
from mountainash_files import FileSinkSpec, FileSourceSpec, parse, write

with tempfile.TemporaryDirectory() as root:
    sink = FileSinkSpec(path=f"{root}/2026/q1/sales.csv")
    write(sink, pa.table({"region": ["north"], "total": [120]}))
    write(sink, pa.table({"region": ["south"], "total": [95]}))
    result, = parse(FileSourceSpec(path=sink.path), output="pydata")
    print(result.data)

    write(FileSinkSpec(path=f"{root}/raw/notes.txt"), b"exported by the nightly job\n")
    print(Path(root, "raw", "notes.txt").read_bytes())
```

```text
[{'region': 'south', 'total': 95}]
b'exported by the nightly job\n'
```

The second `write()` replaced the first file's contents, and the parent directories `2026/q1` and `raw` were created on the way.

<!-- concept:86 -->

### Creating parent directories

`FileSinkSpec.create_path` defaults to `True`, which creates missing parent directories on storage that has directories (local disk, SFTP). With `create_path=False`, a missing parent raises transport's `PathNotFoundError` and nothing is created. Object stores and HTTP have no directories, so the setting has no effect there.

```python
import tempfile

import pyarrow as pa
from mountainash_files import FileSinkSpec, write
from mountainash_transport import PathNotFoundError

with tempfile.TemporaryDirectory() as root:
    sink = FileSinkSpec(path=f"{root}/missing/sales.csv", create_path=False)
    try:
        write(sink, pa.table({"region": ["north"], "total": [120]}))
    except PathNotFoundError as exc:
        print(type(exc).__name__)
```

```text
PathNotFoundError
```

<!-- concept:88 -->

### Writing raw bytes

When `data` is a `bytes` object, `write()` skips format handling: it resolves no format and calls no serialiser, so any path works, including one with an unknown suffix such as `notes.txt` above. The sink's `transforms` still apply, so `write(FileSinkSpec(path="sales.csv.gz", transforms=Pipeline(Gzip())), raw)` compresses the bytes on the way out. `copy()` is the usual route for moving existing bytes between locations; see [Copying bytes and opening streams](../reading-and-writing/index.md#copying-bytes-and-opening-streams).

The check is for `bytes` exactly. A `bytearray` or `memoryview` goes through format resolution and the serialiser like any other value: with a `.txt` path it raises `UnknownFormatError`, and with a `.csv` path the CSV serialiser fails with `AttributeError`. Pass `bytes(buffer)` instead. Raw data of any of the three types is rejected for append with `WriteError: Raw-byte append is not supported; supply tabular records`.

## Appending to Parquet

<!-- concept:84 -->

An append to Parquet is a read-modify-write. `write()` reads the complete existing table, combines it with the incoming rows, serialises the result and writes the whole file again. If the destination does not exist yet, the incoming rows become the new file. The incoming data can be a `pyarrow.Table`, one record dictionary, or a list of record dictionaries. Records are normalised to a table with every key that appears in any row, in first-seen order.

```python
import tempfile

import pyarrow as pa
from mountainash_files import FileSinkSpec, FileSourceSpec, parse, write

with tempfile.TemporaryDirectory() as root:
    append = FileSinkSpec(path=f"{root}/sales.parquet", write_disposition="append")
    write(append, pa.table({"region": ["north"], "total": [120]}))  # creates the file
    write(append, {"region": "south", "total": 95})
    write(append, [{"region": "east", "total": 101}, {"region": "west", "total": 77}])

    result, = parse(FileSourceSpec(path=append.path), output="pydata")
    print(len(result.data), result.data[-1])
```

```text
4 {'region': 'west', 'total': 77}
```

Points that follow from the read-modify-write design (`write` in `src/mountainash_files/_operations.py`):

- The cost of each append grows with the size of the existing file, because the whole table is held in memory and rewritten, even for an empty append.
- There is no atomicity or crash recovery beyond what the transport backend gives a single write. An interrupted write can damage the destination, and concurrent writers can lose updates. Use one writer per file.
- Append needs read and write access to the destination.
- A `columns` projection on the sink's `ParquetSpec` is ignored when the existing table is loaded, so every column is kept.
- Compression or encryption needs an explicit, symmetric `transforms` pipeline on the sink. Append uses it both to read the existing file and to write the new one. Suffixes such as `.gz` do not enable transforms during append. Without the pipeline, the compressed bytes reach the Parquet parser and the append fails with `ParseError: [parquet] Parquet magic bytes not found in footer...`.

```python
import tempfile

from mountainash_files import FileSinkSpec, FileSourceSpec, parse, write
from mountainash_transport import Gzip, Pipeline

with tempfile.TemporaryDirectory() as root:
    append = FileSinkSpec(
        path=f"{root}/sales.parquet.gz",
        write_disposition="append",
        transforms=Pipeline(Gzip()),
    )
    write(append, {"region": "north", "total": 120})
    write(append, {"region": "south", "total": 95})
    result, = parse(FileSourceSpec(path=append.path), output="pydata")
    print(result.data)
```

```text
[{'region': 'north', 'total': 120}, {'region': 'south', 'total': 95}]
```

Format, input, schema and serialisation checks all finish before the first byte is written to the destination. Permission and parse errors from reading the existing file propagate unchanged.

<!-- concept:85 -->

### The append schema check

The incoming table must match the existing one exactly: the same column names, in the same order, with the same Arrow types. There are no implicit casts, no column reordering and no schema evolution. A mismatch raises `AppendSchemaMismatchError`, a `WriteError` subclass with `path`, `expected_schema` and `actual_schema` attributes, and the destination is left as it was:

```python
import tempfile
from pathlib import Path

import pyarrow as pa
from mountainash_files import AppendSchemaMismatchError, FileSinkSpec, write

with tempfile.TemporaryDirectory() as root:
    path = f"{root}/sales.parquet"
    write(FileSinkSpec(path=path), pa.table({"region": ["north"], "total": [120]}))
    before = Path(path).read_bytes()

    append = FileSinkSpec(path=path, write_disposition="append")
    for rows in (
        {"region": "west", "total": "unknown"},   # string instead of int64
        {"total": 95, "region": "south"},         # columns in a different order
    ):
        try:
            write(append, rows)
        except AppendSchemaMismatchError as exc:
            print(exc.expected_schema.names, exc.expected_schema.types)
            print(exc.actual_schema.names, exc.actual_schema.types)
    print(Path(path).read_bytes() == before)
```

```text
['region', 'total'] [DataType(string), DataType(int64)]
['region', 'total'] [DataType(string), DataType(string)]
['region', 'total'] [DataType(string), DataType(int64)]
['total', 'region'] [DataType(int64), DataType(string)]
True
```

Record input is typed by Arrow's inference, so a column whose incoming values are all `None` becomes type `null` and does not match a typed column. An untyped empty list has no columns at all and also mismatches. Build the incoming table with the destination's schema to append such rows:

```python
import tempfile

import pyarrow as pa
from mountainash_files import AppendSchemaMismatchError, FileSinkSpec, FileSourceSpec, parse, write

with tempfile.TemporaryDirectory() as root:
    append = FileSinkSpec(path=f"{root}/sales.parquet", write_disposition="append")
    schema = pa.schema([("region", pa.string()), ("total", pa.int64())])
    write(append, pa.table({"region": ["north"], "total": [120]}, schema=schema))

    try:
        write(append, {"region": "south", "total": None})
    except AppendSchemaMismatchError as exc:
        print(exc.actual_schema.field("total").type)

    write(append, pa.Table.from_pylist([{"region": "south", "total": None}], schema=schema))
    result, = parse(FileSourceSpec(path=append.path), output="pydata")
    print(result.data)
```

```text
null
[{'region': 'north', 'total': 120}, {'region': 'south', 'total': None}]
```

When the schemas match, the result keeps the existing file's schema metadata and field metadata, and each field is nullable if either side allows nulls. The merge rules are described in [Append merge rules](../format-internals/index.md#append-merge-rules).
