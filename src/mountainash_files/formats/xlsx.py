from __future__ import annotations

import dataclasses
import io
from typing import BinaryIO, ClassVar, Literal

import pyarrow as pa

from mountainash_files._exceptions import MissingDependencyError
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._rows import apply_header_plan
from mountainash_files.formats._types import FormatSpec
from mountainash_resource_provider import ProviderFormatDescriptor


@dataclasses.dataclass(frozen=True)
class XlsxSpec(FormatSpec):
    FORMAT: ClassVar[str] = "xlsx"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".xlsx", ".xlsm", ".xlsb", ".ods")
    MEDIATYPES: ClassVar[tuple[str, ...]] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    PROVIDER_FORMATS: ClassVar[tuple[ProviderFormatDescriptor, ...]] = (
        ProviderFormatDescriptor(
            "xlsx", frozenset(), frozenset({".xlsx"}),
            frozenset({"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}),
            frozenset(), "spreadsheet", "xlsx",
        ),
        ProviderFormatDescriptor(
            "xlsm", frozenset(), frozenset({".xlsm"}),
            frozenset({"application/vnd.ms-excel.sheet.macroenabled.12"}),
            frozenset(), "spreadsheet", "xlsx",
        ),
        ProviderFormatDescriptor(
            "xlsb", frozenset(), frozenset({".xlsb"}),
            frozenset({"application/vnd.ms-excel.sheet.binary.macroenabled.12"}),
            frozenset(), "spreadsheet", "xlsx",
        ),
        ProviderFormatDescriptor(
            "ods", frozenset(), frozenset({".ods"}),
            frozenset({"application/vnd.oasis.opendocument.spreadsheet"}),
            frozenset(), "spreadsheet", "xlsx",
        ),
    )
    sheet_name: str | None = None
    sheet_number: int | None = None
    header: bool = True
    header_rows: tuple[int, ...] = (1,)
    header_join: str = " "
    comment_rows: tuple[int, ...] = ()
    comment_char: str | None = None
    engine: Literal["auto", "fastexcel", "openpyxl"] = "auto"


def xlsx_parse(data: bytes | BinaryIO, spec: XlsxSpec) -> pa.Table:
    if spec.sheet_name is not None and spec.sheet_number is not None:
        raise ParseError("xlsx", "sheet_name and sheet_number are mutually exclusive")
    raw = data.read() if hasattr(data, "read") else data
    if not raw:
        raise ParseError("xlsx", "Empty input")
    if spec.engine == "fastexcel":
        raise MissingDependencyError("fastexcel raw-row spreadsheet parsing", "xlsx")
    try:
        import openpyxl
    except ImportError as exc:
        raise MissingDependencyError("XLSX parsing", "xlsx") from exc
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        if spec.sheet_name is not None:
            worksheet = workbook[spec.sheet_name]
        else:
            number = 1 if spec.sheet_number is None else spec.sheet_number
            if number < 1:
                raise ParseError("xlsx", "sheet_number is one-based")
            worksheet = workbook.worksheets[number - 1]
        rows = tuple(tuple(cell for cell in row) for row in worksheet.iter_rows(values_only=True))
        workbook.close()
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError("xlsx", str(exc)) from exc
    rows = tuple(
        row for index, row in enumerate(rows, 1)
        if index not in set(spec.comment_rows) and not (spec.comment_char and str(row[0] or "").startswith(spec.comment_char))
    )
    labels, values = apply_header_plan(rows, spec.header, spec.header_rows, spec.header_join)
    return pa.table({name: [row[index] for row in values] for index, name in enumerate(labels)})


register_format(XlsxSpec, xlsx_parse)