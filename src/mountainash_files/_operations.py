from __future__ import annotations

import contextlib
import dataclasses
import io
import logging
import typing as t
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, BinaryIO

from mountainash_transport import (
    PathNotFoundError,
    Pipeline,
    RangeNotSupportedError,
    StorageFacade,
    UnsupportedOperationError,
    infer_pipeline,
)

from mountainash_files._exceptions import AppendSchemaMismatchError, WriteError
from mountainash_files.formats._registry import (
    get_access,
    get_parser,
    get_schema_access,
    get_schema_inspector,
    get_serialiser,
    get_spec_class,
    get_suffix_overrides,
    resolve_format,
)
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats._types import FormatSpec, ParseResult, SchemaResult
from mountainash_files.specs.base import FileSpec
from mountainash_files.specs.sink import FileSinkSpec
from mountainash_files.specs.source import FileSourceSpec

if TYPE_CHECKING:
    import pyarrow as pa

    from mountainash_auth_client import AuthProfile
    from mountainash_transport import GPG, Gzip, PolicyOverride, RangePolicy, StorageProfileProtocol

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
) -> tuple["StorageProfileProtocol | None", "AuthProfile | None", "PolicyOverride"]:
    """Materialise the spec's profile fields (spec semantics table).

    A string storage_profile resolves via transport's resolve_storage;
    an explicitly passed auth_profile object always wins. The spec's location policy
    is returned beside them so every caller passes all three to its facades.
    """
    storage = spec.storage_profile
    if isinstance(storage, str):
        from mountainash_transport import resolve_storage

        profile, auth = resolve_storage(storage)
        if spec.auth_profile is not None:
            auth = spec.auth_profile
        return profile, auth, spec.policy
    return storage, spec.auth_profile, spec.policy


def _make_facade(
    path: str,
    storage_profile: "StorageProfileProtocol | None",
    auth_profile: "AuthProfile | None",
    policy: "PolicyOverride",
) -> StorageFacade:
    return StorageFacade.from_path(path, storage_profile, auth_profile=auth_profile, policy=policy)


def _read_infer(transforms: Pipeline | None, infer: bool | None) -> bool:
    """Use explicit inference policy, otherwise infer only without a pipeline."""
    return transforms is None if infer is None else infer


def _read_bytes(
    path: str,
    storage_profile: "StorageProfileProtocol | None",
    auth_profile: "AuthProfile | None",
    policy: "PolicyOverride",
    transforms: Pipeline | None,
    *,
    infer: bool | None = None,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> bytes:
    """Read bytes via transport, applying transforms (decompress/decrypt).

    By default, infer transforms from suffixes unless a pipeline is explicit.
    Archive extraction and append disable inference unless explicitly overridden
    by the source. GPG inference requires a configured GPG instance.
    """
    facade = _make_facade(path, storage_profile, auth_profile, policy)
    return facade.read(
        path, pipeline=transforms, infer=_read_infer(transforms, infer),
        gpg=gpg, gzip=gzip,
    )


def _write_bytes(
    path: str,
    data: bytes,
    storage_profile: "StorageProfileProtocol | None",
    auth_profile: "AuthProfile | None",
    policy: "PolicyOverride",
    create_path: bool,
    transforms: Pipeline | None,
) -> None:
    """Write bytes via transport, applying transforms (compress/encrypt) and the parent policy."""
    facade = _make_facade(path, storage_profile, auth_profile, policy)
    facade.write(path, data, pipeline=transforms, create_parents=create_path)


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

    def make(format_key: str, spec: FormatSpec):
        parser = get_parser(format_key)

        def wrap(data: Any) -> ParseResult:
            return ParseResult(data=_normalise_output(data, output, spec), format_key=format_key, spec=spec)

        def on_bytes(data: bytes) -> ParseResult:
            return wrap(parser(data, spec))

        def on_source(path, storage_profile, auth_profile, policy, src) -> ParseResult:
            run = lambda data: parser(data, spec)  # noqa: E731
            return wrap(_with_access(get_access(format_key, spec), run, path, storage_profile, auth_profile, policy, src))

        return on_bytes, on_source

    return _read_source(source, params=params, make=make)


_Make = t.Callable[[str, FormatSpec], tuple[t.Callable[[bytes], Any], t.Callable[..., Any]]]


def _read_source(source: FileSourceSpec, *, params: dict[str, Any] | None, make: _Make) -> list:
    """Shared source traversal for parse and schema discovery.

    ``make(format_key, spec)`` resolves the format's callable before any I/O and returns
    ``(on_bytes, on_source)``: archive members are handed over as bytes; a single file is
    acquired by ``on_source(path, storage_profile, auth_profile, policy, source)``.
    """
    path = source.path
    if params:
        path = path.format(**params)

    storage_profile, auth_profile, policy = _resolve_profiles(source)

    # Glob resolution
    if source.glob is not None:
        from mountainash_files._glob import resolve_glob

        paths = resolve_glob(
            path,
            source.glob,
            storage_profile=storage_profile,
            auth_profile=auth_profile,
            policy=policy,
        )
        results = []
        for file_path in paths:
            child_source = dataclasses.replace(
                source,
                path=file_path,
                glob=None,
                storage_profile=storage_profile,
                auth_profile=auth_profile,
                policy=policy,
            )
            results.extend(_read_source(child_source, params=None, make=make))
        return results

    # Archive path: read raw bytes (no suffix inference — archive handles decompression),
    # then extract members, then hand each to the format.
    if source.archive is not None:
        try:
            raw = _read_bytes(
                path, storage_profile, auth_profile, policy, source.transforms,
                infer=False if source.infer is None else source.infer,
                gpg=source.gpg, gzip=source.gzip,
            )
        except PathNotFoundError:
            if source.on_missing == "skip":
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
            on_bytes, _ = make(fmt_key, fmt_spec)
            results.append(on_bytes(member_data))
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
    elif isinstance(source.format, str):
        format_key, matched_suffix = resolve_format(format=source.format)
        spec = get_spec_class(format_key)(**get_suffix_overrides(matched_suffix))
    else:
        format_key, matched_suffix = resolve_format(path=path)
        spec = get_spec_class(format_key)(**get_suffix_overrides(matched_suffix))

    _, on_source = make(format_key, spec)
    try:
        result = on_source(path, storage_profile, auth_profile, policy, source)
    except PathNotFoundError:
        if source.on_missing == "skip":
            return []
        raise
    return [result]


def _no_transforms(path: str, source: FileSourceSpec) -> bool:
    """Whether the effective pipeline is empty, using transport's public inference."""
    if source.transforms is not None:
        return source.transforms.is_empty()
    if not _read_infer(source.transforms, source.infer):
        return True
    try:
        pipeline, _ = infer_pipeline(path, gpg=source.gpg, gzip=source.gzip)
    except ValueError:
        # Inference failed (e.g. missing GPG). Defer to the byte path, whose facade
        # applies the location policy before any inference, so denied locations
        # surface as redacted LocationNotAllowed and allowed ones raise the real error.
        return False
    return pipeline is None or pipeline.is_empty()


def _with_access(mode, run, path, storage_profile, auth_profile, policy, source):
    """Hand *run* a transport handle in *mode* ('random'/'sequential') when no transforms apply.

    Whole-object bytes otherwise, and when the backend refuses the mode. The handle is
    closed when *run* returns or raises.
    """
    if mode != "bytes" and _no_transforms(path, source):
        facade = _make_facade(path, storage_profile, auth_profile, policy)
        try:
            handle = facade.read_stream(
                path, pipeline=source.transforms,
                infer=_read_infer(source.transforms, source.infer),
                gpg=source.gpg, gzip=source.gzip,
                access=mode, range_policy=None,
            )
        except (RangeNotSupportedError, UnsupportedOperationError):
            handle = None
        if handle is not None:
            with handle:
                return run(handle)
    data = _read_bytes(
        path, storage_profile, auth_profile, policy, source.transforms,
        infer=source.infer, gpg=source.gpg, gzip=source.gzip,
    )
    return run(data)


def inspect_schema(
    source: FileSourceSpec,
    *,
    params: dict[str, Any] | None = None,
    infer_schema_rows: int | None = None,
) -> list[SchemaResult]:
    """Observe the Arrow schema of each selected input without returning its rows.

    Selection (templates, globs, archives, transforms, profiles, missing files) follows
    :func:`parse`. ``infer_schema_rows`` bounds the data records used per selected input;
    ``None`` uses every record. Results are observations, not a contract on later parses.
    """
    _check_budget(infer_schema_rows)
    n = infer_schema_rows

    def make(format_key: str, spec: FormatSpec):
        inspector = get_schema_inspector(format_key)   # unsupported formats fail before any I/O

        def wrap(found: tuple[Any, t.Literal["metadata", "full", "bounded"]]) -> SchemaResult:
            schema, basis = found
            return SchemaResult(schema=schema, basis=basis, format_key=format_key, spec=spec)

        def on_bytes(data: bytes) -> SchemaResult:
            return wrap(inspector(data, spec, infer_schema_rows=n))

        def on_source(path, storage_profile, auth_profile, policy, src) -> SchemaResult:
            mode = get_schema_access(format_key, spec, n)
            run = lambda data: inspector(data, spec, infer_schema_rows=n)  # noqa: E731
            return wrap(_with_access(mode, run, path, storage_profile, auth_profile, policy, src))

        return on_bytes, on_source

    return _read_source(source, params=params, make=make)


def _append_table(data: Any) -> pa.Table:
    """Normalize append records, retaining keys first seen in later rows."""
    import pyarrow as pa

    if isinstance(data, pa.Table):
        return data
    if isinstance(data, dict):
        rows = [data]
    elif isinstance(data, list) and all(isinstance(row, dict) for row in data):
        rows = data
    else:
        raise WriteError("Tabular append requires an Arrow table or record data")
    keys = list(dict.fromkeys(key for row in rows for key in row))
    try:
        return pa.Table.from_pylist(
            [{key: row.get(key) for key in keys} for row in rows]
        )
    except (pa.ArrowException, TypeError, ValueError, OverflowError) as exc:
        raise WriteError(f"Cannot normalize append input: {exc}") from exc


def _merge_append_tables(path: str, existing: pa.Table, incoming: pa.Table) -> pa.Table:
    """Keep destination metadata and union nullability without schema evolution."""
    import pyarrow as pa

    old, new = existing.schema, incoming.schema
    if old.names != new.names or old.types != new.types:
        raise AppendSchemaMismatchError(path, old, new)
    metadata: dict[bytes | str, bytes | str] | None = (
        None
        if old.metadata is None
        else {key: value for key, value in old.metadata.items()}
    )
    schema = pa.schema(
        [
            pa.field(
                left.name,
                left.type,
                nullable=left.nullable or right.nullable,
                metadata=left.metadata,
            )
            for left, right in zip(old, new)
        ],
        metadata=metadata,
    )
    try:
        before = pa.Table.from_arrays(existing.columns, schema=schema)
        after = pa.Table.from_arrays(incoming.columns, schema=schema)
        return pa.concat_tables([before, after])
    except pa.ArrowException as exc:
        raise WriteError(f"Cannot combine append tables for {path!r}: {exc}") from exc


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

    storage_profile, auth_profile, policy = _resolve_profiles(sink)

    if sink.write_disposition not in ("replace", "append"):
        raise WriteError(f"Unknown write disposition: {sink.write_disposition!r}")
    if sink.write_disposition == "append" and isinstance(
        data, (bytes, bytearray, memoryview)
    ):
        raise WriteError("Raw-byte append is not supported; supply tabular records")

    # Raw bytes bypass format handling
    if isinstance(data, bytes):
        _write_bytes(
            path, data, storage_profile, auth_profile, policy, sink.create_path, sink.transforms
        )
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

    serialiser = get_serialiser(format_key)
    if serialiser is None:
        raise WriteError(f"No serialiser registered for format {format_key!r}")

    if sink.write_disposition == "append":
        import pyarrow as pa

        from mountainash_files.formats.parquet import ParquetSpec

        if not type(spec).APPENDABLE or not type(spec).TABULAR:
            raise WriteError(
                f"Format {format_key!r} does not support append of tabular data."
            )
        incoming = _append_table(data)
        try:
            raw = _read_bytes(
                path, storage_profile, auth_profile, policy, sink.transforms, infer=False
            )
        except PathNotFoundError:
            data = incoming
        else:
            read_spec = (
                dataclasses.replace(spec, columns=None)
                if isinstance(spec, ParquetSpec)
                else spec
            )
            existing = get_parser(format_key)(raw, read_spec)
            if not isinstance(existing, pa.Table):
                raise WriteError(
                    f"Append parser for {format_key!r} must return a complete Arrow table"
                )
            data = _merge_append_tables(path, existing, incoming)

    serialised = serialiser(data, spec)
    _write_bytes(
        path,
        serialised,
        storage_profile,
        auth_profile,
        policy,
        sink.create_path,
        sink.transforms,
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

    src_profile, src_auth, src_policy = _resolve_profiles(source)
    dst_profile, dst_auth, dst_policy = _resolve_profiles(sink)

    try:
        data = _read_bytes(
            src_path, src_profile, src_auth, src_policy, source.transforms,
            infer=source.infer, gpg=source.gpg, gzip=source.gzip,
        )
    except PathNotFoundError:
        if source.on_missing == "skip":
            return
        raise

    _write_bytes(
        dst_path, data, dst_profile, dst_auth, dst_policy, sink.create_path, sink.transforms
    )


@contextlib.contextmanager
def stream(
    source: FileSourceSpec,
    *,
    params: dict[str, Any] | None = None,
    access: t.Literal["sequential", "random", "buffered"] = "sequential",
    range_policy: "RangePolicy | None" = None,
) -> Iterator[BinaryIO]:
    """Return a raw byte stream from a source as a context manager.

    Applies transforms (decompress/decrypt) but no format parsing. Delegates
    consumption and seekability to transport; decoding can fail during reads.
    ``access`` and ``range_policy`` pass to transport unchanged and there is no
    fallback: transport errors propagate. The returned stream is closed when the
    context exits.
    """
    path = source.path
    if params:
        path = path.format(**params)

    storage_profile, auth_profile, policy = _resolve_profiles(source)

    try:
        facade = _make_facade(path, storage_profile, auth_profile, policy)
        handle = facade.read_stream(
            path, pipeline=source.transforms,
            infer=_read_infer(source.transforms, source.infer),
            gpg=source.gpg, gzip=source.gzip,
            access=access, range_policy=range_policy,
        )
    except PathNotFoundError:
        if source.on_missing != "skip":
            raise
        handle = io.BytesIO()
    with handle:
        yield handle


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


def _check_budget(infer_schema_rows: Any) -> None:
    """A schema budget is None (every record) or a positive int; checked before any I/O."""
    if infer_schema_rows is None:
        return
    if isinstance(infer_schema_rows, bool) or not isinstance(infer_schema_rows, int) or infer_schema_rows < 1:
        raise ValueError(f"infer_schema_rows must be a positive int or None, got {infer_schema_rows!r}")


def inspect_schema_bytes(
    data: bytes | BinaryIO,
    format: str | FormatSpec,
    *,
    infer_schema_rows: int | None = None,
) -> SchemaResult:
    """Observe the Arrow schema of an in-memory buffer without returning its rows.

    ``infer_schema_rows=None`` infers from every record; a positive int bounds the data
    records used. A caller's stream is borrowed: it is read but not closed.
    """
    _check_budget(infer_schema_rows)
    format_key, spec = _resolve_format_spec(format)
    inspector = get_schema_inspector(format_key)
    schema, basis = inspector(data, spec, infer_schema_rows=infer_schema_rows)
    return SchemaResult(schema=schema, basis=basis, format_key=format_key, spec=spec)



def serialise_bytes(data: Any, format: str | FormatSpec) -> bytes:
    """Serialise data to bytes with an explicit format (inverse of parse_bytes)."""
    format_key, spec = _resolve_format_spec(format)
    serialiser = get_serialiser(format_key)
    if serialiser is None:
        raise WriteError(f"No serialiser registered for format {format_key!r}")
    return serialiser(data, spec)
