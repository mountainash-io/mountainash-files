from pathlib import Path

import pyarrow as pa
import pytest

from mountainash_files import parse
from mountainash_files.specs.source import FileSourceSpec
from mountainash_files.formats._types import ParseResult

FIXTURES = Path(__file__).parent / "fixtures"
GLOB_DIR = FIXTURES / "glob_dir"


class TestParseGlob:
    def test_glob_csv(self):
        source = FileSourceSpec(path=str(GLOB_DIR), glob="*.csv")
        results = parse(source)
        assert len(results) == 2
        assert all(isinstance(r, ParseResult) for r in results)
        assert all(r.format_key == "csv" for r in results)
        assert all(isinstance(r.data, pa.Table) for r in results)

    def test_glob_recursive(self):
        source = FileSourceSpec(path=str(GLOB_DIR), glob="**/*.csv")
        results = parse(source)
        assert len(results) == 3

    def test_glob_no_match(self):
        source = FileSourceSpec(path=str(GLOB_DIR), glob="*.xyz")
        results = parse(source)
        assert results == []

    def test_glob_with_explicit_format(self):
        source = FileSourceSpec(
            path=str(GLOB_DIR),
            glob="*.csv",
            format="csv",
        )
        results = parse(source)
        assert len(results) == 2

    def test_glob_results_sorted(self):
        source = FileSourceSpec(path=str(GLOB_DIR), glob="data_*.csv")
        results = parse(source)
        # data_2024.csv before data_2025.csv
        years = [r.data.column("year")[0].as_py() for r in results]
        assert years == sorted(years)
