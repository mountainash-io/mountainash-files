import contextlib
import gzip
import io
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
    @pytest.mark.parametrize("caller_error", [None, RuntimeError, FileNotFoundError])
    def test_stream_lifetime(self, tmp_path, missing, caller_error):
        path = tmp_path / "data.bin"
        if not missing:
            path.write_bytes(b"payload")
        source = FileSourceSpec(path=str(path), on_missing="skip")
        expected_exit = (
            pytest.raises(caller_error, match="caller")
            if caller_error
            else contextlib.nullcontext()
        )
        with expected_exit:
            with stream(source) as handle:
                assert not handle.closed
                assert handle.read() == (b"" if missing else b"payload")
                if caller_error:
                    raise caller_error("caller")
        assert handle.closed

    def test_stream_skip_does_not_hide_permission_error(self, tmp_path, monkeypatch):
        from mountainash_transport import StorageFacade

        denied = PermissionError("denied")

        def fail_read(self, path, **kwargs):
            raise denied

        monkeypatch.setattr(StorageFacade, "read_stream", fail_read)
        with pytest.raises(PermissionError) as caught:
            with stream(
                FileSourceSpec(path=str(tmp_path / "data.csv"), on_missing="skip")
            ):
                pytest.fail("permission failure must not yield")
        assert caught.value is denied


@pytest.mark.parametrize("seekable", [False, True])
def test_stream_preserves_consumption_and_capabilities(tmp_path, seekable):
    from mountainash_transport import Pipeline

    opened = []

    class ForwardOnly(io.RawIOBase):
        def read(self, size=-1):
            return opened[0].read(size)

    class Observe:
        def unwrap(self, source):
            opened.append(source)
            return source if seekable else ForwardOnly()

        def wrap(self, source):
            return source

    path = tmp_path / "data.bin"
    path.write_bytes(b"abc")
    source = FileSourceSpec(path=str(path), transforms=Pipeline(Observe()))
    with stream(source) as handle:
        assert opened[0].tell() == 0  # No eager drain before the caller sees it.
        assert handle.read(1) == b"a"
        assert opened[0].tell() == 1
        assert handle.seekable() is seekable
        if seekable:
            assert handle.tell() == 1
            assert handle.seek(0) == 0
            assert handle.read(1) == b"a"
        else:
            with pytest.raises(io.UnsupportedOperation):
                handle.seek(0)
    assert opened[0].closed  # Early exit must close the original source too.
    assert handle.closed


@pytest.mark.parametrize("infer", [None, False, True])
def test_stream_inference_with_path_params(tmp_path, infer):
    from mountainash_transport import Gzip

    class ObservedGzip(Gzip):
        used = False

        def unwrap(self, source):
            self.used = True
            return super().unwrap(source)

    decoder = ObservedGzip()
    payload = gzip.compress(b"abc", mtime=0)
    (tmp_path / "data_2026.bin.gz").write_bytes(payload)
    source = FileSourceSpec(
        path=str(tmp_path / "data_{year}.bin.gz"), infer=infer, gzip=decoder,
    )
    with stream(source, params={"year": 2026}) as handle:
        assert handle.read() == (payload if infer is False else b"abc")
        assert handle.seek(1) == 1
        assert handle.tell() == 1
        assert handle.read(1) == (payload[1:2] if infer is False else b"b")
    assert decoder.used is (infer is not False)


def test_stream_decode_error_occurs_during_consumption_and_closes(tmp_path):
    path = tmp_path / "bad.csv.gz"
    path.write_bytes(b"not gzip")
    with stream(FileSourceSpec(path=str(path), on_missing="skip")) as handle:
        with pytest.raises(gzip.BadGzipFile):
            handle.read()
    assert handle.closed
