import io

import openpyxl
import pyarrow as pa
import pytest

from mountainash_files import FileSourceSpec, parse
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats.xlsx import XlsxSpec, xlsx_parse


def book(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


LAYOUTS = {
    "plain": ([["a", "b"], [1, 1.5], [2, 2.5]], {}),
    "no header": ([[1, 1.5], [2, 2.5]], {"header": False}),
    "comments lead+mid, two header rows": ([["# note"], ["a", "b"], ["x", "y"], [1, 1.5], ["# mid"], [2, 2.5]],
                                           {"comment_char": "#", "header_rows": (1, 2)}),
    "comment_rows": ([["junk"], ["a", "b"], [1, 1.5], [2, 2.5]], {"comment_rows": (1,)}),
    "non-contiguous header": ([["a", "b"], [1, 1.5], ["x", "y"], [2, 2.5]], {"header_rows": (1, 3), "header_join": "."}),
    "header only": ([["a", "b"]], {}),
}


@pytest.mark.parametrize("name", LAYOUTS)
def test_layouts_match_openpyxl_engine(name, tmp_path):
    rows, kw = LAYOUTS[name]
    raw = book(rows)
    path = tmp_path / "b.xlsx"
    path.write_bytes(raw)
    old = xlsx_parse(raw, XlsxSpec(engine="openpyxl", **kw))
    for new in (xlsx_parse(raw, XlsxSpec(**kw)), parse(FileSourceSpec(path=str(path), format=XlsxSpec(**kw)))[0].data):
        assert new.column_names == old.column_names
        assert new.to_pylist() == old.to_pylist()


def test_blank_and_duplicate_header_labels():
    assert xlsx_parse(book([[None, "b"], [1, 2]]), XlsxSpec()).column_names == ["field1", "b"]
    with pytest.raises(ParseError):
        xlsx_parse(book([["a", "a"], [1, 2]]), XlsxSpec())
    with pytest.raises(ParseError):
        xlsx_parse(book([["a", "a"]]), XlsxSpec())


@pytest.mark.parametrize("positions", [(0,), (-1,), (5,)])
def test_header_positions_outside_sheet_raise(positions):
    with pytest.raises(ParseError):
        xlsx_parse(book([["a"], [1]]), XlsxSpec(header_rows=positions))


def test_run_merge_with_fractional_and_large_values():
    raw = book([["a"], [1], ["# c"], ["text"], ["# c"], [2.5], ["# c"], [1e20]])
    t = xlsx_parse(raw, XlsxSpec(comment_char="#"))
    assert t.schema.field("a").type == pa.string()
    assert t.column("a").to_pylist() == ["1", "text", "2.5", "1e+20"]


def test_whole_numbers_become_int64_and_iso_dates_infer():
    t = xlsx_parse(book([["i", "d"], [1, "2020-01-01"], [2, "2021-02-03"]]), XlsxSpec())
    assert t.schema.field("i").type == pa.int64() and t.schema.field("d").type == pa.date32()
    assert xlsx_parse(book([["d"], ["2020-01-01"]]), XlsxSpec(temporal="text")).schema.field("d").type == pa.string()


def test_empty_sheet_and_engine_fastexcel():
    assert xlsx_parse(book([]), XlsxSpec()).num_rows == 0
    assert xlsx_parse(book([]), XlsxSpec(comment_char="#")).num_rows == 0
    assert xlsx_parse(book([["a"], [1]]), XlsxSpec(engine="fastexcel")).to_pylist() == [{"a": 1}]


def test_errors_are_parse_errors():
    with pytest.raises(ParseError):
        xlsx_parse(b"not a workbook", XlsxSpec())
    with pytest.raises(ParseError):
        xlsx_parse(book([["a"], [1]]), XlsxSpec(sheet_name=""))
    with pytest.raises(ParseError):
        xlsx_parse(book([["a"], [1]]), XlsxSpec(sheet_number=9))


def test_whole_sheet_inference_and_validated_sampling():
    raw = book([["a"], *[[i] for i in range(50)], [0.5]])
    assert xlsx_parse(raw, XlsxSpec()).column("a").to_pylist()[-1] == 0.5
    for bad in (0, -1, 1.5, True):
        with pytest.raises(ValueError):
            XlsxSpec(infer_sample_rows=bad)
    with pytest.raises(ValueError):
        XlsxSpec(temporal="dates")


@pytest.mark.parametrize("rows,kw,expected", [
    ([[None], [-4]], {"header": False}, [{"field1": None}, {"field1": -4}]),
    ([[None], [-4]], {}, [{"field1": -4}]),
    ([[None, None], [1, 2]], {"header": False}, [{"field1": None, "field2": None}, {"field1": 1, "field2": 2}]),
])
def test_leading_blank_rows_do_not_lose_data(rows, kw, expected):
    raw = book(rows)
    assert xlsx_parse(raw, XlsxSpec(**kw)).to_pylist() == expected == xlsx_parse(raw, XlsxSpec(engine="openpyxl", **kw)).to_pylist()


def test_leading_blank_rows_count_as_rows_for_header_and_comment_positions():
    rows = [[None], ["# c"], ["a"], ["b"]]
    for kw in ({"comment_char": "#"}, {"comment_rows": (2,)}, {"header_rows": (3,)}):
        raw = book(rows)
        assert xlsx_parse(raw, XlsxSpec(**kw)).to_pylist() == xlsx_parse(raw, XlsxSpec(engine="openpyxl", **kw)).to_pylist()


@pytest.mark.parametrize("rows", [[["", " "]], [[None, None]], [[""]]])
def test_sheet_of_only_empty_cells_is_an_empty_table_not_an_error(rows):
    t = xlsx_parse(book(rows), XlsxSpec())
    assert t.num_rows == 0


@pytest.mark.parametrize("rows,kw,names,records", [
    ([[None, "a"], [None, 1]], {}, ["field1", "a"], [{"field1": None, "a": 1}]),
    ([["", "a", "b"], ["", 1, 2]], {}, ["field1", "a", "b"], [{"field1": None, "a": 1, "b": 2}]),
    ([[None, None, "a"], [None, None, 1]], {}, ["field1", "field2", "a"], [{"field1": None, "field2": None, "a": 1}]),
    ([[None, "a", "b"], [None, "# c", None], [None, 2, 3]], {"comment_char": "#"}, ["field1", "a", "b"],
     [{"field1": None, "a": 2, "b": 3}]),
])
def test_empty_leading_columns_keep_the_sheet_shape(rows, kw, names, records):
    got = xlsx_parse(book(rows), XlsxSpec(**kw))
    assert got.column_names == names and got.to_pylist() == records


@pytest.mark.parametrize("rows,kw", [
    ([["# c"]], {"comment_char": "#"}),
    ([["# c"], ["# d"]], {"comment_char": "#"}),
    ([[1, 2]], {"comment_rows": (1,)}),
])
def test_sheet_with_only_comment_rows_is_an_empty_table(rows, kw):
    t = xlsx_parse(book(rows), XlsxSpec(**kw))
    assert t.num_rows == 0 and t.num_columns == 0
