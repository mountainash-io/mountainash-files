from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pytest

from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats.xlsx import XlsxSpec, xlsx_parse

FIXTURES = Path(__file__).parent / "fixtures"


def test_xlsx_defaults_follow_table_dialect() -> None:
    spec = XlsxSpec()
    assert spec.sheet_name is None
    assert spec.sheet_number is None
    assert spec.header_rows == (1,)
    assert spec.header is True


def test_xlsx_header_controls_and_sheet_name() -> None:
    data = (FIXTURES / "sample.xlsx").read_bytes()
    table = xlsx_parse(data, XlsxSpec(sheet_number=1, header=True, header_rows=(1,)))
    assert isinstance(table, pa.Table)
    assert table.num_rows == 3


def test_xlsx_rejects_conflicting_sheet_selectors() -> None:
    data = (FIXTURES / "sample.xlsx").read_bytes()
    with pytest.raises(ParseError):
        xlsx_parse(data, XlsxSpec(sheet_name="Sheet1", sheet_number=1))


def test_xlsx_empty_sheet_name_is_parse_error() -> None:
    data = (FIXTURES / "sample.xlsx").read_bytes()
    with pytest.raises(ParseError):
        xlsx_parse(data, XlsxSpec(sheet_name=""))
