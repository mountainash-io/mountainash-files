import gzip
import io
import zipfile
from pathlib import Path

import pytest

from mountainash_files._archives import unpack_archive, ArchiveExtractionError, ArchiveEmptyMatchError
from mountainash_files.specs.archive import ZipArchive, GzipCompression

FIXTURES = Path(__file__).parent / "fixtures"


class TestGzipExtraction:
    def test_decompress(self):
        data = (FIXTURES / "sample.csv.gz").read_bytes()
        members = list(unpack_archive(data, GzipCompression()))
        assert len(members) == 1
        name, payload = members[0]
        assert name == ""
        assert b"Alice" in payload

    def test_empty_raises(self):
        with pytest.raises(ArchiveExtractionError):
            list(unpack_archive(b"", GzipCompression()))


class TestZipExtraction:
    def test_extract_all(self):
        data = (FIXTURES / "sample.zip").read_bytes()
        members = list(unpack_archive(data, ZipArchive()))
        assert len(members) == 2

    def test_file_pattern(self):
        data = (FIXTURES / "sample.zip").read_bytes()
        members = list(unpack_archive(data, ZipArchive(file_pattern="*.csv")))
        assert len(members) == 1
        name, payload = members[0]
        assert name.endswith(".csv")
        assert b"Alice" in payload

    def test_no_match_raises(self):
        data = (FIXTURES / "sample.zip").read_bytes()
        with pytest.raises(ArchiveEmptyMatchError):
            list(unpack_archive(data, ZipArchive(file_pattern="*.xyz")))

    def test_sort_order_name(self):
        data = (FIXTURES / "sample.zip").read_bytes()
        members = list(unpack_archive(data, ZipArchive(sort_order="name")))
        names = [m[0] for m in members]
        assert names == sorted(names)

    def test_nested_gzip(self):
        csv_data = b"x,y\n1,2\n"
        gz_data = gzip.compress(csv_data)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("data.csv.gz", gz_data)
        buf.seek(0)

        members = list(unpack_archive(
            buf.read(),
            ZipArchive(file_pattern="*.csv.gz", inner=GzipCompression()),
        ))
        assert len(members) == 1
        _, payload = members[0]
        assert payload == csv_data
