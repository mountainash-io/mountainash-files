import dataclasses
import typing as t

import pytest

from mountainash_files.formats._exceptions import FormatConflictError, UnknownFormatError
from mountainash_files.formats._registry import (
    TRANSFORM_SUFFIXES,
    get_parser,
    get_spec_class,
    get_suffix_overrides,
    register_format,
    resolve_format,
    _reset_registry,
)
from mountainash_files.formats._types import FormatSpec


@dataclasses.dataclass(frozen=True)
class _FakeSpec(FormatSpec):
    FORMAT: t.ClassVar[str] = "fake"
    SUFFIXES: t.ClassVar[tuple[str, ...]] = (".fake", ".fk")


def _fake_parse(data, spec):
    return {"parsed": True}


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset registry between tests."""
    _reset_registry()
    yield
    _reset_registry()


class TestRegisterFormat:
    def test_register_and_lookup(self):
        register_format(_FakeSpec, _fake_parse)
        assert get_spec_class("fake") is _FakeSpec
        assert get_parser("fake") is _fake_parse

    def test_conflict_raises_without_override(self):
        register_format(_FakeSpec, _fake_parse)
        with pytest.raises(FormatConflictError, match="fake"):
            register_format(_FakeSpec, _fake_parse)

    def test_override_replaces(self):
        register_format(_FakeSpec, _fake_parse)

        def _other_parse(data, spec):
            return {"other": True}

        register_format(_FakeSpec, _other_parse, override=True)
        assert get_parser("fake") is _other_parse

    def test_override_cleans_old_suffixes(self) -> None:
        register_format(_FakeSpec, _fake_parse)

        @dataclasses.dataclass(frozen=True)
        class _NewFake(FormatSpec):
            FORMAT: t.ClassVar[str] = "fake"
            SUFFIXES: t.ClassVar[tuple[str, ...]] = (".newfake",)

        register_format(_NewFake, _fake_parse, override=True)
        # Old suffix should no longer resolve
        with pytest.raises(UnknownFormatError):
            resolve_format(path="data.fake")
        # New suffix should resolve
        key, suffix = resolve_format(path="data.newfake")
        assert key == "fake"

    def test_suffix_overrides(self):
        register_format(
            _FakeSpec, _fake_parse,
            suffix_overrides={".fk": {"mode": "fast"}},
        )
        assert get_suffix_overrides(".fk") == {"mode": "fast"}
        assert get_suffix_overrides(".fake") == {}
        assert get_suffix_overrides(None) == {}


class TestResolveFormat:
    def test_explicit_format(self):
        register_format(_FakeSpec, _fake_parse)
        key, suffix = resolve_format(format="fake")
        assert key == "fake"
        assert suffix is None

    def test_explicit_format_case_insensitive(self):
        register_format(_FakeSpec, _fake_parse)
        key, _ = resolve_format(format="FAKE")
        assert key == "fake"

    def test_suffix_detection(self):
        register_format(_FakeSpec, _fake_parse)
        key, suffix = resolve_format(path="/data/file.fake")
        assert key == "fake"
        assert suffix == ".fake"

    def test_suffix_case_insensitive(self):
        register_format(_FakeSpec, _fake_parse)
        key, _ = resolve_format(path="FILE.FAKE")
        assert key == "fake"

    def test_skips_transform_suffixes(self):
        register_format(_FakeSpec, _fake_parse)
        key, suffix = resolve_format(path="data.fake.gz")
        assert key == "fake"
        assert suffix == ".fake"

    def test_unknown_format_raises(self):
        with pytest.raises(UnknownFormatError) as exc_info:
            resolve_format(path="data.xyz")
        assert exc_info.value.path == "data.xyz"

    def test_unknown_explicit_format_raises(self):
        with pytest.raises(UnknownFormatError):
            resolve_format(format="nonexistent")

    def test_no_path_no_format_raises(self):
        with pytest.raises(UnknownFormatError):
            resolve_format()


class TestTransformSuffixes:
    def test_gz_is_transform(self):
        assert ".gz" in TRANSFORM_SUFFIXES

    def test_gpg_is_transform(self):
        assert ".gpg" in TRANSFORM_SUFFIXES

    def test_csv_is_not_transform(self):
        assert ".csv" not in TRANSFORM_SUFFIXES
