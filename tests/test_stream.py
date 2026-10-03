import contextlib
from pathlib import Path

import pytest

from mountainash_files import stream
from mountainash_files.specs.source import FileSourceSpec

FIXTURES = Path(__file__).parent / "fixtures"


class TestStreamLocal:
    def test_stream_csv(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.csv"))
        with stream(source) as s:
            data = s.read()
        assert isinstance(data, bytes)
        assert b"Alice" in data

    def test_stream_binary(self):
        source = FileSourceSpec(path=str(FIXTURES / "sample.parquet"))
        with stream(source) as s:
            data = s.read()
        assert len(data) > 0

    def test_stream_missing_raises(self):
        source = FileSourceSpec(path="/nonexistent/file.csv")
        with pytest.raises(Exception):
            with stream(source) as s:
                s.read()

    @pytest.mark.parametrize("missing", [False, True])
    @pytest.mark.parametrize("caller_raises", [False, True])
    def test_stream_lifetime(self, tmp_path, missing, caller_raises):
        path = tmp_path / "data.bin"
        if not missing:
            path.write_bytes(b"payload")
        source = FileSourceSpec(path=str(path), on_missing="skip")
        expected_exit = (
            pytest.raises(RuntimeError, match="caller")
            if caller_raises
            else contextlib.nullcontext()
        )
        with expected_exit:
            with stream(source) as handle:
                assert not handle.closed
                assert handle.read() == (b"" if missing else b"payload")
                if caller_raises:
                    raise RuntimeError("caller")
        assert handle.closed

    def test_stream_skip_does_not_hide_permission_error(self, tmp_path, monkeypatch):
        from mountainash_transport import StorageFacade

        denied = PermissionError("denied")

        def fail_read(self, path, **kwargs):
            raise denied

        monkeypatch.setattr(StorageFacade, "read", fail_read)
        with pytest.raises(PermissionError) as caught:
            with stream(
                FileSourceSpec(path=str(tmp_path / "data.csv"), on_missing="skip")
            ):
                pytest.fail("permission failure must not yield")
        assert caught.value is denied
