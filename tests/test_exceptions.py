from mountainash_files.formats._exceptions import (
    FormatError,
    UnknownFormatError,
    ParseError,
    FormatConflictError,
)

import builtins

import pytest

from mountainash_files import MissingDependencyError, parse, FileSourceSpec
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_format_error_is_base():
    assert issubclass(UnknownFormatError, FormatError)
    assert issubclass(ParseError, FormatError)
    assert issubclass(FormatConflictError, FormatError)


def test_unknown_format_error_carries_metadata():
    err = UnknownFormatError(path="/data/file.xyz", known_suffixes=(".csv", ".json"))
    assert err.path == "/data/file.xyz"
    assert err.known_suffixes == (".csv", ".json")
    assert ".csv" in str(err)
    assert "file.xyz" in str(err)


def test_parse_error_carries_format_key():
    err = ParseError(format_key="csv", message="malformed row 5")
    assert err.format_key == "csv"
    assert "[csv]" in str(err)
    assert "malformed row 5" in str(err)


class TestMissingDependencyError:
    def test_message_names_the_extra(self):
        err = MissingDependencyError("XLSX parsing", "xlsx")
        assert "mountainash-files[xlsx]" in str(err)
        assert err.extra == "xlsx"

    def test_xlsx_without_engines_raises_missing_dependency(self, monkeypatch):
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name in ("fastexcel", "openpyxl"):
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        with pytest.raises(MissingDependencyError) as ei:
            parse(FileSourceSpec(path=str(FIXTURES / "sample.xlsx")))
        assert "mountainash-files[xlsx]" in str(ei.value)
