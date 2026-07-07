"""Lazy registration, validation, atomicity, mediatype axis (Draft §3.3/§3.4 + rev-3 §2.1/§2.2)."""
import dataclasses
from typing import ClassVar

import pytest

from mountainash_files.formats._exceptions import (
    FormatConflictError,
    FormatResolutionError,
    UnknownFormatError,
)
from mountainash_files.formats._registry import (
    _reset_registry,
    get_parser,
    register_format,
    resolve_format,
)
from mountainash_files.formats._types import FormatSpec


@pytest.fixture(autouse=True)
def fresh_registry():
    _reset_registry()
    yield
    _reset_registry()


@dataclasses.dataclass(frozen=True)
class ToySpec(FormatSpec):
    FORMAT: ClassVar[str] = "toy"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".toy",)
    MEDIATYPES: ClassVar[tuple[str, ...]] = ("application/x-toy",)


def toy_parse(data, spec):
    return {"ok": True}


def test_eager_registration_registers_mediatypes():
    register_format(ToySpec, toy_parse)
    assert resolve_format(mediatype="application/x-toy") == ("toy", None)


def test_mediatype_param_stripping_and_case():
    register_format(ToySpec, toy_parse)
    assert resolve_format(mediatype="Application/X-TOY; charset=utf-8") == ("toy", None)


def test_mediatype_structured_suffix_fallback():
    assert resolve_format(mediatype="application/geo+json") == ("json", None)


def test_mediatype_exact_beats_structured_suffix():
    @dataclasses.dataclass(frozen=True)
    class GeoSpec(FormatSpec):
        FORMAT: ClassVar[str] = "geojson"
        SUFFIXES: ClassVar[tuple[str, ...]] = ()
        MEDIATYPES: ClassVar[tuple[str, ...]] = ("application/geo+json",)

    register_format(GeoSpec, toy_parse)
    assert resolve_format(mediatype="application/geo+json")[0] == "geojson"


def test_mediatype_collision_raises():
    @dataclasses.dataclass(frozen=True)
    class Toy2Spec(FormatSpec):
        FORMAT: ClassVar[str] = "toy2"
        SUFFIXES: ClassVar[tuple[str, ...]] = ()
        MEDIATYPES: ClassVar[tuple[str, ...]] = ("application/x-toy",)

    register_format(ToySpec, toy_parse)
    with pytest.raises(FormatConflictError):
        register_format(Toy2Spec, toy_parse)


def test_lazy_registration_requires_format_key():
    with pytest.raises(ValueError, match="format_key"):
        register_format("pkg.mod:Spec", "pkg.mod:parse")


def test_lazy_registration_defers_import():
    register_format(
        "nonexistent_pkg.mod:Spec",
        "nonexistent_pkg.mod:parse",
        format_key="lazy",
        suffixes=(".lz",),
    )
    with pytest.raises(FormatResolutionError) as ei:
        get_parser("lazy")
    assert ei.value.format_key == "lazy"
    assert ei.value.field == "parser"


def test_dotted_path_validation_at_registration():
    with pytest.raises(ValueError, match="dotted"):
        register_format("no-colon-here", "also.no.colon", format_key="bad", suffixes=())


def test_uppercase_format_key_rejected_at_registration():
    with pytest.raises(ValueError, match="lowercase"):
        register_format(ToySpec, toy_parse, format_key="TOY")


def test_user_format_input_is_lowercased():
    register_format(ToySpec, toy_parse)
    assert resolve_format(format="TOY") == ("toy", None)


def test_suffix_must_start_with_dot():
    with pytest.raises(ValueError, match="suffix"):
        register_format(ToySpec, toy_parse, suffixes=("toy",))


def test_atomic_registration_no_partial_state():
    with pytest.raises(ValueError):
        register_format(ToySpec, toy_parse, suffixes=("bad-no-dot",))
    with pytest.raises(UnknownFormatError):
        resolve_format(format="toy")


def test_override_cleans_old_suffixes_and_mediatypes():
    register_format(ToySpec, toy_parse)

    @dataclasses.dataclass(frozen=True)
    class NewToySpec(FormatSpec):
        FORMAT: ClassVar[str] = "toy"
        SUFFIXES: ClassVar[tuple[str, ...]] = (".newtoy",)
        MEDIATYPES: ClassVar[tuple[str, ...]] = ()

    register_format(NewToySpec, toy_parse, override=True)
    with pytest.raises(UnknownFormatError):
        resolve_format(path="x.toy")
    with pytest.raises(UnknownFormatError):
        resolve_format(mediatype="application/x-toy")
    assert resolve_format(path="x.newtoy") == ("toy", ".newtoy")


def test_reentrant_lock_registration_during_resolution():
    from mountainash_files.formats import _registry

    def sneaky_parse(data, spec):
        return None

    with _registry._LOCK:
        register_format(ToySpec, sneaky_parse)
    assert get_parser("toy") is sneaky_parse
