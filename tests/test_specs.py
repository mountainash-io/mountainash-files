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

    def test_with_storage_profile_name(self):
        spec = FileSpec(path="s3://bucket/data.csv", storage_profile="production-s3")
        assert spec.storage_profile == "production-s3"

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


class TestProfileFields:
    def test_spec_accepts_profile_objects(self):
        from mountainash_transport.settings.storage.profiles import LocalStorageProfile

        profile = LocalStorageProfile()
        spec = FileSourceSpec(path="/tmp/x.csv", storage_profile=profile)
        assert spec.storage_profile is profile
        assert spec.auth_profile is None

    def test_spec_accepts_profile_name(self):
        spec = FileSourceSpec(path="s3://b/x.csv", storage_profile="lake")
        assert spec.storage_profile == "lake"

    def test_resolve_profiles_passthrough_for_objects(self):
        from mountainash_files._operations import _resolve_profiles
        from mountainash_transport.settings.storage.profiles import LocalStorageProfile

        profile = LocalStorageProfile()
        spec = FileSourceSpec(path="/tmp/x.csv", storage_profile=profile)
        resolved_profile, resolved_auth = _resolve_profiles(spec)
        assert resolved_profile is profile
        assert resolved_auth is None

    def test_resolve_profiles_by_name(self, tmp_path, monkeypatch):
        from mountainash_auth_client import NoAuthProfile
        from mountainash_files._operations import _resolve_profiles
        from mountainash_transport.settings.storage.profiles import LocalStorageProfile

        cfg = tmp_path / "profiles.yaml"
        cfg.write_text(
            "storage_profiles:\n"
            "  scratch:\n"
            "    provider: local\n"
            "    parameters:\n"
            "      ROOT_PATH: null\n"
        )
        monkeypatch.setenv("MOUNTAINASH_PROFILES_CONFIG", str(cfg))
        spec = FileSourceSpec(path="/tmp/x.csv", storage_profile="scratch")
        resolved_profile, resolved_auth = _resolve_profiles(spec)
        assert isinstance(resolved_profile, LocalStorageProfile)
        assert isinstance(resolved_auth, NoAuthProfile)

    def test_explicit_auth_overrides_resolved(self, tmp_path, monkeypatch):
        from mountainash_auth_client import TokenAuthProfile
        from mountainash_files._operations import _resolve_profiles

        cfg = tmp_path / "profiles2.yaml"
        cfg.write_text(
            "storage_profiles:\n"
            "  web:\n"
            "    provider: http\n"
        )
        monkeypatch.setenv("MOUNTAINASH_PROFILES_CONFIG", str(cfg))
        token = TokenAuthProfile(TOKEN="t0k3n")
        spec = FileSourceSpec(
            path="https://example.com/x.csv", storage_profile="web", auth_profile=token
        )
        _, resolved_auth = _resolve_profiles(spec)
        assert resolved_auth is token
