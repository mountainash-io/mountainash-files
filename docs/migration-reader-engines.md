# Reader engines: what changed

[API reference](advanced-usage.md) · [README](../README.md)

Tabular readers now use native engines, and each format fetches only what it
needs from storage. Supported options and return types are unchanged except for
the differences below.

| Format | Engine |
|---|---|
| CSV / TSV | pyarrow CSV |
| JSON / NDJSON | polars |
| XLSX | fastexcel (calamine); the `engine` option and the openpyxl reader are removed |
| Parquet | pyarrow `ParquetFile` |
| XML | lxml (unchanged) |

Typical speed-ups at one million rows are recorded in the central cost study;
CSV drops from about a minute to under a second.

## Output types

| Format | Before | After |
|---|---|---|
| CSV / TSV | `int64` or `string` only; empty field `""` | `int64`, `double`, `bool`, `date32`, `timestamp[s]`, `string`. With `null_sequence` unset, an unquoted empty field becomes null and a quoted `""` stays `""`. |
| JSON / NDJSON | `pa.Table.from_pylist` types; mixed types raise | polars types from the whole input; mixed types widen to `string`; ISO dates are inferred |
| XLSX | openpyxl cell types; mixed types raise | calamine types; whole-number floats become `int64`; text in numeric columns may become null; mixed run types become `double` or `string`; ISO date strings are inferred |
| Parquet | `read_table` | identical output |

String, binary and list columns use the standard Arrow types (`string`, not
`large_string`), except for a column whose data cannot fit 32-bit offsets.

### CSV

A quote character in the middle of an unquoted field is kept literally, following
RFC 4180. The previous reader removed it, so `pre"quoted"suffix` was read as
`prequotedsuffix`. Unterminated quotes still raise `ParseError`.

### JSON

A numeric literal that overflows a double (for example `1e400`) raises
`ParseError`; the previous reader returned `inf`.

### XLSX

calamine treats empty-string cells as absent, so a trailing column with no
non-empty cell anywhere (no header label and no value) is not returned; with a
header label or any value, the column is kept. Trailing rows containing only empty
cells are also dropped. Leading empty columns are kept and named `fieldN`.

Each comment-separated run of data rows costs one sheet decode, so a sheet with
many scattered comment rows reads more slowly than a sheet without any.

## Controlling inference

`temporal` applies to CSV, TSV, JSON and XLSX. The default `"infer"` converts a
column to `date32` or `timestamp` when every value is a valid ISO date or
datetime. `"text"` keeps the original text.

```python
from mountainash_files.formats.csv import CsvSpec

CsvSpec(temporal="text")   # "2020-01-01" stays a string
```

Type inference reads the whole input. JSON and XLSX accept `infer_sample_rows`
to limit it to a sample, which is faster on very large inputs but lossy:

```python
from mountainash_files.formats.json import JsonSpec

JsonSpec(ndjson=True, infer_sample_rows=1000)
```

> **Warning.** A sample cannot see later rows. With polars 2.0, a field that
> first appears after the sample is silently dropped, and a late value of a
> different type raises `ParseError`. Leave `infer_sample_rows` unset unless you
> know the schema is uniform.

## Remote Parquet

When `ParquetSpec(columns=...)` selects part of a file, files requests a ranged
handle from transport, so only the footer and the selected column chunks are
fetched. Without `columns`, the whole object is read. Servers that do not
support byte ranges, and transformed paths such as `x.parquet.gz`, fall back to
reading the whole object.

Read-ahead is governed by the storage profile's `RANGE_*` settings, not by
files. Under `parameters:` in the profile, for example:

```yaml
storage_profiles:
  lake:
    provider: http
    parameters:
      RANGE_CACHE: readahead
      RANGE_BLOCK_SIZE: 65536
```

The default read-ahead is 1 MiB. On a 7.6 MB file with one 1.1 MB column, a
single-column read fetched 2.2 MB with the default and 1.2 MB with a 64 KiB
read-ahead. Smaller blocks suit narrow projections of wide files; the default
suits reading most of a file.

## Plugin formats

`register_format(..., access="bytes" | "random")` declares how a format's parser
receives input. `"bytes"` (default) passes the whole decoded object. `"random"`
passes a seekable ranged handle when no transforms apply and the server supports
ranges; otherwise the parser receives `bytes`. A parser registered as `"random"`
must handle both and must finish reading before it returns.

`access` may also be a callable of the spec that returns either value.

## Dependencies

polars 2.x is now a core dependency. The `xlsx` extra pins `fastexcel>=0.21,<0.22`
and `openpyxl>=3.1` (used only to read XLSX header labels).
