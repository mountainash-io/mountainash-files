import gzip
from pathlib import Path

import pytest
from mountainash_transport import PathNotFoundError

from mountainash_files import copy
from mountainash_files.specs.source import FileSourceSpec
from mountainash_files.specs.sink import FileSinkSpec

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("infer", [None, False, True])
def test_copy_inference_override(tmp_path, infer):
    payload = gzip.compress(b"x\n1\n", mtime=0)
    src, dst = tmp_path / "rows.csv.gz", tmp_path / "copy.bin"
    src.write_bytes(payload)
    copy(FileSourceSpec(path=str(src), infer=infer), FileSinkSpec(path=str(dst)))
    assert dst.read_bytes() == (payload if infer is False else b"x\n1\n")


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
        with pytest.raises(PathNotFoundError):
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


class TestCopyEndpointPolicyIndependence:
    """Each endpoint resolves its own override against its own profile."""

    @pytest.fixture
    def stores(self, tmp_path):
        from mountainash_transport.settings.storage.profiles import LocalStorageProfile

        src_root, dst_root = tmp_path / "src", tmp_path / "dst"
        src_root.mkdir(); dst_root.mkdir()
        (src_root / "in.txt").write_bytes(b"inside")
        (tmp_path / "outside.txt").write_bytes(b"outside")
        src_profile = LocalStorageProfile(ROOT_PATH=str(src_root), LOCATION_POLICY={})
        dst_profile = LocalStorageProfile(ROOT_PATH=str(dst_root), LOCATION_POLICY={})
        return tmp_path, src_profile, dst_profile

    def test_inherited_source_policy_denies_before_writing(self, stores):
        from mountainash_transport.location import LocationNotAllowed

        tmp, src_profile, dst_profile = stores
        with pytest.raises(LocationNotAllowed):
            copy(FileSourceSpec(path=str(tmp / "outside.txt"), storage_profile=src_profile),
                 FileSinkSpec(path="out.txt", storage_profile=dst_profile))
        assert not (tmp / "dst" / "out.txt").exists()

    def test_source_off_does_not_disable_inherited_sink_policy(self, stores):
        from mountainash_transport.location import LocationNotAllowed

        tmp, src_profile, dst_profile = stores
        with pytest.raises(LocationNotAllowed):
            copy(FileSourceSpec(path=str(tmp / "outside.txt"), storage_profile=src_profile, policy=None),
                 FileSinkSpec(path=str(tmp / "escaped.txt"), storage_profile=dst_profile))
        assert not (tmp / "escaped.txt").exists()

    def test_sink_off_does_not_disable_inherited_source_policy(self, stores):
        from mountainash_transport.location import LocationNotAllowed

        tmp, src_profile, dst_profile = stores
        with pytest.raises(LocationNotAllowed):
            copy(FileSourceSpec(path=str(tmp / "outside.txt"), storage_profile=src_profile),
                 FileSinkSpec(path=str(tmp / "escaped.txt"), storage_profile=dst_profile, policy=None))
        assert not (tmp / "escaped.txt").exists()

    def test_each_endpoint_off_independently(self, stores):
        tmp, src_profile, dst_profile = stores
        copy(FileSourceSpec(path=str(tmp / "outside.txt"), storage_profile=src_profile, policy=None),
             FileSinkSpec(path=str(tmp / "escaped.txt"), storage_profile=dst_profile, policy=None))
        assert (tmp / "escaped.txt").read_bytes() == b"outside"

    def test_inherited_endpoints_allow_their_own_roots(self, stores):
        tmp, src_profile, dst_profile = stores
        copy(FileSourceSpec(path="in.txt", storage_profile=src_profile),
             FileSinkSpec(path="out.txt", storage_profile=dst_profile))
        assert (tmp / "dst" / "out.txt").read_bytes() == b"inside"
