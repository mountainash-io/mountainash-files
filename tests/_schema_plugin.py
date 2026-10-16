"""A real tiny plugin format for schema-discovery tests.

Payload ``b"int64:7"``: an Arrow type alias, a colon, then one value. The inspector reads only the
declared type; the parser builds the one-row table.
"""
from __future__ import annotations

import dataclasses
from typing import ClassVar

import pyarrow as pa

from mountainash_files.formats._types import FormatSpec

@dataclasses.dataclass(frozen=True)
class TypedSpec(FormatSpec):
    FORMAT: ClassVar[str] = "typed"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".typed",)
    MEDIATYPES: ClassVar[tuple[str, ...]] = ()


def _raw(data) -> bytes:
    return data if isinstance(data, bytes) else data.read()


def typed_parse(data, spec):
    alias, value = _raw(data).decode().split(":")
    return pa.table({"v": pa.array([int(value)], type=pa.type_for_alias(alias))})


def typed_inspect(data, spec, *, infer_schema_rows=None):
    alias = _raw(data).decode().split(":")[0]
    return pa.schema([("v", pa.type_for_alias(alias))]), "metadata"
