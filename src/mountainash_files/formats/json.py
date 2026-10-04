from __future__ import annotations

import dataclasses
import json as _json
from typing import Any, BinaryIO, ClassVar, Literal, cast

import pyarrow as pa

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


def json_parse(data: bytes | BinaryIO, spec: JsonSpec) -> pa.Table | list[object]:
    raw = data.read() if hasattr(data, "read") else data
    if not raw:
        raise ParseError("json", "Empty input")
    try:
        source = (
            [_json.loads(line) for line in raw.splitlines() if line.strip()]
            if spec.ndjson
            else _json.loads(raw)
        )
    except (_json.JSONDecodeError, ValueError) as exc:
        raise ParseError("json", str(exc)) from exc
    if spec.property:
        for key in spec.property.split("."):
            if not isinstance(source, dict) or key not in source:
                raise ParseError("json", f"property {spec.property!r} was not found")
            source = source[key]
    records = source if isinstance(source, list) else [source]
    return _resolve_rows(records, spec)


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
        try:
            return pa.Table.from_pylist(
                [{key: row.get(key) for key in keys} for row in objects]
            )
        except pa.ArrowException as exc:
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
    try:
        return pa.table(
            {name: [row[index] for row in rows] for index, name in enumerate(names)}
        )
    except pa.ArrowException as exc:
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
