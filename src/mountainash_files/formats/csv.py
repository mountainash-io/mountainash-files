from __future__ import annotations

import dataclasses
import io
from typing import BinaryIO, ClassVar

import pyarrow as pa
import pyarrow.csv as pcsv

from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec


@dataclasses.dataclass(frozen=True)
class CsvSpec(FormatSpec):
    FORMAT: ClassVar[str] = "csv"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".csv",)
    MEDIATYPES: ClassVar[tuple[str, ...]] = ("text/csv",)

    delimiter: str = ","
    encoding: str = "utf-8"
    skip_rows: int = 0
    header_row: int | None = 0
    columns: tuple[str, ...] | None = None
    dtypes: tuple[tuple[str, str], ...] | None = None
    quote_char: str | None = None
    escape_char: str | None = None
    null_values: tuple[str, ...] | None = None


def csv_parse(data: bytes | BinaryIO, spec: CsvSpec) -> pa.Table:
    if isinstance(data, bytes):
        if len(data) == 0:
            raise ParseError("csv", "Empty input")
        stream: BinaryIO = io.BytesIO(data)
    else:
        stream = data

    total_skip = spec.skip_rows
    if spec.header_row is not None and spec.header_row > 0:
        total_skip += spec.header_row

    read_options = pcsv.ReadOptions(
        skip_rows=total_skip,
        autogenerate_column_names=(spec.header_row is None),
        encoding=spec.encoding,
    )
    # Read dialect options defensively: csv_parse is shared by CsvSpec and
    # TsvSpec (and any future delimited-text spec), which need not all declare
    # every field.
    quote_char = getattr(spec, "quote_char", None)
    escape_char = getattr(spec, "escape_char", None)
    null_values = getattr(spec, "null_values", None)

    parse_kwargs: dict = {"delimiter": spec.delimiter}
    if quote_char is not None:
        parse_kwargs["quote_char"] = quote_char
    if escape_char is not None:
        parse_kwargs["escape_char"] = escape_char
    parse_options = pcsv.ParseOptions(**parse_kwargs)

    convert_kwargs: dict = {}
    if spec.dtypes is not None:
        convert_kwargs["column_types"] = {
            name: pa.field(name, _resolve_type(dtype)) for name, dtype in spec.dtypes
        }
    if null_values is not None:
        # Custom null tokens replace pyarrow's defaults; strings_can_be_null lets
        # them nullify string columns too (matches Frictionless nullSequence).
        convert_kwargs["null_values"] = list(null_values)
        convert_kwargs["strings_can_be_null"] = True
    convert_options = pcsv.ConvertOptions(**convert_kwargs) if convert_kwargs else None

    try:
        table = pcsv.read_csv(
            stream,
            read_options=read_options,
            parse_options=parse_options,
            convert_options=convert_options,
        )
    except Exception as exc:
        raise ParseError("csv", str(exc)) from exc

    if spec.columns is not None:
        table = table.select(list(spec.columns))

    return table


def _resolve_type(dtype_str: str) -> pa.DataType:
    _TYPE_MAP = {
        "string": pa.string(),
        "int64": pa.int64(),
        "int32": pa.int32(),
        "float64": pa.float64(),
        "float32": pa.float32(),
        "bool": pa.bool_(),
    }
    return _TYPE_MAP.get(dtype_str, pa.string())


def csv_serialise(data: pa.Table, spec: CsvSpec) -> bytes:
    buf = io.BytesIO()
    write_options = pcsv.WriteOptions(delimiter=spec.delimiter)
    pcsv.write_csv(data, buf, write_options=write_options)
    return buf.getvalue()


register_format(CsvSpec, csv_parse, serialiser=csv_serialise)
