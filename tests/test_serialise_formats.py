import csv
import io
import json
import re
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from mountainash_files import WriteError
from mountainash_files.formats.csv import CsvSpec, csv_parse, csv_serialise
from mountainash_files.formats.json import JsonSpec, json_serialise
from mountainash_files.formats.parquet import ParquetSpec, parquet_serialise
from mountainash_files.formats.xml import XmlSpec, xml_serialise


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"delimiter": ";", "line_terminator": "\r\n"},
        {"double_quote": False, "escape_char": "\\"},
        {"quote_char": None, "escape_char": "\\"},
    ],
)
def test_csv_serialization_preserves_lexical_fields(options: dict[str, Any]) -> None:
    spec = CsvSpec(**options)
    names = ["col,one", "quote", "line", "slash", "unicode", "empty"]
    values = ["a,b;c", 'a"b', "a\r\nb", "trailing\\", "café", ""]
    table = pa.Table.from_arrays([pa.array([value]) for value in values], names=names)
    wire = csv_serialise(table, spec)
    assert isinstance(wire, bytes)
    reader = csv.reader(
        io.StringIO(wire.decode(spec.encoding), newline=""),
        delimiter=spec.delimiter,
        quotechar=spec.quote_char,
        escapechar=spec.escape_char,
        doublequote=spec.double_quote,
        quoting=csv.QUOTE_MINIMAL if spec.quote_char else csv.QUOTE_NONE,
    )
    assert list(reader) == [names, values]


def test_extended_dialect_has_independent_wire_contract() -> None:
    spec = CsvSpec(delimiter="||", line_terminator="@@")
    table = pa.table({"x": ["a||b"], "y": ["c@@d"]})
    wire = csv_serialise(table, spec)
    # Adapt unquoted structural tokens; this fixture has no unit separator.
    adapted = re.sub(
        r'"(?:[^"]|"")*"|(\|\|)|(@@)',
        lambda m: "\x1f" if m.group(1) else "\n" if m.group(2) else m.group(0),
        wire.decode(),
    )
    assert list(csv.reader(io.StringIO(adapted), delimiter="\x1f")) == [
        ["x", "y"],
        ["a||b", "c@@d"],
    ]


@pytest.mark.parametrize("value", [" leading", "#not a comment", ""])
def test_protected_records_are_not_trimmed_or_skipped(value: str) -> None:
    spec = CsvSpec(skip_initial_space=True, comment_char="#")
    wire = csv_serialise(pa.table({"x": [value]}), spec)
    assert csv_parse(wire, spec).to_pylist() == [{"x": value}]


@pytest.mark.parametrize(
    "spec,value,expected_wire",
    [
        (
            CsvSpec(delimiter="||", line_terminator="@@", quote_char=None),
            "a|b",
            b"x@@a|b@@",
        ),
        (CsvSpec(quote_char=None, skip_initial_space=True), "a b", b"x\na b\n"),
        (CsvSpec(comment_char='"'), "abc", b"x\nabc\n"),
        (CsvSpec(quote_char=None, comment_char="abc\n"), "abc", b"x\nabc\n"),
        (
            CsvSpec(quote_char=None, escape_char="\\", comment_char="abc\n"),
            "abc",
            b"x\nabc\n",
        ),
        (
            CsvSpec(quote_char=None, line_terminator="@@", comment_char="abc@"),
            "abc",
            b"x@@abc@@",
        ),
        (
            CsvSpec(quote_char=None, escape_char="\\", comment_char="\\"),
            "a,b",
            b"x\na\\,b\n",
        ),
        (
            CsvSpec(quote_char=None, escape_char="\\", comment_char="#"),
            "#a,b",
            b"x\n\\#a\\,b\n",
        ),
    ],
)
def test_safe_unquoted_representations_remain_writable(
    spec: CsvSpec,
    value: str,
    expected_wire: bytes,
) -> None:
    wire = csv_serialise(pa.table({"x": [value]}), spec)
    assert wire == expected_wire
    assert csv_parse(wire, spec).to_pylist() == [{"x": value}]


@pytest.mark.parametrize("values", [["a||b", "c"], ["a|", "b"], ["a", "b@"]])
def test_unprotected_complete_or_boundary_tokens_are_rejected(
    values: list[str],
) -> None:
    spec = CsvSpec(delimiter="||", line_terminator="@@", quote_char=None)
    table = pa.table({"x": [values[0]], "y": [values[1]]})
    with pytest.raises(WriteError):
        csv_serialise(table, spec)


@pytest.mark.parametrize("options", [{}, {"quote_char": None, "escape_char": "\\"}])
def test_boundary_tokens_can_be_protected(options: dict[str, Any]) -> None:
    spec = CsvSpec(delimiter="||", line_terminator="@@", **options)
    wire = csv_serialise(pa.table({"x": ["a|"], "y": ["b@"]}), spec)
    assert csv_parse(wire, spec).to_pylist() == [{"x": "a|", "y": "b@"}]


def test_comment_quote_collision_uses_escape_when_needed() -> None:
    spec = CsvSpec(comment_char='"', escape_char="\\")
    wire = csv_serialise(pa.table({"x": ["a,b"]}), spec)
    assert csv_parse(wire, spec).to_pylist() == [{"x": "a,b"}]


def test_unprotectable_first_field_is_rejected() -> None:
    with pytest.raises(WriteError):
        csv_serialise(pa.table({"x": ["a,b"]}), CsvSpec(comment_char='"'))


@pytest.mark.parametrize(
    "spec,table",
    [
        (CsvSpec(null_sequence="NULL"), pa.table({"x": ["NULL"]})),
        (CsvSpec(null_sequence="NULL"), pa.table({"NULL": ["value"]})),
        (CsvSpec(quote_char=None), pa.table({"x": ["a,b"]})),
        (CsvSpec(double_quote=False), pa.table({"x": ['a"b']})),
        (CsvSpec(quote_char=None, header=False), pa.table({"x": [""]})),
        (CsvSpec(encoding="ascii"), pa.table({"x": ["café"]})),
        (CsvSpec(delimiter=""), pa.table({"x": ["value"]})),
        (CsvSpec(delimiter="", header=False), pa.table({})),
        (CsvSpec(), pa.table({})),
        (CsvSpec(header=False), pa.table({"x": ["value"]}).select([])),
        (CsvSpec(comment_char=""), pa.table({"x": ["abc"]})),
        (CsvSpec(comment_char="", header=False), pa.table({"x": ["abc"]})),
    ],
)
def test_unrepresentable_delimited_output_raises_write_error(
    spec: CsvSpec,
    table: pa.Table,
) -> None:
    with pytest.raises(WriteError) as caught:
        csv_serialise(table, spec)
    assert caught.value.__cause__ is not None


def test_null_marker_and_headerless_encoding() -> None:
    spec = CsvSpec(null_sequence="NULL", header=False, encoding="utf-16-le")
    wire = csv_serialise(pa.table({"x": [None, "café"]}), spec)
    assert list(csv.reader(io.StringIO(wire.decode("utf-16-le")))) == [
        ["NULL"],
        ["café"],
    ]


def test_csv_lexical_output_preserves_duplicate_column_positions() -> None:
    table = pa.Table.from_arrays(
        [pa.array(["left"]), pa.array(["right"])], names=["x", "x"]
    )
    wire = csv_serialise(table, CsvSpec())
    assert list(csv.reader(io.StringIO(wire.decode()))) == [
        ["x", "x"],
        ["left", "right"],
    ]


def test_empty_headerless_table_emits_no_records() -> None:
    assert csv_serialise(pa.table({}), CsvSpec(header=False)) == b""


class TestJsonSerialise:
    def test_dict(self):
        data = {"name": "Alice", "age": 30}
        result = json_serialise(data, JsonSpec())
        assert isinstance(result, bytes)
        parsed = json.loads(result)
        assert parsed == data

    def test_list(self):
        data = [{"a": 1}, {"a": 2}]
        result = json_serialise(data, JsonSpec())
        parsed = json.loads(result)
        assert parsed == data

    def test_ndjson(self):
        data = [{"a": 1}, {"a": 2}]
        result = json_serialise(data, JsonSpec(ndjson=True))
        lines = [json.loads(line) for line in result.splitlines() if line.strip()]
        assert lines == data

    def test_arrow_table_to_json(self):
        table = pa.table({"x": [1, 2]})
        result = json_serialise(table, JsonSpec())
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2


class TestParquetSerialise:
    def test_arrow_table(self):
        table = pa.table({"x": [1, 2], "y": [3, 4]})
        result = parquet_serialise(table, ParquetSpec())
        assert isinstance(result, bytes)
        restored = pq.read_table(io.BytesIO(result))
        assert restored.num_rows == 2

    def test_roundtrip(self):
        table = pa.table({"name": ["Alice"], "age": [30]})
        data = parquet_serialise(table, ParquetSpec())
        restored = pq.read_table(io.BytesIO(data))
        assert restored.column("name")[0].as_py() == "Alice"


class TestXmlSerialise:
    def test_lxml_element(self):
        try:
            from lxml import etree

            root = etree.Element("root")
            child = etree.SubElement(root, "item")
            child.text = "hello"
            result = xml_serialise(root, XmlSpec())
            assert isinstance(result, bytes)
            assert b"hello" in result
        except ImportError:
            pytest.skip("lxml not installed")

    def test_stdlib_element(self):
        import xml.etree.ElementTree as ET

        root = ET.Element("root")
        child = ET.SubElement(root, "item")
        child.text = "hello"
        result = xml_serialise(root, XmlSpec())
        assert isinstance(result, bytes)
        assert b"hello" in result
