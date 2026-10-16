from __future__ import annotations

import dataclasses
import json as _json
import re
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


def _utf8(raw: bytes) -> bytes:
    """UTF-8 bytes of a JSON payload (RFC 8259 encoding detection); empty input is an error."""
    if not raw:
        raise ParseError("json", "Empty input")
    try:
        encoding = _json.detect_encoding(raw)
        if encoding != "utf-8":
            raw = raw.decode(encoding).encode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError("json", str(exc)) from exc
    if not raw.strip():
        raise ParseError("json", "Empty input")
    return raw


def _decode_records(raw: bytes, spec: JsonSpec) -> list[object]:
    """Stdlib decode (document or NDJSON lines), then ``property`` selection, as a record list."""
    try:
        source = (
            [_json.loads(line) for line in raw.splitlines() if line.strip()]
            if spec.ndjson
            else _json.loads(raw)
        )
    except Exception as exc:  # UnicodeDecodeError, JSONDecodeError
        raise ParseError("json", str(exc)) from exc
    if spec.property:
        for key in spec.property.split("."):
            if not isinstance(source, dict) or key not in source:
                raise ParseError("json", f"property {spec.property!r} was not found")
            source = source[key]
    return source if isinstance(source, list) else [source]


def json_parse(data: bytes | BinaryIO, spec: JsonSpec) -> pa.Table | list[object]:
    import polars as pl

    raw = _utf8(data.read() if hasattr(data, "read") else data)
    n = spec.infer_sample_rows
    plain = not spec.property and spec.item_type in (None, "object")
    try:
        head = raw.lstrip()[:1]
        if spec.ndjson and plain and head == b"{":
            table = pl.read_ndjson(raw, infer_schema_length=n).to_arrow()
            return _finish(_with_keys(table, spec.item_keys) if spec.item_keys else table, spec)
        if (not spec.ndjson and plain and not spec.item_keys and head == b"["
                and raw.lstrip()[1:].lstrip()[:1] == b"{"):
            return _finish(pl.read_json(raw, infer_schema_length=n).to_arrow(), spec)
    except Exception as exc:  # polars errors
        raise ParseError("json", str(exc)) from exc
    out = _resolve_rows(_decode_records(raw, spec), spec)
    return _finish(out, spec) if isinstance(out, pa.Table) else out


def json_schema_access(spec: JsonSpec, infer_schema_rows: int | None) -> str:
    """NDJSON with a finite budget reads forward and stops; JSON documents need every byte."""
    return "sequential" if spec.ndjson and infer_schema_rows is not None else "bytes"


def _array_rows(first_line: bytes, spec: JsonSpec) -> bool:
    """Whether rows are arrays, by _resolve_rows' rule: explicit item_type, else the first record."""
    if spec.item_type is not None:
        return spec.item_type == "array"
    return first_line.lstrip()[:1] == b"["


_LINE_END = re.compile(rb"\r\n|\r|\n")   # the boundaries bytes.splitlines() uses in _decode_records


def _ndjson_prefix(data: bytes | BinaryIO, spec: JsonSpec, n: int) -> tuple[bytes, bool]:
    """NDJSON through the Nth data line (an array header is extra), and whether the input ended there."""
    if isinstance(data, bytes):
        buffer, eof, checked = _utf8(data), True, True
    else:
        buffer, eof, checked, size = b"", False, False, 65536
    pos, lines, wanted = 0, 0, None
    while True:
        if not eof:
            chunk = data.read(size)   # type: ignore[union-attr]
            eof, size = not chunk, min(size * 2, 8 << 20)
            buffer += chunk
        if not checked and (len(buffer) >= 4 or eof):
            checked = True
            encoding = _json.detect_encoding(buffer[:4]) if buffer else "utf-8"
            if encoding == "utf-8-sig":
                pos = 3   # skip the BOM and keep reading incrementally
            elif encoding != "utf-8":
                while not eof:   # UTF-16/32: line splitting needs the decoded text
                    chunk = data.read(size)   # type: ignore[union-attr]
                    eof, buffer = not chunk, buffer + chunk
                buffer = _utf8(buffer)
        if not checked:
            continue
        while pos < len(buffer):
            match = _LINE_END.search(buffer, pos)
            if match is None or (match.group() == b"\r" and match.end() == len(buffer) and not eof):
                if not eof:
                    break   # line, or a CRLF, still arriving
                end = len(buffer)
            else:
                end = match.end()
            line, pos = buffer[pos:end], end
            if line.strip():
                if wanted is None:
                    wanted = n + (1 if spec.header and _array_rows(line, spec) else 0)
                lines += 1
                if lines == wanted:
                    return buffer[:pos], eof and not buffer[pos:].strip()
        if eof:
            return buffer, True


def json_inspect_schema(data: bytes | BinaryIO, spec: JsonSpec, *, infer_schema_rows: int | None = None):
    """Schema from the JSON parse engine over every record, or over the first N selected records."""
    n = infer_schema_rows
    if spec.ndjson and n is not None:
        prefix, complete = _ndjson_prefix(data, spec, n)
        table = json_parse(prefix, spec)
    else:
        raw = data if isinstance(data, bytes) else data.read()
        if n is None:
            table, complete = json_parse(raw, spec), True
        else:
            records = _decode_records(_utf8(raw), spec)
            keep = n + (1 if records and isinstance(records[0], list) and spec.header
                        and spec.item_type in (None, "array") else 0)
            sliced = dataclasses.replace(spec, property=None)
            table, complete = json_parse(_json.dumps(records[:keep]).encode(), sliced), len(records) <= keep
    if not isinstance(table, pa.Table):
        raise ParseError("json", "the selected records are not tabular")
    sampled = spec.infer_sample_rows is not None
    return table.schema, "full" if complete and not sampled else "bounded"


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
    schema_inspector=json_inspect_schema,
    schema_access=json_schema_access,
)
