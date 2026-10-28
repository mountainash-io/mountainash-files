from __future__ import annotations

import dataclasses
from typing import BinaryIO, ClassVar, Literal

import pyarrow as pa

from mountainash_files._archives import ArchiveExtractionError, ArchiveLimitError, check_zip_container
from mountainash_files._exceptions import MissingDependencyError
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec


# Measured with xlsxwriter: 1M rows x 3 cols is 144 MiB uncompressed (7.7x), 100k x 23 is
# 97 MiB (12x); real workbooks hold about a dozen members. A zip bomb runs near 1000x.
DEFAULT_XLSX_MAX_DECOMPRESSED_BYTES = 512 * 1024**2  # 512 MiB
DEFAULT_XLSX_MAX_MEMBERS = 1_000


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
    temporal: Literal["infer", "text"] = "infer"
    infer_sample_rows: int | None = None
    max_decompressed_bytes: int = DEFAULT_XLSX_MAX_DECOMPRESSED_BYTES
    max_members: int = DEFAULT_XLSX_MAX_MEMBERS

    def __post_init__(self) -> None:
        if self.temporal not in ("infer", "text"):
            raise ValueError("temporal must be 'infer' or 'text'")
        n = self.infer_sample_rows
        if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 1):
            raise ValueError("infer_sample_rows must be a positive int or None")
        for name in ("max_decompressed_bytes", "max_members"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive int")


def _check_container(raw: bytes, spec: XlsxSpec) -> None:
    """Bound the zip container's actual inflated size and member count before any engine runs.

    Input that is not a zip container is left for the engine to reject, as before.
    """
    try:
        check_zip_container(
            raw,
            max_decompressed_bytes=spec.max_decompressed_bytes,
            max_members=spec.max_members,
            size_hint="XlsxSpec.max_decompressed_bytes",
            members_hint="XlsxSpec.max_members",
        )
    except ArchiveLimitError:
        raise
    except ArchiveExtractionError as exc:
        raise ParseError("xlsx", str(exc)) from exc


def _xlsx_table(data: bytes | BinaryIO, spec: XlsxSpec, limit: int | None = None) -> tuple[pa.Table, bool]:
    """Parse-engine table for the selected sheet (first *limit* data rows), and whether it is complete."""
    if spec.sheet_name is not None and spec.sheet_number is not None:
        raise ParseError("xlsx", "sheet_name and sheet_number are mutually exclusive")
    raw = data.read() if hasattr(data, "read") else data
    if not raw:
        raise ParseError("xlsx", "Empty input")
    _check_container(raw, spec)
    try:
        import fastexcel  # noqa: F401
        import openpyxl  # noqa: F401
    except ImportError as exc:
        raise MissingDependencyError("XLSX parsing", "xlsx") from exc
    from mountainash_files.formats._engines import infer_temporal, normalise_types
    from mountainash_files.formats._xlsx_calamine import read_calamine

    try:
        table, complete = read_calamine(raw, spec, limit)
        table = normalise_types(table)
    except ParseError:
        raise
    except Exception as exc:  # CalamineError, SheetNotFoundError, conversion errors
        raise ParseError("xlsx", str(exc)) from exc
    return (infer_temporal(table) if spec.temporal == "infer" else table), complete


def xlsx_parse(data: bytes | BinaryIO, spec: XlsxSpec) -> pa.Table:
    return _xlsx_table(data, spec)[0]


def xlsx_inspect_schema(data: bytes | BinaryIO, spec: XlsxSpec, *, infer_schema_rows: int | None = None):
    """Schema from the XLSX parse engine over every data row, or the first N.

    The workbook is read whole and the sheet is decoded whole either way; a budget limits
    only the rows used for inference.
    """
    table, complete = _xlsx_table(data, spec, infer_schema_rows)
    return table.schema, "full" if complete and spec.infer_sample_rows is None else "bounded"


register_format(XlsxSpec, xlsx_parse, schema_inspector=xlsx_inspect_schema)
