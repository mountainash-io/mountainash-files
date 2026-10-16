import pyarrow as pa
import pytest

from mountainash_files.formats._engines import infer_temporal, native_buffer, normalise_types


def test_native_buffer_is_an_arrow_owned_copy():
    data = b"abc"
    buf = native_buffer(data)
    assert isinstance(buf, pa.Buffer) and buf.to_pybytes() == data
    assert buf.address != pa.py_buffer(data).address


def test_normalise_types_recurses_and_keeps_values():
    t = pa.table({
        "s": pa.array(["a", None], pa.large_string()),
        "l": pa.array([[1], []], pa.large_list(pa.int64())),
        "st": pa.array([{"x": "a"}, None], pa.struct([("x", pa.large_string())])),
        "b": pa.array([b"x", None], pa.large_binary()),
    })
    out = normalise_types(t)
    assert out.schema.types == [pa.string(), pa.list_(pa.int64()), pa.struct([("x", pa.string())]), pa.binary()]
    assert out.to_pylist() == t.to_pylist()


@pytest.mark.parametrize(("values", "expected_type", "expected_values"), [
    (["2020-01-01", None, "2021-12-31"], pa.date32(), None),
    (["2020-01-01T10:00:00", "2020-01-02 11:00:00"], pa.timestamp("s"), None),
    (["2020-01-01T10:00:00", "2020-01-01T10:00:00.5"], pa.timestamp("ns"), None),
    (["2020-01-01", "not a date"], pa.string(), ["2020-01-01", "not a date"]),
    (["2020-02-30", "2020-01-01"], pa.string(), ["2020-02-30", "2020-01-01"]),
    (["20200101"], pa.string(), ["20200101"]),
])
def test_infer_temporal(values, expected_type, expected_values):
    out = infer_temporal(pa.table({"c": pa.array(values, pa.string())}))
    assert out.schema.field("c").type == expected_type
    if expected_values is not None:
        assert out.column("c").to_pylist() == expected_values
