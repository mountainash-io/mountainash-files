from __future__ import annotations

import dataclasses
import json as _json
import types
from typing import Any, ClassVar, Union, get_args, get_origin, get_type_hints


class FormatSpec:
    """Base for all format specifications.

    Subclasses must be @dataclass(frozen=True) and declare FORMAT and SUFFIXES.
    """

    FORMAT: ClassVar[str]
    SUFFIXES: ClassVar[tuple[str, ...]]
    MEDIATYPES: ClassVar[tuple[str, ...]] = ()
    TABULAR: ClassVar[bool] = True
    COMPLEX_HANDLER_KEY: ClassVar[str | None] = None
    APPENDABLE: ClassVar[bool] = False

    def to_options(self, *, full: bool = False) -> dict[str, Any]:
        options: dict[str, Any] = {}

        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if not full:
                if field.default is not dataclasses.MISSING and value == field.default:
                    continue
                if (
                    field.default_factory is not dataclasses.MISSING
                    and value == field.default_factory()
                ):
                    continue
            try:
                _json.dumps(value, default=_reject_non_json)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{field.name} is not JSON-serialisable") from exc
            options[field.name] = value

        return options

    @classmethod
    def from_options(cls, options: dict[str, Any]) -> "FormatSpec":
        coerced: dict[str, Any] = {}
        fields = {field.name: field for field in dataclasses.fields(cls)}
        type_hints = get_type_hints(cls)

        for name, value in options.items():
            field = fields.get(name)
            if field is not None:
                coerced[name] = _coerce_option_value(
                    value,
                    type_hints.get(name, field.type),
                )
            else:
                coerced[name] = value

        return cls(**coerced)


def _reject_non_json(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"{value!r} is not JSON-serialisable")


def _coerce_option_value(value: Any, annotation: Any) -> Any:
    origin = get_origin(annotation)

    if origin in (Union, types.UnionType):
        if value is None:
            return None
        for arg in get_args(annotation):
            if arg is type(None):
                continue
            if _is_tuple_annotation(arg):
                return _coerce_option_value(value, arg)
        return value

    if origin is tuple and isinstance(value, (list, tuple)):
        args = get_args(annotation)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_coerce_option_value(item, args[0]) for item in value)
        if args:
            if len(value) != len(args):
                raise ValueError(
                    f"tuple length mismatch: expected {len(args)}, got {len(value)}"
                )
            return tuple(
                _coerce_option_value(item, arg)
                for item, arg in zip(value, args, strict=True)
            )
        return tuple(value)

    return value


def _is_tuple_annotation(annotation: Any) -> bool:
    return "tuple" in str(annotation)


@dataclasses.dataclass(frozen=True)
class ParseResult:
    """Typed wrapper around parsed data."""

    data: Any
    format_key: str
    spec: FormatSpec
    skipped_members: tuple[str, ...] = ()
