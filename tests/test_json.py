from __future__ import annotations

import json

import pyarrow as pa
import pytest

from mountainash_files import FileSourceSpec, parse, parse_bytes
from mountainash_files.formats._exceptions import ParseError
from mountainash_files.formats.json import JsonSpec, json_parse


def test_property_empty_string_selects_root() -> None:
    table = json_parse(b'[{"id": 1}]', JsonSpec(property=""))
    assert isinstance(table, pa.Table)
    assert table.to_pylist() == [{"id": 1}]


def test_nested_property_selects_records() -> None:
    table = json_parse(
        b'{"data": {"rows": [{"id": 1}]}}', JsonSpec(property="data.rows")
    )
    assert isinstance(table, pa.Table)
    assert table.to_pylist() == [{"id": 1}]


def test_object_item_keys_order_and_null_fill() -> None:
    table = json_parse(
        b'[{"b": 2}, {"a": 1}]',
        JsonSpec(item_type="object", item_keys=("a", "b")),
    )
    assert isinstance(table, pa.Table)
    assert table.column_names == ["a", "b"]
    assert table.to_pylist() == [{"a": None, "b": 2}, {"a": 1, "b": None}]


def test_array_rows_use_header_or_field_names() -> None:
    table = json_parse(
        b'[["name", "age"], ["A", 1]]', JsonSpec(item_type="array", header=True)
    )
    assert isinstance(table, pa.Table)
    assert table.to_pylist() == [{"name": "A", "age": 1}]
    table = json_parse(b'[["A", 1]]', JsonSpec(item_type="array", header=False))
    assert isinstance(table, pa.Table)
    assert table.column_names == ["field1", "field2"]


def test_mixed_shape_and_width_drift_fail() -> None:
    with pytest.raises(ParseError):
        json_parse(b'[{"a": 1}, [2]]', JsonSpec())
    with pytest.raises(ParseError):
        json_parse(b"[[1], [2, 3]]", JsonSpec(item_type="array"))


@pytest.mark.parametrize(
    "payload,spec",
    [
        (b'[{"x":1},{"x":"bad"}]', JsonSpec()),
        (b'[["x"],[1],["bad"]]', JsonSpec(item_type="array")),
    ],
)
def test_mixed_column_types_widen_to_string(payload: bytes, spec: JsonSpec) -> None:
    assert json_parse(payload, spec).column("x").to_pylist() == ["1", "bad"]


def test_json_input_io_failure_is_not_reclassified() -> None:
    import io

    broken = OSError("input failed")

    class BrokenInput(io.BytesIO):
        def read(self, *args, **kwargs):
            raise broken

    with pytest.raises(OSError) as caught:
        json_parse(BrokenInput(b"[]"), JsonSpec())
    assert caught.value is broken


def test_ndjson_matches_json_records() -> None:
    json_table = json_parse(b'[{"id": 1}]', JsonSpec())
    ndjson_table = json_parse(b'{"id": 1}\n', JsonSpec(ndjson=True))
    assert isinstance(json_table, pa.Table)
    assert isinstance(ndjson_table, pa.Table)
    assert json_table.equals(ndjson_table)


# --- Reader engine contract (polars JSON/NDJSON) ---
BASE = [{"a": 1, "n": {"x": 1}} for _ in range(150)]
LATE = BASE + [{"a": 1.5, "b": "late", "n": {"x": 1, "y": 2}}]
LATE_JSON = json.dumps(LATE).encode()
LATE_NDJSON = "\n".join(json.dumps(r) for r in LATE).encode()


@pytest.mark.parametrize("raw,spec", [(LATE_JSON, JsonSpec()), (LATE_NDJSON, JsonSpec(ndjson=True))])
def test_full_inference_keeps_late_values_and_fields(raw, spec, tmp_path):
    path = tmp_path / ("d.ndjson" if spec.ndjson else "d.json")
    path.write_bytes(raw)
    for t in (parse_bytes(raw, spec).data, parse(FileSourceSpec(path=str(path), format=spec))[0].data):
        last = t.to_pylist()[-1]
        assert last["a"] == 1.5 and last["b"] == "late" and last["n"] == {"x": 1, "y": 2}


def test_sampled_inference_is_opt_in_and_documented_lossy():
    # Verified with polars 2.0.0: a sample silently drops late fields and raises on late type changes.
    late_field = "\n".join(json.dumps(r) for r in [{"a": 1}] * 150 + [{"a": 1, "b": "late"}]).encode()
    assert json_parse(late_field, JsonSpec(ndjson=True, infer_sample_rows=10)).column_names == ["a"]
    late_type = "\n".join(json.dumps(r) for r in [{"a": 1}] * 150 + [{"a": 1.5}]).encode()
    with pytest.raises(ParseError):
        json_parse(late_type, JsonSpec(ndjson=True, infer_sample_rows=10))


@pytest.mark.parametrize("bad", [0, -1, 1.5, True])
def test_sample_rows_is_validated(bad):
    with pytest.raises(ValueError):
        JsonSpec(infer_sample_rows=bad)


def test_invalid_temporal_value():
    with pytest.raises(ValueError):
        JsonSpec(temporal="dates")


def test_ndjson_item_keys_absent_key_is_null_column():
    assert json_parse(b'{"a":1}\n', JsonSpec(ndjson=True, item_keys=("a", "missing"))).to_pylist() == [
        {"a": 1, "missing": None}]


def test_utf16_json_parses_and_truncated_utf16_is_parse_error():
    assert json_parse('[{"a":1}]'.encode("utf-16"), JsonSpec()).to_pylist() == [{"a": 1}]
    with pytest.raises(ParseError):
        json_parse(b"\xff\xfe[", JsonSpec())


def test_iso_dates_inferred_and_text_mode():
    raw = b'[{"d":"2020-01-01"},{"d":"2021-02-03"}]'
    assert str(json_parse(raw, JsonSpec()).schema.field("d").type) == "date32[day]"
    assert json_parse(raw, JsonSpec(temporal="text")).column("d").to_pylist() == ["2020-01-01", "2021-02-03"]


def test_standard_arrow_types():
    t = json_parse(b'[{"s":"a","l":[1]}]', JsonSpec())
    assert str(t.schema.field("s").type) == "string" and str(t.schema.field("l").type).startswith("list<")


@pytest.mark.parametrize("raw", [b"{}", b"[{},{}]", b"[{}]"])
def test_rows_without_keys_give_an_empty_table(raw):
    t = json_parse(raw, JsonSpec())
    assert t.num_rows == 0 and t.num_columns == 0
