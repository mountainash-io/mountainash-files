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

    delimiter: str = ","
    encoding: str = "utf-8"
    skip_rows: int = 0
    header_row: int | None = 0
    columns: tuple[str, ...] | None = None
    dtypes: tuple[tuple[str, str], ...] | None = None


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
    parse_options = pcsv.ParseOptions(delimiter=spec.delimiter)

    convert_options = None
    if spec.dtypes is not None:
        column_types = {name: pa.field(name, _resolve_type(dtype)) for name, dtype in spec.dtypes}
        convert_options = pcsv.ConvertOptions(column_types=column_types)

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


register_format(CsvSpec, csv_parse)
