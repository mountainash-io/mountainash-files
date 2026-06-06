from __future__ import annotations

import typing as t
from pathlib import Path
from typing import Any, BinaryIO

from mountainash_files.formats._exceptions import ParseError, UnknownFormatError
from mountainash_files.formats._registry import (
    get_parser,
    get_spec_class,
    get_suffix_overrides,
    resolve_format,
)
from mountainash_files.formats._types import FormatSpec, ParseResult
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
    """Read bytes from a path. Uses utils-files for remote paths, direct read for local."""
    p = Path(path)
    if p.exists():
        return p.read_bytes()

    # Try utils-files for remote paths
    try:
        from mountainash_utils_files import read_bytes
        return read_bytes(path)
    except ImportError:
        pass

    raise FileNotFoundError(f"File not found: {path}")


def _is_not_found(exc: Exception) -> bool:
    """Check if an exception represents a file-not-found condition."""
    if isinstance(exc, FileNotFoundError):
        return True
    try:
        from mountainash_utils_files.exceptions import PathNotFoundError
        return isinstance(exc, PathNotFoundError)
    except ImportError:
        return False
