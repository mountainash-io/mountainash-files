from __future__ import annotations

import dataclasses
from typing import ClassVar

from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec
from mountainash_files.formats.csv import csv_parse


@dataclasses.dataclass(frozen=True)
class TsvSpec(FormatSpec):
    FORMAT: ClassVar[str] = "tsv"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".tsv", ".tab")
    delimiter: ClassVar[str] = "\t"

    encoding: str = "utf-8"
    skip_rows: int = 0
    header_row: int | None = 0
    columns: tuple[str, ...] | None = None
    dtypes: tuple[tuple[str, str], ...] | None = None


register_format(TsvSpec, csv_parse)
