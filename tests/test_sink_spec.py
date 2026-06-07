import pytest

from mountainash_files.specs.sink import FileSinkSpec
from mountainash_files.specs.base import FileSpec
from mountainash_files._exceptions import WriteError


class TestFileSinkSpec:
    def test_inherits_file_spec(self):
        assert issubclass(FileSinkSpec, FileSpec)

    def test_defaults(self):
        sink = FileSinkSpec(path="/output/data.csv")
        assert sink.write_disposition == "replace"
        assert sink.create_path is True

    def test_append(self):
        sink = FileSinkSpec(path="/output/data.parquet", write_disposition="append")
        assert sink.write_disposition == "append"

    def test_frozen(self):
        sink = FileSinkSpec(path="/data.csv")
        with pytest.raises(AttributeError):
            sink.path = "/other.csv"

    def test_with_format(self):
        sink = FileSinkSpec(path="/data.csv", format="csv")
        assert sink.format == "csv"

    def test_with_auth_profile(self):
        sink = FileSinkSpec(path="s3://bucket/out.parquet", auth_profile="prod")
        assert sink.auth_profile == "prod"


class TestWriteError:
    def test_is_exception(self):
        assert issubclass(WriteError, Exception)

    def test_message(self):
        err = WriteError("Cannot append to CSV")
        assert "Cannot append to CSV" in str(err)
