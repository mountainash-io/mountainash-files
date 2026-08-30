from __future__ import annotations

import dataclasses
import json as _json
from typing import BinaryIO, ClassVar

from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._registry import register_format
from mountainash_files.formats._types import FormatSpec
from mountainash_resource_provider import ProviderFormatDescriptor


@dataclasses.dataclass(frozen=True)
class JsonSpec(FormatSpec):
    FORMAT: ClassVar[str] = "json"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".json", ".ndjson", ".jsonl")
    MEDIATYPES: ClassVar[tuple[str, ...]] = (
        "application/json",
        "application/x-ndjson",
    )
    PROVIDER_FORMATS: ClassVar[tuple[ProviderFormatDescriptor, ...]] = (
        ProviderFormatDescriptor(
            canonical_format="json",
            aliases=frozenset(),
            suffixes=frozenset({".json"}),
            mediatypes=frozenset({"application/json"}),
            locator_prefixes=frozenset(),
            dialect_family="structured",
            provider_format_key="json",
        ),
        ProviderFormatDescriptor(
            canonical_format="ndjson",
            aliases=frozenset({"jsonl"}),
            suffixes=frozenset({".ndjson", ".jsonl"}),
            mediatypes=frozenset({"application/ndjson", "application/x-ndjson"}),
            locator_prefixes=frozenset(),
            dialect_family="structured",
            provider_format_key="json",
        ),
        ProviderFormatDescriptor(
            canonical_format="geojson",
            aliases=frozenset(),
            suffixes=frozenset({".geojson"}),
            mediatypes=frozenset({"application/geo+json"}),
            locator_prefixes=frozenset(),
            dialect_family="structured",
            provider_format_key="json",
        ),
    )

    records_path: str | None = None
    ndjson: bool = False
    empty_on_missing: bool = False


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
                    if spec.empty_on_missing:
                        # An absent records collection means zero records — mirror an
                        # explicit empty list rather than erroring (e.g. an API page
                        # that omits the records key when the window has no data).
                        return []
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
