from __future__ import annotations

import dataclasses
from typing import ClassVar

from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec
from mountainash_files.formats.csv import csv_parse
from mountainash_resource_provider import ProviderFormatDescriptor


@dataclasses.dataclass(frozen=True)
class TsvSpec(FormatSpec):
    FORMAT: ClassVar[str] = "tsv"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".tsv", ".tab")
    MEDIATYPES: ClassVar[tuple[str, ...]] = ("text/tab-separated-values",)
    PROVIDER_FORMATS: ClassVar[tuple[ProviderFormatDescriptor, ...]] = (
        ProviderFormatDescriptor(
            canonical_format="tsv",
            aliases=frozenset({"tab"}),
            suffixes=frozenset({".tsv", ".tab"}),
            mediatypes=frozenset({"text/tab-separated-values"}),
            locator_prefixes=frozenset(),
            dialect_family="delimited",
            provider_format_key="tsv",
        ),
    )
    delimiter: ClassVar[str] = "\t"

    encoding: str = "utf-8"
    skip_rows: int = 0
    header_row: int | None = 0
    columns: tuple[str, ...] | None = None
    dtypes: tuple[tuple[str, str], ...] | None = None
    quote_char: str | None = None
    escape_char: str | None = None
    null_values: tuple[str, ...] | None = None


register_format(TsvSpec, csv_parse)
