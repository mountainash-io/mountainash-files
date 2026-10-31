---
title: mountainash-files
---

[← Back to Ecosystem](https://docs.mountainash.io/)

# mountainash-files

mountainash-files reads and writes structured files through one Python API. It handles CSV, TSV, JSON and NDJSON, Parquet, Excel (read) and XML, on local disk or on any storage that [mountainash-transport](https://docs.mountainash.io/mountainash-transport/) can reach. You describe a file with a spec (its path, format options, storage profile and compression or encryption transforms), and an operation such as `parse`, `write` or `inspect_schema` acts on it. Tabular reads return Arrow tables by default, or Python records if you ask for them.

## Quick start

```python
import tempfile
from pathlib import PurePosixPath

from mountainash_files import FileSinkSpec, FileSourceSpec, inspect_schema, parse, write

with tempfile.TemporaryDirectory() as tmp:
    csv_path = str(PurePosixPath(tmp) / "sales.csv")
    write(FileSinkSpec(path=csv_path), b"region,total\nnorth,120\nsouth,95\n")

    [result] = parse(FileSourceSpec(path=csv_path))
    print(result.format_key, result.data.num_rows, result.data.column_names)

    parquet_path = str(PurePosixPath(tmp) / "sales.parquet")
    write(FileSinkSpec(path=parquet_path), result.data)

    [schema] = inspect_schema(FileSourceSpec(path=parquet_path))
    print(schema.basis, schema.schema)
```

```text
csv 2 ['region', 'total']
metadata region: string
total: int64
```

In this example the `.csv` and `.parquet` suffixes select the formats, `write` turns raw bytes or an Arrow table into a file, and `inspect_schema` reads the Parquet footer without loading any rows.

## Installation

mountainash-files requires Python 3.12 or later. Its runtime dependencies are PyArrow, Polars and mountainash-transport. The repository [README](https://github.com/mountainash-io/mountainash-files#installation) gives the current installation steps and lists the optional extras:

| Extra | Adds |
|---|---|
| `xlsx` | Excel reading (fastexcel and openpyxl) |
| `xml` | lxml; without it, XML uses the standard library |
| `http`, `s3`, `sftp`, `gcs`, `azure` | The matching mountainash-transport storage backend |
| `encryption` | GPG transforms through mountainash-transport |
| `all` | Everything above |

If a feature's extra is missing, it raises [`MissingDependencyError`](chapters/errors/index.md#missing-optional-dependencies), which names the extra to install.

## Where to start

- [Files, specs and formats](chapters/files-specs-and-formats/index.md) explains the model the rest of the book uses.
- [Reading and writing files](chapters/reading-and-writing/index.md) covers the operations.
- [Format options](chapters/format-options/index.md) is the per-format reference, with a [support matrix](chapters/format-options/index.md#what-each-format-supports).
- [Custom formats and plugins](chapters/custom-formats/index.md) shows how to add a format.
- [How mountainash-files works](chapters/architecture/index.md) is for people changing the package.

The full list is on the [chapters page](chapters/index.md). [Why mountainash-files](why.md) describes what the package does differently.
