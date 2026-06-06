from pathlib import Path

import pyarrow as pa
import pytest

from mountainash_files.formats.xlsx import XlsxSpec, xlsx_parse
from mountainash_files.formats._exceptions import ParseError

FIXTURES = Path(__file__).parent / "fixtures"


class TestXlsxSpec:
    def test_defaults(self):
        spec = XlsxSpec()
        assert spec.FORMAT == "xlsx"
        assert spec.sheet_name == 0
        assert spec.skip_rows == 0
        assert spec.header_row == 0
        assert spec.engine == "auto"

    def test_suffixes(self):
        assert ".xlsx" in XlsxSpec.SUFFIXES
        assert ".xlsb" in XlsxSpec.SUFFIXES


class TestXlsxParse:
    def test_from_fixture(self):
        path = FIXTURES / "sample.xlsx"
        if not path.exists():
            pytest.skip("XLSX fixture not created")
        data = path.read_bytes()
        table = xlsx_parse(data, XlsxSpec())
        assert isinstance(table, pa.Table)
        assert table.num_rows == 3

    def test_empty_raises(self):
        with pytest.raises((ParseError, ImportError)):
            xlsx_parse(b"", XlsxSpec())

    def test_engine_openpyxl(self):
        path = FIXTURES / "sample.xlsx"
        if not path.exists():
            pytest.skip("XLSX fixture not created")
        data = path.read_bytes()
        table = xlsx_parse(data, XlsxSpec(engine="openpyxl"))
        assert isinstance(table, pa.Table)
        assert table.num_rows == 3
