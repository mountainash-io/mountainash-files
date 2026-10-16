from __future__ import annotations

import importlib
import importlib.metadata
import logging
import threading
import typing as t
from pathlib import PurePosixPath

from mountainash_files.formats._exceptions import (
    FormatConflictError,
    FormatResolutionError,
    SchemaDiscoveryUnsupportedError,
    UnknownFormatError,
)
from mountainash_files.formats._types import FormatSpec

_logger = logging.getLogger(__name__)

TRANSFORM_SUFFIXES: frozenset[str] = frozenset(
    {
        ".gz",
        ".gzip",
        ".bz2",
        ".zst",
        ".lz4",
        ".xz",
        ".gpg",
        ".pgp",
        ".asc",
        ".age",
    }
)

_LOCK = threading.RLock()

_SPECS: dict[str, type[FormatSpec] | str] = {}
_PARSERS: dict[str, t.Callable | str] = {}
_SERIALISERS: dict[str, t.Callable | str | None] = {}
_ACCESS: dict[str, t.Any] = {}
_ACCESS_VALUES = ("bytes", "random")
_INSPECTORS: dict[str, t.Callable | str | None] = {}
_SCHEMA_ACCESS: dict[str, t.Any] = {}
_SCHEMA_ACCESS_VALUES = ("bytes", "random", "sequential")
_SUFFIX_MAP: dict[str, str] = {}
_MEDIATYPE_MAP: dict[str, str] = {}
_SUFFIX_OVERRIDES: dict[str, dict[str, t.Any]] = {}
_FAILED_ENTRYPOINTS: dict[str, Exception] = {}
_DISCOVERY_DONE: bool = False


def _reset_registry() -> None:
    """Reset registrations to built-ins and clear the discovery latch.

    Tests use this to isolate plugin/user registrations without making later
    parse tests depend on import-order side effects.
    """
    global _DISCOVERY_DONE
    with _LOCK:
        _SPECS.clear()
        _PARSERS.clear()
        _SERIALISERS.clear()
        _ACCESS.clear()
        _INSPECTORS.clear()
        _SCHEMA_ACCESS.clear()
        _SUFFIX_MAP.clear()
        _MEDIATYPE_MAP.clear()
        _SUFFIX_OVERRIDES.clear()
        _FAILED_ENTRYPOINTS.clear()
        _DISCOVERY_DONE = False
        _register_builtin_formats()


def _register_builtin_formats() -> None:
    from mountainash_files.formats.csv import (
        CsvSpec,
        csv_inspect_schema,
        csv_parse,
        csv_schema_access,
        csv_serialise,
    )
    from mountainash_files.formats.json import (
        JsonSpec,
        json_inspect_schema,
        json_parse,
        json_schema_access,
        json_serialise,
    )
    from mountainash_files.formats.parquet import (
        ParquetSpec,
        parquet_access,
        parquet_inspect_schema,
        parquet_parse,
        parquet_serialise,
    )
    from mountainash_files.formats.tsv import TsvSpec
    from mountainash_files.formats.xlsx import XlsxSpec, xlsx_inspect_schema, xlsx_parse
    from mountainash_files.formats.xml import XmlSpec, xml_parse, xml_serialise

    register_format(
        CsvSpec, csv_parse, serialiser=csv_serialise,
        schema_inspector=csv_inspect_schema, schema_access=csv_schema_access, override=True,
    )
    register_format(
        JsonSpec,
        json_parse,
        serialiser=json_serialise,
        suffix_overrides={".ndjson": {"ndjson": True}, ".jsonl": {"ndjson": True}},
        schema_inspector=json_inspect_schema,
        schema_access=json_schema_access,
        override=True,
    )
    register_format(
        ParquetSpec,
        parquet_parse,
        serialiser=parquet_serialise,
        access=parquet_access,
        schema_inspector=parquet_inspect_schema,
        schema_access="random",
        override=True,
    )
    register_format(
        TsvSpec, csv_parse, serialiser=csv_serialise,
        schema_inspector=csv_inspect_schema, schema_access=csv_schema_access, override=True,
    )
    register_format(XlsxSpec, xlsx_parse, schema_inspector=xlsx_inspect_schema, override=True)
    register_format(XmlSpec, xml_parse, serialiser=xml_serialise, override=True)


def _validate_dotted(ref: str, what: str) -> None:
    if ref.count(":") != 1 or not all(ref.split(":")):
        raise ValueError(
            f"{what} must be a dotted path of the form 'package.module:attr', "
            f"got {ref!r}"
        )


def register_format(
    spec_cls: type[FormatSpec] | str,
    parser: t.Callable | str,
    *,
    format_key: str | None = None,
    suffixes: tuple[str, ...] | None = None,
    mediatypes: tuple[str, ...] | None = None,
    serialiser: t.Callable | str | None = None,
    suffix_overrides: dict[str, dict[str, t.Any]] | None = None,
    override: bool = False,
    access: t.Any = "bytes",
    schema_inspector: t.Callable | str | None = None,
    schema_access: t.Any = "bytes",
) -> None:
    if isinstance(spec_cls, str):
        _validate_dotted(spec_cls, "spec_cls")
        if format_key is None:
            raise ValueError("format_key is required for lazy (string) registrations")
        if suffixes is None:
            raise ValueError("suffixes is required for lazy (string) registrations")
        key = format_key
        sfx = suffixes
        mts = mediatypes or ()
    else:
        key = format_key if format_key is not None else spec_cls.FORMAT
        sfx = suffixes if suffixes is not None else spec_cls.SUFFIXES
        mts = mediatypes if mediatypes is not None else spec_cls.MEDIATYPES

    if isinstance(parser, str):
        _validate_dotted(parser, "parser")
    if isinstance(serialiser, str):
        _validate_dotted(serialiser, "serialiser")
    if isinstance(schema_inspector, str):
        _validate_dotted(schema_inspector, "schema_inspector")
    elif schema_inspector is not None and not callable(schema_inspector):
        raise ValueError("schema_inspector must be a callable, a 'package.module:attr' reference or None")
    if isinstance(schema_access, str) and schema_access not in _SCHEMA_ACCESS_VALUES:
        raise ValueError(f"schema_access must be one of {_SCHEMA_ACCESS_VALUES} or a callable, got {schema_access!r}")
    if not isinstance(schema_access, str) and not callable(schema_access):
        raise ValueError("schema_access must be 'bytes', 'random', 'sequential' or a callable")
    if isinstance(access, str) and access not in _ACCESS_VALUES:
        raise ValueError(f"access must be one of {_ACCESS_VALUES} or a callable, got {access!r}")
    if not isinstance(access, str) and not callable(access):
        raise ValueError("access must be 'bytes', 'random' or a callable of the spec")
    if key != key.lower():
        raise ValueError(f"Format keys must be lowercase, got {key!r}")

    normalised_suffixes = []
    for suffix in sfx:
        if not suffix.startswith(".") or len(suffix) < 2:
            raise ValueError(
                f"Invalid suffix {suffix!r}: must start with '.' and be non-empty"
            )
        normalised_suffixes.append(suffix.lower())
    sfx = tuple(normalised_suffixes)
    mts = tuple(mediatype.lower() for mediatype in mts)

    with _LOCK:
        if key in _SPECS and not override:
            raise FormatConflictError(
                f"Format {key!r} already registered. Pass override=True to replace."
            )
        for suffix in sfx:
            owner = _SUFFIX_MAP.get(suffix)
            if owner is not None and owner != key and not override:
                raise FormatConflictError(
                    f"Suffix {suffix!r} already owned by format {owner!r}. "
                    "Pass override=True to replace."
                )
        for mediatype in mts:
            owner = _MEDIATYPE_MAP.get(mediatype)
            if owner is not None and owner != key and not override:
                raise FormatConflictError(
                    f"Mediatype {mediatype!r} already owned by format {owner!r}. "
                    "Pass override=True to replace."
                )

        if key in _SPECS and override:
            for suffix in [s for s, owner in _SUFFIX_MAP.items() if owner == key]:
                del _SUFFIX_MAP[suffix]
            for mediatype in [m for m, owner in _MEDIATYPE_MAP.items() if owner == key]:
                del _MEDIATYPE_MAP[mediatype]

        _SPECS[key] = spec_cls
        _PARSERS[key] = parser
        _SERIALISERS[key] = serialiser
        _ACCESS[key] = access
        _INSPECTORS[key] = schema_inspector
        _SCHEMA_ACCESS[key] = schema_access
        for suffix in sfx:
            _SUFFIX_MAP[suffix] = key
        for mediatype in mts:
            _MEDIATYPE_MAP[mediatype] = key
        if suffix_overrides:
            for suffix, overrides in suffix_overrides.items():
                _SUFFIX_OVERRIDES[suffix.lower()] = overrides


def _strip_mediatype(mediatype: str) -> str:
    return mediatype.split(";")[0].strip().lower()


def _raise_unknown(*, path: str | None) -> t.NoReturn:
    raise UnknownFormatError(
        path=path,
        known_suffixes=tuple(_SUFFIX_MAP.keys()),
        failed_plugins=tuple(sorted(_FAILED_ENTRYPOINTS)),
        failures=dict(_FAILED_ENTRYPOINTS),
    )


def resolve_format(
    path: str | None = None,
    format: str | None = None,
    mediatype: str | None = None,
) -> tuple[str, str | None]:
    """Resolve a format key. Precedence: explicit format -> mediatype -> suffix."""
    with _LOCK:
        if format is not None:
            fmt = format.lower()
            if fmt not in _SPECS:
                _raise_unknown(path=None)
            return fmt, None

        if mediatype is not None:
            mt = _strip_mediatype(mediatype)
            key = _MEDIATYPE_MAP.get(mt)
            if key is not None:
                return key, None
            if "+" in mt and "/" in mt:
                base = mt.split("/")[0] + "/" + mt.rsplit("+", 1)[1]
                key = _MEDIATYPE_MAP.get(base)
                if key is not None:
                    return key, None

        if path is not None:
            for suffix in reversed(PurePosixPath(path).suffixes):
                s = suffix.lower()
                if s in TRANSFORM_SUFFIXES:
                    continue
                matched_format = _SUFFIX_MAP.get(s)
                if matched_format is not None:
                    return matched_format, s

        _raise_unknown(path=path)


def get_suffix_overrides(suffix: str | None) -> dict[str, t.Any]:
    if suffix is None:
        return {}
    return _SUFFIX_OVERRIDES.get(suffix, {})


def _resolve(ref: str, format_key: str, field: str) -> t.Any:
    module_path, attr_name = ref.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
        return getattr(module, attr_name)
    except (ImportError, AttributeError) as exc:
        raise FormatResolutionError(
            format_key=format_key, ref=ref, field=field
        ) from exc


def get_access(format_key: str, spec: t.Any) -> str:
    """The registered acquisition mode for *spec*: 'bytes' or 'random'."""
    key = format_key.lower()
    with _LOCK:
        if key not in _SPECS:
            _raise_unknown(path=None)
        mode = _ACCESS.get(key, "bytes")
    value = mode(spec) if callable(mode) else mode
    if value not in _ACCESS_VALUES:
        raise ValueError(f"access for {key!r} returned {value!r}; expected one of {_ACCESS_VALUES}")
    return value


def get_schema_inspector(format_key: str) -> t.Callable:
    """The format's schema inspector; raises SchemaDiscoveryUnsupportedError if it has none."""
    key = format_key.lower()
    with _LOCK:
        if key not in _SPECS:
            _raise_unknown(path=None)
        ref = _INSPECTORS.get(key)
        if ref is None:
            raise SchemaDiscoveryUnsupportedError(key, "the format has no schema inspector")
        if isinstance(ref, str):
            resolved = _resolve(ref, key, "schema_inspector")
            _INSPECTORS[key] = resolved
            return resolved
        return ref


def get_schema_access(format_key: str, spec: t.Any, infer_schema_rows: int | None) -> str:
    """What discovery hands the inspector when no transforms apply: 'bytes', 'random' or 'sequential'."""
    key = format_key.lower()
    with _LOCK:
        if key not in _SPECS:
            _raise_unknown(path=None)
        mode = _SCHEMA_ACCESS.get(key, "bytes")
    value = mode(spec, infer_schema_rows) if callable(mode) else mode
    if value not in _SCHEMA_ACCESS_VALUES:
        raise ValueError(f"schema_access for {key!r} returned {value!r}; expected one of {_SCHEMA_ACCESS_VALUES}")
    return value


def get_parser(format_key: str) -> t.Callable:
    key = format_key.lower()
    with _LOCK:
        if key not in _PARSERS:
            _raise_unknown(path=None)
        ref = _PARSERS[key]
        if isinstance(ref, str):
            resolved = _resolve(ref, key, "parser")
            _PARSERS[key] = resolved
            return resolved
        return ref


def get_spec_class(format_key: str) -> type[FormatSpec]:
    key = format_key.lower()
    with _LOCK:
        if key not in _SPECS:
            _raise_unknown(path=None)
        ref = _SPECS[key]
        if isinstance(ref, str):
            resolved = _resolve(ref, key, "spec_cls")
            _SPECS[key] = resolved
            return resolved
        return ref


def get_serialiser(format_key: str) -> t.Callable | None:
    key = format_key.lower()
    with _LOCK:
        if key not in _SERIALISERS:
            _raise_unknown(path=None)
        ref = _SERIALISERS[key]
        if isinstance(ref, str):
            resolved = _resolve(ref, key, "serialiser")
            _SERIALISERS[key] = resolved
            return resolved
        return ref


def _discover_entrypoint_formats() -> None:
    """Import all modules in the mountainash_files.formats entry-point group."""
    global _DISCOVERY_DONE
    with _LOCK:
        if _DISCOVERY_DONE:
            return
        _DISCOVERY_DONE = True
        eps = importlib.metadata.entry_points(group="mountainash_files.formats")
        for ep in sorted(eps, key=lambda e: (e.group, e.name, e.value)):
            try:
                ep.load()
            except Exception as exc:
                _FAILED_ENTRYPOINTS[ep.name] = exc
                _logger.warning(
                    "Failed to load format plugin %r from %s",
                    ep.name,
                    ep.value,
                    exc_info=True,
                )
