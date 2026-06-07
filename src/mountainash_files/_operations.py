from __future__ import annotations

import contextlib
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any, BinaryIO

from mountainash_utils_files import StorageFacade, read_bytes as _utils_read_bytes
from mountainash_utils_files.exceptions import PathNotFoundError

from mountainash_files._exceptions import WriteError
from mountainash_files.formats._registry import (
    get_parser,
    get_serialiser,
    get_spec_class,
    get_suffix_overrides,
    resolve_format,
)
from mountainash_files.formats._types import FormatSpec, ParseResult
from mountainash_files.specs.sink import FileSinkSpec
from mountainash_files.specs.source import FileSourceSpec


def parse(
    source: FileSourceSpec,
    *,
    params: dict[str, Any] | None = None,
) -> list[ParseResult]:
    """Parse file(s) from a source spec.

    Always returns a list of ParseResult, even for single files.
    """
    path = source.path
    if params:
        path = path.format(**params)

    # Resolve format before IO — unknown suffix raises immediately without touching the file.
    if isinstance(source.format, FormatSpec):
        format_key = source.format.FORMAT
        spec = source.format
        matched_suffix = None
    elif isinstance(source.format, str):
        format_key, matched_suffix = resolve_format(format=source.format)
        overrides = get_suffix_overrides(matched_suffix)
        spec = get_spec_class(format_key)(**overrides)
    else:
        format_key, matched_suffix = resolve_format(path=path)
        overrides = get_suffix_overrides(matched_suffix)
        spec = get_spec_class(format_key)(**overrides)

    # Phase 1: single file only (no glob, no archive)
    try:
        data = _read_bytes(path, source.auth_profile)
    except (FileNotFoundError, Exception) as exc:
        # Catch both local FileNotFoundError and utils-files PathNotFoundError
        if source.on_missing == "skip" and _is_not_found(exc):
            return []
        raise

    parser = get_parser(format_key)
    result_data = parser(data, spec)

    return [ParseResult(data=result_data, format_key=format_key, spec=spec)]


def _read_bytes(path: str, auth_profile: str | None) -> bytes:
    """Read bytes from a path via utils-files (handles local + remote)."""
    return _utils_read_bytes(path)


_APPENDABLE_FORMATS = frozenset({"parquet"})


def write(
    sink: FileSinkSpec,
    data: Any,
    *,
    params: dict[str, Any] | None = None,
) -> None:
    """Write data to a destination."""
    path = sink.path
    if params:
        path = path.format(**params)

    # Raw bytes bypass format handling
    if isinstance(data, bytes):
        _write_bytes(path, data, sink.auth_profile, sink.create_path)
        return

    # Resolve format
    if isinstance(sink.format, FormatSpec):
        format_key = sink.format.FORMAT
        spec = sink.format
    elif isinstance(sink.format, str):
        format_key, matched_suffix = resolve_format(format=sink.format)
        overrides = get_suffix_overrides(matched_suffix)
        spec = get_spec_class(format_key)(**overrides)
    else:
        format_key, matched_suffix = resolve_format(path=path)
        overrides = get_suffix_overrides(matched_suffix)
        spec = get_spec_class(format_key)(**overrides)

    # Check append support
    if sink.write_disposition == "append" and format_key not in _APPENDABLE_FORMATS:
        raise WriteError(
            f"Format {format_key!r} does not support append. "
            f"Appendable formats: {', '.join(sorted(_APPENDABLE_FORMATS))}"
        )

    serialiser = get_serialiser(format_key)
    if serialiser is None:
        raise WriteError(f"No serialiser registered for format {format_key!r}")

    serialised = serialiser(data, spec)
    _write_bytes(path, serialised, sink.auth_profile, sink.create_path)


def _write_bytes(
    path: str,
    data: bytes,
    auth_profile: str | None,
    create_path: bool,
) -> None:
    """Write bytes to a path via utils-files (handles local + remote)."""
    if "://" not in path:
        p = Path(path)
        if create_path:
            p.parent.mkdir(parents=True, exist_ok=True)
        elif not p.parent.exists():
            raise WriteError(f"Parent directory does not exist: {p.parent}")
    facade = StorageFacade.from_path(path)
    facade.write(path, data)


def copy(
    source: FileSourceSpec,
    sink: FileSinkSpec,
    *,
    params: dict[str, Any] | None = None,
) -> None:
    """Copy bytes from source to destination without parsing."""
    src_path = source.path
    dst_path = sink.path
    if params:
        src_path = src_path.format(**params)
        dst_path = dst_path.format(**params)

    try:
        data = _read_bytes(src_path, source.auth_profile)
    except (FileNotFoundError, Exception) as exc:
        if source.on_missing == "skip" and _is_not_found(exc):
            return
        raise

    _write_bytes(dst_path, data, sink.auth_profile, sink.create_path)


def _is_not_found(exc: Exception) -> bool:
    """Check if an exception represents a file-not-found condition."""
    return isinstance(exc, (FileNotFoundError, PathNotFoundError))
