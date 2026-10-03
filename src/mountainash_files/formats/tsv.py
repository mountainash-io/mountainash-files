from __future__ import annotations

import dataclasses
from typing import ClassVar

from mountainash_files.formats._registry import register_format
from mountainash_files.formats.csv import CsvSpec, csv_parse, csv_serialise


@dataclasses.dataclass(frozen=True)
class TsvSpec(CsvSpec):
    FORMAT: ClassVar[str] = "tsv"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".tsv", ".tab")
    MEDIATYPES: ClassVar[tuple[str, ...]] = ("text/tab-separated-values",)

    delimiter: str = "\t"


register_format(TsvSpec, csv_parse, serialiser=csv_serialise)
