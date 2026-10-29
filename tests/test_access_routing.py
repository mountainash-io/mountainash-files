from __future__ import annotations

import dataclasses
import gzip
import io
from typing import ClassVar

import pyarrow as pa
import pytest
from mountainash_transport import Gzip, PathNotFoundError, Pipeline, RangePolicy

from mountainash_files import FileSourceSpec, parse, parse_bytes, stream
from mountainash_files.formats._registry import _reset_registry, get_access, register_format
from mountainash_files.formats._types import FormatSpec
from _range_server import bytes_sent, plain_gets, ranged_gets, serve

SEEN: list[dict] = []


@dataclasses.dataclass(frozen=True)
class ProbeSpec(FormatSpec):
    FORMAT: ClassVar[str] = "probe"
    SUFFIXES: ClassVar[tuple[str, ...]] = (".probe",)
    MEDIATYPES: ClassVar[tuple[str, ...]] = ()
    fail: bool = False
    head: int | None = None


def probe_parse(data, spec):
    if isinstance(data, bytes):
        SEEN.append({"kind": "bytes"})
        body = data if spec.head is None else data[: spec.head]
    else:
        SEEN.append({"kind": "handle", "seekable": data.seekable(), "handle": data})
        body = data.read() if spec.head is None else data.read(spec.head)
    if spec.fail:
        raise RuntimeError("parser failed")
    return pa.table({"n": [len(body)]})


@pytest.fixture(autouse=True)
def registry():
    _reset_registry()
    SEEN.clear()
    register_format(ProbeSpec, probe_parse, access="random")
    yield
    _reset_registry()


def test_random_route_over_http_uses_ranges_not_whole_object():
    with serve({"a.probe": b"x" * 1000}) as (base, log):
        result = parse(FileSourceSpec(path=f"{base}/a.probe"))
    assert result[0].data.to_pylist() == [{"n": 1000}]
    assert SEEN == [{"kind": "handle", "seekable": True, "handle": SEEN[0]["handle"]}]
    assert ranged_gets(log) >= 1 and plain_gets(log) == 0


def test_server_without_ranges_falls_back_to_whole_object_bytes():
    with serve({"a.probe": b"y" * 500}, ranges=False) as (base, log):
        result = parse(FileSourceSpec(path=f"{base}/a.probe"))
    assert result[0].data.to_pylist() == [{"n": 500}]
    assert SEEN[-1]["kind"] == "bytes"


def test_suffix_transform_routes_to_decoded_bytes(tmp_path):
    path = tmp_path / "a.probe.gz"
    path.write_bytes(gzip.compress(b"z" * 300))
    assert parse(FileSourceSpec(path=str(path)))[0].data.to_pylist() == [{"n": 300}]
    assert SEEN[-1]["kind"] == "bytes"


def test_explicit_pipeline_routes_to_decoded_bytes(tmp_path):
    path = tmp_path / "a.probe"
    path.write_bytes(gzip.compress(b"z" * 40))
    result = parse(FileSourceSpec(path=str(path), transforms=Pipeline(Gzip())))
    assert result[0].data.to_pylist() == [{"n": 40}] and SEEN[-1]["kind"] == "bytes"


def test_gzip_configuration_without_gz_suffix_stays_random():
    with serve({"a.probe": b"q" * 50}) as (base, log):
        parse(FileSourceSpec(path=f"{base}/a.probe", gzip=Gzip()))
    assert SEEN[-1]["kind"] == "handle" and plain_gets(log) == 0


def test_empty_explicit_pipeline_stays_random():
    with serve({"a.probe": b"q" * 50}) as (base, log):
        parse(FileSourceSpec(path=f"{base}/a.probe", transforms=Pipeline()))
    assert SEEN[-1]["kind"] == "handle" and plain_gets(log) == 0


def test_handle_closed_after_parser_failure(tmp_path):
    path = tmp_path / "a.probe"
    path.write_bytes(b"data")
    with pytest.raises(RuntimeError, match="parser failed"):
        parse(FileSourceSpec(path=str(path), format=ProbeSpec(fail=True)))
    assert SEEN[0]["handle"].closed


def test_on_missing_skip_on_random_and_bytes_routes(tmp_path):
    assert parse(FileSourceSpec(path=str(tmp_path / "missing.probe"), on_missing="skip")) == []
    assert parse(FileSourceSpec(path=str(tmp_path / "missing.probe.gz"), on_missing="skip")) == []


def test_non_capability_error_propagates_without_whole_object_retry():
    with serve({}) as (base, log):
        with pytest.raises(PathNotFoundError):
            parse(FileSourceSpec(path=f"{base}/missing.probe"))
    assert plain_gets(log) == 0


def test_caller_owned_stream_stays_open():
    data = io.BytesIO(b"abc")
    assert parse_bytes(data, ProbeSpec()).data.to_pylist() == [{"n": 3}]
    assert not data.closed


def test_stream_policy_passes_through_and_changes_fetching():
    payload = b"p" * (4 * 1024 * 1024)
    with serve({"a.bin": payload}) as (base, log_none):
        with stream(FileSourceSpec(path=f"{base}/a.bin"), access="random", range_policy=RangePolicy("none")) as h:
            assert h.read(10) == b"p" * 10
    with serve({"a.bin": payload}) as (base, log_ahead):
        with stream(FileSourceSpec(path=f"{base}/a.bin"), access="random",
                    range_policy=RangePolicy("readahead", block_size=1024 * 1024)) as h:
            assert h.read(10) == b"p" * 10
    assert bytes_sent(log_none) < 1024 < bytes_sent(log_ahead)


def test_stream_random_seeks_from_end():
    with serve({"a.bin": bytes(range(256))}) as (base, _):
        with stream(FileSourceSpec(path=f"{base}/a.bin"), access="random") as handle:
            handle.seek(-2, io.SEEK_END)
            assert handle.read() == bytes([254, 255])


def test_stream_random_with_transforms_raises_transport_error(tmp_path):
    path = tmp_path / "a.bin.gz"
    path.write_bytes(gzip.compress(b"abc"))
    with pytest.raises(ValueError):
        with stream(FileSourceSpec(path=str(path)), access="random"):
            pass


def test_access_survives_override_lazy_registration_and_reset():
    assert get_access("probe", ProbeSpec()) == "random"
    register_format(ProbeSpec, probe_parse, override=True)
    assert get_access("probe", ProbeSpec()) == "bytes"
    register_format("test_access_routing:ProbeSpec", "test_access_routing:probe_parse",
                    format_key="probe", suffixes=(".probe",), access="random", override=True)
    assert get_access("probe", ProbeSpec()) == "random"
    register_format(ProbeSpec, probe_parse, access=lambda spec: "random" if spec.head else "bytes", override=True)
    assert get_access("probe", ProbeSpec(head=1)) == "random"
    assert get_access("probe", ProbeSpec()) == "bytes"
    _reset_registry()
    with pytest.raises(Exception):
        get_access("probe", ProbeSpec())


def test_invalid_access_value_is_rejected():
    with pytest.raises(ValueError):
        register_format(ProbeSpec, probe_parse, access="sequential", override=True)


def test_profile_range_settings_govern_parse(tmp_path, monkeypatch):
    payload = b"p" * (4 * 1024 * 1024)

    def run(cache: str, block: int) -> int:
        config = tmp_path / f"{cache}.yaml"
        config.write_text(
            "storage_profiles:\n  web:\n    provider: http\n    parameters:\n"
            f"      RANGE_CACHE: {cache}\n      RANGE_BLOCK_SIZE: {block}\n"
        )
        monkeypatch.setenv("MOUNTAINASH_PROFILES_CONFIG", str(config))
        with serve({"a.probe": payload}) as (base, log):
            parse(FileSourceSpec(path=f"{base}/a.probe", storage_profile="web", format=ProbeSpec(head=10)))
        return bytes_sent(log)

    assert run("none", 1024) < 1024 < run("readahead", 1024 * 1024)
