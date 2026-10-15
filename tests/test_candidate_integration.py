"""Files operations exercise the migrated transport/settings boundary."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pyarrow as pa
import pytest

from mountainash_auth_client import NoAuthProfile
from mountainash_files import FileSinkSpec, FileSourceSpec, copy, parse, stream, write
from mountainash_settings import FilesystemBackend, SecretCapabilityError, SettingsParameters
from mountainash_transport import resolve_storage
from mountainash_transport.settings.storage.profiles import LocalStorageProfile


@pytest.mark.parametrize("profile_kind", ["implicit", "named", "object"])
def test_local_operations_with_migrated_profiles(tmp_path, monkeypatch, profile_kind):
    profile = None
    auth = None
    if profile_kind == "named":
        config = tmp_path / "profiles.yaml"
        config.write_text("storage_profiles:\n  local-files:\n    provider: local\n")
        monkeypatch.setenv("MOUNTAINASH_PROFILES_CONFIG", str(config))
        profile = "local-files"
    elif profile_kind == "object":
        profile, auth = LocalStorageProfile(), NoAuthProfile()
    kwargs = {"storage_profile": profile, "auth_profile": auth}
    original, copied = tmp_path / "original.csv", tmp_path / "copied.csv"
    write(FileSinkSpec(path=str(original), **kwargs), pa.table({"value": [7, 11]}))
    source = FileSourceSpec(path=str(original), **kwargs)
    copy(source, FileSinkSpec(path=str(copied), **kwargs))
    assert copied.read_bytes() == original.read_bytes()
    with stream(source) as handle:
        assert handle.read() == original.read_bytes()
    assert handle.closed
    results = parse(FileSourceSpec(path=str(copied), **kwargs))
    assert results[0].data.to_pylist() == [{"value": 7}, {"value": 11}]


@pytest.mark.parametrize("operation", ["parse", "stream"])
def test_selected_store_profiles_work_after_owner_closes_store(tmp_path, operation):
    """Actual loopback HTTP proves resolved auth reaches files' transport I/O."""
    config = tmp_path / "profiles.yaml"
    config.write_text(
        "storage_profiles:\n  web:\n    provider: http\n"
        "    auth:\n      mode: token\n      parameters:\n"
        "        TOKEN: secret:web.token\n"
    )
    observed = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            token = self.headers.get("Authorization")
            observed.append(token)
            if token not in {"Bearer first-token", "Bearer second-token"}:
                self.send_error(401)
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"value\n19\n")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        for index, token in enumerate(("first-token", "second-token", "first-token")):
            root = tmp_path / f"store-{index}"
            root.mkdir(mode=0o700)
            with FilesystemBackend(root) as store:
                store.set("web", {"token": token})
                parameters = SettingsParameters.create(config_files=[str(config)], secret_store=store)
                profile, auth = resolve_storage("web", settings_parameters=parameters)
                # Resolution borrows the store; the application retains ownership.
                assert store.get("web") == {"token": token}
            source = FileSourceSpec(
                path=f"http://127.0.0.1:{server.server_port}/data.csv",
                storage_profile=profile, auth_profile=auth,
            )
            if operation == "parse":
                assert parse(source)[0].data.to_pylist() == [{"value": 19}]
            else:
                with stream(source) as handle:
                    assert handle.read() == b"value\n19\n"
                assert handle.closed
        assert observed == ["Bearer first-token", "Bearer second-token", "Bearer first-token"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_named_secret_profile_without_selected_reader_fails_closed(tmp_path, monkeypatch):
    config = tmp_path / "profiles.yaml"
    config.write_text(
        "storage_profiles:\n  web:\n    provider: http\n"
        "    auth:\n      mode: token\n      parameters:\n"
        "        TOKEN: secret:private-record.private-field\n"
    )
    monkeypatch.setenv("MOUNTAINASH_PROFILES_CONFIG", str(config))
    monkeypatch.setenv("MOUNTAINASH_SECRETS_PROVIDER", "obsolete-global-selection")
    with pytest.raises(SecretCapabilityError) as caught:
        parse(FileSourceSpec(path="http://127.0.0.1:1/data.csv", storage_profile="web"))
    assert "private-record" not in str(caught.value)
    assert "private-field" not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
