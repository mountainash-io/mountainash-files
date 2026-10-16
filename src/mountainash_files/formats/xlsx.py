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


@dataclasses.dataclass(frozen=True)
class XlsxSpec(FormatSpec):
    FORMAT: ClassVar[str] = "xlsx"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".xlsx", ".xlsm", ".xlsb", ".ods")
    MEDIATYPES: ClassVar[tuple[str, ...]] = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    sheet_name: str | None = None
    sheet_number: int | None = None
    header: bool = True
    header_rows: tuple[int, ...] = (1,)
    header_join: str = " "
    comment_rows: tuple[int, ...] = ()
    comment_char: str | None = None
    engine: Literal["auto", "fastexcel", "openpyxl"] = "auto"
    temporal: Literal["infer", "text"] = "infer"
    infer_sample_rows: int | None = None

    def __post_init__(self) -> None:
        if self.temporal not in ("infer", "text"):
            raise ValueError("temporal must be 'infer' or 'text'")
        n = self.infer_sample_rows
        if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 1):
            raise ValueError("infer_sample_rows must be a positive int or None")


def xlsx_parse(data: bytes | BinaryIO, spec: XlsxSpec) -> pa.Table:
    if spec.sheet_name is not None and spec.sheet_number is not None:
        raise ParseError("xlsx", "sheet_name and sheet_number are mutually exclusive")
    raw = data.read() if hasattr(data, "read") else data
    if not raw:
        raise ParseError("xlsx", "Empty input")
    if spec.engine != "openpyxl":
        try:
            import fastexcel  # noqa: F401
            import openpyxl  # noqa: F401
        except ImportError as exc:
            raise MissingDependencyError("XLSX parsing", "xlsx") from exc
        from mountainash_files.formats._engines import infer_temporal, normalise_types
        from mountainash_files.formats._xlsx_calamine import read_calamine

        try:
            table = normalise_types(read_calamine(raw, spec))
        except ParseError:
            raise
        except Exception as exc:  # CalamineError, SheetNotFoundError, conversion errors
            raise ParseError("xlsx", str(exc)) from exc
        return infer_temporal(table) if spec.temporal == "infer" else table
    try:
        import openpyxl
        from openpyxl.worksheet._read_only import ReadOnlyWorksheet
        from openpyxl.worksheet.worksheet import Worksheet
    except ImportError as exc:
        raise MissingDependencyError("XLSX parsing", "xlsx") from exc
    try:
        workbook = openpyxl.load_workbook(
            io.BytesIO(raw), read_only=True, data_only=True
        )
        worksheet: object
        if spec.sheet_name is not None:
            worksheet = workbook[spec.sheet_name]
        else:
            number = 1 if spec.sheet_number is None else spec.sheet_number
            if number < 1:
                raise ParseError("xlsx", "sheet_number is one-based")
            worksheet = workbook.worksheets[number - 1]
        if not isinstance(worksheet, (Worksheet, ReadOnlyWorksheet)):
            workbook.close()
            raise ParseError("xlsx", "Selected sheet is not a worksheet")
        rows = tuple(
            tuple(cell for cell in row) for row in worksheet.iter_rows(values_only=True)
        )
        workbook.close()
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError("xlsx", str(exc)) from exc
    rows = tuple(
        row
        for index, row in enumerate(rows, 1)
        if index not in set(spec.comment_rows)
        and not (spec.comment_char and str(row[0] or "").startswith(spec.comment_char))
    )
    labels, values = apply_header_plan(
        rows, spec.header, spec.header_rows, spec.header_join
    )
    return pa.table(
        {name: [row[index] for row in values] for index, name in enumerate(labels)}
    )


register_format(XlsxSpec, xlsx_parse)
