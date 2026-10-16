from __future__ import annotations

import dataclasses
import json as _json
from typing import Any, BinaryIO, ClassVar, Literal, cast

import pyarrow as pa

from mountainash_files.formats._engines import infer_temporal, normalise_types
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec


@dataclasses.dataclass(frozen=True)
class JsonSpec(FormatSpec):
    FORMAT: ClassVar[str] = "json"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".json", ".ndjson", ".jsonl", ".geojson")
    MEDIATYPES: ClassVar[tuple[str, ...]] = ("application/json", "application/x-ndjson")
    property: str | None = None
    item_type: Literal["object", "array"] | None = None
    item_keys: tuple[str, ...] | None = None
    header: bool = True
    ndjson: bool = False
    temporal: Literal["infer", "text"] = "infer"
    infer_sample_rows: int | None = None

    def __post_init__(self) -> None:
        if self.temporal not in ("infer", "text"):
            raise ValueError("temporal must be 'infer' or 'text'")
        n = self.infer_sample_rows
        if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 1):
            raise ValueError("infer_sample_rows must be a positive int or None")


def _finish(table: pa.Table, spec: JsonSpec) -> pa.Table:
    if table.num_columns == 0:
        return pa.table({})   # rows without keys carry no data
    table = normalise_types(table)
    return infer_temporal(table) if spec.temporal == "infer" else table


def _with_keys(table: pa.Table, keys: tuple[str, ...]) -> pa.Table:
    columns = [table.column(k) if k in table.column_names else pa.chunked_array([pa.nulls(table.num_rows)]) for k in keys]
    return pa.Table.from_arrays(columns, names=list(keys))


def json_parse(data: bytes | BinaryIO, spec: JsonSpec) -> pa.Table | list[object]:
    import polars as pl

    raw = data.read() if hasattr(data, "read") else data
    if not raw:
        raise ParseError("json", "Empty input")
    n = spec.infer_sample_rows
    plain = not spec.property and spec.item_type in (None, "object")
    try:
        encoding = _json.detect_encoding(raw)
        if encoding != "utf-8":
            raw = raw.decode(encoding).encode("utf-8")
        if not raw.strip():
            raise ParseError("json", "Empty input")
        head = raw.lstrip()[:1]
        if spec.ndjson and plain and head == b"{":
            table = pl.read_ndjson(raw, infer_schema_length=n).to_arrow()
            return _finish(_with_keys(table, spec.item_keys) if spec.item_keys else table, spec)
        if (not spec.ndjson and plain and not spec.item_keys and head == b"["
                and raw.lstrip()[1:].lstrip()[:1] == b"{"):
            return _finish(pl.read_json(raw, infer_schema_length=n).to_arrow(), spec)
        source = (
            [_json.loads(line) for line in raw.splitlines() if line.strip()]
            if spec.ndjson
            else _json.loads(raw)
        )
    except ParseError:
        raise
    except Exception as exc:  # UnicodeDecodeError, JSONDecodeError, polars errors
        raise ParseError("json", str(exc)) from exc
    if spec.property:
        for key in spec.property.split("."):
            if not isinstance(source, dict) or key not in source:
                raise ParseError("json", f"property {spec.property!r} was not found")
            source = source[key]
    records = source if isinstance(source, list) else [source]
    out = _resolve_rows(records, spec)
    return _finish(out, spec) if isinstance(out, pa.Table) else out


def _resolve_rows(records: list[object], spec: JsonSpec) -> pa.Table | list[object]:
    if not records:
        return pa.table({})
    shape = spec.item_type or (
        "object"
        if isinstance(records[0], dict)
        else "array"
        if isinstance(records[0], list)
        else None
    )
    if shape is None:
        return records
    if any(not isinstance(row, dict if shape == "object" else list) for row in records):
        raise ParseError("json", "mixed or unsupported structured row shapes")
    if shape == "object":
        objects = cast(list[dict[str, Any]], records)
        keys = spec.item_keys or tuple(
            dict.fromkeys(key for row in objects for key in row)
        )
        import polars as pl

        try:
            return pl.from_dicts(
                [{key: row.get(key) for key in keys} for row in objects],
                infer_schema_length=spec.infer_sample_rows,
            ).to_arrow()
        except Exception as exc:
            raise ParseError("json", str(exc)) from exc
    rows = cast(list[list[Any]], records)
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ParseError("json", "array row widths differ")
    if spec.header:
        names = [
            str(value) if value not in (None, "") else f"field{index}"
            for index, value in enumerate(rows[0], 1)
        ]
        rows = rows[1:]
    else:
        names = [f"field{index}" for index in range(1, width + 1)]
    import polars as pl

    try:
        return pl.DataFrame(
            rows, schema=names, orient="row", infer_schema_length=spec.infer_sample_rows
        ).to_arrow()
    except Exception as exc:
        raise ParseError("json", str(exc)) from exc


def json_serialise(data: dict | list | pa.Table, spec: JsonSpec) -> bytes:
    if isinstance(data, pa.Table):
        data = data.to_pylist()
    if spec.ndjson and isinstance(data, list):
        return (
            "\n".join(_json.dumps(item, default=str) for item in data) + "\n"
        ).encode()
    return _json.dumps(data, default=str).encode()


register_format(
    JsonSpec,
    json_parse,
    serialiser=json_serialise,
    suffix_overrides={".ndjson": {"ndjson": True}, ".jsonl": {"ndjson": True}},
)
