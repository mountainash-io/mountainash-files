import dataclasses
import io
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq
import pytest
from mountainash_transport import PathNotFoundError

from mountainash_files import AppendSchemaMismatchError, copy, write, parse, FileSourceSpec
from mountainash_files.specs.sink import FileSinkSpec
from mountainash_files._exceptions import WriteError
from mountainash_files.formats.csv import CsvSpec


class TestWriteLocal:
    def test_write_csv(self, tmp_path):
        table = pa.table({"name": ["Alice", "Bob"], "age": [30, 25]})
        sink = FileSinkSpec(path=str(tmp_path / "out.csv"))
        write(sink, table)
        assert (tmp_path / "out.csv").exists()
        restored = pcsv.read_csv(str(tmp_path / "out.csv"))
        assert restored.num_rows == 2

    def test_write_parquet(self, tmp_path):
        table = pa.table({"x": [1, 2, 3]})
        sink = FileSinkSpec(path=str(tmp_path / "out.parquet"))
        write(sink, table)
        restored = pq.read_table(str(tmp_path / "out.parquet"))
        assert restored.num_rows == 3

    def test_write_json_dict(self, tmp_path):
        data = {"key": "value"}
        sink = FileSinkSpec(path=str(tmp_path / "out.json"))
        write(sink, data)
        content = json.loads((tmp_path / "out.json").read_text())
        assert content == data

    def test_write_ndjson(self, tmp_path):
        data = [{"a": 1}, {"a": 2}]
        sink = FileSinkSpec(path=str(tmp_path / "out.ndjson"))
        write(sink, data)
        lines = [
            json.loads(l)
            for l in (tmp_path / "out.ndjson").read_text().splitlines()
            if l.strip()
        ]
        assert lines == data

    def test_write_xml(self, tmp_path):
        import xml.etree.ElementTree as ET

        root = ET.Element("root")
        ET.SubElement(root, "item").text = "test"
        sink = FileSinkSpec(path=str(tmp_path / "out.xml"))
        write(sink, root)
        assert (tmp_path / "out.xml").exists()
        assert b"test" in (tmp_path / "out.xml").read_bytes()

    def test_write_raw_bytes(self, tmp_path):
        sink = FileSinkSpec(path=str(tmp_path / "out.bin"), format="csv")
        write(sink, b"raw,data\n1,2\n")
        assert (tmp_path / "out.bin").read_bytes() == b"raw,data\n1,2\n"

    def test_write_creates_parent_dirs(self, tmp_path):
        sink = FileSinkSpec(path=str(tmp_path / "sub" / "dir" / "out.csv"))
        table = pa.table({"x": [1]})
        write(sink, table)
        assert (tmp_path / "sub" / "dir" / "out.csv").exists()

    def test_write_no_create_path_raises(self, tmp_path):
        sink = FileSinkSpec(
            path=str(tmp_path / "nonexistent" / "out.csv"),
            create_path=False,
        )
        table = pa.table({"x": [1]})
        with pytest.raises(PathNotFoundError):
            write(sink, table)
        assert not (tmp_path / "nonexistent").exists()

    def test_copy_no_create_path_raises(self, tmp_path):
        source = tmp_path / "in.csv"
        source.write_bytes(b"x\n1\n")
        sink = FileSinkSpec(path=str(tmp_path / "nonexistent" / "out.csv"), create_path=False)
        with pytest.raises(PathNotFoundError):
            copy(FileSourceSpec(path=str(source)), sink)
        assert not (tmp_path / "nonexistent").exists()

    def test_write_explicit_format_spec(self, tmp_path):
        table = pa.table({"a": [1], "b": [2]})
        sink = FileSinkSpec(
            path=str(tmp_path / "out.txt"),
            format=CsvSpec(delimiter=";"),
        )
        write(sink, table)
        content = (tmp_path / "out.txt").read_bytes()
        assert b";" in content

    def test_roundtrip_csv(self, tmp_path):
        table = pa.table({"name": ["Alice"], "age": [30]})
        path = str(tmp_path / "roundtrip.csv")
        write(FileSinkSpec(path=path), table)
        results = parse(FileSourceSpec(path=path))
        assert results[0].data.num_rows == 1

    def test_append_unsupported_raises(self, tmp_path):
        table = pa.table({"x": [1]})
        sink = FileSinkSpec(
            path=str(tmp_path / "out.csv"),
            write_disposition="append",
        )
        with pytest.raises(WriteError, match="append"):
            write(sink, table)


@pytest.mark.parametrize(
    "spec,value",
    [
        (CsvSpec(null_sequence="NULL"), "NULL"),
        (CsvSpec(encoding="ascii"), "café"),
        (CsvSpec(comment_char=""), "abc"),
    ],
)
def test_serialization_rejection_preserves_destination(
    tmp_path: Path,
    spec: CsvSpec,
    value: str,
) -> None:
    path = tmp_path / "keep.csv"
    path.write_bytes(b"original bytes")
    with pytest.raises(WriteError):
        write(FileSinkSpec(path=str(path), format=spec), pa.table({"x": [value]}))
    assert path.read_bytes() == b"original bytes"


@pytest.mark.parametrize("tabular", [True, False])
def test_append_capability_is_spec_declared(tmp_path: Path, tabular: bool) -> None:
    from typing import ClassVar

    from mountainash_files import FormatSpec, register_format
    from mountainash_files.formats._registry import _reset_registry

    @dataclasses.dataclass(frozen=True)
    class PluginSpec(FormatSpec):
        FORMAT: ClassVar[str] = "appendprobe"
        SUFFIXES: ClassVar[tuple[str, ...]] = (".appendprobe",)
        APPENDABLE: ClassVar[bool] = True
        TABULAR: ClassVar[bool] = tabular

    def decode(data, spec):
        return pa.Table.from_pylist(json.loads(data))

    def encode(table, spec):
        return json.dumps(table.to_pylist()).encode()

    try:
        register_format(PluginSpec, decode, serialiser=encode)
        path = tmp_path / "rows.appendprobe"
        sink = FileSinkSpec(path=str(path), write_disposition="append")
        if not tabular:
            with pytest.raises(WriteError):
                write(sink, pa.table({"x": [1]}))
            assert not path.exists()
            return
        write(sink, pa.table({"x": [1]}))
        write(sink, pa.table({"x": [2]}))
        assert json.loads(path.read_bytes()) == [{"x": 1}, {"x": 2}]
    finally:
        _reset_registry()


def test_append_rejects_plugin_parser_without_arrow_table(tmp_path: Path) -> None:
    from typing import ClassVar

    from mountainash_files import FormatSpec, register_format
    from mountainash_files.formats._registry import _reset_registry

    @dataclasses.dataclass(frozen=True)
    class PluginSpec(FormatSpec):
        FORMAT: ClassVar[str] = "recordprobe"
        SUFFIXES: ClassVar[tuple[str, ...]] = (".recordprobe",)
        APPENDABLE: ClassVar[bool] = True
        TABULAR: ClassVar[bool] = True

    def decode(data, spec):
        return json.loads(data)

    def encode(table, spec):
        return json.dumps(table.to_pylist()).encode()

    path = tmp_path / "rows.recordprobe"
    original = b'[{"x": 1}]'
    path.write_bytes(original)
    try:
        register_format(PluginSpec, decode, serialiser=encode)
        with pytest.raises(WriteError):
            write(
                FileSinkSpec(path=str(path), write_disposition="append"),
                pa.table({"x": [2]}),
            )
        assert path.read_bytes() == original
    finally:
        _reset_registry()


def test_append_preserves_rows_and_replace_replaces(tmp_path):
    path = tmp_path / "rows.parquet"
    sink = FileSinkSpec(path=str(path), write_disposition="append")
    write(sink, pa.table({"x": [1]}))
    write(sink, pa.table({"x": [2]}))
    assert pq.read_table(path).to_pylist() == [{"x": 1}, {"x": 2}]
    write(dataclasses.replace(sink, write_disposition="replace"), pa.table({"x": [9]}))
    assert pq.read_table(path).to_pylist() == [{"x": 9}]


@pytest.mark.parametrize(
    "incoming",
    [
        pa.table({"x": ["bad"], "y": [4]}),
        pa.table({"y": [4], "x": [2]}),
        pa.table({"x": [2]}),
        [],
    ],
)
def test_append_schema_rejection_preserves_bytes(tmp_path, incoming):
    path = tmp_path / "rows.parquet"
    pq.write_table(pa.table({"x": [1], "y": [3]}), path)
    original = path.read_bytes()
    with pytest.raises(AppendSchemaMismatchError) as caught:
        write(FileSinkSpec(path=str(path), write_disposition="append"), incoming)
    assert caught.value.path == str(path)
    assert caught.value.expected_schema == pa.schema(
        [("x", pa.int64()), ("y", pa.int64())]
    )
    assert caught.value.actual_schema == (
        incoming.schema if isinstance(incoming, pa.Table) else pa.schema([])
    )
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "mode,payload",
    [
        ("append", b"raw"),
        ("append", bytearray(b"raw")),
        ("append", memoryview(b"raw")),
        ("invalid", b"raw"),
        ("invalid", pa.table({"x": [2]})),
    ],
)
def test_write_mode_validation_precedes_raw_bypass(tmp_path, mode, payload):
    path = tmp_path / "keep.parquet"
    path.write_bytes(b"original")
    with pytest.raises(WriteError):
        write(FileSinkSpec(path=str(path), write_disposition=mode), payload)
    assert path.read_bytes() == b"original"


def test_append_corrupt_target_is_not_replaced(tmp_path):
    from mountainash_files import ParseError

    path = tmp_path / "bad.parquet"
    path.write_bytes(b"corrupt")
    with pytest.raises(ParseError):
        write(
            FileSinkSpec(path=str(path), write_disposition="append"),
            pa.table({"x": [1]}),
        )
    assert path.read_bytes() == b"corrupt"


def test_append_ignores_read_projection_and_preserves_schema_metadata(tmp_path):
    from mountainash_files.formats.parquet import ParquetSpec

    path = tmp_path / "schema.parquet"
    original_schema = pa.schema(
        [
            pa.field("x", pa.int64(), nullable=False, metadata={b"unit": b"count"}),
            pa.field("y", pa.string(), nullable=False),
        ],
        metadata={b"owner": b"old"},
    )
    pq.write_table(
        pa.Table.from_pylist([{"x": 1, "y": "first"}], schema=original_schema), path
    )
    incoming_schema = pa.schema(
        [
            pa.field("x", pa.int64(), metadata={b"unit": b"incoming"}),
            pa.field("y", pa.string(), nullable=False),
        ],
        metadata={b"owner": b"incoming"},
    )
    incoming = pa.Table.from_pylist(
        [{"x": None, "y": "second"}], schema=incoming_schema
    )
    write(
        FileSinkSpec(
            path=str(path),
            format=ParquetSpec(columns=("x",)),
            write_disposition="append",
        ),
        incoming,
    )
    restored = pq.read_table(path)
    assert restored.to_pylist() == [{"x": 1, "y": "first"}, {"x": None, "y": "second"}]
    assert restored.schema.metadata == {b"owner": b"old"}
    assert restored.schema.field("x").metadata == {b"unit": b"count"}
    assert restored.schema.field("x").nullable
    assert not restored.schema.field("y").nullable


@pytest.mark.parametrize("records", [{"x": 2}, [{"x": 2}]])
def test_append_accepts_record_inputs(tmp_path, records):
    path = tmp_path / "records.parquet"
    pq.write_table(pa.table({"x": [1]}), path)
    write(FileSinkSpec(path=str(path), write_disposition="append"), records)
    assert pq.read_table(path).to_pylist() == [{"x": 1}, {"x": 2}]


def test_append_normalizes_all_record_keys(tmp_path):
    path = tmp_path / "records.parquet"
    pq.write_table(pa.table({"x": [1], "y": [3]}), path)
    write(
        FileSinkSpec(path=str(path), write_disposition="append"), [{"x": 2}, {"y": 4}]
    )
    assert pq.read_table(path).to_pylist() == [
        {"x": 1, "y": 3},
        {"x": 2, "y": None},
        {"x": None, "y": 4},
    ]


@pytest.mark.parametrize(
    "incoming,cause_type",
    [
        (42, None),
        ([1], None),
        ([{"x": 2}, {"x": "bad"}], pa.ArrowException),
        ({"x": 2**100}, OverflowError),
    ],
)
def test_append_invalid_input_preserves_bytes(tmp_path, incoming, cause_type):
    path = tmp_path / "keep.parquet"
    pq.write_table(pa.table({"x": [1]}), path)
    original = path.read_bytes()
    with pytest.raises(WriteError) as caught:
        write(FileSinkSpec(path=str(path), write_disposition="append"), incoming)
    assert path.read_bytes() == original
    if cause_type is not None:
        assert isinstance(caught.value.__cause__, cause_type)


def test_typed_empty_append_retains_existing_rows(tmp_path):
    path = tmp_path / "empty.parquet"
    empty = pa.table({"x": pa.array([], type=pa.int64())})
    sink = FileSinkSpec(path=str(path), write_disposition="append")
    write(sink, empty)
    assert pq.read_table(path).schema == empty.schema
    write(sink, pa.table({"x": [1]}))
    write(sink, empty)
    assert pq.read_table(path).to_pylist() == [{"x": 1}]


@pytest.mark.parametrize("compressed", [False, True])
def test_append_uses_sink_pipeline_symmetrically(tmp_path, compressed):
    import gzip
    from mountainash_transport import Gzip, Pipeline

    path = tmp_path / "rows.parquet.gz"
    sink = FileSinkSpec(
        path=str(path),
        format="parquet",
        write_disposition="append",
        transforms=Pipeline(Gzip()) if compressed else None,
    )
    write(sink, pa.table({"x": [1]}))
    write(sink, pa.table({"x": [2]}))
    raw = path.read_bytes()
    payload = gzip.decompress(raw) if compressed else raw
    assert pq.read_table(io.BytesIO(payload)).to_pylist() == [{"x": 1}, {"x": 2}]


def test_append_denial_is_not_absence(tmp_path, monkeypatch):
    from mountainash_transport import StorageFacade

    path = tmp_path / "keep.parquet"
    path.write_bytes(b"original")
    denied = PermissionError("denied")

    def fail_read(self, path, **kwargs):
        raise denied

    monkeypatch.setattr(StorageFacade, "read", fail_read)
    with pytest.raises(PermissionError) as caught:
        write(
            FileSinkSpec(path=str(path), write_disposition="append"),
            pa.table({"x": [1]}),
        )
    assert caught.value is denied
    assert path.read_bytes() == b"original"


def test_append_forwards_remote_profile_and_auth(tmp_path, monkeypatch):
    from mountainash_transport import StorageFacade
    from mountainash_transport.settings.storage.profiles import LocalStorageProfile
    from mountainash_auth_client import NoAuthProfile

    target = tmp_path / "remote.parquet"
    local = StorageFacade.from_path(str(target))
    route = "s3://bucket/rows.parquet"
    seen, operations = [], []
    profile, auth = LocalStorageProfile(), NoAuthProfile()

    class RoutedFacade:
        def read(self, path, **kwargs):
            assert path == route
            operations.append("read")
            return local.read(str(target), **kwargs)

        def write(self, path, data, **kwargs):
            assert path == route
            operations.append("write")
            return local.write(str(target), data, **kwargs)

    def route_factory(path, storage_profile=None, *, auth_profile=None):
        assert path == route
        seen.append((storage_profile, auth_profile))
        return RoutedFacade()

    monkeypatch.setattr(StorageFacade, "from_path", staticmethod(route_factory))
    sink = FileSinkSpec(
        path=route,
        format="parquet",
        write_disposition="append",
        storage_profile=profile,
        auth_profile=auth,
    )
    write(sink, pa.table({"x": [1]}))
    write(sink, pa.table({"x": [2]}))
    assert pq.read_table(target).to_pylist() == [{"x": 1}, {"x": 2}]
    assert operations == ["read", "write", "read", "write"]
    assert seen and all(p is profile and a is auth for p, a in seen)
