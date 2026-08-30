from __future__ import annotations

import dataclasses
import io
from typing import BinaryIO, ClassVar

import pyarrow as pa
import pyarrow.parquet as pq

from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec
from mountainash_resource_provider import ProviderFormatDescriptor


@dataclasses.dataclass(frozen=True)
class ParquetSpec(FormatSpec):
    FORMAT: ClassVar[str] = "parquet"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".parquet", ".pq")
    MEDIATYPES: ClassVar[tuple[str, ...]] = (
        "application/vnd.apache.parquet",
        "application/x-parquet",
    )
    APPENDABLE: ClassVar[bool] = True
    PROVIDER_FORMATS: ClassVar[tuple[ProviderFormatDescriptor, ...]] = (
        ProviderFormatDescriptor(
            canonical_format="parquet",
            aliases=frozenset(),
            suffixes=frozenset({".parquet"}),
            mediatypes=frozenset({"application/vnd.apache.parquet", "application/x-parquet"}),
            locator_prefixes=frozenset(),
            dialect_family=None,
            provider_format_key="parquet",
        ),
    )

    columns: tuple[str, ...] | None = None


def parquet_parse(data: bytes | BinaryIO, spec: ParquetSpec) -> pa.Table:
    if isinstance(data, bytes):
        if len(data) == 0:
            raise ParseError("parquet", "Empty input")
        source: BinaryIO = io.BytesIO(data)
    else:
        source = data

    try:
        return pq.read_table(
            source,
            columns=list(spec.columns) if spec.columns else None,
        )
    except Exception as exc:
        raise ParseError("parquet", str(exc)) from exc


def parquet_serialise(data: pa.Table, spec: ParquetSpec) -> bytes:
    buf = io.BytesIO()
    pq.write_table(data, buf)
    return buf.getvalue()


register_format(ParquetSpec, parquet_parse, serialiser=parquet_serialise)
