"""Schema discovery through the public byte operation: Parquet, budgets, errors and plugins."""
from __future__ import annotations

import io

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from mountainash_files import (
    FormatResolutionError,
    ParseError,
    SchemaDiscoveryUnsupportedError,
    SchemaResult,
    inspect_schema_bytes,
    parse_bytes,
)
from mountainash_files.formats._registry import _reset_registry, register_format
from mountainash_files.formats.csv import CsvSpec
from mountainash_files.formats.json import JsonSpec
from mountainash_files.formats.parquet import ParquetSpec
from mountainash_files.formats.tsv import TsvSpec

from _schema_plugin import TypedSpec, typed_inspect, typed_parse


@pytest.fixture(autouse=True)
def fresh_registry():
    _reset_registry()
    yield
    _reset_registry()


def _parquet(schema: pa.Schema, rows: list[dict] | None = None) -> bytes:
    sink = io.BytesIO()
    table = pa.Table.from_pylist(rows, schema=schema) if rows else schema.empty_table()
    pq.write_table(table, sink)
    return sink.getvalue()


RICH_FIELDS: list[pa.Field] = [
    pa.field("amount", pa.decimal128(20, 4), metadata={b"unit": b"GBP"}),
    pa.field("at", pa.timestamp("ns", "UTC")),
    pa.field("nested", pa.struct([("x", pa.int64()), ("y", pa.string())])),
    pa.field("literal.dot", pa.int32()),
]
RICH = pa.schema(RICH_FIELDS).with_metadata({b"origin": b"fixture"})


@pytest.mark.parametrize("columns", [
    None,
    ("amount", "nested.x"),
    ("nested",),
    ("literal.dot", "amount", "amount"),
])
def test_parquet_schema_equals_parse_including_metadata(columns):
    raw = _parquet(RICH)
    spec = ParquetSpec(columns=columns)
    result = inspect_schema_bytes(raw, spec, infer_schema_rows=1)
    assert isinstance(result, SchemaResult)
    assert result.basis == "metadata" and result.format_key == "parquet" and result.spec == spec
    assert result.schema.equals(parse_bytes(raw, spec).data.schema, check_metadata=True)


def test_parquet_nested_projection_uses_the_leaf_name():
    result = inspect_schema_bytes(_parquet(RICH), ParquetSpec(columns=("amount", "nested.x")))
    assert result.schema.names == ["amount", "x"]


def test_parquet_reads_the_footer_not_data_pages():
    schema = pa.schema([("v", pa.int64())])
    raw = bytearray(_parquet(schema, [{"v": i} for i in range(1000)]))
    page = pq.ParquetFile(io.BytesIO(bytes(raw))).metadata.row_group(0).column(0).data_page_offset
    raw[page:page + 64] = b"\xff" * 64
    with pytest.raises(Exception):
        parse_bytes(bytes(raw), "parquet")
    assert inspect_schema_bytes(bytes(raw), "parquet").schema == schema


class Unreadable(io.BytesIO):
    def read(self, *args):
        raise AssertionError("payload read before validation")


@pytest.mark.parametrize("budget", [0, -1, True, 1.5, "1"])
def test_invalid_budget_fails_before_reading(budget):
    stream = Unreadable(b"x")
    with pytest.raises(ValueError):
        inspect_schema_bytes(stream, "parquet", infer_schema_rows=budget)
    assert not stream.closed


def test_xml_is_unsupported_before_reading():
    stream = Unreadable(b"<a/>")
    with pytest.raises(SchemaDiscoveryUnsupportedError) as caught:
        inspect_schema_bytes(stream, "xml")
    assert caught.value.format_key == "xml"
    assert not stream.closed


def test_borrowed_buffers_stay_open_on_success_and_failure():
    good = io.BytesIO(_parquet(pa.schema([("v", pa.int64())])))
    inspect_schema_bytes(good, "parquet")
    bad = io.BytesIO(b"not parquet at all")
    with pytest.raises(Exception):
        inspect_schema_bytes(bad, "parquet")
    assert not good.closed and not bad.closed


# --- Plugins -----------------------------------------------------------------------------------

def test_callable_inspector_is_dispatched():
    register_format(TypedSpec, typed_parse, schema_inspector=typed_inspect)
    result = inspect_schema_bytes(b"int16:7", "typed")
    assert result.schema == pa.schema([("v", pa.int16())]) and result.basis == "metadata"
    borrowed = io.BytesIO(b"int32:3")
    assert inspect_schema_bytes(borrowed, "typed").schema == pa.schema([("v", pa.int32())])
    assert not borrowed.closed


def test_lazy_inspector_does_not_import_parser_or_serialiser():
    register_format(
        TypedSpec, "missing.module:parse", serialiser="missing.module:dump",
        schema_inspector="_schema_plugin:typed_inspect",
    )
    assert inspect_schema_bytes(b"int8:1", TypedSpec()).schema == pa.schema([("v", pa.int8())])


def test_broken_lazy_inspector_reports_its_reference():
    register_format(TypedSpec, typed_parse, schema_inspector="missing.module:inspect")
    with pytest.raises(FormatResolutionError) as caught:
        inspect_schema_bytes(b"int8:1", "typed")
    assert caught.value.field == "schema_inspector" and caught.value.ref == "missing.module:inspect"


def test_override_without_inspector_removes_discovery_but_not_parsing():
    register_format(TypedSpec, typed_parse, schema_inspector=typed_inspect)
    register_format(TypedSpec, typed_parse, override=True)
    with pytest.raises(SchemaDiscoveryUnsupportedError):
        inspect_schema_bytes(b"int64:7", "typed")
    assert parse_bytes(b"int64:7", "typed").data.to_pylist() == [{"v": 7}]


def test_reset_restores_builtin_discovery():
    register_format(ParquetSpec, typed_parse, override=True)
    _reset_registry()
    raw = _parquet(pa.schema([("v", pa.int64())]))
    assert inspect_schema_bytes(raw, "parquet").basis == "metadata"


def test_schema_access_is_validated():
    with pytest.raises(ValueError):
        register_format(TypedSpec, typed_parse, schema_inspector=typed_inspect, schema_access="bogus")
    with pytest.raises(ValueError):
        register_format(TypedSpec, typed_parse, schema_inspector=typed_inspect, schema_access=3)


# --- CSV / TSV -----------------------------------------------------------------------------------

CSV_WIRE = b'# c\nvalue,note\n1,"two\nlines"\n2,next\nlate,tail\n'


def test_csv_bounded_is_an_observation_and_full_matches_parse():
    spec = CsvSpec(comment_char="#")
    bounded = inspect_schema_bytes(CSV_WIRE, spec, infer_schema_rows=1)
    full = inspect_schema_bytes(CSV_WIRE, spec)
    assert bounded.schema == pa.schema([("value", pa.int64()), ("note", pa.string())])
    assert bounded.basis == "bounded"
    assert full.schema == parse_bytes(CSV_WIRE, spec).data.schema and full.basis == "full"
    assert full.schema.field("value").type == pa.string()


def test_csv_multi_row_header_is_not_charged():
    wire = b"id,amount\nunit,usd\n1,2.5\n2,3.5\n"
    result = inspect_schema_bytes(wire, CsvSpec(header_rows=(1, 2)), infer_schema_rows=1)
    assert result.schema == pa.schema([("id unit", pa.int64()), ("amount usd", pa.float64())])
    assert result.basis == "bounded"


def test_csv_comment_rows_count_logical_records():
    # record 2 spans two physical lines; record 3 is the comment row
    wire = b'a,b\n1,"x\ny"\nskip,me\n2,z\nlate,w\n'
    result = inspect_schema_bytes(wire, CsvSpec(comment_rows=(3,)), infer_schema_rows=2)
    assert result.schema == pa.schema([("a", pa.int64()), ("b", pa.string())])
    assert result.basis == "bounded"


@pytest.mark.parametrize("wire,basis", [
    (b"a\n1\n2\n", "full"),
    (b"a\n1\n2", "full"),
    (b"a\n1\n2\n3\n", "bounded"),
])
def test_csv_exact_boundary(wire, basis):
    assert inspect_schema_bytes(wire, "csv", infer_schema_rows=2).basis == basis


class Trickle(io.RawIOBase):
    """Returns at most `size` bytes per read, so chunk ends land inside quotes and escapes."""

    def __init__(self, data: bytes, size: int):
        self._data, self._pos, self._size = data, 0, size

    def readable(self):
        return True

    def read(self, n=-1):
        chunk = self._data[self._pos:self._pos + self._size]
        self._pos += len(chunk)
        return chunk


@pytest.mark.parametrize("size", [1, 2, 3, 7, 64])
@pytest.mark.parametrize("spec,body", [
    (CsvSpec(), '{i},"a ""q"" b\nc"\n'),
    (CsvSpec(escape_char="\\", quote_char=None), '{i},a\\,b\n'),
])
def test_csv_bounded_prefix_survives_chunk_boundaries(size, spec, body):
    rows = "".join(body.format(i=i) for i in range(50))
    wire = ("id,text\n" + rows + "late,x\n").encode()
    result = inspect_schema_bytes(Trickle(wire, size), spec, infer_schema_rows=5)
    assert result.basis == "bounded" and result.schema.field("id").type == pa.int64()


def test_csv_malformed_input_still_fails_at_eof():
    with pytest.raises(ParseError):
        inspect_schema_bytes(Trickle(b'a\n"unterminated\n', 3), "csv", infer_schema_rows=5)


@pytest.mark.parametrize("wire,spec", [
    (b"a,b\n1,2020-01-01\n", CsvSpec(temporal="text")),
    (b"a,b\nNA,1\n2,\n", CsvSpec(null_sequence="NA")),
    (b"a,b\n1,2\n", CsvSpec(dtypes=(("a", "string"),))),
    (b"a,b,c\n1,2,3\n", CsvSpec(columns=("c", "a"))),
    ("a,b\n1,\u00e9\n".encode("latin-1"), CsvSpec(encoding="latin-1")),
    (b"a,b\n1,x\\,y\n", CsvSpec(escape_char="\\", quote_char=None)),
    (b"a,b\n", CsvSpec()),
    (b"\n\n", CsvSpec(header=False)),
    (b"a\tb\n1\t2.5\n", TsvSpec()),
])
def test_csv_full_schema_equals_parse(wire, spec):
    result = inspect_schema_bytes(wire, spec)
    assert result.schema == parse_bytes(wire, spec).data.schema and result.basis == "full"


def test_csv_empty_input_keeps_the_parse_error():
    with pytest.raises(ParseError) as caught:
        inspect_schema_bytes(b"", TsvSpec())
    assert caught.value.format_key == "tsv"


# --- JSON / NDJSON -------------------------------------------------------------------------------

DRIFT = b'[{"id":1,"nested":{"a":1}},{"id":2,"nested":{"a":2,"later":"x"},"extra":true}]'


def test_json_bounded_omits_late_fields_and_full_matches_parse():
    first = inspect_schema_bytes(DRIFT, "json", infer_schema_rows=1)
    full = inspect_schema_bytes(DRIFT, "json")
    assert first.schema.names == ["id", "nested"] and first.basis == "bounded"
    assert full.schema == parse_bytes(DRIFT, "json").data.schema and full.basis == "full"
    assert "extra" in full.schema.names


@pytest.mark.parametrize("spec", [
    JsonSpec(ndjson=True, item_type="array", header=True),
    JsonSpec(ndjson=True, header=True),
])
def test_ndjson_array_header_is_not_charged(spec):
    wire = b'["id","amount"]\n[1,2.5]\n[2,3.5]\n'
    result = inspect_schema_bytes(wire, spec, infer_schema_rows=1)
    assert result.schema == pa.schema([("id", pa.int64()), ("amount", pa.float64())])
    assert result.basis == "bounded"


def test_ndjson_blank_lines_are_not_records():
    wire = b'{"a":1}\n\n\n{"a":2}\n{"a":"late"}\n'
    result = inspect_schema_bytes(io.BytesIO(wire), JsonSpec(ndjson=True), infer_schema_rows=2)
    assert result.schema == pa.schema([("a", pa.int64())]) and result.basis == "bounded"


@pytest.mark.parametrize("wire,basis", [(b'{"a":1}\n{"a":2}', "full"), (b'{"a":1}\n{"a":2}\n{"a":3}\n', "bounded")])
def test_ndjson_exact_boundary(wire, basis):
    assert inspect_schema_bytes(wire, JsonSpec(ndjson=True), infer_schema_rows=2).basis == basis


def test_json_property_selection_and_budget():
    wire = b'{"meta":{"rows":[{"a":1},{"a":"late"}]}}'
    spec = JsonSpec(property="meta.rows")
    assert inspect_schema_bytes(wire, spec, infer_schema_rows=1).schema == pa.schema([("a", pa.int64())])
    assert inspect_schema_bytes(wire, spec).schema == parse_bytes(wire, spec).data.schema
    with pytest.raises(ParseError):
        inspect_schema_bytes(wire, JsonSpec(property="meta.missing"), infer_schema_rows=1)


def test_spec_sampling_makes_a_full_budget_bounded():
    assert inspect_schema_bytes(b'[{"a":1},{"a":2}]', JsonSpec(infer_sample_rows=5)).basis == "bounded"


def test_scalar_array_is_a_parse_error():
    with pytest.raises(ParseError) as caught:
        inspect_schema_bytes(b"[1,2,3]", "json")
    assert caught.value.format_key == "json"


@pytest.mark.parametrize("wire,spec", [
    (b'{"a":1,"b":"x"}', JsonSpec()),
    (b"[]", JsonSpec()),
    (b'[{"a":1},{"b":2}]', JsonSpec(item_keys=("b", "a"))),
    (b'[["x","y"],[1,2]]', JsonSpec(item_type="array")),
    (b'[{"d":"2020-01-01"}]', JsonSpec(temporal="text")),
])
def test_json_full_schema_equals_parse(wire, spec):
    result = inspect_schema_bytes(wire, spec)
    assert result.schema == parse_bytes(wire, spec).data.schema and result.basis == "full"


@pytest.mark.parametrize("size", [1, 3, 64])
def test_ndjson_prefix_from_small_chunks(size):
    wire = b"".join(b'{"a":%d,"s":"x\\ny"}\n' % i for i in range(20)) + b'{"a":"late"}\n'
    result = inspect_schema_bytes(Trickle(wire, size), JsonSpec(ndjson=True), infer_schema_rows=5)
    assert result.schema == pa.schema([("a", pa.int64()), ("s", pa.string())]) and result.basis == "bounded"


def test_utf16_ndjson_stream_matches_bytes():
    wire = '{"a":1}\n{"a":2}\n{"a":"late"}\n'.encode("utf-16-le")
    spec = JsonSpec(ndjson=True)
    from_stream = inspect_schema_bytes(Trickle(wire, 5), spec, infer_schema_rows=2)
    assert from_stream.schema == inspect_schema_bytes(wire, spec, infer_schema_rows=2).schema
    assert from_stream.schema == pa.schema([("a", pa.int64())])


def test_xlsx_discovery_without_the_extra_raises_missing_dependency(monkeypatch):
    import sys

    from mountainash_files import MissingDependencyError

    monkeypatch.setitem(sys.modules, "fastexcel", None)   # import fails as if the extra were absent
    with pytest.raises(MissingDependencyError):
        inspect_schema_bytes(b"PK\x03\x04 not inspected", "xlsx", infer_schema_rows=1)


class Chunks(io.RawIOBase):
    """Returns the given chunks one read at a time and counts reads."""

    def __init__(self, parts: list[bytes]):
        self.parts, self.reads = list(parts), 0

    def readable(self):
        return True

    def read(self, n=-1):
        self.reads += 1
        return self.parts.pop(0) if self.parts else b""


def test_csv_escaped_terminator_at_a_chunk_end_is_not_a_record_end():
    spec = CsvSpec(quote_char=None, escape_char="\\")
    wire = [b"a,b\n1\\\n", b",x\n2,y\n"]
    streamed = inspect_schema_bytes(Chunks(wire), spec, infer_schema_rows=1)
    assert streamed.schema == inspect_schema_bytes(b"".join(wire), spec, infer_schema_rows=1).schema


@pytest.mark.parametrize("separator", [b"\r", b"\r\n", b"\n"])
def test_ndjson_budget_counts_every_line_separator(separator):
    wire = separator.join([b"[1]", b"[2.5]", b""])
    result = inspect_schema_bytes(wire, JsonSpec(ndjson=True, header=False), infer_schema_rows=1)
    assert result.schema == pa.schema([("field1", pa.int64())]) and result.basis == "bounded"


def test_ndjson_crlf_split_across_chunks():
    result = inspect_schema_bytes(Chunks([b'{"a":1}\r', b'\n{"a":"x"}\n']), JsonSpec(ndjson=True), infer_schema_rows=1)
    assert result.schema == pa.schema([("a", pa.int64())])


def test_bom_ndjson_stream_reads_only_a_prefix():
    stream = Chunks([b'\xef\xbb\xbf{"a":1}\n'] + [b'{"a":"x"}\n'] * 100)
    result = inspect_schema_bytes(stream, JsonSpec(ndjson=True), infer_schema_rows=1)
    assert result.schema == pa.schema([("a", pa.int64())]) and stream.reads < 5
