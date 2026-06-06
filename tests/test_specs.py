import pytest

from mountainash_files.specs.base import FileSpec
from mountainash_files.specs.source import FileSourceSpec
from mountainash_files.specs.archive import ZipArchive, GzipCompression


class TestFileSpec:
    def test_minimal(self):
        spec = FileSpec(path="s3://bucket/data.csv")
        assert spec.path == "s3://bucket/data.csv"
        assert spec.format is None
        assert spec.auth_profile is None
        assert spec.archive is None
        assert spec.transforms is None

    def test_with_format_string(self):
        spec = FileSpec(path="/local/data.csv", format="csv")
        assert spec.format == "csv"

    def test_with_auth_profile(self):
        spec = FileSpec(path="s3://bucket/data.csv", auth_profile="production-s3")
        assert spec.auth_profile == "production-s3"

    def test_frozen(self):
        spec = FileSpec(path="/data.csv")
        with pytest.raises(AttributeError):
            spec.path = "/other.csv"


class TestFileSourceSpec:
    def test_inherits_file_spec(self):
        assert issubclass(FileSourceSpec, FileSpec)

    def test_defaults(self):
        src = FileSourceSpec(path="/data.csv")
        assert src.glob is None
        assert src.on_missing == "raise"

    def test_with_glob(self):
        src = FileSourceSpec(path="/data/", glob="*.csv")
        assert src.glob == "*.csv"

    def test_on_missing_skip(self):
        src = FileSourceSpec(path="/data.csv", on_missing="skip")
        assert src.on_missing == "skip"


class TestArchiveSpecs:
    def test_gzip_compression(self):
        gz = GzipCompression()
        assert gz is not None

    def test_zip_archive_defaults(self):
        z = ZipArchive()
        assert z.file_pattern == "*"
        assert z.sort_order == "name"
        assert z.password is None
        assert z.inner is None

    def test_zip_with_nested_gzip(self):
        z = ZipArchive(file_pattern="*.csv", inner=GzipCompression())
        assert z.file_pattern == "*.csv"
        assert isinstance(z.inner, GzipCompression)

    def test_file_spec_with_archive(self):
        spec = FileSpec(
            path="s3://bucket/archive.zip",
            archive=ZipArchive(file_pattern="*.csv"),
        )
        assert isinstance(spec.archive, ZipArchive)
