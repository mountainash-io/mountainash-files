"""Schema discovery through the public byte operation: Parquet, budgets, errors and plugins."""
from __future__ import annotations

import io

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from mountainash_files import (
    FormatResolutionError,
    SchemaDiscoveryUnsupportedError,
    SchemaResult,
    inspect_schema_bytes,
    parse_bytes,
)
from mountainash_files.formats._registry import _reset_registry, register_format
from mountainash_files.formats.parquet import ParquetSpec

import _schema_plugin
from _schema_plugin import TypedSpec, typed_inspect, typed_parse


@pytest.fixture(autouse=True)
def fresh_registry():
    _reset_registry()
    _schema_plugin.SEEN.clear()
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


def test_plugin_receives_the_borrowed_stream():
    register_format(TypedSpec, typed_parse, schema_inspector=typed_inspect)
    stream = io.BytesIO(b"int32:3")
    inspect_schema_bytes(stream, "typed")
    assert _schema_plugin.SEEN == [stream]


def test_schema_access_is_validated():
    with pytest.raises(ValueError):
        register_format(TypedSpec, typed_parse, schema_inspector=typed_inspect, schema_access="bogus")
    with pytest.raises(ValueError):
        register_format(TypedSpec, typed_parse, schema_inspector=typed_inspect, schema_access=3)
