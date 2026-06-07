from pathlib import Path

import pyarrow as pa
import pytest

from mountainash_files import parse, write, copy
from mountainash_files.specs.source import FileSourceSpec
from mountainash_files.specs.sink import FileSinkSpec

FIXTURES = Path(__file__).parent / "fixtures"


class TestParseParams:
    def test_param_expansion(self, tmp_path):
        (tmp_path / "data_2024.csv").write_text("x,y\n1,2\n")
        source = FileSourceSpec(path=str(tmp_path / "data_{year}.csv"))
        results = parse(source, params={"year": "2024"})
        assert len(results) == 1
        assert results[0].data.num_rows == 1

    def test_multiple_params(self, tmp_path):
        (tmp_path / "us_2024_q1.csv").write_text("x\n1\n")
        source = FileSourceSpec(
            path=str(tmp_path / "{region}_{year}_{quarter}.csv"),
        )
        results = parse(source, params={"region": "us", "year": "2024", "quarter": "q1"})
        assert len(results) == 1

    def test_missing_param_raises(self, tmp_path):
        source = FileSourceSpec(path=str(tmp_path / "data_{year}.csv"))
        with pytest.raises(KeyError):
            parse(source, params={"month": "01"})

    def test_no_params_no_expansion(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.csv"))
        results = parse(source)
        assert len(results) == 1


class TestWriteParams:
    def test_param_expansion(self, tmp_path):
        table = pa.table({"x": [1]})
        sink = FileSinkSpec(path=str(tmp_path / "out_{date}.csv"))
        write(sink, table, params={"date": "2024-01-01"})
        assert (tmp_path / "out_2024-01-01.csv").exists()


class TestCopyParams:
    def test_param_expansion(self, tmp_path):
        (tmp_path / "src_2024.csv").write_text("x\n1\n")
        source = FileSourceSpec(path=str(tmp_path / "src_{year}.csv"))
        sink = FileSinkSpec(path=str(tmp_path / "dst_{year}.csv"))
        copy(source, sink, params={"year": "2024"})
        assert (tmp_path / "dst_2024.csv").exists()
