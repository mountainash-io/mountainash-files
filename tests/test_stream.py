from pathlib import Path

import pytest

from mountainash_files import stream
from mountainash_files.specs.source import FileSourceSpec

FIXTURES = Path(__file__).parent / "fixtures"


class TestStreamLocal:
    def test_stream_csv(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.csv"))
        with stream(source) as s:
            data = s.read()
        assert isinstance(data, bytes)
        assert b"Alice" in data

    def test_stream_binary(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.parquet"))
        with stream(source) as s:
            data = s.read()
        assert len(data) > 0

    def test_stream_missing_raises(self):
        source = FileSourceSpec(path="/nonexistent/file.csv")
        with pytest.raises(Exception):
            with stream(source) as s:
                s.read()

    def test_stream_missing_skip(self):
        source = FileSourceSpec(path="/nonexistent/file.csv", on_missing="skip")
        with stream(source) as s:
            assert s is not None
            data = s.read()
            assert data == b""
