"""FormatParser/FormatSerialiser protocol conformance (Draft §3.1, amended §3.2 of rev-3 spec)."""

from mountainash_files.formats._exceptions import FormatError, FormatResolutionError
from mountainash_files.formats._protocols import FormatParser, FormatSerialiser
from mountainash_files.formats.csv import CsvSpec, csv_parse
from mountainash_files.formats.json import JsonSpec, json_parse, json_serialise


def test_builtin_parsers_satisfy_protocol():
    # Runtime Protocol check; detailed behavior is exercised below.
    assert isinstance(csv_parse, FormatParser)
    assert isinstance(json_parse, FormatParser)


def test_builtin_serialisers_satisfy_protocol():
    assert isinstance(json_serialise, FormatSerialiser)


def test_json_serialiser_returns_bytes():
    result = json_serialise({"a": 1}, JsonSpec())
    assert isinstance(result, bytes)
    assert b'"a": 1' in result


def test_parser_accepts_binaryio():
    import io

    result = csv_parse(io.BytesIO(b"a,b\n1,2\n"), CsvSpec())
    assert result.num_rows == 1


def test_format_resolution_error_context():
    exc = FormatResolutionError(
        format_key="aemo-mms",
        ref="pkg.mod:attr",
        field="parser",
    )
    assert isinstance(exc, FormatError)
    assert exc.format_key == "aemo-mms"
    assert exc.ref == "pkg.mod:attr"
    assert exc.field == "parser"
    assert (
        "aemo-mms" in str(exc)
        and "pkg.mod:attr" in str(exc)
        and "parser" in str(exc)
    )
