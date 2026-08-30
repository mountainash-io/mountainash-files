from __future__ import annotations

import pyarrow as pa
import pytest

from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats.json import JsonSpec, json_parse


def test_property_empty_string_selects_root() -> None:
    table = json_parse(b'[{"id": 1}]', JsonSpec(property=""))
    assert table.to_pylist() == [{"id": 1}]


def test_nested_property_selects_records() -> None:
    table = json_parse(b'{"data": {"rows": [{"id": 1}]}}', JsonSpec(property="data.rows"))
    assert table.to_pylist() == [{"id": 1}]


def test_object_item_keys_order_and_null_fill() -> None:
    table = json_parse(
        b'[{"b": 2}, {"a": 1}]',
        JsonSpec(item_type="object", item_keys=("a", "b")),
    )
    assert table.column_names == ["a", "b"]
    assert table.to_pylist() == [{"a": None, "b": 2}, {"a": 1, "b": None}]


def test_array_rows_use_header_or_field_names() -> None:
    table = json_parse(b'[["name", "age"], ["A", 1]]', JsonSpec(item_type="array", header=True))
    assert table.to_pylist() == [{"name": "A", "age": 1}]
    table = json_parse(b'[["A", 1]]', JsonSpec(item_type="array", header=False))
    assert table.column_names == ["field1", "field2"]


def test_mixed_shape_and_width_drift_fail() -> None:
    with pytest.raises(ParseError):
        json_parse(b'[{"a": 1}, [2]]', JsonSpec())
    with pytest.raises(ParseError):
        json_parse(b'[[1], [2, 3]]', JsonSpec(item_type="array"))


def test_ndjson_matches_json_records() -> None:
    json_table = json_parse(b'[{"id": 1}]', JsonSpec())
    ndjson_table = json_parse(b'{"id": 1}\n', JsonSpec(ndjson=True))
    assert isinstance(json_table, pa.Table)
    assert json_table.equals(ndjson_table)
