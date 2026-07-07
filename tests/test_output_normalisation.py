"""output= seam (rev-3 spec §1.2/§1.3): every tabular format -> Arrow by default."""
import pyarrow as pa
import pytest

from mountainash_files import ParseError, parse_bytes

CSV = b"a,b\n1,x\n2,y\n"


def test_csv_arrow_default():
    result = parse_bytes(CSV, "csv")
    assert isinstance(result.data, pa.Table)
    assert result.data.num_rows == 2


def test_csv_pydata():
    result = parse_bytes(CSV, "csv", output="pydata")
    assert result.data == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]


def test_json_records_arrow_default():
    result = parse_bytes(b'[{"a": 1}, {"a": 2}]', "json")
    assert isinstance(result.data, pa.Table)
    assert result.data.column("a").to_pylist() == [1, 2]


def test_json_single_dict_is_one_row():
    result = parse_bytes(b'{"a": 1, "b": [1, 2]}', "json")
    assert isinstance(result.data, pa.Table)
    assert result.data.num_rows == 1


def test_json_pydata_passes_through():
    result = parse_bytes(b'[{"a": 1}]', "json", output="pydata")
    assert result.data == [{"a": 1}]


def test_empty_json_array_is_zero_by_zero_table():
    result = parse_bytes(b"[]", "json")
    assert isinstance(result.data, pa.Table)
    assert result.data.num_rows == 0
    assert result.data.num_columns == 0


def test_json_scalar_array_raises_under_arrow():
    with pytest.raises(ParseError, match="non-record"):
        parse_bytes(b"[1, 2, 3]", "json")


def test_json_scalar_array_passes_under_pydata():
    result = parse_bytes(b"[1, 2, 3]", "json", output="pydata")
    assert result.data == [1, 2, 3]


def test_mixed_record_keys_union_with_nulls():
    result = parse_bytes(b'[{"a": 1}, {"b": 2}]', "json")
    assert result.data.column("a").to_pylist() == [1, None]
    assert result.data.column("b").to_pylist() == [None, 2]


def test_xml_passes_through_under_both_flags():
    xml = b"<root><item>1</item></root>"
    arrow_result = parse_bytes(xml, "xml")
    pydata_result = parse_bytes(xml, "xml", output="pydata")
    for result in (arrow_result, pydata_result):
        assert not isinstance(result.data, pa.Table)
        assert result.data.tag == "root"


def test_invalid_output_value_raises():
    with pytest.raises(ValueError, match="output"):
        parse_bytes(CSV, "csv", output="pandas")


def test_parse_path_and_gzip_also_normalised(tmp_path):
    import gzip

    from mountainash_files import FileSourceSpec, parse
    from mountainash_files.specs.archive import GzipCompression

    path = tmp_path / "data.json.gz"
    path.write_bytes(gzip.compress(b'[{"a": 1}]'))
    results = parse(
        FileSourceSpec(path=str(path), format="json", archive=GzipCompression())
    )
    assert isinstance(results[0].data, pa.Table)
