from __future__ import annotations

import dataclasses
import io
from typing import BinaryIO, ClassVar

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from mountainash_transport import StorageError

from mountainash_files.formats._engines import native_buffer
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec


@dataclasses.dataclass(frozen=True)
class ParquetSpec(FormatSpec):
    FORMAT: ClassVar[str] = "parquet"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".parquet", ".pq")
    MEDIATYPES: ClassVar[tuple[str, ...]] = (
        "application/vnd.apache.parquet",
        "application/x-parquet",
    )
    APPENDABLE: ClassVar[bool] = True

    columns: tuple[str, ...] | None = None


def parquet_access(spec: ParquetSpec) -> str:
    """Ranged reads help only when a projection selects part of the file."""
    return "random" if spec.columns else "bytes"


def _leaf_field(schema: pa.Schema, path: list[str]) -> pa.Field:
    field = schema.field(path[0])
    for part in path[1:]:
        field = field.type.field(part)
    return field


def _project(table: pa.Table, columns: list[str], schema: pa.Schema) -> pa.Table:
    """read_table output: request order, duplicates kept, exact names first, nested -> leaf name, metadata kept."""
    arrays, fields = [], []
    for name in columns:
        if name in schema.names:
            arrays.append(table[name])
            fields.append(schema.field(name))
            continue
        parts = name.split(".")
        array = table[parts[0]]
        for part in parts[1:]:
            array = pc.struct_field(array, part)
        arrays.append(array)
        fields.append(_leaf_field(schema, parts))
    return pa.Table.from_arrays(arrays, schema=pa.schema(fields).with_metadata(schema.metadata or {}))


def parquet_parse(data: bytes | BinaryIO, spec: ParquetSpec) -> pa.Table:
    if isinstance(data, bytes) and not data:
        raise ParseError("parquet", "Empty input")
    columns = list(spec.columns) if spec.columns else None
    try:
        if isinstance(data, bytes):
            reader, threaded = pq.ParquetFile(pa.BufferReader(native_buffer(data))), True
        else:  # transport random handle (parse() only passes handles on the random route)
            reader, threaded = pq.ParquetFile(data, pre_buffer=False), False
        if columns is None:
            return reader.read(use_threads=threaded)
        schema = reader.schema_arrow
        top = list(dict.fromkeys(c if c in schema.names else c.split(".")[0] for c in columns))
        return _project(reader.read(columns=top, use_threads=threaded), columns, schema)
    except StorageError:
        raise
    except Exception as exc:
        raise ParseError("parquet", str(exc)) from exc


def parquet_serialise(data: pa.Table, spec: ParquetSpec) -> bytes:
    buf = io.BytesIO()
    pq.write_table(data, buf)
    return buf.getvalue()


register_format(ParquetSpec, parquet_parse, serialiser=parquet_serialise, access=parquet_access)
