---
title: Format options
---

# Format options

Each built-in format has a format spec, a frozen dataclass whose fields are that format's options: the CSV delimiter, the JSON property to read, the Parquet columns to load, the Excel sheet to open. Passing a spec as `format=` on a `FileSourceSpec` or `FileSinkSpec`, or to `parse_bytes`, `serialise_bytes` and `inspect_schema_bytes`, applies those options. Passing a format key such as `"csv"`, or letting the path suffix choose, uses the spec's defaults. [Formats and format specs](../files-specs-and-formats/index.md#formats-and-format-specs) explains the relationship between a format key and its spec, and [How a format is chosen](../files-specs-and-formats/index.md#how-a-format-is-chosen) explains resolution.

The spec classes live in public modules, one per format:

| Spec | Module | Format key |
|---|---|---|
| `CsvSpec` | `mountainash_files.formats.csv` | `csv` |
| `TsvSpec` | `mountainash_files.formats.tsv` | `tsv` |
| `JsonSpec` | `mountainash_files.formats.json` | `json` |
| `ParquetSpec` | `mountainash_files.formats.parquet` | `parquet` |
| `XlsxSpec` | `mountainash_files.formats.xlsx` | `xlsx` |
| `XmlSpec` | `mountainash_files.formats.xml` | `xml` |

## Format specs as options

<!-- concept:20 -->

A format spec converts to and from a plain dictionary. `to_options()` returns the fields that differ from their defaults, and `to_options(full=True)` returns every field. Tuples become lists when the dictionary is encoded as JSON, and `from_options()` turns them back into tuples, including nested tuples such as `CsvSpec.dtypes`. A spec can therefore be stored in a JSON or YAML configuration file and rebuilt exactly:

```python
import json

from mountainash_files.formats.csv import CsvSpec

spec = CsvSpec(delimiter=";", comment_char="#", columns=("region", "total"))
options = spec.to_options()
print(options)
print(json.dumps(options))

restored = CsvSpec.from_options(json.loads(json.dumps(options)))
print(restored.columns, restored == spec)
print(len(spec.to_options(full=True)))
```

```text
{'delimiter': ';', 'comment_char': '#', 'columns': ('region', 'total')}
{"delimiter": ";", "comment_char": "#", "columns": ["region", "total"]}
('region', 'total') True
17
```

The dictionary holds field values only, not the format. `TsvSpec().to_options()` is `{}`, so store the format key (each spec class's `FORMAT`) next to the options and use it to pick the class when rebuilding. `from_options()` passes keys straight to the constructor: an unknown key raises `TypeError`, and the constructor's own checks still run, so `CsvSpec(temporal="auto")` raises `ValueError`. `to_options()` raises `ValueError` for a field value that cannot be encoded as JSON. The `format_options` example in `examples/format_options/example.py` performs the same round trip before parsing a file.

<!-- concept:21 -->

### Capability flags

Every spec class also carries class-level flags that describe the format rather than one file. They are read by the package, never passed as options, and are the same for every instance:

| Flag | Meaning |
|---|---|
| `FORMAT` | The lowercase format key. |
| `SUFFIXES` | Path suffixes that select the format, matched case-insensitively. |
| `MEDIATYPES` | Media types that select the format. Empty by default. |
| `TABULAR` | `True` when parsed data can be normalised to an Arrow table or records. Default `True`. |
| `APPENDABLE` | `True` when a sink may use `write_disposition="append"`. Default `False`. |
| `COMPLEX_HANDLER_KEY` | Optional link to a mountainash-treespec handler. Default `None`. |

`TABULAR` decides what `parse` returns. For a tabular format, the output seam turns the parser's result into a `pyarrow.Table`, or into a list of dictionaries with `output="pydata"` (see [Arrow or Python records](../reading-and-writing/index.md#arrow-or-python-records)). For a non-tabular format such as XML, the parser's object is returned unchanged whatever `output` says. `APPENDABLE` and `TABULAR` must both be `True` for append, otherwise `write` raises `WriteError` before touching the destination (`src/mountainash_files/_operations.py`). `COMPLEX_HANDLER_KEY` is covered in [Complex formats and treespec](../custom-formats/index.md#complex-formats-and-treespec).

The flags are ordinary class attributes:

```python
from mountainash_files.formats.csv import CsvSpec
from mountainash_files.formats.json import JsonSpec
from mountainash_files.formats.parquet import ParquetSpec
from mountainash_files.formats.tsv import TsvSpec
from mountainash_files.formats.xlsx import XlsxSpec
from mountainash_files.formats.xml import XmlSpec

for cls in (CsvSpec, TsvSpec, JsonSpec, ParquetSpec, XlsxSpec, XmlSpec):
    print(f"{cls.FORMAT:8} tabular={cls.TABULAR!s:5} appendable={cls.APPENDABLE!s:5} {cls.SUFFIXES}")
```

```text
csv      tabular=True  appendable=False ('.csv',)
tsv      tabular=True  appendable=False ('.tsv', '.tab')
json     tabular=True  appendable=False ('.json', '.ndjson', '.jsonl', '.geojson')
parquet  tabular=True  appendable=True  ('.parquet', '.pq')
xlsx     tabular=True  appendable=False ('.xlsx', '.xlsm', '.xlsb', '.ods')
xml      tabular=False appendable=False ('.xml',)
```

Whether a format can be written or schema-inspected is not a flag. It depends on whether a serialiser and a schema inspector were registered with the format; [What each format supports](#what-each-format-supports) lists both for the built-in formats.

## Dates and times

<!-- concept:58 -->

CSV, TSV, JSON and Excel specs have a `temporal` field. With the default `"infer"`, a text column whose every non-null value is an ISO 8601 date becomes `date32`, and one whose every value is an ISO date and time becomes a timestamp. With `"text"`, the column stays a string. Any other value raises `ValueError` when the spec is built.

The rules differ by engine:

- CSV and TSV use the pyarrow CSV reader's own inference. Times without fractions give `timestamp[s]`, a `Z` or offset suffix gives a timezone-aware timestamp, and `"text"` re-reads the input with those columns forced to `string`.
- JSON and Excel use the package's ISO check in `src/mountainash_files/formats/_engines.py`. A column becomes `date32` when every value matches `YYYY-MM-DD`, or a timestamp when every value matches `YYYY-MM-DD` followed by `T` or a space and `HH:MM:SS` with optional fractions. The unit is `timestamp[ns]` if any value has fractional seconds and `timestamp[s]` otherwise. Values with a timezone suffix, and values that are not real calendar dates such as `2024-02-30`, leave the column as text.

```python
from mountainash_files import parse_bytes
from mountainash_files.formats.csv import CsvSpec
from mountainash_files.formats.json import JsonSpec

CSV = (
    b"day,seen_at,logged_at\n"
    b"2024-03-01,2024-03-01 09:30:00,2024-03-01T09:30:00Z\n"
    b"2024-03-02,2024-03-02T10:15:00,2024-03-02T10:15:00Z\n"
)
print(parse_bytes(CSV, "csv").data.schema)
print(parse_bytes(CSV, CsvSpec(temporal="text")).data.schema)

NDJSON = (
    b'{"day": "2024-03-01", "seen_at": "2024-03-01T09:30:00.250", '
    b'"due": "2024-02-30", "logged_at": "2024-03-01T09:30:00Z"}\n'
)
print(parse_bytes(NDJSON, JsonSpec(ndjson=True)).data.schema)
```

```text
day: date32[day]
seen_at: timestamp[s]
logged_at: timestamp[s, tz=UTC]
day: string
seen_at: string
logged_at: string
day: date32[day]
seen_at: timestamp[ns]
due: string
logged_at: string
```

Use `temporal="text"` when date-like strings are identifiers, or when the exact text must survive a round trip. Parquet stores its own types and XML returns elements, so neither has the option.

## CSV

<!-- concept:51 -->

`CsvSpec` describes a delimited text file: its dialect (delimiter, quoting, line ending, encoding), where its header is, which records are comments, which columns to keep and how to type them. Parsing returns an Arrow table. Column types are inferred from every record: `int64`, `double`, `bool`, `date32`, timestamps and `string`. Writing takes a `pyarrow.Table` and produces one record per row, with a header record unless `header=False`.

| Field | Default | Purpose |
|---|---|---|
| `delimiter` | `","` | Field separator; may be more than one character. |
| `line_terminator` | `"\n"` | Record separator. |
| `quote_char` | `'"'` | Quote character, or `None` for no quoting. |
| `double_quote` | `True` | A doubled quote inside a quoted field is a literal quote. |
| `escape_char` | `None` | Character that makes the next character literal. |
| `null_sequence` | `None` | Text that means null. |
| `skip_initial_space` | `False` | Drop spaces that follow a delimiter. |
| `header` | `True` | Whether the file has a header. |
| `header_rows` | `(1,)` | Record numbers that make up the header. |
| `header_join` | `" "` | Separator for labels built from several header rows. |
| `comment_char` | `None` | Records starting with this text are skipped. |
| `comment_rows` | `()` | Record numbers to skip. |
| `encoding` | `"utf-8"` | Text encoding for reading and writing. |
| `columns` | `None` | Columns to keep, in this order. |
| `dtypes` | `None` | Column type overrides, as `(name, type)` pairs. |
| `temporal` | `"infer"` | See [Dates and times](#dates-and-times). |
| `formula_neutralise` | `False` | Write-only spreadsheet formula guard. |

Simple files go straight to the pyarrow CSV reader. Files that use comments, multi-character tokens, non-contiguous header rows or other features that reader cannot express are tokenised in Python first and then handed to pyarrow, so every option produces the same types either way. [CSV internals](../format-internals/index.md#csv-internals) describes the two paths.

The serialiser accepts a `pyarrow.Table`. Passing a list of dictionaries to `write` or `serialise_bytes` for CSV currently fails with `AttributeError`; convert with `pa.Table.from_pylist(rows)` first. Values that cannot be represented safely in the chosen dialect raise `WriteError` before anything is written.

<!-- concept:52 -->

### Delimiters and quoting

`delimiter` and `line_terminator` must be non-empty and neither may be a prefix of the other. `quote_char` and `escape_char` are single characters or `None`, must differ, and must not appear inside the delimiter or terminator; a spec that breaks these rules raises `ParseError` on parse and `WriteError` on write. With `double_quote=True`, `''` inside a field quoted with `'` reads as one `'`. An escape character makes the following character literal, so `\,` keeps a comma inside a field. `skip_initial_space` drops spaces that follow a delimiter, and `encoding` decodes the input before tokenising.

```python
from mountainash_files import parse_bytes
from mountainash_files.formats.csv import CsvSpec

DATA = b"id|name|note\r\n1|'Smith, J'|'said ''hi'''\r\n2|Lee|\r\n"
spec = CsvSpec(delimiter="|", quote_char="'", line_terminator="\r\n")
print(parse_bytes(DATA, spec).data.to_pylist())

ESCAPED = b"id,city\n1,Paris\\, France\n"
print(parse_bytes(ESCAPED, CsvSpec(escape_char="\\")).data.to_pylist())

SPACED = b"id, city\n1, Oslo\n"
print(parse_bytes(SPACED, CsvSpec(skip_initial_space=True)).data.to_pylist())

LATIN = "id,city\n1,Zürich\n".encode("latin-1")
print(parse_bytes(LATIN, CsvSpec(encoding="latin-1")).data.to_pylist())
```

```text
[{'id': 1, 'name': 'Smith, J', 'note': "said 'hi'"}, {'id': 2, 'name': 'Lee', 'note': None}]
[{'id': 1, 'city': 'Paris, France'}]
[{'id': 1, 'city': 'Oslo'}]
[{'id': 1, 'city': 'Zürich'}]
```

Quoted fields may contain the delimiter and line breaks. An unterminated quote raises `ParseError`. A quote in the middle of an unquoted field is kept as a literal character, following RFC 4180.

<!-- concept:53 -->

### Null sequence

With `null_sequence=None`, an unquoted empty field reads as null and a quoted `""` reads as an empty string. Setting `null_sequence` makes that exact text, quoted or not, the only null marker; empty fields then read as empty strings. On write, nulls are written as the marker, and a non-null value (or column name) equal to the marker raises `WriteError`, because it could not be told apart from a null when read back.

```python
import pyarrow as pa

from mountainash_files import WriteError, parse_bytes, serialise_bytes
from mountainash_files.formats.csv import CsvSpec

DATA = b'id,score,label\n1,,""\n2,NA,NA\n'
print(parse_bytes(DATA, "csv").data.to_pylist())
print(parse_bytes(DATA, CsvSpec(null_sequence="NA")).data.to_pylist())

table = pa.table({"id": [1, 2], "label": [None, "x"]})
print(serialise_bytes(table, CsvSpec(null_sequence="NA")))

clash = pa.table({"label": ["NA"]})
try:
    serialise_bytes(clash, CsvSpec(null_sequence="NA"))
except WriteError as exc:
    print(exc)
```

```text
[{'id': 1, 'score': None, 'label': ''}, {'id': 2, 'score': 'NA', 'label': 'NA'}]
[{'id': 1, 'score': '', 'label': ''}, {'id': 2, 'score': None, 'label': None}]
b'"id","label"\n"1","NA"\n"2","x"\n'
Cannot serialise csv: non-null value collides with null marker
```

Without a null sequence, the writer quotes every field, so a null is written as `""` and reads back as an empty string. Set `null_sequence` on both the writing and the reading spec when nulls must survive a CSV round trip.

<!-- concept:54 -->

### Header rows

`header_rows` lists the record numbers, counted from 1, that form the header. With several rows, the labels for each column are joined with `header_join`, skipping empty cells. Records above the last header row that are not listed are kept as data. A column whose label comes out empty is named `fieldN`, where N is its one-based position, and duplicate final labels raise `ParseError`. With `header=False`, every record is data and the columns are named `field1`, `field2` and so on.

```python
from mountainash_files import parse_bytes
from mountainash_files.formats.csv import CsvSpec

REPORT = b"""Sales,Sales,Returns
north,south,
120,95,4
130,90,6
"""
spec = CsvSpec(header_rows=(1, 2), header_join="_")
print(parse_bytes(REPORT, spec).data.column_names)

print(parse_bytes(b"1,2\n3,4\n", CsvSpec(header=False)).data.to_pylist())
```

```text
['Sales_north', 'Sales_south', 'Returns']
[{'field1': 1, 'field2': 2}, {'field1': 3, 'field2': 4}]
```

Header row numbers count records after comment rows and blank lines are removed.

<!-- concept:55 -->

### Comment rows

Two options remove records before the header is located. `comment_rows` lists record numbers to drop, counted from 1 over every logical record in the input, blank ones included. `comment_char` drops every record that starts with that text, wherever it appears. A quoted field containing a line break is one logical record, so a comment marker inside it is not a comment.

```python
from mountainash_files import parse_bytes
from mountainash_files.formats.csv import CsvSpec

EXPORT = b"""Exported 2024-03-01 by billing
region,total
# north is provisional
north,120
south,95
"""
spec = CsvSpec(comment_rows=(1,), comment_char="#")
print(parse_bytes(EXPORT, spec).data.to_pylist())
```

```text
[{'region': 'north', 'total': 120}, {'region': 'south', 'total': 95}]
```

A data record whose first field legitimately starts with the comment text is dropped too. When writing with `comment_char` set, the serialiser quotes or escapes a first field that would otherwise start with it, and raises `WriteError` if it cannot.

<!-- concept:56 -->

### Column selection

`columns` keeps only the named columns, in the order given. The names are final header labels, after `header_rows` and `header_join` are applied. A name that is not in the file raises `ParseError`. `columns=()` returns a table with no columns but the correct number of rows, after the whole file has been validated. Selection does not shorten the read: the whole file is still fetched and tokenised.

<!-- concept:57 -->

### Column types

`dtypes` overrides inference for named columns. It is a tuple of `(column, type)` pairs, and six type names are recognised: `string`, `int64`, `int32`, `float64`, `float32` and `bool`. Any other name currently falls back to `string` without an error, so check spelling against that list. A value that cannot be converted raises `ParseError`.

```python
from mountainash_files import parse_bytes
from mountainash_files.formats.csv import CsvSpec

DATA = b"region,code,total,share\nnorth,007,120,0.5\nsouth,012,95,0.25\n"

print(parse_bytes(DATA, "csv").data.schema)

spec = CsvSpec(
    columns=("code", "total", "share"),
    dtypes=(("code", "string"), ("total", "int32"), ("share", "decimal")),
)
table = parse_bytes(DATA, spec).data
print(table.schema)
print(table.column("code").to_pylist())
```

```text
region: string
code: int64
total: int64
share: double
code: string
total: int32
share: string
['007', '012']
```

Forcing `code` to `string` keeps its leading zeros. `decimal` is not one of the six names, so `share` became `string` rather than a decimal type. For other Arrow types, read the column as `string` and cast the returned table with `pyarrow.compute.cast`.

<!-- concept:59 -->

### Formula neutralisation

A CSV file opened in a spreadsheet application may evaluate a cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return as a formula, which allows CSV injection when the data came from untrusted users. `formula_neutralise=True` makes the writer prefix such string cells, and header labels, with `'`. Numbers are never altered. The option affects writing only: the prefix becomes part of the data and parsing does not remove it.

```python
import pyarrow as pa

from mountainash_files import parse_bytes, serialise_bytes
from mountainash_files.formats.csv import CsvSpec

table = pa.table({"name": ["=HYPERLINK(\"http://x\")", "Lee"], "delta": [-5, 3]})
spec = CsvSpec(formula_neutralise=True)
encoded = serialise_bytes(table, spec)
print(encoded)
print(parse_bytes(encoded, spec).data.to_pylist())
```

```text
b'"name","delta"\n"\'=HYPERLINK(""http://x"")","-5"\n"Lee","3"\n'
[{'name': '\'=HYPERLINK("http://x")', 'delta': -5}, {'name': 'Lee', 'delta': 3}]
```

Use it for exports that people will open in a spreadsheet, and leave it off for files read by other programs. It applies equally to `TsvSpec`.

## TSV

<!-- concept:60 -->

`TsvSpec` is `CsvSpec` with a tab as its default delimiter, registered under its own format key, `tsv`, with the suffixes `.tsv` and `.tab` and the media type `text/tab-separated-values`. It is a subclass of `CsvSpec`, so every CSV field, behaviour and limit above applies, and the same parser, serialiser and schema inspector handle it. `to_options()` omits the tab because it is the default.

A file that needs options beyond the defaults takes an explicit `TsvSpec`. Here a comment line breaks the default parse:

```python
import tempfile
from pathlib import Path

from mountainash_files import FileSourceSpec, ParseError, parse
from mountainash_files.formats.tsv import TsvSpec

with tempfile.TemporaryDirectory() as root:
    path = Path(root) / "codes.tab"
    path.write_bytes(b"code\tlabel\nA1\tAlpha\n# draft\nB2\tBeta\n")

    try:
        parse(FileSourceSpec(path=str(path)))
    except ParseError as exc:
        print(exc)

    result, = parse(FileSourceSpec(path=str(path), format=TsvSpec(comment_char="#")))
    print(result.format_key, result.data.to_pylist())
```

```text
[tsv] CSV parse error: Expected 2 columns, got 1: # draft
tsv [{'code': 'A1', 'label': 'Alpha'}, {'code': 'B2', 'label': 'Beta'}]
```

The error message names the `tsv` key, while the message text comes from the shared CSV engine. Like CSV, TSV does not support append.

## JSON and NDJSON

<!-- concept:61 -->

`JsonSpec` reads a JSON document, or newline-delimited JSON, and turns a list of records into a table. It covers arrays of objects, arrays of arrays with or without a header row, a single object, and data nested under a property. Records that are not tabular, such as an array of numbers, are returned as Python values with `output="pydata"`.

| Field | Default | Purpose |
|---|---|---|
| `property` | `None` | Dotted path to the records inside the document. |
| `item_type` | `None` | `"object"` or `"array"`; inferred from the first record when `None`. |
| `item_keys` | `None` | Exact keys to keep from object rows, in order. |
| `header` | `True` | For array rows: whether the first row holds the column names. |
| `ndjson` | `False` | Read one JSON value per line. |
| `temporal` | `"infer"` | See [Dates and times](#dates-and-times). |
| `infer_sample_rows` | `None` | Rows used for type inference; see [Inference sample rows](#inference-sample-rows). |

The input encoding is detected (UTF-8, UTF-16 or UTF-32, with or without a byte order mark), and empty input raises `ParseError`. A plain array of objects, or NDJSON with object rows, is read by polars; property selection and array rows go through the standard library decoder first. Types are inferred over the whole input, and a column whose values have mixed types widens to `string`. A number too large for a double, such as `1e400`, raises `ParseError`.

The serialiser accepts an Arrow table, a list or a dictionary. A table is converted to records first. It writes a JSON document, or one line per record with `ndjson=True`, and it turns any value the `json` module cannot encode into its `str()` form, so dates become `"2024-03-01"` and timestamps `"2024-03-01 09:30:00"`.

<!-- concept:19 -->

### Suffix overrides

A format can register suffix overrides: field values applied to the default spec when a path suffix selects the format. JSON registers two. A path ending in `.ndjson` or `.jsonl` resolves to the `json` format with `ndjson=True`, while `.json` and `.geojson` keep `ndjson=False`. Overrides apply only to suffix resolution. A source with `format="json"` or with an explicit `JsonSpec` gets exactly what it names:

```python
import tempfile
from pathlib import Path

from mountainash_files import FileSourceSpec, ParseError, parse

with tempfile.TemporaryDirectory() as root:
    path = Path(root) / "events.jsonl"
    path.write_bytes(b'{"id": 1, "kind": "open"}\n{"id": 2, "kind": "close"}\n')

    result, = parse(FileSourceSpec(path=str(path)))
    print(result.format_key, result.spec.ndjson, result.data.num_rows)

    try:
        parse(FileSourceSpec(path=str(path), format="json"))
    except ParseError as exc:
        print(exc)
```

```text
json True 2
[json] Extra data: line 2 column 1 (char 26)
```

The same holds for writing: a sink path ending in `.jsonl` writes NDJSON. Format plugins can declare their own overrides; see [Registering a format](../custom-formats/index.md#registering-a-format).

<!-- concept:62 -->

### NDJSON

With `ndjson=True`, each non-blank line is one JSON value. Object lines become rows, and a key missing from some lines becomes a null in those rows. Serialising with `ndjson=True` writes one record per line with a trailing newline; without it, the same table is written as one JSON array.

```python
from mountainash_files import parse_bytes, serialise_bytes
from mountainash_files.formats.json import JsonSpec

LINES = b'{"id": 1, "kind": "open"}\n\n{"id": 2, "kind": "close", "user": "lee"}\n'
table = parse_bytes(LINES, JsonSpec(ndjson=True)).data
print(table.to_pylist())

print(serialise_bytes(table, JsonSpec(ndjson=True)))
print(serialise_bytes(table, "json"))
```

```text
[{'id': 1, 'kind': 'open', 'user': None}, {'id': 2, 'kind': 'close', 'user': 'lee'}]
b'{"id": 1, "kind": "open", "user": null}\n{"id": 2, "kind": "close", "user": "lee"}\n'
b'[{"id": 1, "kind": "open", "user": null}, {"id": 2, "kind": "close", "user": "lee"}]'
```

NDJSON is also the only JSON form that schema discovery can read partially: with `infer_schema_rows` set, it reads forward only until it has enough lines (see [How a schema was obtained](../schema-discovery/index.md#how-a-schema-was-obtained)).

<!-- concept:63 -->

### Property path

`property` selects the records inside a larger document. It is a dot-separated list of object keys, followed from the top level; each step must be an object containing the key, otherwise `ParseError` names the missing path. Array indexes are not supported. The value found is treated like a top-level document, so a list becomes rows and a single object becomes one row. `property` cannot be combined with `ndjson=True`: the lines form a list, which has no keys, so the lookup raises `ParseError`.

```python
from mountainash_files import ParseError, parse_bytes
from mountainash_files.formats.json import JsonSpec

PAYLOAD = b'{"meta": {"page": 1}, "data": {"items": [{"id": 1}, {"id": 2}]}}'
print(parse_bytes(PAYLOAD, JsonSpec(property="data.items")).data.to_pylist())

try:
    parse_bytes(PAYLOAD, JsonSpec(property="data.rows"))
except ParseError as exc:
    print(exc)
```

```text
[{'id': 1}, {'id': 2}]
[json] property 'data.rows' was not found
```

A GeoJSON `FeatureCollection` read without a property is one row with `type` and `features` columns. `property="features"` gives one row per feature, with `properties` and `geometry` as struct columns.

<!-- concept:64 -->

### Row shapes

The first record decides the row shape unless `item_type` sets it. Object rows become columns named by their keys, collected in first-seen order across all rows; `item_keys` fixes the column list instead, dropping other keys and adding missing ones as null. Array rows take their names from the first row when `header=True` (an empty or null name becomes `fieldN`) or are named `field1`, `field2` and so on when `header=False`; every array row must have the same width. Mixed object and array rows raise `ParseError`.

Records that are neither objects nor arrays, such as numbers or strings, are not tabular. `parse_bytes(..., output="pydata")` returns them as a Python list, and the default Arrow output raises `ParseError`:

```python
from mountainash_files import ParseError, parse_bytes
from mountainash_files.formats.json import JsonSpec

ARRAYS = b'[["id", "kind"], [1, "open"], [2, "close"]]'
print(parse_bytes(ARRAYS, "json").data.to_pylist())
print(parse_bytes(ARRAYS, JsonSpec(header=False)).data.column_names)

OBJECTS = b'[{"id": 1, "kind": "open", "debug": true}, {"id": 2}]'
spec = JsonSpec(item_keys=("id", "kind", "user"))
print(parse_bytes(OBJECTS, spec).data.to_pylist())

SCALARS = b"[3, 1, 4]"
print(parse_bytes(SCALARS, "json", output="pydata").data)
try:
    parse_bytes(SCALARS, "json")
except ParseError as exc:
    print(exc)
```

```text
[{'id': 1, 'kind': 'open'}, {'id': 2, 'kind': 'close'}]
['field1', 'field2']
[{'id': 1, 'kind': 'open', 'user': None}, {'id': 2, 'kind': None, 'user': None}]
[3, 1, 4]
[json] non-record JSON array is not tabular; expected an array of objects
```

## Parquet

<!-- concept:66 -->

`ParquetSpec` reads and writes Apache Parquet files with pyarrow. Parquet files carry their own schema, so there is no type inference: parsing returns the stored Arrow types and schema metadata. The spec has one field, `columns`, and is the only built-in format with `APPENDABLE=True`; [Appending to Parquet](../write-modes/index.md#appending-to-parquet) covers the schema-checked append. Schema discovery reads only the footer, as described in [Parquet footers](../schema-discovery/index.md#parquet-footers).

The serialiser ignores the spec and calls `pyarrow.parquet.write_table` with its defaults, so `ParquetSpec` has no writer options such as compression codec or row-group size. When those matter, serialise the table with pyarrow yourself and write the bytes; `write` stores bytes as they are, without a serialiser:

```python
import io
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from mountainash_files import FileSinkSpec, write

table = pa.table({"id": list(range(1000))})
buffer = io.BytesIO()
pq.write_table(table, buffer, compression="zstd", row_group_size=250)

with tempfile.TemporaryDirectory() as root:
    path = str(Path(root) / "ids.parquet")
    write(FileSinkSpec(path=path), buffer.getvalue())
    print(pq.ParquetFile(path).metadata.num_row_groups)
```

```text
4
```

Raw bytes cannot be appended, so this route suits replace writes. Like CSV, the Parquet serialiser takes a `pyarrow.Table`.

<!-- concept:67 -->

### Column projection

`columns` names the columns to read, in the order wanted. A name with a dot that is not itself a column name selects a field inside a struct column, and the result column is named after the leaf. Duplicate names are kept, and a name that does not exist raises `ParseError`.

```python
import tempfile
from pathlib import Path

import pyarrow as pa

from mountainash_files import FileSinkSpec, FileSourceSpec, parse, write
from mountainash_files.formats.parquet import ParquetSpec

table = pa.table({
    "id": [1, 2],
    "region": ["north", "south"],
    "geo": [{"lat": -33.9, "lon": 151.2}, {"lat": -37.8, "lon": 145.0}],
})

with tempfile.TemporaryDirectory() as root:
    path = str(Path(root) / "sites.parquet")
    write(FileSinkSpec(path=path), table)

    spec = ParquetSpec(columns=("region", "geo.lat"))
    result, = parse(FileSourceSpec(path=path, format=spec))
    print(result.data.schema)
    print(result.data.to_pylist())
```

```text
region: string
lat: double
[{'region': 'north', 'lat': -33.9}, {'region': 'south', 'lat': -37.8}]
```

Projection also changes how the file is fetched. With `columns` set, the format asks for random access: on storage that supports byte ranges, mountainash-transport hands the parser a seekable handle, and only the footer and the selected column chunks are downloaded. Without `columns`, or when a transform such as `.gz` applies, or when the server does not support ranges, the whole object is read. Read-ahead size is a transport storage-profile setting; see [Stream access](../storage-and-transforms/index.md#stream-access) and the [mountainash-transport documentation](https://docs.mountainash.io/mountainash-transport/). When appending, the projection is ignored and the full existing file is read.

## Excel

<!-- concept:68 -->

`XlsxSpec` reads one worksheet from an Excel or OpenDocument workbook into an Arrow table. It handles the suffixes `.xlsx`, `.xlsm`, `.xlsb` and `.ods`, and the XLSX media type. Reading needs the `[xlsx]` extra, which installs fastexcel (the calamine engine, which reads cell values) and openpyxl (used only to read header labels). Without them, parsing raises `MissingDependencyError` with the install command; see [Optional extras](../files-specs-and-formats/index.md#where-files-live).

| Field | Default | Purpose |
|---|---|---|
| `sheet_name` | `None` | Sheet to read, by name. |
| `sheet_number` | `None` | Sheet to read, counted from 1. |
| `header`, `header_rows`, `header_join` | `True`, `(1,)`, `" "` | As for CSV. |
| `comment_rows`, `comment_char` | `()`, `None` | As for CSV; `comment_char` is tested against the first used column. |
| `temporal` | `"infer"` | See [Dates and times](#dates-and-times). |
| `infer_sample_rows` | `None` | Rows used for type inference. |
| `max_decompressed_bytes` | 512 MiB | Workbook container limit. |
| `max_members` | 1,000 | Workbook container limit. |

Header and comment rows work as they do for CSV and are removed before types are inferred. Rows above the header that are not comment rows are data, and can change a column's type. Whole-number floats become `int64`, and a column whose rows mix numbers and text becomes `double` or `string`. Leading empty columns are kept and named `fieldN`; a trailing column with no label and no values, and trailing empty rows, are dropped. [Excel internals](../format-internals/index.md#excel-internals) has the details.

<!-- concept:69 -->

### Sheet selection

With neither field set, the first sheet is read. `sheet_name` picks a sheet by name and `sheet_number` by one-based position; setting both raises `ParseError`, and so does a sheet number below 1 or a sheet that does not exist. The example builds a two-sheet workbook with openpyxl and reads it three ways:

```python
import io

from openpyxl import Workbook

from mountainash_files import ParseError, parse_bytes
from mountainash_files.formats.xlsx import XlsxSpec

workbook = Workbook()
summary = workbook.active
summary.title = "Summary"
summary.append(["metric", "value"])
summary.append(["total", 215])
sales = workbook.create_sheet("Sales")
sales.append(["Quarterly sales"])
sales.append(["region", "total", "booked"])
sales.append(["north", 120, "2024-03-01"])
sales.append(["south", 95, "2024-03-02"])
buffer = io.BytesIO()
workbook.save(buffer)
data = buffer.getvalue()

print(parse_bytes(data, "xlsx").data.to_pylist())

by_name = parse_bytes(data, XlsxSpec(sheet_name="Sales", comment_rows=(1,))).data
print(by_name.schema)

by_number = parse_bytes(data, XlsxSpec(sheet_number=2, header_rows=(2,))).data
print(by_number.to_pylist())

try:
    parse_bytes(data, XlsxSpec(sheet_name="Sales", sheet_number=2))
except ParseError as exc:
    print(exc)
```

```text
[{'metric': 'total', 'value': 215}]
region: string
total: int64
booked: date32[day]
[{'region': 'Quarterly sales', 'total': None, 'booked': None}, {'region': 'north', 'total': '120', 'booked': datetime.date(2024, 3, 1)}, {'region': 'south', 'total': '95', 'booked': datetime.date(2024, 3, 2)}]
[xlsx] sheet_name and sheet_number are mutually exclusive
```

Marking the title row as a comment gives clean types and an ISO-date column inferred as `date32`. Using only `header_rows=(2,)` keeps the title row as data, so `total` becomes `string`. fastexcel also logs `Could not determine dtype for column N, falling back to string` warnings through the `fastexcel.types.dtype` logger for that read; they come from the third-party engine and do not change the result.

<!-- concept:70 -->

### Excel is read-only

No serialiser is registered for `xlsx`, so writing a workbook is not supported. `write` to an `.xlsx` path, a sink with `format="xlsx"`, and `serialise_bytes(..., "xlsx")` all raise `WriteError`. To produce a workbook, write it with a spreadsheet library such as openpyxl (installed by the `[xlsx]` extra), save it to bytes, and pass the bytes to `write`, which stores them unchanged. Schema discovery is supported.

<!-- concept:71 -->

### Workbook container limits

An XLSX file is a zip container, so a small file can inflate to a very large one. Before the engine sees any bytes, the container is inflated once in chunks and the output discarded, counting the bytes actually produced and the number of members. Over `max_decompressed_bytes` (default 512 MiB across all members) or `max_members` (default 1,000) parsing raises `ArchiveLimitError`, whose message names the field to raise. Both limits must be positive integers, checked when the spec is built. The defaults sit well above real workbooks: the README records a 1-million-row, 3-column sheet at 144 MiB uncompressed.

```python
import io

import pyarrow as pa
from openpyxl import Workbook

from mountainash_files import WriteError, parse_bytes, serialise_bytes
from mountainash_files.formats.xlsx import XlsxSpec

buffer = io.BytesIO()
Workbook().save(buffer)
data = buffer.getvalue()

try:
    parse_bytes(data, XlsxSpec(max_members=3))
except Exception as exc:
    print(type(exc).__name__, exc)

try:
    serialise_bytes(pa.table({"a": [1]}), "xlsx")
except WriteError as exc:
    print(exc)
```

```text
ArchiveLimitError zip: 9 members exceeds max_members=3; raise XlsxSpec.max_members if trusted
No serialiser registered for format 'xlsx'
```

`ArchiveLimitError` is not exported from the package root, which is why the example catches `Exception`; [Archive errors](../errors/index.md#archive-errors) explains how to handle it. Raise the limits for trusted workbooks, for example `XlsxSpec(max_decompressed_bytes=2 * 1024**3)`. These limits are separate from the `ZipArchive` limits in [Gzip archives and decompression limits](../selecting-files/index.md#gzip-archives-and-decompression-limits), which apply when a workbook is itself a member of an archive. Damaged or ambiguous zip directories raise `ParseError`; [ZIP container hardening](../format-internals/index.md#zip-container-hardening) lists the cases.

<!-- concept:65 -->

### Inference sample rows

By default, JSON and Excel infer each column's type from every row. `infer_sample_rows=N` on `JsonSpec` or `XlsxSpec` limits inference to the first N rows, which is faster on large inputs but can be wrong when later rows differ. With JSON, a key that first appears after the sample is dropped without an error, and a later value of another type raises `ParseError`:

```python
from mountainash_files import ParseError, parse_bytes
from mountainash_files.formats.json import JsonSpec

LINES = b'{"id": 1}\n{"id": 2}\n{"id": 3, "note": "late"}\n'
print(parse_bytes(LINES, JsonSpec(ndjson=True)).data.column_names)
print(parse_bytes(LINES, JsonSpec(ndjson=True, infer_sample_rows=2)).data.column_names)

MIXED = b'{"id": 1}\n{"id": 2}\n{"id": "three"}\n'
try:
    parse_bytes(MIXED, JsonSpec(ndjson=True, infer_sample_rows=2))
except ParseError as exc:
    print(exc)
```

```text
['id', 'note']
['id']
[json] cannot parse 'three' (string) as Int64
```

Leave it unset unless the schema is known to be uniform. The value must be a positive integer or `None`, checked when the spec is built. It is distinct from the `infer_schema_rows` argument of `inspect_schema`, which bounds how many rows schema discovery reads; a spec with `infer_sample_rows` set always reports a `bounded` schema basis.

## XML

<!-- concept:72 -->

`XmlSpec` parses an XML document into an element tree. XML is the one built-in format with `TABULAR=False`: `parse` returns the root element, or a list of elements when `xpath` is set, and the `output` argument has no effect. The serialiser writes an element back to bytes with an XML declaration. XML has no schema inspector, so `inspect_schema` raises `SchemaDiscoveryUnsupportedError`.

| Field | Default | Purpose |
|---|---|---|
| `xpath` | `None` | Path expression selecting elements below the root. |
| `encoding` | `None` | Override the document's declared encoding (lxml only). |

```python
from mountainash_files import SchemaDiscoveryUnsupportedError, inspect_schema_bytes, parse_bytes, serialise_bytes
from mountainash_files.formats.xml import XmlSpec

DOC = b"""<?xml version="1.0"?>
<catalog>
  <book id="b1"><title>Dune</title></book>
  <book id="b2"><title>Emma</title></book>
</catalog>"""

root = parse_bytes(DOC, "xml").data
print(type(root).__module__, root.tag)

books = parse_bytes(DOC, XmlSpec(xpath="./book")).data
print([(book.get("id"), book.findtext("title")) for book in books])

print(serialise_bytes(root, "xml")[:38])

try:
    inspect_schema_bytes(DOC, "xml")
except SchemaDiscoveryUnsupportedError as exc:
    print(exc)
```

```text
lxml.etree catalog
[('b1', 'Dune'), ('b2', 'Emma')]
b"<?xml version='1.0' encoding='UTF-8'?>"
[xml] schema discovery is not supported: the format has no schema inspector
```

To turn elements into a table, build records from them in your own code and pass the records to `pyarrow.Table.from_pylist`.

<!-- concept:73 -->

### XPath selection

`xpath` is passed to the root element's `findall`, so it accepts the ElementPath subset of XPath that both lxml and the standard library support: relative paths such as `./book` or `.//book`, `*`, and predicates such as `.//book[@id='b2']`. The result is always a list, empty when nothing matches. Expressions outside that subset are not wrapped in `ParseError`: an absolute path such as `//book` raises `SyntaxError`, and a function such as `text()` raises `KeyError`. For full XPath, parse without `xpath` and call lxml's `root.xpath(...)` on the returned element.

<!-- concept:74 -->

### lxml and the ElementTree fallback

With the `[xml]` extra installed, parsing and serialising use lxml (version 6.1.0 or later), and results are `lxml.etree` elements. lxml 6.1.0 expands only entities declared inside the document, so a reference to an external entity is a parse error rather than a way for an untrusted document to read local files. Without the extra, the standard library's `xml.etree.ElementTree` is used and results are its elements. The fallback ignores `XmlSpec.encoding`, and its serialiser writes a lowercase `encoding='utf-8'` declaration. Code that handles the parsed elements should use the API the two libraries share, or require the `[xml]` extra.

## What each format supports

<!-- concept:75 -->

A format's capabilities come from two places: the flags on its spec class ([Capability flags](#capability-flags)) and the functions registered for it. A parser is always registered. A serialiser and a schema inspector are optional, and an access mode tells the read pipeline how to fetch input for the parser and for schema discovery. The table below is built from the registrations in `src/mountainash_files/formats/` and checked against the installed package.

| Format | Parse | Write | Schema discovery | Append | Tabular | Parse access | Schema access | Extra |
|---|---|---|---|---|---|---|---|---|
| `csv` | yes | yes | yes | no | yes | bytes | bytes; sequential with a row budget | core |
| `tsv` | yes | yes | yes | no | yes | bytes | bytes; sequential with a row budget | core |
| `json` | yes | yes | yes | no | yes | bytes | bytes; sequential for NDJSON with a row budget | core |
| `parquet` | yes | yes | yes (footer) | yes | yes | random with `columns`, else bytes | random | core |
| `xlsx` | yes | no | yes | no | yes | bytes | bytes | `[xlsx]` |
| `xml` | yes | yes | no | no | no | bytes | none | core; `[xml]` for lxml |

The access modes mean:

- `bytes`: the parser receives the whole object, after any decompression or decryption transforms.
- `random`: the parser receives a seekable handle that fetches byte ranges, when no transforms apply and the storage supports ranges; otherwise it receives bytes.
- `sequential`: the reader reads forward and stops once it has the rows it needs.

The read pipeline chooses between these routes ([The read pipeline](../architecture/index.md#the-read-pipeline)), and plugins declare them at registration ([Registering a format](../custom-formats/index.md#registering-a-format)). "Core" means the base install: pyarrow, polars and mountainash-transport.

The engines and the detection rules for each format:

| Format | Read engine | Write engine | Suffixes | Media types |
|---|---|---|---|---|
| `csv` | pyarrow CSV, with a Python tokeniser for complex dialects | package CSV encoder | `.csv` | `text/csv` |
| `tsv` | as `csv` | as `csv` | `.tsv`, `.tab` | `text/tab-separated-values` |
| `json` | polars, with the standard library `json` decoder for property paths and array rows | standard library `json` | `.json`, `.geojson`, `.ndjson` and `.jsonl` (both set `ndjson=True`) | `application/json`, `application/x-ndjson` |
| `parquet` | pyarrow `ParquetFile` | `pyarrow.parquet.write_table` with defaults | `.parquet`, `.pq` | `application/vnd.apache.parquet`, `application/x-parquet` |
| `xlsx` | fastexcel (calamine), openpyxl for header labels | none | `.xlsx`, `.xlsm`, `.xlsb`, `.ods` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `xml` | lxml, or `xml.etree.ElementTree` | lxml, or `xml.etree.ElementTree` | `.xml` | `application/xml`, `text/xml` |

Media types are used only where a media type is passed to format resolution ([How a format is chosen](../files-specs-and-formats/index.md#how-a-format-is-chosen)). Even then, `application/x-ndjson` resolves to `json` with `ndjson=False`, because suffix overrides apply only to suffix resolution, so NDJSON identified that way needs an explicit `JsonSpec(ndjson=True)`. Suffixes are matched case-insensitively, after compression and encryption suffixes such as `.gz` are skipped.

Tabular parse results go through the same output seam, so `output="pydata"` works for every tabular format. Writing needs an Arrow table for CSV, TSV and Parquet, while JSON also accepts lists and dictionaries and XML takes an element. Formats added with `register_format` or an entry-point plugin carry their own capabilities, described in [Custom formats and plugins](../custom-formats/index.md#registering-a-format).
