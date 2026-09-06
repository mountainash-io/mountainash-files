from __future__ import annotations

import dataclasses
import io
import re
from typing import BinaryIO, ClassVar

import pyarrow as pa

from mountainash_files.formats._delimited import (
    remove_comment_records,
    scan_logical_records,
    tokenize_record,
)
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


def csv_parse(data: bytes | BinaryIO, spec: CsvSpec) -> pa.Table:
    if isinstance(data, bytes):
        raw = data
    else:
        raw = data.read()
    if not raw:
        raise ParseError("csv", "Empty input")
    try:
        text = raw.decode(spec.encoding)
    except UnicodeDecodeError as exc:
        raise ParseError("csv", str(exc)) from exc
    records = remove_comment_records(scan_logical_records(text, spec), spec)
    rows = tuple(tokenize_record(record, spec) for record in records if record != "")
    labels, values = apply_header_plan(rows, spec.header, spec.header_rows, spec.header_join)
    arrays = {
        label: _infer_values([row[index] for row in values])
        for index, label in enumerate(labels)
    }
    try:
        table = pa.table(arrays)
    except Exception as exc:
        raise ParseError("csv", str(exc)) from exc
    if spec.dtypes is not None:
        table = table.cast(
            pa.schema([pa.field(name, _resolve_type(dtype)) for name, dtype in spec.dtypes])
        )
    if spec.columns is not None:
        table = table.select(list(spec.columns))
    return table


_INTEGER = re.compile(r"[+-]?\d+\Z")
_FLOAT = re.compile(r"[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?\Z")


def _infer_values(values: list[str | None]) -> list[str | int | float | None]:
    non_null = [value for value in values if value is not None]
    if non_null and all(_INTEGER.fullmatch(value) for value in non_null):
        return [None if value is None else int(value) for value in values]
    if non_null and all(_FLOAT.fullmatch(value) for value in non_null):
        return [None if value is None else float(value) for value in values]
    return values


def _resolve_type(dtype_str: str) -> pa.DataType:
    return {
        "string": pa.string(),
        "int64": pa.int64(),
        "int32": pa.int32(),
        "float64": pa.float64(),
        "float32": pa.float32(),
        "bool": pa.bool_(),
    }.get(dtype_str, pa.string())


def csv_serialise(data: pa.Table, spec: CsvSpec) -> bytes:
    output = io.StringIO()
    if spec.header:
        output.write(spec.delimiter.join(data.column_names) + spec.line_terminator)
    for row in data.to_pylist():
        output.write(
            spec.delimiter.join("" if row[name] is None else str(row[name]) for name in data.column_names)
            + spec.line_terminator
        )
    return output.getvalue().encode(spec.encoding)


register_format(CsvSpec, csv_parse, serialiser=csv_serialise)