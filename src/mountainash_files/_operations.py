from __future__ import annotations

import contextlib
import dataclasses
import io
import logging
import typing as t
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

from mountainash_transport import PathNotFoundError, Pipeline, StorageFacade

from mountainash_files._exceptions import WriteError
from mountainash_files.formats._registry import (
    get_parser,
    get_serialiser,
    get_spec_class,
    get_suffix_overrides,
    resolve_format,
)
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._types import FormatSpec, ParseResult
from mountainash_files.specs.base import FileSpec
from mountainash_files.specs.sink import FileSinkSpec
from mountainash_files.specs.source import FileSourceSpec

if TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile
    from mountainash_transport import StorageProfileProtocol

_VALID_OUTPUTS = ("arrow", "pydata")
_logger = logging.getLogger(__name__)


def _check_output(output: str) -> None:
    if output not in _VALID_OUTPUTS:
        raise ValueError(f"output must be one of {_VALID_OUTPUTS}, got {output!r}")


def _normalise_output(data: Any, output: str, spec: FormatSpec) -> Any:
    """The single tabular-normalisation seam (rev-3 spec §1.3)."""
    if not type(spec).TABULAR:
        return data

    import pyarrow as pa

    if output == "arrow":
        if isinstance(data, pa.Table):
            return data
        if isinstance(data, dict):
            return pa.Table.from_pylist([data])
        if isinstance(data, list):
            if data and not all(isinstance(row, dict) for row in data):
                raise ParseError(
                    spec.FORMAT,
                    "non-record JSON array is not tabular; expected an array "
                    "of objects",
                )
            if data:
                keys = list(dict.fromkeys(key for row in data for key in row))
                data = [{key: row.get(key) for key in keys} for row in data]
            return pa.Table.from_pylist(data)
        raise ParseError(
            spec.FORMAT,
            f"payload type {type(data).__name__} is not normalisable to Arrow",
        )

    if isinstance(data, pa.Table):
        return data.to_pylist()
    return data


def _resolve_profiles(
    spec: FileSpec,
) -> tuple["StorageProfileProtocol | None", "AuthProfile | None"]:
    """Materialise the spec's profile fields (spec semantics table).

    A string storage_profile resolves via transport's resolve_storage;
    an explicitly passed auth_profile object always wins.
    """
    storage = spec.storage_profile
    if isinstance(storage, str):
        from mountainash_transport import resolve_storage

        profile, auth = resolve_storage(storage)
        if spec.auth_profile is not None:
            auth = spec.auth_profile
        return profile, auth
    return storage, spec.auth_profile


def _make_facade(
    path: str,
    storage_profile: "StorageProfileProtocol | None",
    auth_profile: "AuthProfile | None",
) -> StorageFacade:
    return StorageFacade.from_path(path, storage_profile, auth_profile=auth_profile)


def _read_bytes(
    path: str,
    storage_profile: "StorageProfileProtocol | None",
    auth_profile: "AuthProfile | None",
    transforms: Pipeline | None,
    *,
    infer: bool = True,
) -> bytes:
    """Read bytes via transport, applying transforms (decompress/decrypt).

    When infer=True and no explicit transforms, auto-detects compression
    from path suffixes (.gz, .gpg). Disable infer when archive extraction
    will handle decompression separately.
    """
    facade = _make_facade(path, storage_profile, auth_profile)
    if transforms is not None:
        return facade.read(path, pipeline=transforms)
    if infer:
        return facade.read(path, infer=True)
    return facade.read(path)


def _write_bytes(
    path: str,
    data: bytes,
    storage_profile: "StorageProfileProtocol | None",
    auth_profile: "AuthProfile | None",
    create_path: bool,
    transforms: Pipeline | None,
) -> None:
    """Write bytes via transport, applying transforms (compress/encrypt)."""
    if "://" not in path:
        p = Path(path)
        if create_path:
            p.parent.mkdir(parents=True, exist_ok=True)
        elif not p.parent.exists():
            raise WriteError(f"Parent directory does not exist: {p.parent}")
    facade = _make_facade(path, storage_profile, auth_profile)
    facade.write(path, data, pipeline=transforms)


def parse(
    source: FileSourceSpec,
    *,
    params: dict[str, Any] | None = None,
    output: t.Literal["arrow", "pydata"] = "arrow",
) -> list[ParseResult]:
    """Parse file(s) from a source spec.

    Always returns a list of ParseResult, even for single files.
    """
    _check_output(output)
    path = source.path
    if params:
        path = path.format(**params)

    storage_profile, auth_profile = _resolve_profiles(source)

    # Glob resolution
    if source.glob is not None:
        from mountainash_files._glob import resolve_glob

        paths = resolve_glob(
            path,
            source.glob,
            storage_profile=storage_profile,
            auth_profile=auth_profile,
        )
        results = []
        for file_path in paths:
            child_source = FileSourceSpec(
                path=file_path,
                format=source.format,
                storage_profile=storage_profile,
                auth_profile=auth_profile,
                archive=source.archive,
                transforms=source.transforms,
                on_missing=source.on_missing,
            )
            results.extend(parse(child_source, output=output))
        return results

    # Archive path: read raw bytes (no suffix inference — archive handles decompression),
    # then extract members, then parse each.
    if source.archive is not None:
        try:
            raw = _read_bytes(
                path, storage_profile, auth_profile, source.transforms, infer=False
            )
        except (FileNotFoundError, Exception) as exc:
            if source.on_missing == "skip" and _is_not_found(exc):
                return []
            raise

        from mountainash_files._archives import unpack_archive

        members = list(unpack_archive(raw, source.archive))
        on_unrecognised = getattr(source.archive, "on_unrecognised", "error")
        results = []
        skipped: list[str] = []
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
            except Exception as exc:
                if on_unrecognised == "skip":
                    skipped.append(member_name)
                    _logger.warning(
                        "Skipping archive member %r (unrecognised format): %s",
                        member_name,
                        exc,
                    )
                    continue
                raise ParseError(
                    "archive",
                    f"member {member_name!r} in {path!r} has no resolvable "
                    f"format ({exc}); scope members with file_pattern or set "
                    "on_unrecognised='skip'",
                ) from exc
            parser = get_parser(fmt_key)
            result_data = _normalise_output(parser(member_data, fmt_spec), output, fmt_spec)
            results.append(ParseResult(data=result_data, format_key=fmt_key, spec=fmt_spec))
        if not results:
            raise ParseError(
                "archive",
                f"archive {path!r} produced no recognised members "
                f"(skipped: {skipped or 'none'})",
            )
        if skipped:
            results = [
                dataclasses.replace(result, skipped_members=tuple(skipped))
                for result in results
            ]
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
        data = _read_bytes(path, storage_profile, auth_profile, source.transforms)
    except (FileNotFoundError, Exception) as exc:
        if source.on_missing == "skip" and _is_not_found(exc):
            return []
        raise

    parser = get_parser(format_key)
    result_data = _normalise_output(parser(data, spec), output, spec)

    return [ParseResult(data=result_data, format_key=format_key, spec=spec)]


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

    storage_profile, auth_profile = _resolve_profiles(sink)

    # Raw bytes bypass format handling
    if isinstance(data, bytes):
        _write_bytes(path, data, storage_profile, auth_profile, sink.create_path, sink.transforms)
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

    if sink.write_disposition == "append" and not type(spec).APPENDABLE:
        raise WriteError(f"Format {format_key!r} does not support append.")

    serialiser = get_serialiser(format_key)
    if serialiser is None:
        raise WriteError(f"No serialiser registered for format {format_key!r}")

    serialised = serialiser(data, spec)
    _write_bytes(
        path, serialised, storage_profile, auth_profile, sink.create_path, sink.transforms
    )


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

    src_profile, src_auth = _resolve_profiles(source)
    dst_profile, dst_auth = _resolve_profiles(sink)

    try:
        data = _read_bytes(src_path, src_profile, src_auth, source.transforms)
    except (FileNotFoundError, Exception) as exc:
        if source.on_missing == "skip" and _is_not_found(exc):
            return
        raise

    _write_bytes(dst_path, data, dst_profile, dst_auth, sink.create_path, sink.transforms)


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

    storage_profile, auth_profile = _resolve_profiles(source)

    try:
        data = _read_bytes(path, storage_profile, auth_profile, source.transforms)
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


def _resolve_format_spec(format: str | FormatSpec) -> tuple[str, FormatSpec]:
    if isinstance(format, FormatSpec):
        return format.FORMAT, format
    format_key, matched_suffix = resolve_format(format=format)
    overrides = get_suffix_overrides(matched_suffix)
    return format_key, get_spec_class(format_key)(**overrides)


def parse_bytes(
    data: bytes | BinaryIO,
    format: str | FormatSpec,
    *,
    output: t.Literal["arrow", "pydata"] = "arrow",
) -> ParseResult:
    """Parse an in-memory buffer with an explicit format.

    The path-based :func:`parse` remains the primary entry; this exposes
    the format registry for bytes the caller already holds (HTTP bodies,
    message payloads, fixtures) without a fake temp path.
    """
    _check_output(output)
    if not isinstance(data, bytes):
        data = data.read()
    format_key, spec = _resolve_format_spec(format)
    parser = get_parser(format_key)
    result_data = _normalise_output(parser(data, spec), output, spec)
    return ParseResult(data=result_data, format_key=format_key, spec=spec)


def serialise_bytes(data: Any, format: str | FormatSpec) -> bytes:
    """Serialise data to bytes with an explicit format (inverse of parse_bytes)."""
    format_key, spec = _resolve_format_spec(format)
    serialiser = get_serialiser(format_key)
    if serialiser is None:
        raise WriteError(f"No serialiser registered for format {format_key!r}")
    return serialiser(data, spec)
