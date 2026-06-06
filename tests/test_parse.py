import io
from pathlib import Path
from unittest.mock import patch, MagicMock

import pyarrow as pa
import pytest

from mountainash_files import parse
from mountainash_files.specs.source import FileSourceSpec
from mountainash_files.formats._types import ParseResult
from mountainash_files.formats._exceptions import UnknownFormatError, ParseError
from mountainash_files.formats.csv import CsvSpec


FIXTURES = Path(__file__).parent / "fixtures"


class TestParseLocalFile:
    def test_csv_by_suffix(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.csv"))
        results = parse(source)
        assert len(results) == 1
        assert isinstance(results[0], ParseResult)
        assert results[0].format_key == "csv"
        assert isinstance(results[0].data, pa.Table)
        assert results[0].data.num_rows == 3

    def test_json_by_suffix(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.json"))
        results = parse(source)
        assert len(results) == 1
        assert results[0].format_key == "json"
        assert isinstance(results[0].data, dict)

    def test_ndjson_suffix_override(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.ndjson"))
        results = parse(source)
        assert len(results) == 1
        assert results[0].format_key == "json"
        assert isinstance(results[0].data, list)
        assert len(results[0].data) == 3

    def test_parquet_by_suffix(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.parquet"))
        results = parse(source)
        assert results[0].format_key == "parquet"
        assert isinstance(results[0].data, pa.Table)

    def test_xml_by_suffix(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.xml"))
        results = parse(source)
        assert results[0].format_key == "xml"
        assert results[0].data.tag == "people"

    def test_explicit_format_overrides_suffix(self):
        source = FileSourceSpec(
            path=str(FIXTURES / "sample.csv"),
            format="csv",
        )
        results = parse(source)
        assert results[0].format_key == "csv"

    def test_explicit_spec(self):
        source = FileSourceSpec(
            path=str(FIXTURES / "sample.csv"),
            format=CsvSpec(delimiter=","),
        )
        results = parse(source)
        assert results[0].format_key == "csv"

    def test_unknown_suffix_raises(self):
        source = FileSourceSpec(path="/data/file.xyz")
        with pytest.raises(UnknownFormatError):
            parse(source)

    def test_missing_file_raises(self):
        source = FileSourceSpec(path="/nonexistent/file.csv")
        with pytest.raises(Exception):  # PathNotFoundError or FileNotFoundError
            parse(source)

    def test_missing_file_skip(self):
        source = FileSourceSpec(path="/nonexistent/file.csv", on_missing="skip")
        results = parse(source)
        assert results == []

    def test_result_carries_spec(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.csv"))
        results = parse(source)
        assert isinstance(results[0].spec, CsvSpec)


class TestParseTsvFixture:
    def test_tsv_by_suffix(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.tsv"))
        results = parse(source)
        assert results[0].format_key == "tsv"
        assert isinstance(results[0].data, pa.Table)
        assert results[0].data.num_rows == 2
