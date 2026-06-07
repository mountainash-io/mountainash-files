from __future__ import annotations

import contextlib
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any, BinaryIO

from mountainash_utils_files import StorageFacade
from mountainash_utils_files.exceptions import PathNotFoundError
from mountainash_utils_files.settings import load_storage
from mountainash_utils_files.storage_transforms import Pipeline

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


def _resolve_auth(auth_profile: str | None) -> tuple:
    """Resolve an auth_profile name to materialised (profile, auth) instances."""
    if auth_profile is None:
        return None, None
    return load_storage(auth_profile)


def _make_facade(path: str, auth_profile: str | None) -> StorageFacade:
    profile, auth = _resolve_auth(auth_profile)
    return StorageFacade.from_path(path, profile=profile, auth=auth)


def _read_bytes(
    path: str,
    auth_profile: str | None,
    transforms: Pipeline | None,
    *,
    infer: bool = True,
) -> bytes:
    """Read bytes via utils-files, applying transforms (decompress/decrypt).

    When infer=True and no explicit transforms, auto-detects compression
    from path suffixes (.gz, .gpg). Disable infer when archive extraction
    will handle decompression separately.
    """
    facade = _make_facade(path, auth_profile)
    if transforms is not None:
        return facade.read(path, pipeline=transforms)
    if infer:
        return facade.read(path, infer=True)
    return facade.read(path)


def _write_bytes(
    path: str,
    data: bytes,
    auth_profile: str | None,
    create_path: bool,
    transforms: Pipeline | None,
) -> None:
    """Write bytes via utils-files, applying transforms (compress/encrypt)."""
    if "://" not in path:
        p = Path(path)
        if create_path:
            p.parent.mkdir(parents=True, exist_ok=True)
        elif not p.parent.exists():
            raise WriteError(f"Parent directory does not exist: {p.parent}")
    facade = _make_facade(path, auth_profile)
    facade.write(path, data, pipeline=transforms)


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

    # Glob resolution
    if source.glob is not None:
        from mountainash_files._glob import resolve_glob

        paths = resolve_glob(path, source.glob, auth_profile=source.auth_profile)
        results = []
        for file_path in paths:
            child_source = FileSourceSpec(
                path=file_path,
                format=source.format,
                auth_profile=source.auth_profile,
                archive=source.archive,
                transforms=source.transforms,
                on_missing=source.on_missing,
            )
            results.extend(parse(child_source))
        return results

    # Archive path: read raw bytes (no suffix inference — archive handles decompression),
    # then extract members, then parse each.
    if source.archive is not None:
        try:
            raw = _read_bytes(path, source.auth_profile, source.transforms, infer=False)
        except (FileNotFoundError, Exception) as exc:
            if source.on_missing == "skip" and _is_not_found(exc):
                return []
            raise

        from mountainash_files._archives import unpack_archive

        members = list(unpack_archive(raw, source.archive))
        results = []
        for member_name, member_data in members:
            try:
                if isinstance(source.format, FormatSpec):
                    fmt_key = source.format.FORMAT
                    fmt_spec = source.format
                elif isinstance(source.format, str):
                    fmt_key, ms = resolve_format(format=source.format)
                    fmt_spec = get_spec_class(fmt_key)(**get_suffix_overrides(ms))
                elif member_name:
                    fmt_key, ms = resolve_format(path=member_name)
                    fmt_spec = get_spec_class(fmt_key)(**get_suffix_overrides(ms))
                else:
                    fmt_key, ms = resolve_format(path=path)
                    fmt_spec = get_spec_class(fmt_key)(**get_suffix_overrides(ms))
            except Exception:
                continue  # Skip members with unrecognised formats
            parser = get_parser(fmt_key)
            result_data = parser(member_data, fmt_spec)
            results.append(ParseResult(data=result_data, format_key=fmt_key, spec=fmt_spec))
        return results

    # Non-archive: resolve format before IO — unknown suffix raises without touching the file.
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

    try:
        data = _read_bytes(path, source.auth_profile, source.transforms)
    except (FileNotFoundError, Exception) as exc:
        if source.on_missing == "skip" and _is_not_found(exc):
            return []
        raise

    parser = get_parser(format_key)
    result_data = parser(data, spec)

    return [ParseResult(data=result_data, format_key=format_key, spec=spec)]


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
        _write_bytes(path, data, sink.auth_profile, sink.create_path, sink.transforms)
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
    _write_bytes(path, serialised, sink.auth_profile, sink.create_path, sink.transforms)


def copy(
    source: FileSourceSpec,
    sink: FileSinkSpec,
    *,
    params: dict[str, Any] | None = None,
) -> None:
    """Copy bytes from source to destination without parsing.

    Source transforms unwrap (decompress/decrypt).
    Sink transforms wrap (compress/encrypt).
    """
    src_path = source.path
    dst_path = sink.path
    if params:
        src_path = src_path.format(**params)
        dst_path = dst_path.format(**params)

    try:
        data = _read_bytes(src_path, source.auth_profile, source.transforms)
    except (FileNotFoundError, Exception) as exc:
        if source.on_missing == "skip" and _is_not_found(exc):
            return
        raise

    _write_bytes(dst_path, data, sink.auth_profile, sink.create_path, sink.transforms)


@contextlib.contextmanager
def stream(
    source: FileSourceSpec,
    *,
    params: dict[str, Any] | None = None,
) -> Iterator[BinaryIO]:
    """Return a raw byte stream from a source as a context manager.

    Applies transforms (decompress/decrypt) but no format parsing.
    """
    path = source.path
    if params:
        path = path.format(**params)

    try:
        data = _read_bytes(path, source.auth_profile, source.transforms)
    except (FileNotFoundError, Exception) as exc:
        if source.on_missing == "skip" and _is_not_found(exc):
            yield io.BytesIO(b"")
            return
        raise

    buf = io.BytesIO(data)
    try:
        yield buf
    finally:
        buf.close()


def _is_not_found(exc: Exception) -> bool:
    """Check if an exception represents a file-not-found condition."""
    return isinstance(exc, (FileNotFoundError, PathNotFoundError))
