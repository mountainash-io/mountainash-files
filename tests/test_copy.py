from pathlib import Path

import pytest

from mountainash_files import copy
from mountainash_files.specs.source import FileSourceSpec
from mountainash_files.specs.sink import FileSinkSpec

FIXTURES = Path(__file__).parent / "fixtures"


class TestCopyLocal:
    def test_copy_file(self, tmp_path):
        source = FileSourceSpec(path=str(FIXTURES / "sample.csv"))
        sink = FileSinkSpec(path=str(tmp_path / "copied.csv"))
        copy(source, sink)
        assert (tmp_path / "copied.csv").exists()
        assert (tmp_path / "copied.csv").read_bytes() == (FIXTURES / "sample.csv").read_bytes()

    def test_copy_creates_dirs(self, tmp_path):
        source = FileSourceSpec(path=str(FIXTURES / "sample.json"))
        sink = FileSinkSpec(path=str(tmp_path / "sub" / "dir" / "out.json"))
        copy(source, sink)
        assert (tmp_path / "sub" / "dir" / "out.json").exists()

    def test_copy_missing_raises(self):
        source = FileSourceSpec(path="/nonexistent/file.csv")
        sink = FileSinkSpec(path="/tmp/out.csv")
        with pytest.raises(FileNotFoundError):
            copy(source, sink)

    def test_copy_missing_skip(self, tmp_path):
        source = FileSourceSpec(path="/nonexistent/file.csv", on_missing="skip")
        sink = FileSinkSpec(path=str(tmp_path / "out.csv"))
        copy(source, sink)  # Should not raise
        assert not (tmp_path / "out.csv").exists()

    def test_copy_binary_file(self, tmp_path):
        source = FileSourceSpec(path=str(FIXTURES / "sample.parquet"))
        sink = FileSinkSpec(path=str(tmp_path / "copy.parquet"))
        copy(source, sink)
        assert (tmp_path / "copy.parquet").read_bytes() == (FIXTURES / "sample.parquet").read_bytes()
