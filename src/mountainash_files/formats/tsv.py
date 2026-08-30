from __future__ import annotations

import dataclasses
from typing import ClassVar

from mountainash_files.formats._registry import register_format
from mountainash_files.formats.csv import CsvSpec, csv_parse
from mountainash_resource_provider import ProviderFormatDescriptor


@dataclasses.dataclass(frozen=True)
class TsvSpec(CsvSpec):
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

    delimiter: str = "\t"


register_format(TsvSpec, csv_parse)