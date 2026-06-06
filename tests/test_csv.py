import io
from pathlib import Path

import pyarrow as pa
import pytest

from mountainash_files.formats.csv import CsvSpec, csv_parse
from mountainash_files.formats._exceptions import ParseError

FIXTURES = Path(__file__).parent / "fixtures"


class TestCsvSpec:
    def test_defaults(self):
        spec = CsvSpec()
        assert spec.FORMAT == "csv"
        assert spec.delimiter == ","
        assert spec.encoding == "utf-8"
        assert spec.skip_rows == 0
        assert spec.header_row == 0
        assert spec.columns is None
        assert spec.dtypes is None

    def test_suffixes(self):
        assert CsvSpec.SUFFIXES == (".csv",)


class TestCsvParse:
    def test_from_bytes(self):
        data = b"x,y\n1,2\n3,4\n"
        table = csv_parse(data, CsvSpec())
        assert isinstance(table, pa.Table)
        assert table.num_rows == 2
        assert table.column_names == ["x", "y"]

    def test_from_stream(self):
        data = io.BytesIO(b"x,y\n1,2\n3,4\n")
        table = csv_parse(data, CsvSpec())
        assert table.num_rows == 2

    def test_from_fixture(self):
        data = (FIXTURES / "sample.csv").read_bytes()
        table = csv_parse(data, CsvSpec())
        assert table.num_rows == 3
        assert "name" in table.column_names

    def test_custom_delimiter(self):
        data = b"x;y\n1;2\n3;4\n"
        table = csv_parse(data, CsvSpec(delimiter=";"))
        assert table.column_names == ["x", "y"]

    def test_no_header(self):
        data = b"1,2\n3,4\n"
        table = csv_parse(data, CsvSpec(header_row=None))
        assert table.num_rows == 2
        assert table.column_names[0].startswith("f")  # pyarrow auto-names

    def test_skip_rows(self):
        data = b"# comment\nx,y\n1,2\n"
        table = csv_parse(data, CsvSpec(skip_rows=1))
        assert table.num_rows == 1
        assert "x" in table.column_names

    def test_select_columns(self):
        data = b"x,y,z\n1,2,3\n"
        table = csv_parse(data, CsvSpec(columns=("x", "z")))
        assert table.column_names == ["x", "z"]

    def test_empty_file_raises(self):
        with pytest.raises(ParseError, match="csv"):
            csv_parse(b"", CsvSpec())
