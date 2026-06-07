from __future__ import annotations

import typing as t
from pathlib import PurePosixPath

from mountainash_files.formats._exceptions import FormatConflictError, UnknownFormatError
from mountainash_files.formats._types import FormatSpec

TRANSFORM_SUFFIXES: frozenset[str] = frozenset({
    ".gz", ".gzip", ".bz2", ".zst", ".lz4", ".xz",
    ".gpg", ".pgp", ".asc", ".age",
})

_SPECS: dict[str, type[FormatSpec]] = {}
_PARSERS: dict[str, t.Callable] = {}
_SERIALISERS: dict[str, t.Callable | None] = {}
_SUFFIX_MAP: dict[str, str] = {}
_SUFFIX_OVERRIDES: dict[str, dict[str, t.Any]] = {}


def _reset_registry() -> None:
    """Clear all registrations. For testing only."""
    _SPECS.clear()
    _PARSERS.clear()
    _SERIALISERS.clear()
    _SUFFIX_MAP.clear()
    _SUFFIX_OVERRIDES.clear()


def register_format(
    spec_cls: type[FormatSpec],
    parser: t.Callable,
    *,
    serialiser: t.Callable | None = None,
    suffix_overrides: dict[str, dict[str, t.Any]] | None = None,
    override: bool = False,
) -> None:
    key = spec_cls.FORMAT
    if key in _SPECS and not override:
        raise FormatConflictError(
            f"Format {key!r} already registered by {_SPECS[key].__name__}. "
            "Pass override=True to replace."
        )
    if key in _SPECS and override:
        for old_suffix in _SPECS[key].SUFFIXES:
            s = old_suffix.lower()
            if _SUFFIX_MAP.get(s) == key:
                del _SUFFIX_MAP[s]

    _SPECS[key] = spec_cls
    _PARSERS[key] = parser
    _SERIALISERS[key] = serialiser
    for suffix in spec_cls.SUFFIXES:
        _SUFFIX_MAP[suffix.lower()] = key
    if suffix_overrides:
        for suffix, overrides in suffix_overrides.items():
            _SUFFIX_OVERRIDES[suffix.lower()] = overrides


def resolve_format(
    path: str | None = None,
    format: str | None = None,
) -> tuple[str, str | None]:
    if format is not None:
        fmt = format.lower()
        if fmt not in _SPECS:
            raise UnknownFormatError(path=None, known_suffixes=tuple(_SUFFIX_MAP.keys()))
        return fmt, None
    if path is not None:
        for suffix in reversed(PurePosixPath(path).suffixes):
            s = suffix.lower()
            if s in TRANSFORM_SUFFIXES:
                continue
            fmt = _SUFFIX_MAP.get(s)
            if fmt is not None:
                return fmt, s
    raise UnknownFormatError(path=path, known_suffixes=tuple(_SUFFIX_MAP.keys()))


def get_suffix_overrides(suffix: str | None) -> dict[str, t.Any]:
    if suffix is None:
        return {}
    return _SUFFIX_OVERRIDES.get(suffix, {})


def get_parser(format_key: str) -> t.Callable:
    return _PARSERS[format_key]


def get_spec_class(format_key: str) -> type[FormatSpec]:
    return _SPECS[format_key]


def get_serialiser(format_key: str) -> t.Callable | None:
    return _SERIALISERS.get(format_key)
