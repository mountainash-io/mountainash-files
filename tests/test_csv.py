from __future__ import annotations

import io

import pyarrow as pa
import pytest

from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats.csv import CsvSpec, csv_parse


def test_csv_defaults_follow_table_dialect() -> None:
    spec = CsvSpec()
    assert spec.header is True
    assert spec.header_rows == (1,)
    assert spec.quote_char == '"'
    assert spec.null_sequence is None


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [(False, " leading"), (True, "leading")],
)
def test_skip_initial_space_is_discriminating(enabled: bool, expected: str) -> None:
    table = csv_parse(b"left,right\na, leading\n", CsvSpec(skip_initial_space=enabled))
    assert table.to_pylist() == [{"left": "a", "right": expected}]


def test_quote_aware_records_keep_embedded_newlines_and_comments() -> None:
    data = b"# comment\nname,note\na,\"line one\n# still data\"\n"
    table = csv_parse(data, CsvSpec(comment_char="#"))
    assert table.to_pylist() == [{"name": "a", "note": "line one\n# still data"}]


def test_multicharacter_delimiter_and_terminator() -> None:
    table = csv_parse(b"x||y@@1||2@@", CsvSpec(delimiter="||", line_terminator="@@"))
    assert table.to_pylist() == [{"x": 1, "y": 2}]


def test_header_rows_join_and_normalize_positions() -> None:
    data = b"left,right\nvalue,amount\na,1\n"
    table = csv_parse(data, CsvSpec(header_rows=(2, 1, 2), header_join="."))
    assert table.column_names == ["left.value", "right.amount"]
    assert table.to_pylist() == [{"left.value": "a", "right.amount": 1}]


def test_no_header_generates_field_names() -> None:
    table = csv_parse(b"1,2\n", CsvSpec(header=False))
    assert table.column_names == ["field1", "field2"]


def test_null_sequence_and_escape_mode() -> None:
    table = csv_parse(
        b'a,b\nNA,"he said \\"hi\\""\n',
        CsvSpec(escape_char="\\", double_quote=False, null_sequence="NA"),
    )
    assert table.to_pylist() == [{"a": None, "b": 'he said "hi"'}]


def test_empty_delimiter_is_rejected() -> None:
    with pytest.raises(ParseError):
        csv_parse(b"a\n", CsvSpec(delimiter=""))


def test_stream_input() -> None:
    table = csv_parse(io.BytesIO(b"x\n1\n"), CsvSpec())
    assert isinstance(table, pa.Table)
