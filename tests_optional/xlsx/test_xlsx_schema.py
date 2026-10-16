"""XLSX schema discovery on the fastexcel parse engine (requires the xlsx extra)."""
from __future__ import annotations

import io

import openpyxl
import pyarrow as pa
import pytest

from mountainash_files import FileSourceSpec, ParseError, inspect_schema, inspect_schema_bytes, parse_bytes
from mountainash_files.formats.xlsx import XlsxSpec


def _book(rows, title="facts") -> bytes:
    wb = openpyxl.Workbook()
    wb.active.append(["other"])
    ws = wb.create_sheet(title)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


FACTS = [("# skip", None), ("n", "flag"), (1, True), (2, False), ("late", True)]


def test_selected_sheet_bounded_and_full(tmp_path):
    raw = _book(FACTS)
    spec = XlsxSpec(sheet_name="facts", comment_char="#")
    first = inspect_schema_bytes(raw, spec, infer_schema_rows=1)
    path = tmp_path / "f.xlsx"
    path.write_bytes(raw)
    (full,) = inspect_schema(FileSourceSpec(path=str(path), format=spec))
    assert first.schema == pa.schema([("n", pa.int64()), ("flag", pa.bool_())]) and first.basis == "bounded"
    assert full.schema == parse_bytes(raw, spec).data.schema and full.basis == "full"
    assert full.schema.field("n").type == pa.string()


def test_budget_covering_every_row_is_full():
    raw = _book([("n",), (1,), (2,)])
    assert inspect_schema_bytes(raw, XlsxSpec(sheet_name="facts"), infer_schema_rows=2).basis == "full"


def test_multi_row_header_and_comment_rows_are_not_charged():
    raw = _book([("id", "amount"), ("unit", "usd"), ("junk", "row"), (1, 2.5), ("late", 1)])
    spec = XlsxSpec(sheet_name="facts", header_rows=(1, 2), comment_rows=(3,))
    result = inspect_schema_bytes(raw, spec, infer_schema_rows=1)
    assert result.schema == pa.schema([("id unit", pa.int64()), ("amount usd", pa.float64())])


def test_spec_sampling_makes_full_budget_bounded():
    raw = _book([("n",), (1,), (2,)])
    assert inspect_schema_bytes(raw, XlsxSpec(sheet_name="facts", infer_sample_rows=5)).basis == "bounded"


@pytest.mark.parametrize("rows,kw", [
    ([("# a",), ("# b",)], {"comment_char": "#"}),
    ([(None, "a"), (None, 1)], {}),
    ([(1, 2.5), (2, 3.5)], {"header": False}),
    ([("d",), ("2020-01-01",)], {"temporal": "text"}),
])
def test_full_schema_equals_parse(rows, kw):
    raw = _book(rows)
    spec = XlsxSpec(sheet_name="facts", **kw)
    result = inspect_schema_bytes(raw, spec)
    assert result.schema == parse_bytes(raw, spec).data.schema and result.basis == "full"


@pytest.mark.parametrize("spec", [XlsxSpec(sheet_number=0), XlsxSpec(sheet_number=9), XlsxSpec(sheet_name="nope")])
def test_sheet_selection_errors_are_parse_errors(spec):
    with pytest.raises(ParseError):
        inspect_schema_bytes(_book(FACTS), spec, infer_schema_rows=1)
