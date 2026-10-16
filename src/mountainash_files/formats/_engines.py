"""Shared native-memory, type-normalisation and temporal helpers for engine-based readers."""
from __future__ import annotations

import re
from typing import Literal

import pyarrow as pa
import pyarrow.compute as pc

_OFFSET_LIMIT = 2**31 - 1

_LIST_TYPES = (pa.ListType, pa.LargeListType, pa.ListViewType, pa.LargeListViewType)
# MapArray subclasses ListArray, so maps are covered here.
_LIST_ARRAYS = (pa.ListArray, pa.LargeListArray, pa.ListViewArray, pa.LargeListViewArray, pa.FixedSizeListArray)
_BYTE_ARRAYS = (pa.LargeStringArray, pa.LargeBinaryArray, pa.StringViewArray, pa.BinaryViewArray)


def native_buffer(data: bytes) -> pa.Buffer:
    """Copy *data* into Arrow-owned memory, so no Python object backs the buffer."""
    buf = pa.allocate_buffer(len(data))
    memoryview(buf).cast("B")[:] = data
    return buf


def _standard(t: pa.DataType) -> pa.DataType:
    if pa.types.is_large_string(t) or pa.types.is_string_view(t):
        return pa.string()
    if pa.types.is_large_binary(t) or pa.types.is_binary_view(t):
        return pa.binary()
    if isinstance(t, _LIST_TYPES):
        f = t.value_field
        return pa.list_(pa.field(f.name, _standard(f.type), f.nullable))
    if isinstance(t, pa.FixedSizeListType):
        f = t.value_field
        return pa.list_(pa.field(f.name, _standard(f.type), f.nullable), t.list_size)
    if isinstance(t, pa.StructType):
        return pa.struct([pa.field(f.name, _standard(f.type), f.nullable, f.metadata) for f in t])
    if isinstance(t, pa.MapType):
        return pa.map_(_standard(t.key_type), _standard(t.item_type))
    return t


def _offsets_fit(array: pa.Array) -> bool:
    """Whether every offset-bearing array narrowed by _standard fits signed 32-bit offsets."""
    if isinstance(array, _BYTE_ARRAYS):
        lengths = pc.binary_length(array)  # type: ignore[arg-type]  # stubs lack view-array overloads
        return (pc.sum(lengths).as_py() or 0) <= _OFFSET_LIMIT
    if isinstance(array, _LIST_ARRAYS):
        values = array.flatten()
        return len(values) <= _OFFSET_LIMIT and _offsets_fit(values)
    if isinstance(array, pa.StructArray):
        return all(_offsets_fit(array.field(i)) for i in range(array.type.num_fields))
    return True


def normalise_types(table: pa.Table) -> pa.Table:
    """large_*/view → standard types, decided per column; a column whose offsets overflow keeps its type."""
    fields = []
    for f, column in zip(table.schema, table.columns):
        target = _standard(f.type)
        keep = target != f.type and not all(_offsets_fit(chunk) for chunk in column.chunks)
        fields.append(pa.field(f.name, f.type if keep else target, f.nullable, f.metadata))
    schema = pa.schema(fields).with_metadata(table.schema.metadata or {})
    return table if schema.equals(table.schema) else table.cast(schema)


_ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"
_ISO_DATETIME = r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d{1,9})?$"
_ISO_PREFIX = re.compile(r"\d{4}-\d{2}-\d{2}")


def _first_non_null(column: pa.ChunkedArray):
    for chunk in column.chunks:
        valid = chunk.drop_null()
        if len(valid):
            return valid[0].as_py()
    return None


def _all_match(valid: pa.ChunkedArray, pattern: str) -> bool:
    return pc.all(pc.match_substring_regex(valid, pattern)).as_py()


def infer_temporal(table: pa.Table) -> pa.Table:
    """Cast string columns whose every non-null value is a valid ISO date or datetime.

    pyarrow CSV parity: date32; timestamp[s] without fractions; timestamp[ns] if any value has
    fractional seconds. Invalid calendar values keep the column as text.
    """
    for i, f in enumerate(table.schema):
        if not pa.types.is_string(f.type):
            continue
        column = table.column(i)
        first = _first_non_null(column)
        if not isinstance(first, str) or not _ISO_PREFIX.match(first):
            continue
        valid = column.drop_null()
        new: pa.ChunkedArray
        try:
            if _all_match(valid, _ISO_DATE):
                new = pc.cast(column, pa.date32())
            elif _all_match(valid, _ISO_DATETIME):
                unit: Literal["s", "ns"] = "ns" if pc.any(pc.match_substring(valid, ".")).as_py() else "s"
                new = pc.cast(pc.replace_substring(column, " ", "T"), pa.timestamp(unit))
            else:
                continue
        except pa.ArrowInvalid:
            continue
        table = table.set_column(i, pa.field(f.name, new.type, f.nullable, f.metadata), new)
    return table
