import gzip
import io
import zipfile
from pathlib import Path

import pytest

from mountainash_files._archives import unpack_archive, ArchiveExtractionError, ArchiveEmptyMatchError, ArchiveLimitError
from mountainash_files import FileSourceSpec, ParseError, parse
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


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.mark.parametrize("explicit_pipeline", [False, True])
def test_archive_outer_gzip_options(tmp_path, explicit_pipeline):
    from mountainash_transport import Gzip, Pipeline

    path = tmp_path / "rows.zip.gz"
    path.write_bytes(gzip.compress(_zip_bytes({"rows.csv": b"x\n1\n"})))
    source = FileSourceSpec(
        path=str(path), archive=ZipArchive(),
        transforms=Pipeline(Gzip()) if explicit_pipeline else None,
        infer=None if explicit_pipeline else True,
    )
    assert parse(source, output="pydata")[0].data == [{"x": 1}]


def test_unrecognised_member_errors_by_default(tmp_path):
    path = tmp_path / "mixed.zip"
    path.write_bytes(_zip_bytes({"data.csv": b"a\n1\n", "README.xyz": b"hi"}))
    with pytest.raises(ParseError, match="README.xyz"):
        parse(FileSourceSpec(path=str(path), archive=ZipArchive()))


def test_unrecognised_member_skip_mode_records_names(tmp_path):
    path = tmp_path / "mixed.zip"
    path.write_bytes(_zip_bytes({"data.csv": b"a\n1\n", "README.xyz": b"hi"}))
    results = parse(
        FileSourceSpec(path=str(path), archive=ZipArchive(on_unrecognised="skip"))
    )
    assert len(results) == 1
    assert results[0].skipped_members == ("README.xyz",)


def test_zero_recognised_members_raises_even_under_skip(tmp_path):
    path = tmp_path / "junk.zip"
    path.write_bytes(_zip_bytes({"a.xyz": b"x", "b.xyz": b"y"}))
    with pytest.raises(ParseError, match="no recognised members"):
        parse(
            FileSourceSpec(
                path=str(path),
                archive=ZipArchive(on_unrecognised="skip"),
            )
        )


def test_file_pattern_exclusion_is_not_unrecognised(tmp_path):
    path = tmp_path / "mixed.zip"
    path.write_bytes(_zip_bytes({"data.csv": b"a\n1\n", "README.xyz": b"hi"}))
    results = parse(
        FileSourceSpec(path=str(path), archive=ZipArchive(file_pattern="*.csv"))
    )
    assert len(results) == 1
    assert results[0].skipped_members == ()


class TestDecompressionLimits:
    """Item 385: bounded decompression for hostile archives."""

    BOMB = 64 * 1024 * 1024  # 64 MiB of zeros compresses to ~64 KiB

    @staticmethod
    def _zip(members: dict[str, bytes]) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, payload in members.items():
                zf.writestr(name, payload)
        return buf.getvalue()

    def test_gzip_over_size_limit_raises(self):
        data = gzip.compress(b"\0" * self.BOMB)
        with pytest.raises(ArchiveLimitError, match="decompressed"):
            list(unpack_archive(data, GzipCompression(max_decompressed_bytes=1024 * 1024)))

    def test_zip_over_size_limit_raises(self):
        data = self._zip({"a.csv": b"\0" * self.BOMB})
        with pytest.raises(ArchiveLimitError, match="decompressed"):
            list(unpack_archive(data, ZipArchive(max_decompressed_bytes=1024 * 1024)))

    def test_zip_size_limit_is_total_across_members(self):
        data = self._zip({f"{i}.csv": b"x" * 600 for i in range(3)})
        with pytest.raises(ArchiveLimitError):
            list(unpack_archive(data, ZipArchive(max_decompressed_bytes=1000)))

    def test_zip_inner_gzip_counts_against_limit(self):
        data = self._zip({"a.csv.gz": gzip.compress(b"\0" * self.BOMB)})
        with pytest.raises(ArchiveLimitError):
            list(unpack_archive(
                data,
                ZipArchive(max_decompressed_bytes=1024 * 1024, inner=GzipCompression()),
            ))

    def test_zip_over_member_limit_raises(self):
        data = self._zip({f"{i}.csv": b"a\n1\n" for i in range(5)})
        with pytest.raises(ArchiveLimitError, match="members"):
            list(unpack_archive(data, ZipArchive(max_members=4)))

    def test_limit_error_is_extraction_error(self):
        assert issubclass(ArchiveLimitError, ArchiveExtractionError)

    def test_bomb_does_not_allocate_full_payload(self):
        import tracemalloc

        data = gzip.compress(b"\0" * self.BOMB)
        tracemalloc.start()
        with pytest.raises(ArchiveLimitError):
            list(unpack_archive(data, GzipCompression(max_decompressed_bytes=1024 * 1024)))
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < 16 * 1024 * 1024

    def test_override_raises_limits(self):
        payload = b"x" * 5000
        assert list(unpack_archive(gzip.compress(payload), GzipCompression(max_decompressed_bytes=5000))) == [("", payload)]
        data = self._zip({f"{i}.csv": b"a" for i in range(5)})
        assert len(list(unpack_archive(data, ZipArchive(max_members=5)))) == 5

    def test_defaults_allow_normal_archives(self):
        assert ZipArchive().max_decompressed_bytes > 0 and ZipArchive().max_members > 0
        data = (FIXTURES / "sample.zip").read_bytes()
        assert len(list(unpack_archive(data, ZipArchive()))) == 2

    def test_parse_surfaces_limit_error(self, tmp_path):
        path = tmp_path / "bomb.zip"
        path.write_bytes(self._zip({"a.csv": b"a\n" + b"1\n" * 1_000_000}))
        with pytest.raises(ArchiveLimitError):
            parse(FileSourceSpec(path=str(path), archive=ZipArchive(max_decompressed_bytes=1000)))
