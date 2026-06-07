from __future__ import annotations

import dataclasses
import json as _json
from typing import BinaryIO, ClassVar

from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec


@dataclasses.dataclass(frozen=True)
class JsonSpec(FormatSpec):
    FORMAT: ClassVar[str] = "json"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".json", ".ndjson", ".jsonl")

    records_path: str | None = None
    ndjson: bool = False


def json_parse(data: bytes | BinaryIO, spec: JsonSpec) -> dict | list:
    if hasattr(data, "read"):
        raw = data.read()
    else:
        raw = data

    if len(raw) == 0:
        raise ParseError("json", "Empty input")

    if spec.ndjson:
        try:
            return [_json.loads(line) for line in raw.splitlines() if line.strip()]
        except (_json.JSONDecodeError, ValueError) as exc:
            raise ParseError("json", str(exc)) from exc

    try:
        parsed = _json.loads(raw)
    except (_json.JSONDecodeError, ValueError) as exc:
        raise ParseError("json", str(exc)) from exc

    if spec.records_path is not None:
        for key in spec.records_path.split("."):
            if isinstance(parsed, dict):
                if key not in parsed:
                    raise ParseError(
                        "json",
                        f"Key {key!r} not found at path {spec.records_path!r}",
                    )
                parsed = parsed[key]
            else:
                raise ParseError(
                    "json",
                    f"Expected dict at {key!r} in path {spec.records_path!r}, "
                    f"got {type(parsed).__name__}",
                )

    return parsed


import pyarrow as pa  # noqa: E402


def json_serialise(data: dict | list | pa.Table, spec: JsonSpec) -> bytes:
    if isinstance(data, pa.Table):
        data = data.to_pylist()

    if spec.ndjson and isinstance(data, list):
        lines = [_json.dumps(item, default=str) for item in data]
        return ("\n".join(lines) + "\n").encode("utf-8")

    return _json.dumps(data, default=str, indent=2).encode("utf-8")


register_format(
    JsonSpec,
    json_parse,
    serialiser=json_serialise,
    suffix_overrides={".ndjson": {"ndjson": True}, ".jsonl": {"ndjson": True}},
)
