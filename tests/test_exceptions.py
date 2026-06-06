from mountainash_files.formats._exceptions import (
    FormatError,
    UnknownFormatError,
    ParseError,
    FormatConflictError,
)


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
