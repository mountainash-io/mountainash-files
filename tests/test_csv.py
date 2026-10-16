from __future__ import annotations

import io

import pyarrow as pa
import pytest

from mountainash_files import FileSourceSpec, parse, parse_bytes
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats.csv import CsvSpec, csv_parse, csv_serialise
from mountainash_files.formats.tsv import TsvSpec


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
    data = b'# comment\nname,note\na,"line one\n# still data"\n'
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


@pytest.mark.parametrize(
    ("wire", "spec", "expected"),
    [
        (b"x\na\\,b\n", CsvSpec(quote_char=None, escape_char="\\"), "a,b"),
        (b'x\n"trailing\\\\"\n', CsvSpec(escape_char="\\"), "trailing\\"),
        (b'x\n"a\\"b"\n', CsvSpec(double_quote=False, escape_char="\\"), 'a"b'),
        (
            b"x@@a\\|\\|b@@",
            CsvSpec(
                delimiter="||", line_terminator="@@", quote_char=None, escape_char="\\"
            ),
            "a||b",
        ),
        (b'x\n" leading"\n', CsvSpec(skip_initial_space=True), " leading"),
        (b"x\na\\\nb\n", CsvSpec(escape_char="\\"), "a\nb"),
        (
            b"x\n\\ leading\n",
            CsvSpec(escape_char="\\", skip_initial_space=True),
            " leading",
        ),
    ],
)
def test_delimited_escape_contract(wire: bytes, spec: CsvSpec, expected: str) -> None:
    assert csv_parse(wire, spec).to_pylist() == [{"x": expected}]


@pytest.mark.parametrize(
    "spec",
    [
        CsvSpec(delimiter=""),
        CsvSpec(line_terminator=""),
        CsvSpec(delimiter="@@", line_terminator="@@"),
        CsvSpec(delimiter="|", line_terminator="||"),
        CsvSpec(delimiter="||", line_terminator="|"),
        CsvSpec(quote_char="xx"),
        CsvSpec(escape_char="xx"),
        CsvSpec(quote_char='"', escape_char='"'),
        CsvSpec(delimiter='"|'),
        CsvSpec(line_terminator="\\n", escape_char="\\"),
        CsvSpec(escape_char=""),
    ],
)
def test_ambiguous_dialect_is_rejected(spec: CsvSpec) -> None:
    with pytest.raises(ParseError):
        csv_parse(b"x\ny\n", spec)


def test_dangling_escape_is_rejected() -> None:
    with pytest.raises(ParseError):
        csv_parse(b"x\ntrailing\\", CsvSpec(escape_char="\\"))


def test_stream_input() -> None:
    table = csv_parse(io.BytesIO(b"x\n1\n"), CsvSpec())
    assert isinstance(table, pa.Table)


# --- Reader engine contract (pyarrow CSV) ---
MIXED = (b"id,amount,flag,day,ts,maybe,name\n"
         b'1,1.5,true,2020-01-01,2020-01-01T10:00:00,,"a, b"\n'
         b'2,2,false,2021-02-03,2021-02-03T11:00:00,7,""\n')


def test_inferred_types_and_nulls_through_public_entrypoints(tmp_path):
    path = tmp_path / "m.csv"
    path.write_bytes(MIXED)
    for t in (parse_bytes(MIXED, CsvSpec()).data, parse(FileSourceSpec(path=str(path)))[0].data):
        assert {f.name: str(f.type) for f in t.schema} == {
            "id": "int64", "amount": "double", "flag": "bool", "day": "date32[day]",
            "ts": "timestamp[s]", "maybe": "int64", "name": "string"}
        assert t.column("maybe").to_pylist() == [None, 7]
        assert t.column("name").to_pylist() == ["a, b", ""]


def test_temporal_text_keeps_original_text():
    t = csv_parse(MIXED, CsvSpec(temporal="text"))
    assert t.column("day").to_pylist() == ["2020-01-01", "2021-02-03"]
    assert t.column("ts").to_pylist() == ["2020-01-01T10:00:00", "2021-02-03T11:00:00"]


@pytest.mark.parametrize("spec", [CsvSpec(null_sequence="NULL"), CsvSpec(null_sequence="NULL", comment_char="#")])
def test_custom_null_sequence_round_trips(spec):
    table = pa.table({"a": [None, "x", ""]})
    assert csv_parse(csv_serialise(table, spec), spec).to_pylist() == table.to_pylist()


def test_single_column_null_row_survives_prefilter():
    data = b"#c\na\nNULL\nx\n"
    assert csv_parse(data, CsvSpec(null_sequence="NULL", comment_char="#")).to_pylist() == [{"a": None}, {"a": "x"}]


def test_comment_prefilter_preserves_null_vs_empty():
    assert csv_parse(b'#c\na,b\n,""\n', CsvSpec(comment_char="#")).to_pylist() == [{"a": None, "b": ""}]


def test_blank_and_duplicate_header_labels():
    assert csv_parse(b",b\n1,2\n", CsvSpec()).column_names == ["field1", "b"]
    with pytest.raises(ParseError):
        csv_parse(b"a,a\n1,2\n", CsvSpec())


def test_multiline_header_label_and_leading_blank_line():
    t = csv_parse(b'\n"a\nx",b\n1,2\n', CsvSpec())
    assert t.column_names == ["a\nx", "b"] and t.to_pylist() == [{"a\nx": 1, "b": 2}]


def test_header_rows_empty_tuple_means_first_row():
    assert csv_parse(b"a,b\n1,2\n", CsvSpec(header_rows=())).to_pylist() == [{"a": 1, "b": 2}]


def test_headerless_columns_and_dtypes_use_public_names():
    t = csv_parse(b"1,x\n2,y\n", CsvSpec(header=False, columns=("field2",), dtypes=(("field2", "string"),)))
    assert t.to_pylist() == [{"field2": "x"}, {"field2": "y"}]


def test_empty_columns_selection_keeps_validation():
    assert csv_parse(b"a,b\n1,2\n", CsvSpec(columns=())).shape == (1, 0)
    with pytest.raises(ParseError):
        csv_parse(b"a,b\n1,2,3\n", CsvSpec(columns=()))


def test_row_wider_than_header_raises():
    with pytest.raises(ParseError) as caught:
        csv_parse(b"a,b\n1,2,3\n", CsvSpec())
    assert caught.value.format_key == "csv"


def test_non_ascii_delimiter_uses_lexer_path():
    assert csv_parse("a§b\n1§2\n".encode(), CsvSpec(delimiter="§")).to_pylist() == [{"a": 1, "b": 2}]


def test_bare_carriage_return_inside_field_is_data():
    assert csv_parse(b"a,b\n1,hello\rworld\n", CsvSpec()).column("b").to_pylist() == ["hello\rworld"]


def test_windows_line_endings():
    assert csv_parse(b"a,b\r\n1,2\r\n", CsvSpec(line_terminator="\r\n")).to_pylist() == [{"a": 1, "b": 2}]


def test_escaped_final_newline_is_data():
    assert csv_parse(b"x\na\\\n", CsvSpec(escape_char="\\")).to_pylist() == [{"x": "a\n"}]


@pytest.mark.parametrize("data", [b'a\n"unterminated', b'a\n"unterminated\n'])
def test_unterminated_quote_raises(data):
    with pytest.raises(ParseError):
        csv_parse(data, CsvSpec())


def test_stray_quote_inside_unquoted_field_is_literal():
    # Documented change (RFC 4180): previously the lexer stripped these quotes.
    assert csv_parse(b'a\npre"quoted"suffix\n', CsvSpec()).column("a").to_pylist() == ['pre"quoted"suffix']


def test_tsv_format_key_in_errors():
    with pytest.raises(ParseError) as caught:
        parse_bytes(b"", TsvSpec())
    assert caught.value.format_key == "tsv"


def test_invalid_temporal_value():
    with pytest.raises(ValueError):
        CsvSpec(temporal="dates")


@pytest.mark.parametrize("data", [b"a,b\n", b"a,b", b"#c\na,b\n"])
def test_header_only_input_gives_zero_rows_with_labels(data):
    t = csv_parse(data, CsvSpec(comment_char="#"))
    assert t.column_names == ["a", "b"] and t.num_rows == 0


def test_header_only_input_honours_columns_and_dtypes():
    t = csv_parse(b"a,b\n", CsvSpec(columns=("b",), dtypes=(("b", "int64"),)))
    assert t.column_names == ["b"] and t.num_rows == 0 and t.schema.field("b").type == pa.int64()


@pytest.mark.parametrize("spec", [CsvSpec(header=False), CsvSpec()])
def test_blank_only_input_gives_empty_table(spec):
    t = csv_parse(b"\n\n", spec)
    assert t.num_rows == 0 and t.num_columns == 0
