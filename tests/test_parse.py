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
from mountainash_files.specs.archive import ZipArchive, GzipCompression


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


class TestParseWithArchive:
    def test_gzip_csv(self):
        source = FileSourceSpec(
            path=str(FIXTURES / "sample.csv.gz"),
            format="csv",
            archive=GzipCompression(),
        )
        results = parse(source)
        assert len(results) == 1
        assert results[0].format_key == "csv"
        assert results[0].data.num_rows == 3

    def test_zip_csv(self):
        source = FileSourceSpec(
            path=str(FIXTURES / "sample.zip"),
            archive=ZipArchive(file_pattern="*.csv"),
        )
        results = parse(source)
        assert len(results) == 1
        assert results[0].format_key == "csv"
        assert results[0].data.num_rows == 3

    def test_zip_all_parseable(self):
        source = FileSourceSpec(
            path=str(FIXTURES / "sample.zip"),
            archive=ZipArchive(file_pattern="*"),
        )
        results = parse(source)
        # Only CSV member is parseable (readme.txt has no registered format)
        assert len(results) >= 1
        assert any(r.format_key == "csv" for r in results)


class TestParseBytes:
    def test_parse_csv_bytes(self):
        from mountainash_files import parse_bytes

        result = parse_bytes(b"a,b\n1,2\n", "csv")
        assert result.format_key == "csv"
        assert result.data.num_rows == 1

    def test_parse_bytes_accepts_binaryio(self):
        import io

        from mountainash_files import parse_bytes

        result = parse_bytes(io.BytesIO(b"a,b\n1,2\n"), "csv")
        assert result.data.num_rows == 1

    def test_parse_bytes_with_format_spec(self):
        from mountainash_files import parse_bytes
        from mountainash_files.formats.csv import CsvSpec

        result = parse_bytes(b"a;b\n1;2\n", CsvSpec(delimiter=";"))
        assert result.data.num_rows == 1

    def test_parse_bytes_unknown_format_raises(self):
        import pytest

        from mountainash_files import UnknownFormatError, parse_bytes

        with pytest.raises(UnknownFormatError):
            parse_bytes(b"x", "nosuchformat")


class TestSerialiseBytes:
    def test_roundtrip_csv(self):
        from mountainash_files import parse_bytes, serialise_bytes

        table = parse_bytes(b"a,b\n1,2\n", "csv").data
        out = serialise_bytes(table, "csv")
        assert parse_bytes(out, "csv").data.num_rows == 1

    def test_no_serialiser_raises_write_error(self):
        import pytest

        from mountainash_files import WriteError, serialise_bytes

        with pytest.raises(WriteError):
            serialise_bytes(object(), "xlsx")   # xlsx registers no serialiser
