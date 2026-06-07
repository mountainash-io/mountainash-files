import importlib
import io
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.parquet as pq
import pytest

from mountainash_files import write, parse, FileSourceSpec
from mountainash_files.specs.sink import FileSinkSpec
from mountainash_files._exceptions import WriteError
from mountainash_files.formats.csv import CsvSpec


@pytest.fixture(autouse=True)
def _ensure_formats_registered():
    """Re-trigger format registration in case a previous test reset the registry."""
    from mountainash_files.formats._registry import _SPECS, _reset_registry
    import mountainash_files.formats.csv
    import mountainash_files.formats.tsv
    import mountainash_files.formats.json
    import mountainash_files.formats.parquet
    import mountainash_files.formats.xlsx
    import mountainash_files.formats.xml

    if not _SPECS:
        _reset_registry()
        for mod in [
            mountainash_files.formats.csv,
            mountainash_files.formats.tsv,
            mountainash_files.formats.json,
            mountainash_files.formats.parquet,
            mountainash_files.formats.xlsx,
            mountainash_files.formats.xml,
        ]:
            importlib.reload(mod)


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
        lines = [json.loads(l) for l in (tmp_path / "out.ndjson").read_text().splitlines() if l.strip()]
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
        with pytest.raises((WriteError, FileNotFoundError)):
            write(sink, table)

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
