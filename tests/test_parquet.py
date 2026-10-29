from pathlib import Path

import pyarrow as pa
import pytest

from mountainash_files.formats.parquet import ParquetSpec, parquet_parse
from mountainash_files.formats._exceptions import ParseError

FIXTURES = Path(__file__).parent / "fixtures"


class TestParquetSpec:
    def test_defaults(self):
        spec = ParquetSpec()
        assert spec.FORMAT == "parquet"
        assert spec.columns is None

    def test_suffixes(self):
        assert ".parquet" in ParquetSpec.SUFFIXES
        assert ".pq" in ParquetSpec.SUFFIXES


class TestParquetParse:
    def test_from_fixture(self):
        data = (FIXTURES / "sample.parquet").read_bytes()
        table = parquet_parse(data, ParquetSpec())
        assert isinstance(table, pa.Table)
        assert table.num_rows == 3
        assert "name" in table.column_names

    def test_select_columns(self):
        data = (FIXTURES / "sample.parquet").read_bytes()
        table = parquet_parse(data, ParquetSpec(columns=("name", "age")))
        assert table.column_names == ["name", "age"]

    def test_empty_raises(self):
        with pytest.raises(ParseError, match="parquet"):
            parquet_parse(b"", ParquetSpec())


# --- Reader engine contract (ParquetFile, access routing) ---
import gzip
import io
import os
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from mountainash_transport import Gzip, ObjectChangedError, Pipeline

from mountainash_files import FileSourceSpec, parse, parse_bytes
from mountainash_files.formats._engines import native_buffer
from mountainash_files.formats._registry import get_access
from mountainash_files.formats.parquet import ParquetSpec
from _range_server import plain_gets, serve


def _pq(table: pa.Table) -> bytes:
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()


def _reference(data: bytes, columns=None) -> pa.Table:
    """Reference read on an Arrow-owned buffer (never Python-backed)."""
    return pq.read_table(pa.BufferReader(native_buffer(data)), columns=columns)


SCHEMA = pa.schema(
    [pa.field("id", pa.int64(), metadata={b"unit": b"m"}),
     pa.field("nested", pa.struct([pa.field("x", pa.int64(), metadata={b"k": b"v"}), pa.field("y", pa.string())])),
     pa.field("literal.dot", pa.int64())],
    metadata={b"owner": b"files"},
)
NESTED = pa.Table.from_pylist([{"id": 7, "nested": {"x": 1, "y": "a"}, "literal.dot": 3}], schema=SCHEMA)


def test_parquet_access_routes_by_projection():
    assert get_access("parquet", ParquetSpec(columns=("id",))) == "random"
    assert get_access("parquet", ParquetSpec()) == "bytes"


@pytest.mark.parametrize("columns", [
    ("nested.x", "id"), ("id", "id"), ("id", "nested"), ("literal.dot",), ("nested", "nested.x"),
])
def test_projection_matches_read_table_including_metadata(columns):
    data = _pq(NESTED)
    got = parse_bytes(data, ParquetSpec(columns=columns)).data
    ref = _reference(data, list(columns))
    assert got.column_names == ref.column_names
    assert got.to_pylist() == ref.to_pylist()
    assert got.schema.equals(ref.schema, check_metadata=True)


def test_full_read_rich_types_and_metadata(tmp_path):
    import datetime as dt
    import decimal
    t = pa.Table.from_arrays(
        [pa.array([decimal.Decimal("1.23")], pa.decimal128(10, 2)),
         pa.array([dt.datetime(2020, 1, 1)], pa.timestamp("ms", tz="Australia/Sydney")),
         pa.array([b"abcd"], pa.binary(4)),
         pa.array([[("k", 1)]], pa.map_(pa.string(), pa.int64())),
         pa.array(["x"]).dictionary_encode()],
        schema=pa.schema([pa.field("d", pa.decimal128(10, 2), metadata={b"unit": b"m"}),
                          pa.field("ts", pa.timestamp("ms", tz="Australia/Sydney")),
                          pa.field("f", pa.binary(4)), pa.field("m", pa.map_(pa.string(), pa.int64())),
                          pa.field("c", pa.dictionary(pa.int32(), pa.string()))],
                         metadata={b"owner": b"files"}))
    path = tmp_path / "rich.parquet"
    path.write_bytes(_pq(t))
    got = parse(FileSourceSpec(path=str(path)))[0].data
    expected = _reference(path.read_bytes())
    assert got.equals(expected) and got.schema.equals(expected.schema, check_metadata=True)


def _big() -> bytes:
    # Random hex padding resists dictionary/compression, so the 'id' column is ~14% of the file.
    n = 200_000
    return _pq(pa.table({"id": list(range(n)), "pad": [os.urandom(16).hex() for _ in range(n)]}))


def test_projected_http_read_transfers_part_of_the_object():
    data = _big()
    with serve({"big.parquet": data}) as (base, log):
        got = parse(FileSourceSpec(path=f"{base}/big.parquet", format=ParquetSpec(columns=("id",))))[0].data
    assert got.num_rows == 200_000
    assert sum(sent for *_, sent in log) < len(data) * 0.5
    assert plain_gets(log) == 0


def test_server_without_ranges_gives_equal_result():
    data = _big()
    with serve({"big.parquet": data}, ranges=False) as (base, _):
        got = parse(FileSourceSpec(path=f"{base}/big.parquet", format=ParquetSpec(columns=("id",))))[0].data
    assert got.equals(_reference(data, ["id"]))


@pytest.mark.parametrize("explicit", [False, True])
def test_transformed_parquet_uses_bytes_route(tmp_path, explicit):
    path = tmp_path / ("t.parquet" if explicit else "t.parquet.gz")
    path.write_bytes(gzip.compress(_pq(NESTED)))
    source = FileSourceSpec(path=str(path), format=ParquetSpec(columns=("id",)),
                            transforms=Pipeline(Gzip()) if explicit else None)
    assert parse(source)[0].data.to_pylist() == [{"id": 7}]


def test_transport_error_while_reading_propagates_unwrapped():
    data = _big()
    with serve({"big.parquet": data}, etag_changes=True) as (base, log):
        with pytest.raises(ObjectChangedError):
            parse(FileSourceSpec(path=f"{base}/big.parquet", format=ParquetSpec(columns=("id",))))
    assert plain_gets(log) == 0
