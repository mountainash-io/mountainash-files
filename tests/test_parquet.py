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
