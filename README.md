# mountainash-files

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

Parse and write structured files through one API: CSV, TSV, JSON, Parquet, Excel
and XML, on local disk or storage supported by `mountainash-transport`. File
specs combine a path, format options, storage profiles and stream transforms.
Tabular reads return Arrow tables by default, with Python records available on request.

[Examples](examples/) · [Reference](docs/advanced-usage.md) ·
[Profiles and migration](docs/profiles.md) · [Release process](RELEASE.md)

## What it provides

| Area | Capabilities | Explore |
|---|---|---|
| Parsing | Suffix-based format selection; Arrow tables or Python records; in-memory buffers | [Parsing](examples/#parsing) |
| Schema discovery | Arrow schema of each selected input without returning rows; full or bounded inference | [Reference](docs/advanced-usage.md#schema-discovery) |
| Format options | Immutable format specs for delimiters, headers, column selection and structured data | [Format options](examples/format_options/) |
| Writing | Serialisation, format conversion and schema-checked Parquet append | [Writing](examples/#writing) |
| File selection | Path templates, globs, missing-file handling and ZIP member selection | [Selecting files](examples/#selecting-files) |
| Transport | Compression/encryption options, byte copy, delegated streams and named storage profiles | [Storage and transforms](examples/#storage-and-transforms) |
| Extension | Register custom parsers and serialisers with `register_format()` | [Reference](docs/advanced-usage.md#custom-formats) |

## Installation

Requires **Python 3.12+**, **PyArrow 16+** and `mountainash-transport` 0.1.

This README describes the **unpublished 0.1.0 candidate**. Until the runtime
dependency chain is public, install the development checkouts together. From
the directory that will contain the repositories:

```bash
git clone --branch develop https://github.com/mountainash-io/mountainash-settings.git
git clone --branch develop https://github.com/mountainash-io/mountainash-auth-client.git
git clone --branch develop https://github.com/mountainash-io/mountainash-transport.git
git clone --branch develop https://github.com/mountainash-io/mountainash-files.git
cd mountainash-files
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ../mountainash-settings -e ../mountainash-auth-client \
  -e ../mountainash-transport -e .
```

| Extra | Adds |
|---|---|
| `[xlsx]` | fastexcel and openpyxl for Excel reads |
| `[xml]` | lxml; basic XML uses the standard library |
| `[s3]`, `[sftp]` | Transport dependencies for the corresponding backend |
| `[encryption]` | Transport's GPG support; also requires GnuPG and keys |
| `[gcs]`, `[azure]` | SDKs for backends still pending in transport |
| `[all]` | All of the above |

To include extras during the source install, replace `-e .` with, for example,
`-e '.[xlsx]'`. Missing optional dependencies raise `MissingDependencyError`
with installation guidance.

## Quick start

Save this as `quickstart.py` and run it with `python quickstart.py`:

```python
import tempfile
from pathlib import Path

import pyarrow as pa
from mountainash_files import FileSinkSpec, FileSourceSpec, parse, write

sales = pa.table({"region": ["north", "south"], "total": [120, 95]})

with tempfile.TemporaryDirectory() as root:
    path = str(Path(root) / "sales.parquet")
    write(FileSinkSpec(path=path), sales)
    result, = parse(FileSourceSpec(path=path))
    print(f"{result.format_key}: {result.data.num_rows} rows")
    print(result.data.to_pylist())
```

Expected output:

```text
parquet: 2 rows
[{'region': 'north', 'total': 120}, {'region': 'south', 'total': 95}]
```

`parse()` always returns a list of `ParseResult`, even for a single file.
Use `output="pydata"` for Python records. The suffix selects the format;
`format="csv"` or a format spec overrides it.

## Supported formats and storage

| Format | Parse | Schema discovery | Serialise | Append | Dependency |
|---|---|---|---|---|---|
| CSV / TSV | ✓ | ✓ | ✓ | — | core |
| JSON / NDJSON | ✓ | ✓ | ✓ | — | core |
| Parquet | ✓ | ✓ (footer) | ✓ | ✓ | core |
| XLSX | ✓ | ✓ | — | — | `[xlsx]` |
| XML | ✓ | — | ✓ | — | core; `[xml]` for lxml |

Append reads and rewrites the complete table, requires matching ordered column
names and Arrow types, and is intended for a single writer. See
[write modes](docs/advanced-usage.md#write-modes) for the full contract.

| Storage | Status | Extra |
|---|---|---|
| Local disk | implemented | core |
| HTTP / HTTPS | implemented; operations depend on the server | core |
| S3, S3 Express, R2, MinIO, B2 | implemented | `[s3]` |
| SFTP | implemented | `[sftp]` |
| GCS, Azure, FTP, SMB, GitHub | profiles only; backend pending in transport | — |

Pass `storage_profile` and `auth_profile` on a file spec for remote access.
Named profiles and explicit secret-store selection are covered in
[profiles and migration](docs/profiles.md). Available operations depend on the
transport backend; having a profile or an extra does not implement a backend.

## Untrusted file contents

**Archives.** Zip and gzip extraction is bounded. `ZipArchive` and
`GzipCompression` take `max_decompressed_bytes` (default 1 GiB, which is the
total across all extracted members, including an inner gzip layer). `ZipArchive`
also takes `max_members` (default 10,000 members after `file_pattern`).
Extraction streams with a running byte count, so if a limit is exceeded it raises
`ArchiveLimitError` before the whole payload is held in memory. For trusted
sources you can raise the limits, for example
`ZipArchive(max_decompressed_bytes=8 * 1024**3)`.

**XLSX workbooks.** An `.xlsx` file is a zip container read by a third-party
engine, so `XlsxSpec` applies the same kind of limit before any engine sees the
bytes: `max_decompressed_bytes` (default 512 MiB, total across all members) and
`max_members` (default 1,000). The container is inflated in chunks and the
output discarded, so the check counts the bytes actually produced, not the sizes
the zip directory declares (which an attacker can forge), and holds only a chunk
in memory. Over either limit it raises `ArchiveLimitError`, naming the field to
raise. The defaults sit well above real workbooks: measured with xlsxwriter, a
1M-row, 3-column sheet is 144 MiB uncompressed (7.7x its file size), a
100k-row, 23-column sheet is 97 MiB (12x), and a workbook holds about a dozen
members, while a zip bomb expands about 1000x. Raise the limits for trusted
workbooks, for example `XlsxSpec(max_decompressed_bytes=2 * 1024**3)`. The check
adds one inflate pass over the file before parsing. Members compressed with
anything other than stored or deflate, encrypted members, a damaged zip
directory, and containers whose directory is ambiguous (prepended or trailing
data, an entry count that disagrees with the directory, a stray end-record
signature) are refused with `ParseError`, because different zip readers could
walk such a directory differently; input with no zip end record is left to the
engine, which rejects it as before. The limit bounds one pass over
the container; an engine may read a member more than once.

**XML external entities.** XML parsing with the `[xml]` extra requires
`lxml>=6.1.0`. Earlier lxml releases resolve external entities by default
(CVE-2026-41066), which lets an untrusted document read local files. From 6.1.0
the parser expands only entities declared inside the document and a reference
to an external entity is a parse error.

**CSV/TSV formula cells.** By default the CSV and TSV writers write cell values
unchanged. A value starting with `=`, `+`, `-`, `@`, a tab or a carriage return may
be evaluated as a formula when the export is opened in a spreadsheet application.
Set `CsvSpec(formula_neutralise=True)` (or the same on `TsvSpec`) to prefix such
string cells and header labels with `'`. This changes the data: the prefix is
written into the file and is not removed when the file is parsed, and numeric
values are never altered. Leave it off for machine-to-machine exports.

## Learn more

Explore the [file recipes](examples/): each runs offline and independently,
using the same small sales dataset and documenting its expected output.

| Guide | Contents |
|---|---|
| [API and format reference](docs/advanced-usage.md) | Results, format options, append, archives, transforms and extensions |
| [Profiles and migration](docs/profiles.md) | Named profiles, selected secret stores and the 0.1 baseline |
| [Contributing](CONTRIBUTING.md) | Source setup, tests, optional cohorts and typing qualification |
| [Release process](RELEASE.md) | Sibling-wheel rehearsal, public-only verification and publication |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and checks. Branch from
`develop` and target `develop` with pull requests.

Part of the [Mountain Ash ecosystem](https://github.com/mountainash-io), alongside
`mountainash-settings`, `mountainash-auth-client`, `mountainash-transport`,
`mountainash-data` and `mountainash`. Transport owns storage access;
auth-client owns authentication models and OAuth flows.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE).
