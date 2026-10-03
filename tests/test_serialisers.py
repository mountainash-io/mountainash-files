import dataclasses
import subprocess
import sys
import typing as t
from pathlib import Path

import pytest

from mountainash_files.formats._registry import (
    register_format,
    get_serialiser,
    _reset_registry,
)
from mountainash_files.formats._types import FormatSpec


@dataclasses.dataclass(frozen=True)
class _FakeSpec(FormatSpec):
    FORMAT: t.ClassVar[str] = "fake"
    SUFFIXES: t.ClassVar[tuple[str, ...]] = (".fake",)


def _fake_parse(data, spec):
    return {"parsed": True}


def _fake_serialise(data, spec):
    return b"serialised"


@pytest.fixture(autouse=True)
def _clean():
    _reset_registry()
    yield
    _reset_registry()


def test_tsv_initial_registration_and_reset(tmp_path: Path) -> None:
    code = r"""
import csv, io
import pyarrow as pa
from mountainash_files import FileSinkSpec, serialise_bytes, write
from mountainash_files.formats._registry import _reset_registry
from pathlib import Path
path = Path(__import__("sys").argv[1])
for reset in (False, True):
    if reset:
        _reset_registry()
    table = pa.table({"x": ["a\tb"]})
    wire = serialise_bytes(table, "tsv")
    assert list(csv.reader(io.StringIO(wire.decode()), delimiter="\t")) == [["x"], ["a\tb"]]
    write(FileSinkSpec(path=str(path)), table)
    assert list(csv.reader(io.StringIO(path.read_text()), delimiter="\t")) == [["x"], ["a\tb"]]
"""
    subprocess.run([sys.executable, "-c", code, str(tmp_path / "out.tsv")], check=True)


class TestSerialiserRegistry:
    def test_no_serialiser_returns_none(self):
        register_format(_FakeSpec, _fake_parse)
        assert get_serialiser("fake") is None

    def test_register_with_serialiser(self):
        register_format(_FakeSpec, _fake_parse, serialiser=_fake_serialise)
        assert get_serialiser("fake") is _fake_serialise

    def test_override_replaces_serialiser(self):
        register_format(_FakeSpec, _fake_parse, serialiser=_fake_serialise)

        def _other_serialise(data, spec):
            return b"other"

        register_format(
            _FakeSpec, _fake_parse, serialiser=_other_serialise, override=True
        )
        assert get_serialiser("fake") is _other_serialise

    def test_override_without_serialiser_clears(self):
        register_format(_FakeSpec, _fake_parse, serialiser=_fake_serialise)
        register_format(_FakeSpec, _fake_parse, override=True)
        assert get_serialiser("fake") is None
