from __future__ import annotations

import codecs
import dataclasses
from typing import BinaryIO, ClassVar, Literal

import pyarrow as pa
import pyarrow.csv as pacsv

from mountainash_files._exceptions import WriteError
from mountainash_files.formats._delimited import (
    _validate_delimited_spec,
    encode_record,
    iter_logical_records,
    remove_comment_records,
    tokenize_record,
    tokenize_record_quoted,
)
from mountainash_files.formats._engines import native_buffer
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._rows import apply_header_plan
from mountainash_files.formats._types import FormatSpec


@dataclasses.dataclass(frozen=True)
class CsvSpec(FormatSpec):
    FORMAT: ClassVar[str] = "csv"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".csv",)
    MEDIATYPES: ClassVar[tuple[str, ...]] = ("text/csv",)

    delimiter: str = ","
    line_terminator: str = "\n"
    quote_char: str | None = '"'
    double_quote: bool = True
    escape_char: str | None = None
    null_sequence: str | None = None
    skip_initial_space: bool = False
    header: bool = True
    header_rows: tuple[int, ...] = (1,)
    header_join: str = " "
    comment_char: str | None = None
    comment_rows: tuple[int, ...] = ()
    encoding: str = "utf-8"
    columns: tuple[str, ...] | None = None
    dtypes: tuple[tuple[str, str], ...] | None = None
    temporal: Literal["infer", "text"] = "infer"
    # Write-only: prefix string cells (and header labels) that a spreadsheet
    # would evaluate as a formula with "'". Lossy; parsing does not reverse it.
    formula_neutralise: bool = False

    def __post_init__(self) -> None:
        if self.temporal not in ("infer", "text"):
            raise ValueError(f"temporal must be 'infer' or 'text', got {self.temporal!r}")


def _positions(spec: CsvSpec) -> tuple[int, ...]:
    return tuple(sorted(set(spec.header_rows))) or (1,)   # apply_header_plan's own default


def _ascii1(value: str | None) -> bool:
    return value is None or (len(value) == 1 and value.isascii())


def _breaks_safe(data: bytes, terminator: str) -> bool:
    if terminator == "\n":
        return b"\r" not in data
    if terminator == "\r\n":
        return data.count(b"\r") == data.count(b"\r\n") == data.count(b"\n")
    if terminator == "\r":
        return b"\n" not in data
    return False


def _quotes_balanced(data: bytes, spec: CsvSpec) -> bool:
    """Even quote count after removing escaped characters: unterminated quotes stay on the lexer path."""
    if spec.quote_char is None:
        return True
    quote = spec.quote_char.encode()
    if spec.escape_char is not None:
        escape = spec.escape_char.encode()
        data = data.replace(escape + escape, b"").replace(escape + quote, b"")
    return data.count(quote) % 2 == 0


def _native_eligible(data: bytes, spec: CsvSpec) -> bool:
    positions = _positions(spec)
    contiguous = not spec.header or positions == tuple(range(1, len(positions) + 1))
    return (
        _ascii1(spec.delimiter) and _ascii1(spec.quote_char) and _ascii1(spec.escape_char)
        and spec.comment_char is None and not spec.comment_rows and not spec.skip_initial_space
        and contiguous and _breaks_safe(data, spec.line_terminator) and _quotes_balanced(data, spec)
    )


def _dangling_escape(text: str, spec: CsvSpec) -> bool:
    """An odd run of escape characters at the very end of the input (the lexer's rule)."""
    if spec.escape_char is None or not text.endswith(spec.escape_char):
        return False
    return (len(text) - len(text.rstrip(spec.escape_char))) % 2 == 1


def _header(text: str, spec: CsvSpec) -> tuple[tuple[str, ...], int]:
    """Labels from files' header plan and the text offset where data records begin."""
    if not spec.header:
        for record, _ in iter_logical_records(text, spec):
            if record != "":
                width = len(tokenize_record(record, spec))
                return tuple(f"field{i}" for i in range(1, width + 1)), 0
        return (), 0
    needed = max(_positions(spec))
    rows, end = [], 0
    for record, offset in iter_logical_records(text, spec):
        end = offset
        if record != "":
            rows.append(tokenize_record(record, spec))
        if len(rows) == needed:
            break
    labels, _ = apply_header_plan(tuple(rows), True, spec.header_rows, spec.header_join)
    return labels, end


def _plain_csv(labels, rows) -> bytes:
    """Canonical CSV: text always quoted, nulls empty and unquoted."""
    def cell(value):
        return "" if value is None else '"' + value.replace('"', '""') + '"'
    lines = [",".join(cell(v) for v in labels)] + [",".join(cell(v) for v in row) for row in rows]
    return ("\n".join(lines) + "\n").encode()


def _empty(spec, labels, column_types=None):
    """Zero-row table for header-only input: null columns unless dtypes say otherwise."""
    types = {name: _resolve_type(dtype) for name, dtype in (spec.dtypes or ())}
    types.update(column_types or {})
    names = [name for name in labels if not spec.columns or name in spec.columns]
    return pa.table({name: pa.array([], types.get(name, pa.null())) for name in names})


def _read(buffer, spec, labels, plain, column_types=None):
    if not labels or len(buffer) == (0 if not plain else len(_plain_csv(labels, ()))):
        return _empty(spec, labels, column_types)
    parse_opts = pacsv.ParseOptions(
        delimiter="," if plain else spec.delimiter,
        quote_char='"' if plain else (spec.quote_char or False),
        double_quote=True if plain else spec.double_quote,
        escape_char=False if plain else (spec.escape_char or False),
        newlines_in_values=True,
        ignore_empty_lines=not plain,   # canonical rows are never blank; a one-column null row is an empty line
    )
    if spec.null_sequence is not None and not plain:
        null_values, quoted_null = [spec.null_sequence], True
    else:
        null_values, quoted_null = [""], False
    types = {name: _resolve_type(dtype) for name, dtype in (spec.dtypes or ())}
    types.update(column_types or {})
    convert = pacsv.ConvertOptions(
        null_values=null_values, strings_can_be_null=True, quoted_strings_can_be_null=quoted_null,
        include_columns=list(spec.columns) if spec.columns else None, column_types=types,
    )
    read = pacsv.ReadOptions(use_threads=True, encoding="utf8",
                             column_names=list(labels), skip_rows=1 if plain else 0)
    return pacsv.read_csv(pa.BufferReader(buffer), read_options=read, parse_options=parse_opts,
                          convert_options=convert)


def csv_parse(data: bytes | BinaryIO, spec: CsvSpec) -> pa.Table:
    try:
        _validate_delimited_spec(spec)
    except ValueError as exc:
        raise ParseError(spec.FORMAT, str(exc)) from exc
    raw = data if isinstance(data, bytes) else data.read()
    if not raw:
        raise ParseError(spec.FORMAT, "Empty input")
    try:
        text = raw.decode(spec.encoding)
    except UnicodeDecodeError as exc:
        raise ParseError(spec.FORMAT, str(exc)) from exc
    if _dangling_escape(text, spec):
        raise ParseError(spec.FORMAT, "dangling escape")
    selection = spec
    if spec.columns == ():
        selection = dataclasses.replace(spec, columns=None)   # validate fully, then select nothing
    try:
        if _native_eligible(raw, selection):
            labels, start = _header(text, selection)
            buffer, plain = native_buffer(text[start:].encode("utf-8")), False
        else:
            records = remove_comment_records(tuple(r for r, _ in iter_logical_records(text, selection)), selection)
            rows = tuple(
                tuple(None if ((selection.null_sequence is not None and value == selection.null_sequence)
                               or (selection.null_sequence is None and value == "" and not quoted))
                      else value for value, quoted in tokenize_record_quoted(r, selection))
                for r in records if r != ""
            )
            labels, values = apply_header_plan(rows, selection.header, selection.header_rows, selection.header_join)
            buffer, plain = native_buffer(_plain_csv(labels, values)), True
        if len(labels) != len(set(labels)):
            raise ParseError(spec.FORMAT, "duplicate final header labels")
        table = _read(buffer, selection, labels, plain)
        if selection.temporal == "text":
            temporal = {f.name: pa.string() for f in table.schema if pa.types.is_temporal(f.type)}
            if temporal:
                table = _read(buffer, selection, labels, plain, temporal)
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(spec.FORMAT, str(exc)) from exc
    return table.select([]) if spec.columns == () else table


def csv_schema_access(spec: CsvSpec, infer_schema_rows: int | None) -> str:
    """A finite budget needs only a prefix, so read forward and stop; otherwise read it all."""
    return "bytes" if infer_schema_rows is None else "sequential"


def _csv_prefix(data: bytes | BinaryIO, spec: CsvSpec, n: int) -> tuple[bytes, bool]:
    """Input through the last header row and the Nth data record, and whether the input ended there.

    Streams are read in growing chunks and lexed from the last complete record, so the work is
    linear in the prefix. Before EOF a trailing record is complete only once its terminator has
    arrived; an unterminated quote or a dangling escape at a chunk end means "read more".
    """
    try:
        _validate_delimited_spec(spec)
    except ValueError as exc:
        raise ParseError(spec.FORMAT, str(exc)) from exc
    need = max(_positions(spec)) if spec.header else 0
    comment_rows = set(spec.comment_rows)
    decoder = codecs.getincrementaldecoder(spec.encoding)()
    text, consumed, number, retained, rows = "", 0, 0, 0, 0
    size, eof = 65536, False
    while not eof:
        if isinstance(data, bytes):
            chunk, eof = data, True
        else:
            chunk = data.read(size)
            eof, size = not chunk, min(size * 2, 8 << 20)
        try:
            text += decoder.decode(chunk, final=eof)
        except UnicodeDecodeError as exc:
            raise ParseError(spec.FORMAT, str(exc)) from exc
        try:
            base = consumed
            for record, end in iter_logical_records(text[base:], spec):
                end += base
                if end == len(text) and not eof:
                    break   # the last record may still be arriving (even after an escaped terminator)
                consumed, number = end, number + 1
                if record == "" or number in comment_rows or (
                        spec.comment_char is not None and record.startswith(spec.comment_char)):
                    continue
                retained += 1
                rows += retained > need
                if rows >= n and retained >= need:
                    return text[:consumed].encode(spec.encoding), eof and consumed == len(text)
        except ParseError:
            if eof:
                raise
    return text.encode(spec.encoding), True


def csv_inspect_schema(data: bytes | BinaryIO, spec: CsvSpec, *, infer_schema_rows: int | None = None):
    """Schema from the CSV parse engine over every record, or over the budgeted prefix."""
    if infer_schema_rows is None:
        raw = data if isinstance(data, bytes) else data.read()
        return csv_parse(raw, spec).schema, "full"
    prefix, ended = _csv_prefix(data, spec, infer_schema_rows)
    return csv_parse(prefix, spec).schema, "full" if ended else "bounded"



def _resolve_type(dtype_str: str) -> pa.DataType:
    types: dict[str, pa.DataType] = {
        "string": pa.string(),
        "int64": pa.int64(),
        "int32": pa.int32(),
        "float64": pa.float64(),
        "float32": pa.float32(),
        "bool": pa.bool_(),
    }
    return types.get(dtype_str, pa.string())


_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")  # OWASP CSV-injection leading characters


def _neutralise(value: object) -> object:
    return "'" + value if isinstance(value, str) and value.startswith(_FORMULA_TRIGGERS) else value


def csv_serialise(data: pa.Table, spec: CsvSpec) -> bytes:
    try:
        _validate_delimited_spec(spec)
        columns = [column.to_pylist() for column in data.columns]
        if not columns and data.num_rows:
            raise ValueError("nonempty zero-column table is not representable")
        rows: list[tuple[object, ...]] = []
        if spec.header:
            rows.append(tuple(data.column_names))
        rows.extend(zip(*columns))
        if spec.formula_neutralise:
            rows = [tuple(_neutralise(v) for v in row) for row in rows]
        encoded_rows = [encode_record(row, spec) for row in rows]
        return "".join(encoded_rows).encode(spec.encoding)
    except (ParseError, ValueError, TypeError, LookupError) as exc:
        raise WriteError(f"Cannot serialise {spec.FORMAT}: {exc}") from exc


register_format(
    CsvSpec, csv_parse, serialiser=csv_serialise,
    schema_inspector=csv_inspect_schema, schema_access=csv_schema_access,
)
