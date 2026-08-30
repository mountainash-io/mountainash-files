"""Resource-provider implementation for registered file formats."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pyarrow as pa

from mountainash_resource_provider import (
    RESOURCE_PROVIDER_API_VERSION,
    DialectFieldDisposition,
    FrozenMap,
    NativeReadRequest,
    ProviderCompatibilityError,
    ProviderReadError,
    ProviderReadResult,
    ReaderBackend,
    ResourceRequest,
)

from mountainash_files._operations import _read_bytes, parse_bytes
from mountainash_files.access import FileAccessParameters, resolve_file_access
from mountainash_files.formats._registry import get_spec_class, iter_provider_formats


@dataclass(frozen=True)
class FileProviderReadPlan:
    """Immutable, secret-free plan for one file resource read."""

    provider_key: str
    dialect_fields: FrozenMap
    payload: FrozenMap


class FileResourceProvider:
    """Read registered file formats through the neutral Arrow provider contract."""

    key = "file"
    api_version = RESOURCE_PROVIDER_API_VERSION

    def __init__(self, access: FileAccessParameters | None = None) -> None:
        self._access = access or FileAccessParameters()

    @property
    def formats(self):
        return iter_provider_formats()

    @property
    def parser_keys(self) -> frozenset[str]:
        return frozenset(descriptor.provider_format_key for descriptor in self.formats)

    @classmethod
    def default(cls) -> "FileResourceProvider":
        return cls()

    @classmethod
    def from_parameters(
        cls,
        storage: Any = None,
        auth: Any = None,
    ) -> "FileResourceProvider":
        return cls(FileAccessParameters(storage=storage, auth=auth))

    @classmethod
    def from_profile_name(cls, name: str) -> "FileResourceProvider":
        return cls(FileAccessParameters(storage=name))

    def plan(self, request: ResourceRequest) -> FileProviderReadPlan:
        parser_key = request.detected_format.provider_format_key
        if parser_key not in self.parser_keys:
            raise ProviderCompatibilityError(f"unknown file parser key: {parser_key!r}")
        dialect_fields = FrozenMap(
            {
                key: (
                    DialectFieldDisposition.DEFERRED
                    if request.detected_format.dialect_family == "structured"
                    and key in {"header", "itemKeys", "item_keys"}
                    else DialectFieldDisposition.CONSUMED
                )
                for key in request.dialect
                if key != "$schema"
            }
        )
        return FileProviderReadPlan(
            provider_key=self.key,
            dialect_fields=dialect_fields,
            payload=FrozenMap(
                {
                    "locator": request.locator,
                    "parser_key": parser_key,
                    "canonical_format": request.detected_format.canonical_format,
                    "dialect": request.dialect,
                    "encoding": request.encoding,
                }
            ),
        )

    def read_arrow(self, plan: FileProviderReadPlan) -> ProviderReadResult:
        locator = plan.payload["locator"]
        if not isinstance(locator, str):
            raise ProviderReadError("file provider requires one string locator")
        parser_key = plan.payload["parser_key"]
        if not isinstance(parser_key, str):
            raise ProviderCompatibilityError("file plan parser_key must be a string")
        storage, auth = resolve_file_access(self._access)
        try:
            raw = _read_bytes(locator, storage, auth, None)
            spec = self._spec_for_plan(plan, parser_key)
            parsed = parse_bytes(raw, spec, output="arrow")
        except ProviderCompatibilityError:
            raise
        except Exception as exc:
            raise ProviderReadError(f"could not read file resource {locator!r}") from exc
        if not isinstance(parsed.data, pa.Table):
            raise ProviderReadError("file parser did not produce an Arrow table")
        deferred = any(
            value is DialectFieldDisposition.DEFERRED
            for value in plan.dialect_fields.values()
        )
        resolved_context: dict[str, str] = {}
        dialect_fields = dict(plan.dialect_fields)
        if deferred:
            item_type = plan.payload["dialect"].get("item_type")
            shape = item_type if item_type in {"object", "array"} else "object"
            resolved_context["structured_row_shape"] = shape
            dialect_fields = {
                key: DialectFieldDisposition.CONSUMED
                if value is DialectFieldDisposition.DEFERRED
                else value
                for key, value in dialect_fields.items()
            }
        return ProviderReadResult(
            table=parsed.data,
            resolved_context=resolved_context,
            dialect_fields=dialect_fields,
        )

    def native_request(
        self,
        plan: FileProviderReadPlan,
        backend: ReaderBackend,
    ) -> NativeReadRequest | None:
        return None

    def _spec_for_plan(self, plan: FileProviderReadPlan, parser_key: str):
        options = dict(plan.payload["dialect"])
        canonical_format = plan.payload["canonical_format"]
        if parser_key == "json" and canonical_format == "ndjson":
            options["ndjson"] = True
        spec_class = get_spec_class(parser_key)
        return spec_class.from_options(options)


def create_provider() -> FileResourceProvider:
    """Entry-point factory for the file resource provider."""
    return FileResourceProvider.default()


__all__ = ["FileProviderReadPlan", "FileResourceProvider", "create_provider"]
