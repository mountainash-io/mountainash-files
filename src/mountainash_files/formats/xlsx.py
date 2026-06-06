from __future__ import annotations

import dataclasses
import io
import typing as t
from typing import BinaryIO, ClassVar, Literal

import pyarrow as pa

from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec


@dataclasses.dataclass(frozen=True)
class XlsxSpec(FormatSpec):
    FORMAT: ClassVar[str] = "xlsx"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".xlsx", ".xlsb")

    sheet_name: str | int = 0
    skip_rows: int = 0
    header_row: int | None = 0
    columns: tuple[str, ...] | None = None
    engine: Literal["auto", "fastexcel", "openpyxl"] = "auto"


def xlsx_parse(data: bytes | BinaryIO, spec: XlsxSpec) -> pa.Table:
    if hasattr(data, "read"):
        raw = data.read()
    else:
        raw = data

    if len(raw) == 0:
        raise ParseError("xlsx", "Empty input")

    use_fastexcel = spec.engine in ("auto", "fastexcel")
    use_openpyxl = spec.engine in ("auto", "openpyxl")

    if use_fastexcel:
        try:
            import fastexcel

            excel = fastexcel.read_excel(raw)
            if isinstance(spec.sheet_name, int):
                sheet = excel.load_sheet(spec.sheet_name)
            else:
                sheet = excel.load_sheet_by_name(spec.sheet_name)
            result = sheet.to_arrow()
            # fastexcel may return RecordBatch; normalise to Table
            if isinstance(result, pa.RecordBatch):
                table = pa.Table.from_batches([result])
            else:
                table = result

            if spec.skip_rows > 0:
                table = table.slice(spec.skip_rows)
            if spec.columns is not None:
                table = table.select(list(spec.columns))
            return table
        except ImportError:
            if spec.engine == "fastexcel":
                raise

    if use_openpyxl:
        try:
            import openpyxl
        except ImportError:
            raise ImportError(
                "XLSX decoding requires fastexcel or openpyxl. "
                "Install with: pip install mountainash-files[xlsx]"
            )

        try:
            wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            if isinstance(spec.sheet_name, int):
                ws = wb.worksheets[spec.sheet_name]
            else:
                ws = wb[spec.sheet_name]

            rows = list(ws.iter_rows(min_row=spec.skip_rows + 1, values_only=True))
            wb.close()
        except Exception as exc:
            raise ParseError("xlsx", str(exc)) from exc

        if not rows:
            return pa.table({})

        if spec.header_row is not None:
            header_idx = max(0, spec.header_row - spec.skip_rows)
            if header_idx >= len(rows):
                return pa.table({})
            headers = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(rows[header_idx])]
            data_rows = rows[header_idx + 1:]
        else:
            headers = [f"col_{i}" for i in range(len(rows[0]))]
            data_rows = rows

        columns = {h: [row[i] if i < len(row) else None for row in data_rows] for i, h in enumerate(headers)}

        if spec.columns is not None:
            columns = {k: v for k, v in columns.items() if k in spec.columns}

        return pa.table(columns)

    raise ImportError(
        "XLSX decoding requires fastexcel or openpyxl. "
        "Install with: pip install mountainash-files[xlsx]"
    )


register_format(
    XlsxSpec,
    xlsx_parse,
    suffix_overrides={".xlsb": {"engine": "fastexcel"}},
)
